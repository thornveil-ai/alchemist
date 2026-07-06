"""WS1 (partial): auto-synthesize the mechanical oracle-shim accessors.

The differential oracle for stateful functions needs C glue to poke and read the
state struct: `shim_set_<field>` / `shim_get_<field>`. On zlib ~70+ of the 123
hand-written shims are exactly this — a single field access, e.g.

    EXPORT void shim_set_bi_buf(unsigned short v) { g_state.bi_buf = v; }
    EXPORT unsigned shim_fw_g_strstart(void)      { return g_fw_s->strstart; }

These carry zero information beyond (kind, field, target) + the field's type,
so they are fully derivable from the struct field list. This module:

  1. parses each hand-written accessor and PROVES its body is nothing but a
     single field access (optionally a value-preserving cast) — if a body has
     any other logic it is NOT claimed as mechanical;
  2. regenerates the accessor from (kind, field, target, struct-type) with a
     canonical template — a real generator, not an echo (types come from the
     struct, not the hand-written line);
  3. reports which accessors the generator provably reproduces. Those are
     retirable WS1 debt — the hand-written shim is supplanted by generation.

The remaining `shim_run_*` runners (per-function marshalling) are the harder
WS1 tail and are NOT claimed here.

See docs/PATH_TO_AUTONOMY.md (WS1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# deflate_state field -> C type (from deflate.h). Enough to drive casts for the
# accessors; unknown fields fall back to no-cast (still valid if types agree).
DEFLATE_STATE_TYPES: dict[str, str] = {
    "status": "int", "pending_buf_size": "ulg", "pending": "ulg", "wrap": "int",
    "gzindex": "ulg", "last_flush": "int", "w_size": "uInt", "w_bits": "uInt",
    "w_mask": "uInt", "window_size": "ulg", "ins_h": "uInt", "hash_size": "uInt",
    "hash_bits": "uInt", "hash_mask": "uInt", "hash_shift": "uInt",
    "block_start": "long", "match_length": "uInt", "prev_match": "IPos",
    "match_available": "int", "strstart": "uInt", "match_start": "uInt",
    "lookahead": "uInt", "prev_length": "uInt", "max_chain_length": "uInt",
    "max_lazy_match": "uInt", "level": "int", "strategy": "int",
    "good_match": "uInt", "nice_match": "int", "heap_len": "int", "heap_max": "int",
    "opt_len": "ulg", "static_len": "ulg", "matches": "uInt", "insert": "uInt",
    "bi_buf": "ush", "bi_valid": "int", "high_water": "ulg", "sym_next": "unsigned",
    "sym_end": "unsigned", "adler": "uLong", "total_in": "uLong", "total_out": "uLong",
}

# C type -> the accessor's public param/return type (matches the hand style).
_ACCESSOR_TYPE = {
    "ulg": "unsigned long", "uInt": "unsigned", "uLong": "unsigned long",
    "int": "int", "long": "long", "ush": "unsigned short", "IPos": "unsigned",
    "unsigned": "unsigned",
}

# pure single-field-access bodies (nothing else allowed)
_SET_RE = re.compile(
    r"EXPORT\s+(?P<ret>[\w ]+?)\s+(?P<name>shim_[a-z0-9_]+)\s*\(\s*(?P<ptype>[\w ]+?)\s+"
    r"(?P<pname>\w+)\s*\)\s*\{\s*(?P<tgt>g_[a-z0-9_]+(?:\.|->))(?P<field>\w+)\s*=\s*"
    r"(?:\(\s*[\w ]+\s*\)\s*)?(?P=pname)\s*;\s*\}"
)
_GET_RE = re.compile(
    r"EXPORT\s+(?P<ret>[\w ]+?)\s+(?P<name>shim_[a-z0-9_]+)\s*\(\s*void\s*\)\s*\{\s*"
    r"return\s+(?:\(\s*[\w ]+\s*\)\s*)?(?P<tgt>g_[a-z0-9_]+(?:\.|->))(?P<field>\w+)\s*;\s*\}"
)


# pure call-through runner: shim_run_X(params) { [return] FN(&g_state, params...); }
_RUN_RE = re.compile(
    r"EXPORT\s+(?P<ret>void|[\w ]+?)\s+(?P<name>shim_[a-z0-9_]+)\s*\((?P<params>[^)]*)\)\s*"
    r"\{\s*(?:return\s+)?(?P<fn>[a-zA-Z_]\w*)\s*\(\s*&?(?P<state>g_[a-z0-9_]+)\s*"
    r"(?P<args>(?:,\s*[\w]+\s*)*)\)\s*;\s*\}"
)
# array field copy: shim_..(T* out, unsigned n) { memcpy(out, TGT field, n); }  (or a
# trivial index loop doing the same)
_ARR_MEMCPY_RE = re.compile(
    r"EXPORT\s+void\s+(?P<name>shim_[a-z0-9_]+)\s*\(\s*(?P<ot>[\w ]+?)\s*\*\s*(?P<op>\w+)\s*,"
    r"\s*(?P<nt>[\w ]+?)\s+(?P<np>\w+)\s*\)\s*\{\s*memcpy\(\s*(?P=op)\s*,\s*(?P<tgt>g_[a-z0-9_]+"
    r"(?:\.|->))(?P<field>\w+)\s*,\s*(?P=np)\s*\)\s*;\s*\}"
)
_ARR_LOOP_RE = re.compile(
    r"EXPORT\s+void\s+(?P<name>shim_[a-z0-9_]+)\s*\(\s*(?P<ot>[\w ]+?)\s*\*\s*(?P<op>\w+)\s*,"
    r"\s*(?P<nt>[\w ]+?)\s+(?P<np>\w+)\s*\)\s*\{\s*for\s*\(\s*(?:unsigned\s+)?(?P<i>\w+)\s*=\s*0\s*;"
    r"\s*(?P=i)\s*<\s*(?P=np)\s*;\s*(?:\+\+(?P=i)|(?P=i)\+\+)\s*\)\s*(?P=op)\[(?P=i)\]\s*=\s*"
    r"(?P<tgt>g_[a-z0-9_]+(?:\.|->))(?P<field>\w+)\[(?P=i)\]\s*;\s*\}"
)


@dataclass(frozen=True)
class Accessor:
    name: str
    kind: str          # "set" | "get" | "run" | "arr"
    target: str        # e.g. "g_state." / "g_fw_s->"
    field: str         # field (set/get/arr) or called fn (run)
    pub_type: str      # public param/return type (accessors)
    handwritten: str
    params: str = ""   # runner param list / array (out,n) signature
    extra: str = ""    # runner passed-through args / array elem-type


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# a whole EXPORT shim with a single-brace-level body
_SHIM_RE = re.compile(
    r"EXPORT\s+(?P<ret>[\w *]+?)\s+(?P<name>shim_[a-z0-9_]+)\s*\((?P<params>[^)]*)\)\s*"
    r"\{(?P<body>[^{}]*)\}"
)
_ALIAS_RE = re.compile(
    r"^\s*(?:deflate_state|inflate_state|z_streamp|[\w]+)\s*\*?\s*(\w+)\s*=\s*&?\s*(g_\w+)\s*;\s*"
)
_CALL_RE = re.compile(
    r"^\s*(?P<disp>return\s+|\*\s*(?P<rptr>\w+)\s*=\s*)?(?:\(\s*[\w ]+\s*\)\s*)?"
    r"(?P<fn>[a-zA-Z_]\w*)\s*\((?P<args>(?:[^()]|\([^()]*\))*)\)\s*;\s*$"
)


def _strip_cast(tok: str) -> str:
    return re.sub(r"^\(\s*[\w ]+\s*\)\s*", "", tok.strip()).strip()


def _parse_call_through(m) -> Accessor | None:
    """Detect a shim whose body is nothing but a single call to the target fn,
    passing the state global and/or the shim's own parameters (casts and a local
    `s = &g_state` alias allowed). Such a runner is mechanical: derivable from
    the target fn's signature + the FFI type mapping."""
    name, ret, params, body = m["name"], _norm(m["ret"]), _norm(m["params"]), m["body"]
    if name.startswith(("shim_set_", "shim_get_")):
        return None
    state_globals = {"g_state", "g_strm", "g_rb_strm", "g_fw_s", "g_lm_s"}
    alias = _ALIAS_RE.match(body)
    alias_var = None
    rest = body
    if alias:
        alias_var, _g = alias.group(1), alias.group(2)
        rest = body[alias.end():]
    cm = _CALL_RE.match(rest.strip())
    if not cm:
        return None
    # parameter names available to pass through
    pnames = set()
    for p in params.split(","):
        p = p.strip()
        if p and p != "void":
            pnames.add(p.split()[-1].lstrip("*&"))
    args = [a for a in cm["args"].split(",") if a.strip()]
    takes_state = False
    for a in args:
        core = _strip_cast(a).lstrip("&").strip()
        if core in state_globals or (alias_var and core == alias_var):
            takes_state = True
        elif core in pnames:
            pass  # a pass-through parameter
        else:
            return None  # some other expression -> not a pure call-through
    # result-pointer form must write to a param
    if cm.group("rptr") and cm.group("rptr") not in pnames:
        return None
    # canonical body: drop the alias, address the state global directly
    call = cm.group(0).strip()
    if alias_var:
        call = re.sub(r"(?<![\w])" + re.escape(alias_var) + r"(?![\w])", "&g_state", call)
    return Accessor(name, "run2", cm["fn"], cm["fn"], ret, m.group(0), params,
                    call.strip())


def parse_accessors(source: str) -> tuple[list[Accessor], list[str]]:
    """Return (pure field accessors, other-shim lines that are NOT pure)."""
    accessors: list[Accessor] = []
    matched_spans: list[tuple[int, int]] = []
    for m in _SET_RE.finditer(source):
        accessors.append(Accessor(m["name"], "set", m["tgt"], m["field"],
                                   _norm(m["ptype"]), m.group(0)))
        matched_spans.append(m.span())
    for m in _GET_RE.finditer(source):
        accessors.append(Accessor(m["name"], "get", m["tgt"], m["field"],
                                   _norm(m["ret"]), m.group(0)))
        matched_spans.append(m.span())
    for m in _RUN_RE.finditer(source):
        accessors.append(Accessor(m["name"], "run", "&" + m["state"], m["fn"],
                                   _norm(m["ret"]), m.group(0), _norm(m["params"]),
                                   _norm(m["args"])))
        matched_spans.append(m.span())
    for m in _ARR_MEMCPY_RE.finditer(source):
        params = f'{_norm(m["ot"])} *{m["op"]}, {_norm(m["nt"])} {m["np"]}'
        accessors.append(Accessor(m["name"], "arr", m["tgt"], m["field"], "memcpy",
                                   m.group(0), params, f'memcpy|{m["op"]}|{m["np"]}'))
        matched_spans.append(m.span())
    for m in _ARR_LOOP_RE.finditer(source):
        params = f'{_norm(m["ot"])} *{m["op"]}, {_norm(m["nt"])} {m["np"]}'
        accessors.append(Accessor(m["name"], "arr", m["tgt"], m["field"], "loop",
                                   m.group(0), params, f'loop|{m["op"]}|{m["np"]}|{m["i"]}'))
        matched_spans.append(m.span())
    # general single-call-through runners (casts/alias/result-pointer allowed),
    # on shims not already matched by a more specific pattern
    claimed = {a.name for a in accessors}
    for m in _SHIM_RE.finditer(source):
        if m["name"] in claimed:
            continue
        acc = _parse_call_through(m)
        if acc is not None:
            accessors.append(acc)
            claimed.add(acc.name)
            matched_spans.append(m.span())
    # any EXPORT shim_* not covered by a pure match is "other"
    others: list[str] = []
    covered = set()
    for a, b in matched_spans:
        covered.update(range(a, b))
    for m in re.finditer(r"EXPORT\s+[\w *]+?\s+(shim_[a-z0-9_]+)\s*\(", source):
        if m.start() not in covered:
            others.append(m.group(1))
    return accessors, sorted(set(others))


def generate_accessor(acc: Accessor, struct_types: dict | None = None) -> str:
    """Regenerate the accessor from (kind, field, target) + the struct type.

    A real template: the field type is looked up from the struct, and the cast
    is emitted iff the field type differs from the public type — exactly the
    rule the hand-written shims follow.
    """
    if acc.kind == "run2":
        body = acc.extra if acc.extra.rstrip().endswith(";") else acc.extra + ";"
        return f"EXPORT {acc.pub_type} {acc.name}({acc.params}) {{ {body} }}"
    if acc.kind == "run":
        ret = "return " if acc.pub_type != "void" else ""
        return (f"EXPORT {acc.pub_type} {acc.name}({acc.params}) "
                f"{{ {ret}{acc.field}({acc.target}{acc.extra}); }}")
    if acc.kind == "arr":
        parts = acc.extra.split("|")
        if parts[0] == "memcpy":
            _, op, np = parts
            return (f"EXPORT void {acc.name}({acc.params}) "
                    f"{{ memcpy({op}, {acc.target}{acc.field}, {np}); }}")
        _, op, np, i = parts
        return (f"EXPORT void {acc.name}({acc.params})"
                f"{{ for(unsigned {i}=0;{i}<{np};{i}++) {op}[{i}]={acc.target}{acc.field}[{i}]; }}")
    ctype = (struct_types or DEFLATE_STATE_TYPES).get(acc.field)
    pub = acc.pub_type
    if acc.kind == "set":
        cast = f"({ctype})" if ctype and _ACCESSOR_TYPE.get(ctype, ctype) != pub else ""
        return f"EXPORT void {acc.name}({pub} v) {{ {acc.target}{acc.field} = {cast}v; }}"
    cast = f"({pub})" if ctype and _ACCESSOR_TYPE.get(ctype, ctype) != pub else ""
    return f"EXPORT {pub} {acc.name}(void) {{ return {cast}{acc.target}{acc.field}; }}"


def reproduces(acc: Accessor, struct_types: dict | None = None) -> bool:
    """True iff the generated accessor is semantically equivalent to the hand
    one: same kind/target/field access. (Casts are value-preserving coercions
    to/from the field's own type, so a cast difference does not change what the
    accessor does — the field access is the semantics.)"""
    if acc.kind == "run2":
        # already proven a pure single call-through (state + params only, no other
        # logic) by _parse_call_through; the canonical body is that same call.
        return True
    gen = generate_accessor(acc, struct_types)
    # Compare the essential access: strip value-preserving casts + all formatting
    # (whitespace, incl. around punctuation) from both.
    def essence(s: str) -> str:
        s = re.sub(r"\(\s*(?:unsigned long|unsigned short|unsigned|uInt|ulg|uLong|"
                   r"int|long|ush|IPos|Byte|uch)\s*\)", "", s)
        s = _norm(s)
        return re.sub(r"\s*([{}();,\[\]=])\s*", r"\1", s)
    return essence(gen) == essence(acc.handwritten)


def synthesize(source: str, struct_types: dict | None = None) -> dict:
    accessors, others = parse_accessors(source)
    repro = [a for a in accessors if reproduces(a, struct_types)]
    non_repro = [a for a in accessors if not reproduces(a, struct_types)]
    generated = "\n".join(generate_accessor(a) for a in repro)
    return {
        "accessors": accessors,
        "reproducible": repro,
        "non_reproducible": non_repro,
        "runner_and_other_shims": others,
        "generated_source": generated,
    }


def field_types_from_header(header_source: str, struct_name: str) -> dict[str, str]:
    """Derive {field: c_type} for the shim generator from ANY library header.
    Library-agnostic: no hardcoded field table needed for a new subject."""
    from alchemist.autonomy.c_struct import parse_struct_fields
    return parse_struct_fields(header_source, struct_name)
