"""Whole-workspace type coherence.

The extractor infers a Rust type for each function parameter independently,
so the SAME C type can fracture into several incompatible Rust types across
the workspace. zlib's `ct_data` (a Huffman tree node) became three different
things: `TreeElement`, `HuffmanNode`, and `Vec<(u16, u16)>` — so a function
taking `&[TreeElement]` cannot be handed a `DeflateState` field of type
`Vec<(u16, u16)>`, and the crate literally cannot be made to compile
coherently. No amount of per-function fill fixes that; it is a
type-*generation* defect.

This pass restores coherence BEFORE the skeleton is generated:

  1. Correlate every spec parameter with its C base type (from analysis.json).
  2. Build the map: C base type → the Rust ELEMENT types assigned to it.
  3. Choose one canonical element type per C base type (a registered canonical
     for known-hard types like `ct_data`, else the most-frequent structured
     choice), and rewrite every parameter / field to use it — preserving the
     container shape (`&[T]`, `Vec<T>`, `&mut T`, …).
  4. Emit/repair the canonical struct definitions with their COMPLETE field
     set (so `ct_data` carries freq/code/dad/len, not a lossy subset).

The result is a workspace where one C type is one Rust type everywhere.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Canonical type registry — element type + complete field set for C types
# whose faithful Rust shape the extractor cannot reliably infer.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CanonicalType:
    """A canonical Rust element type for a C base type."""
    c_type: str
    rust_name: str
    # Complete field set (name -> rust_type). Empty => scalar/opaque alias.
    fields: tuple[tuple[str, str], ...] = ()
    derives: tuple[str, ...] = ("Debug", "Default", "Clone", "Copy")
    doc: str = ""
    # Container policy: "slice" means this type is always used as an array in
    # C (indexed `x[n]`), so a parameter is a slice `&[T]`/`&mut [T]` with
    # mutability taken from the extractor's existing choice; "value" leaves
    # the extractor's container as-is and only fixes the element type.
    container: str = "value"
    # Rust element spellings that are known stand-ins or byte-identical
    # duplicates for this canonical. The extractor emits a 2-tuple like
    # `(u16, u16)` when it cannot name a small struct, and it duplicated
    # ct_data as both `TreeElement` and `HuffmanNode`. Any field/param whose
    # element matches an alias is rewritten to the canonical, and the
    # duplicate struct definitions are dropped. The C-type correlation
    # cannot reach struct FIELDS (the parser drops their names), so aliases
    # are how state-field coherence is achieved.
    aliases: tuple[str, ...] = ()


# zlib's ct_data: `struct { union {ush freq; ush code;} fc; union {ush dad;
# ush len;} dl; }`. Freq/Code share storage and Dad/Len share storage, but
# they are used at temporally-disjoint phases of tree building, so four
# separate u16 fields is a faithful model in safe Rust.
_CT_DATA = CanonicalType(
    c_type="ct_data",
    rust_name="TreeElement",
    fields=(
        ("freq", "u16"),   # fc union: symbol frequency (build phase)
        ("code", "u16"),   # fc union: bit code (post-gen_codes)
        ("dad", "u16"),    # dl union: parent node (build phase)
        ("len", "u16"),    # dl union: bit length (post-gen_bitlen)
    ),
    doc="zlib ct_data — Huffman tree node (freq/code and dad/len are the two "
        "union slots, used at disjoint tree-building phases).",
    container="slice",  # ct_data is always `tree[n]` — an array/slice
    aliases=("HuffmanNode", "(u16, u16)", "(u16,u16)"),
)

DEFAULT_CANONICAL: dict[str, CanonicalType] = {c.c_type: c for c in (_CT_DATA,)}


# Explicit (struct, field) → Rust type corrections for state fields the
# extractor collapsed to a scalar (losing the struct). The struct-field
# parser drops field names, so these cannot be recovered by C-type
# correlation; they are curated per-subject knowledge, like the canonical
# registry. zlib's deflate_state embeds three tree_desc VALUE members which
# the tree-builders access as `s.l_desc.max_code` — collapsing them to u32
# makes that access uncompilable.
@dataclass(frozen=True)
class FieldOverride:
    struct: str
    field: str
    rust_type: str


DEFAULT_FIELD_OVERRIDES: tuple[FieldOverride, ...] = (
    FieldOverride("DeflateState", "l_desc", "TreeDesc"),
    FieldOverride("DeflateState", "d_desc", "TreeDesc"),
    FieldOverride("DeflateState", "bl_desc", "TreeDesc"),
)


# Explicit (function, param) → Rust type corrections. The extractor infers
# parameter mutability inconsistently: build_tree correctly takes
# `desc: &mut TreeDesc` but gen_bitlen got `&TreeDesc` — yet gen_bitlen
# MUTATES the tree's bit lengths (tree[n].Len = desc.dyn_tree), so an
# immutable borrow makes it impossible to implement. The same `tree_desc *`
# C type, mutated in both, must map to `&mut TreeDesc` in both.
@dataclass(frozen=True)
class ParamOverride:
    function: str
    param: str
    rust_type: str


DEFAULT_PARAM_OVERRIDES: tuple[ParamOverride, ...] = (
    ParamOverride("gen_bitlen", "desc", "&mut TreeDesc"),
)


# ---------------------------------------------------------------------------
# Rust type surgery: swap an element type while keeping the container shape.
# ---------------------------------------------------------------------------

# Recognized container wrappers, matched from the outside in. Each returns
# (prefix, inner, suffix) so we can rewrite `inner` and reassemble.
_CONTAINERS = [
    re.compile(r"^(?P<pre>&\s*mut\s*\[\s*)(?P<inner>.+?)(?P<suf>\s*\]\s*)$"),
    re.compile(r"^(?P<pre>&\s*\[\s*)(?P<inner>.+?)(?P<suf>\s*\]\s*)$"),
    re.compile(r"^(?P<pre>Vec\s*<\s*)(?P<inner>.+?)(?P<suf>\s*>\s*)$"),
    re.compile(r"^(?P<pre>Option\s*<\s*)(?P<inner>.+?)(?P<suf>\s*>\s*)$"),
    re.compile(r"^(?P<pre>&\s*mut\s+)(?P<inner>.+?)(?P<suf>\s*)$"),
    re.compile(r"^(?P<pre>&\s*)(?P<inner>.+?)(?P<suf>\s*)$"),
]

# The set of Rust "element" spellings we treat as an unknown-tree-node stand-in
# so we can recognize the incoherent forms. A 2-tuple of small ints is the
# lossy shape the extractor sometimes emits for a struct it couldn't name.
_TUPLE_ELEMENT = re.compile(r"^\(\s*u\d+\s*,\s*u\d+\s*\)$")


def _element_of(rust_type: str) -> tuple[str, str, str]:
    """Peel container wrappers → (prefix, element, suffix). Idempotent on a
    bare element type (returns ('', type, ''))."""
    pre, suf = "", ""
    t = rust_type.strip()
    changed = True
    while changed:
        changed = False
        for pat in _CONTAINERS:
            m = pat.match(t)
            if m:
                pre += m.group("pre")
                suf = m.group("suf") + suf
                t = m.group("inner").strip()
                changed = True
                break
    return pre, t, suf


def _rewrite_element(rust_type: str, canonical_rust: str) -> str:
    pre, _elem, suf = _element_of(rust_type)
    return f"{pre}{canonical_rust}{suf}"


def _norm_elem(s: str) -> str:
    """Normalize an element spelling for alias matching (whitespace-insensitive)."""
    return re.sub(r"\s+", "", s or "")


_FIELD_LINE = re.compile(
    r"^(?P<pre>\s*(?:pub\s+)?[A-Za-z_]\w*\s*:\s*)(?P<ty>.+?)(?P<suf>,?\s*)$")


def _canon_rust_definition(
    rust_def: str, alias_to_canon: dict[str, str],
) -> tuple[str, int]:
    """Rewrite `pub name: <type>,` field types inside a raw struct-definition
    string, canonicalizing any field whose element is a known alias. Returns
    (new_definition, num_rewritten)."""
    out: list[str] = []
    n = 0
    for line in rust_def.splitlines(keepends=True):
        m = _FIELD_LINE.match(line.rstrip("\n"))
        if not m:
            out.append(line)
            continue
        ty = m.group("ty")
        pre_c, elem, suf_c = _element_of(ty)
        canon = alias_to_canon.get(_norm_elem(elem))
        if canon:
            newline = (m.group("pre") + f"{pre_c}{canon}{suf_c}"
                       + m.group("suf") + ("\n" if line.endswith("\n") else ""))
            out.append(newline)
            n += 1
        else:
            out.append(line)
    return "".join(out), n


# ---------------------------------------------------------------------------
# Correlation + unification
# ---------------------------------------------------------------------------

@dataclass
class UnifyReport:
    rewrites: int = 0
    field_rewrites: int = 0
    dropped_structs: tuple[str, ...] = ()
    # C base type -> {rust element types seen}
    conflicts: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    canonical: dict[str, str] = field(default_factory=dict)  # c_type -> rust_name
    structs: dict[str, CanonicalType] = field(default_factory=dict)

    def summary(self) -> str:
        parts = []
        for c, rusts in sorted(self.conflicts.items()):
            if len(rusts) > 1:
                parts.append(f"{c}:{{{','.join(sorted(rusts))}}}=>{self.canonical.get(c, '?')}")
        head = (f"{self.rewrites} param + {self.field_rewrites} field type(s) "
                f"unified")
        if self.dropped_structs:
            head += f", dropped dup struct(s) {', '.join(self.dropped_structs)}"
        return head + ("; " + "; ".join(parts) if parts else "")


def _c_base(c_type: str) -> str:
    """Strip pointer/const/array/struct qualifiers to the base C type name."""
    t = c_type.strip()
    t = re.sub(r"\bconst\b", "", t)
    t = re.sub(r"\b(struct|union|enum)\b", "", t)
    t = t.replace("*", " ").replace("[", " ").replace("]", " ")
    return t.strip().split()[0] if t.strip() else ""


@dataclass(frozen=True)
class CShape:
    """The pointer/array/const structure of a C type, for container choice."""
    is_const: bool
    is_pointer: bool
    is_array: bool


def _c_shape(c_type: str) -> CShape:
    t = (c_type or "").strip()
    return CShape(
        is_const="const" in t,
        is_pointer="*" in t,
        is_array="[" in t,
    )


def _derive_rust_type(canon: "CanonicalType", prior_rust: str) -> str:
    """Build the coherent Rust type for a parameter of a registered C type.

    For a `container="slice"` type (an array-in-C like ct_data), the result
    is always `&[Elem]` / `&mut [Elem]`, with mutability taken from the
    extractor's existing choice — repairing the case where a slice was
    mistakenly wrapped as a struct (`&HuffmanTree` for `const ct_data *`).
    For a `container="value"` type only the element name is canonicalized.
    """
    if canon.container == "slice":
        is_mut = bool(re.search(r"&\s*mut", prior_rust or ""))
        return (f"&mut [{canon.rust_name}]" if is_mut
                else f"&[{canon.rust_name}]")
    return _rewrite_element(prior_rust, canon.rust_name)


def _analysis_param_types(analysis: dict) -> dict[str, list[tuple[str, str]]]:
    """function name -> [(param_name, c_type), ...] from analysis.json."""
    out: dict[str, list[tuple[str, str]]] = {}
    for f in (analysis.get("files") or {}).values():
        for fn in f.get("functions") or []:
            name = fn.get("name")
            if not name:
                continue
            params = fn.get("params") or fn.get("parameters") or []
            out[name] = [(p.get("name", ""), p.get("type", "")) for p in params]
    return out


def _apply_field_overrides(specs, overrides) -> int:
    """Rewrite specific `pub <field>: <type>` inside named struct definitions.

    For state fields the extractor collapsed to a scalar (DeflateState.l_desc
    → u32 instead of TreeDesc), which no correlation or alias can recover
    because the struct-field parser drops names. Rewrites both the raw
    rust_definition and any structured TypeField."""
    by_struct: dict[str, dict[str, str]] = defaultdict(dict)
    for ov in overrides:
        by_struct[ov.struct][ov.field] = ov.rust_type
    n = 0
    for module in specs:
        for st in getattr(module, "shared_types", None) or []:
            fixes = by_struct.get(st.name)
            if not fixes:
                continue
            rd = getattr(st, "rust_definition", None)
            if rd:
                lines = rd.splitlines(keepends=True)
                for i, line in enumerate(lines):
                    m = re.match(r"^(\s*(?:pub\s+)?([A-Za-z_]\w*)\s*:\s*)(.+?)(,?\s*)$",
                                 line.rstrip("\n"))
                    if m and m.group(2) in fixes and m.group(3).strip() != fixes[m.group(2)]:
                        nl = m.group(1) + fixes[m.group(2)] + m.group(4)
                        lines[i] = nl + ("\n" if line.endswith("\n") else "")
                        n += 1
                st.rust_definition = "".join(lines)
            for tf in getattr(st, "fields", None) or []:
                if tf.name in fixes and tf.rust_type != fixes[tf.name]:
                    tf.rust_type = fixes[tf.name]
                    n += 1
    return n


def unify_types(
    specs: list,
    analysis: dict,
    *,
    registry: dict[str, CanonicalType] | None = None,
    field_overrides: tuple[FieldOverride, ...] | None = None,
) -> UnifyReport:
    """Canonicalize Rust types across the workspace, in place on `specs`.

    Returns an UnifyReport with the rewrite count and the canonical struct
    definitions to emit. A C type is unified when it is either registered or
    mapped to more than one distinct Rust element type across the specs.
    """
    registry = {**DEFAULT_CANONICAL, **(registry or {})}
    overrides = (DEFAULT_FIELD_OVERRIDES if field_overrides is None
                 else field_overrides)
    c_params = _analysis_param_types(analysis)
    report = UnifyReport()

    # Pass 1 — observe: for each C base type, which Rust element types appear?
    # Correlate spec params with the C signature by position (names may be
    # normalized), falling back to name match.
    observations: list[tuple[str, str, object]] = []  # (c_base, c_type, Param)
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            sig = c_params.get(alg.name) or []
            inputs = list(alg.inputs or [])
            for i, p in enumerate(inputs):
                c_type = ""
                if i < len(sig):
                    c_type = sig[i][1]
                else:
                    for pn, ct in sig:
                        if pn == p.name:
                            c_type = ct
                            break
                base = _c_base(c_type)
                if base:
                    _pre, elem, _suf = _element_of(p.rust_type or "")
                    report.conflicts[base].add(elem)
                    observations.append((base, c_type, p))

    # Pass 2 — decide canonical per C base type. ONLY the curated registry
    # drives unification: C's `int`, `void *`, and `z_streamp` legitimately
    # map to different Rust types by context (z_streamp is both a deflate and
    # an inflate stream), so a "conflict → pick one" heuristic would corrupt
    # them. A type earns a canonical form only by being registered.
    for base in report.conflicts:
        if base in registry:
            report.canonical[base] = registry[base].rust_name
            report.structs[registry[base].rust_name] = registry[base]

    # Pass 3 — rewrite params in place using the registered canonical type +
    # its container policy (uses the C-type correlation).
    for base, _c_type, p in observations:
        if base not in registry:
            continue
        new_rt = _derive_rust_type(registry[base], p.rust_type or "")
        if new_rt != (p.rust_type or ""):
            p.rust_type = new_rt
            report.rewrites += 1

    # Pass 4 — element-alias canonicalization everywhere (params, TypeFields,
    # rust_definition strings). The struct-field parser drops field names, so
    # this alias fingerprint is how state-field coherence is reached: any
    # element that is a canonical's alias (the (u16,u16) tuple stand-in, the
    # HuffmanNode duplicate) is rewritten to the canonical, keeping the
    # container. Also unifies any param the C-correlation missed.
    alias_to_canon: dict[str, str] = {}
    for c in registry.values():
        report.structs.setdefault(c.rust_name, c)
        for a in c.aliases:
            alias_to_canon[_norm_elem(a)] = c.rust_name

    def _canon_type(rt: str) -> str:
        pre, elem, suf = _element_of(rt or "")
        canon = alias_to_canon.get(_norm_elem(elem))
        return f"{pre}{canon}{suf}" if canon else (rt or "")

    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            for p in alg.inputs or []:
                new = _canon_type(p.rust_type or "")
                if new != (p.rust_type or ""):
                    p.rust_type = new
                    report.field_rewrites += 1
            for sv in getattr(alg, "state", None) or []:
                new = _canon_type(sv.rust_type or "")
                if new != (sv.rust_type or ""):
                    sv.rust_type = new
                    report.field_rewrites += 1
        for st in getattr(module, "shared_types", None) or []:
            for tf in getattr(st, "fields", None) or []:
                new = _canon_type(tf.rust_type or "")
                if new != (tf.rust_type or ""):
                    tf.rust_type = new
                    report.field_rewrites += 1
            rd = getattr(st, "rust_definition", None)
            if rd:
                new_rd, n = _canon_rust_definition(rd, alias_to_canon)
                if n:
                    st.rust_definition = new_rd
                    report.field_rewrites += n

    # Pass 5 — drop the now-redundant duplicate struct definitions (their
    # references were all rewritten to the canonical) and materialize the
    # canonical struct with its COMPLETE field set (the extractor's version
    # was lossy — e.g. TreeElement was missing `dad`).
    dropped: list[str] = []
    canon_names = {c.rust_name for c in registry.values()}
    alias_struct_names = {a for c in registry.values() for a in c.aliases
                          if a[:1].isupper()}
    canon_by_name = {c.rust_name: c for c in registry.values() if c.fields}
    for module in specs:
        st_list = getattr(module, "shared_types", None)
        if st_list is None:
            continue
        kept = []
        for st in st_list:
            if st.name in alias_struct_names and st.name not in canon_names:
                dropped.append(st.name)
                continue
            if st.name in canon_by_name:
                # Replace the lossy definition with the complete canonical one.
                st.rust_definition = render_canonical_struct(canon_by_name[st.name])
            kept.append(st)
        module.shared_types = kept
    report.dropped_structs = tuple(dict.fromkeys(dropped))

    # Pass 6 — explicit field-type overrides for scalar-collapsed state
    # fields (DeflateState.l_desc/d_desc/bl_desc → TreeDesc).
    report.field_rewrites += _apply_field_overrides(specs, overrides)

    # Pass 7 — explicit parameter-type corrections (gen_bitlen.desc → &mut).
    for module in specs:
        for alg in getattr(module, "algorithms", None) or []:
            for ov in DEFAULT_PARAM_OVERRIDES:
                if alg.name != ov.function:
                    continue
                for p in alg.inputs or []:
                    if p.name == ov.param and p.rust_type != ov.rust_type:
                        p.rust_type = ov.rust_type
                        report.rewrites += 1

    return report


def render_canonical_struct(c: CanonicalType) -> str:
    """Emit the Rust definition for a canonical struct type."""
    if not c.fields:
        return ""
    lines = [f"/// {c.doc}" if c.doc else "",
             f"#[derive({', '.join(c.derives)})]",
             f"pub struct {c.rust_name} {{"]
    lines = [l for l in lines if l]
    for name, ty in c.fields:
        lines.append(f"    pub {name}: {ty},")
    lines.append("}")
    return "\n".join(lines)
