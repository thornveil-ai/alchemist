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
)

DEFAULT_CANONICAL: dict[str, CanonicalType] = {c.c_type: c for c in (_CT_DATA,)}


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


# ---------------------------------------------------------------------------
# Correlation + unification
# ---------------------------------------------------------------------------

@dataclass
class UnifyReport:
    rewrites: int = 0
    # C base type -> {rust element types seen}
    conflicts: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    canonical: dict[str, str] = field(default_factory=dict)  # c_type -> rust_name
    structs: dict[str, CanonicalType] = field(default_factory=dict)

    def summary(self) -> str:
        parts = []
        for c, rusts in sorted(self.conflicts.items()):
            if len(rusts) > 1:
                parts.append(f"{c}→{{{', '.join(sorted(rusts))}}}⇒{self.canonical.get(c, '?')}")
        head = f"{self.rewrites} type(s) unified"
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


def unify_types(
    specs: list,
    analysis: dict,
    *,
    registry: dict[str, CanonicalType] | None = None,
) -> UnifyReport:
    """Canonicalize Rust types across the workspace, in place on `specs`.

    Returns an UnifyReport with the rewrite count and the canonical struct
    definitions to emit. A C type is unified when it is either registered or
    mapped to more than one distinct Rust element type across the specs.
    """
    registry = {**DEFAULT_CANONICAL, **(registry or {})}
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

    # Pass 3 — rewrite in place using the registered canonical type + its
    # container policy.
    for base, _c_type, p in observations:
        if base not in registry:
            continue
        new_rt = _derive_rust_type(registry[base], p.rust_type or "")
        if new_rt != (p.rust_type or ""):
            p.rust_type = new_rt
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
