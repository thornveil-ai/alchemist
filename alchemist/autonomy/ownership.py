"""Pillar 6 — memory-ownership translation (the crux for 'securely convert').

Real C uses malloc/free, and that is exactly the bug class Rust exists to kill:
use-after-free, double-free, leaks. Translating heap C to SAFE Rust means inferring
OWNERSHIP and expressing it in the type system:

    malloc(n)            -> Vec<T> (owns the allocation)
    return p;  (a malloc) -> the function RETURNS Vec<T>  (ownership out to caller)
    free(p);   (a param)  -> the function TAKES Vec<T> by value (ownership in -> drop)
    free(p);   (a local)  -> nothing: the Vec drops at scope end

Verification can't compare pointers (malloc addresses are non-deterministic), so the
differential compares the buffer CONTENTS; safety (no UAF/double-free/leak) is
guaranteed by construction and confirmed under Miri. That's the security payoff made
checkable: the C can leak or double-free, the ownership-typed Rust cannot.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from alchemist.autonomy.onboard import c_to_rust_scalar


_RUST_KW = {"in", "type", "match", "move", "ref", "box", "fn", "let", "mut", "use",
            "mod", "as", "impl", "trait", "self", "loop", "where", "become", "final"}


def _esc(name: str) -> str:
    """Escape a C identifier that collides with a Rust keyword (`in` -> `in_`)."""
    return name + "_" if name in _RUST_KW else name


@dataclass
class HeapAlloc:
    name: str            # allocator function
    size_param: str      # the parameter that sizes the allocation
    elem_c: str          # element C type (e.g. "unsigned char")
    elem_rust: str
    other_params: list   # (name, rust_type) scalar params besides size


@dataclass
class HeapAPI:
    alloc: HeapAlloc
    free_fn: str | None   # a function that frees a pointer param (ownership-in -> drop)


def detect_heap_api(funcs: dict) -> HeapAPI | None:
    """An allocate-and-return function (`T* f(size,...)` that mallocs and returns the
    buffer) + optionally a free function (`void g(T* p)` that frees it)."""
    alloc = None
    for n, f in funcs.items():
        body = getattr(f, "body", "")
        # a var assigned malloc(size_param) and then RETURNED -> allocate-and-return.
        # (the `*` binds to the name, so f.ret is the element type without it)
        m = re.search(r"([A-Za-z_]\w*)\s*=\s*(?:\([^)]*\)\s*)?\b(?:malloc|calloc)\s*\(\s*([A-Za-z_]\w*)",
                      body)
        if not m or not re.search(r"\breturn\s+" + re.escape(m.group(1)) + r"\b", body):
            continue
        size_param = m.group(2)
        elem_c = f.ret.strip() or "unsigned char"
        params = [p.strip() for p in f.params.split(",") if p.strip() and p.strip() != "void"]
        others = []
        for p in params:
            nm = p.split()[-1].lstrip("*")
            if nm != size_param and "*" not in p:
                others.append((nm, c_to_rust_scalar(" ".join(p.split()[:-1]))))
        alloc = HeapAlloc(n, size_param, elem_c, c_to_rust_scalar(elem_c), others)
        break
    if not alloc:
        return None
    free_fn = next((n for n, f in funcs.items()
                    if re.search(r"\bfree\s*\(", getattr(f, "body", "")) and "*" in f.params
                    and n != alloc.name), None)
    return HeapAPI(alloc, free_fn)


def detect_box_alloc(fn_body: str) -> str | None:
    """A single-object heap allocation `malloc(sizeof(T))` -> the type T (maps to
    Box<T> in Rust), as opposed to `malloc(n)` for a buffer (-> Vec<T>)."""
    m = re.search(r"\b(?:malloc|calloc)\s*\(\s*sizeof\s*\(\s*(?:struct\s+)?(\w+)\s*\)", fn_body)
    return m.group(1) if m else None


def struct_field_rust_type(c_type: str, typedefs: dict | None = None) -> str:
    """Owned Rust type for a STRUCT FIELD: a `char *` string field -> String; another
    `T *` field -> Box<T> (owned) with Drop handling the free; scalar/array -> as-is.
    This is the deep ownership frontier — a struct that owns heap becomes a Rust
    struct whose Drop frees it, no manual free anywhere."""
    from alchemist.autonomy.stateful import rust_struct_name
    t = c_type.strip()
    if re.search(r"\bchar\s*\*|\*\s*char\b", t) and "unsigned" not in t:
        return "String"                                       # owned C string -> String
    m = re.search(r"\b(\w+)\s*\*", t)
    if m:
        base = m.group(1)
        if base in ("void",) or re.search(r"\b(?:unsigned\s+char|uint8_t|BYTE)\b", t):
            return "Vec<u8>"                                  # owned byte buffer field
        return "Box<%s>" % rust_struct_name(base)             # owned sub-object -> Box
    return c_to_rust_scalar(t)


def classify_pointer_param(fn_body: str, param: str, is_const: bool = False) -> str:
    """Ownership role of a pointer parameter:
      'owned'  — freed or returned (the fn takes ownership)  -> Vec<T> by value
      'borrow' — `const`-qualified, or only read (a view)    -> &[T]
      'out'    — written, non-const (an output buffer)       -> Vec<T> return
    `const` is the reliable signal; the free/return check overrides it."""
    if re.search(r"\bfree\s*\(\s*&?" + re.escape(param) + r"\b", fn_body) \
            or re.search(r"\breturn\s+" + re.escape(param) + r"\b", fn_body):
        return "owned"
    if is_const:
        return "borrow"
    if re.search(re.escape(param) + r"\s*\[[^\]]*\]\s*=", fn_body) \
            or re.search(r"\*\s*" + re.escape(param) + r"\s*=", fn_body):
        return "out"
    return "borrow"


def infer_param_ownership(fn, elem_rust: str = "u8") -> list[tuple[str, str, str]]:
    """(param_name, role, rust_type) per param — coherent ownership typing: read-only
    view -> &[T], written output -> owned Vec<T>, freed/returned -> owned Vec<T> by
    value. Non-pointer scalars pass through."""
    body = getattr(fn, "body", "")
    out = []
    for p in [x.strip() for x in fn.params.split(",") if x.strip() and x.strip() != "void"]:
        nm = p.split()[-1].lstrip("*")
        if "*" in p or "[" in p:
            role = classify_pointer_param(body, nm, is_const="const" in p)
            rty = ("&[%s]" % elem_rust) if role == "borrow" else ("Vec<%s>" % elem_rust)
            out.append((nm, role, rty))
        else:
            out.append((nm, "scalar", c_to_rust_scalar(" ".join(p.split()[:-1]))))
    return out


def multibuffer_signature(fn, elem_rust: str = "u8") -> str:
    """Coherent Rust signature for a multi-buffer 'complex' function: every input
    buffer -> &[T] (borrow), every output buffer -> RETURNED (owned Vec), scalars
    pass through. Length params paired with a buffer are dropped (the slice carries
    its length). This is what unlocks the wide cipher/codec signatures triage marks
    complex -- the wideness is coherent once ownership is inferred per parameter."""
    roles = infer_param_ownership(fn, elem_rust)
    has_buffer = any(role in ("borrow", "out", "owned") for _, role, _ in roles)
    args, rets = [], []
    for nm, role, rty in roles:
        if role == "out":
            rets.append(rty)
        elif role == "scalar" and has_buffer and re.fullmatch(r"len|n|size|count|nbytes|inlen|outlen", nm):
            continue                                   # length is implicit in the slice
        else:
            args.append("%s: %s" % (_esc(nm), rty))
    ret_c = getattr(fn, "ret", "").strip()
    if rets:
        ret = rets[0] if len(rets) == 1 else "(%s)" % ", ".join(rets)
    else:
        ret = c_to_rust_scalar(ret_c) if ret_c not in ("void", "") else "()"
    return "pub fn %s(%s) -> %s" % (fn.name, ", ".join(args), ret)


def owned_signatures(api: HeapAPI) -> dict[str, str]:
    """Coherent ownership-typed Rust signatures. The allocator RETURNS an owned
    Vec (ownership out); the free fn TAKES an owned Vec by value (ownership in ->
    dropped, the C `free` becomes implicit)."""
    a = api.alloc
    others = "".join(", %s: %s" % (nm, ty) for nm, ty in a.other_params)
    sigs = {a.name: "pub fn %s(%s: usize%s) -> Vec<%s>" % (a.name, a.size_param, others, a.elem_rust)}
    if api.free_fn:
        sigs[api.free_fn] = "pub fn %s(_buf: Vec<%s>)" % (api.free_fn, a.elem_rust)
    return sigs


def build_ownership_crate(paths, out_dir, crate_name, gcc="g++", n_vectors=40):
    """Onboard a heap allocate-return function as ownership-typed safe Rust, verified
    on buffer CONTENTS. The oracle derefs the returned pointer and dumps `size` bytes
    (never the pointer itself)."""
    from alchemist.autonomy.onboard import discover_functions, extract_tables
    from alchemist.autonomy.stateful import StatefulResult, emit_macro_helpers
    from alchemist.autonomy.build_discovery import discover_build
    out_dir = Path(out_dir).resolve()
    sources = [s for p in [Path(x) for x in paths]
               for s in ([p] if p.is_file() else sorted(p.rglob("*.c")))
               if out_dir not in s.resolve().parents and s.name != "_own.cpp"]
    headers = sorted({h for s in sources for h in s.parent.glob("*.h")})
    src_all = "\n".join(s.read_text(errors="replace") for s in sources + headers)
    funcs, tables = {}, {}
    for s in sources + headers:
        txt = s.read_text(errors="replace")
        funcs.update(discover_functions(txt)); tables.update(extract_tables(txt))
    api = detect_heap_api(funcs)
    if not api:
        raise ValueError("no-oracle: no heap allocate-return API detected")
    a = api.alloc

    out_dir.mkdir(parents=True, exist_ok=True)
    plan = discover_build(sources, list({s.parent for s in sources}), out_dir, gcc=gcc)
    # standard headers first, then the .c SOURCES (one TU -> file-statics + the
    # allocator definition resolve, no separate link step)
    incs = "".join('#include "%s"\n' % s.name for s in sources)
    other_reads = "".join("  unsigned char %s = (n>%d)?in[%d]:0;\n" % (nm, 2 + i, 2 + i)
                          for i, (nm, _) in enumerate(a.other_params))
    other_args = "".join(", %s" % nm for nm, _ in a.other_params)
    harness = (
        "#include <cstdio>\n#include <cstdlib>\n#include <cstdint>\n%s"
        "int main(){ unsigned char in[64]; int n=(int)fread(in,1,sizeof(in),stdin);\n"
        "  unsigned long sz = (n>0? in[0]:0) + 1;  // 1..256\n"
        "%s"
        "  %s* p = %s(sz%s);\n"
        "  fwrite(p, sizeof(%s), sz, stdout);  // CONTENTS, never the pointer\n"
        "  free(p); return 0; }\n"
        % (incs, other_reads, a.elem_c, a.name, other_args, a.elem_c))
    (out_dir / "_own.cpp").write_text(harness)
    oracle = out_dir / "_own"
    inc_flags = ["-I" + d for d in {str(s.parent) for s in sources}]
    subprocess.run([gcc, "-O2", *inc_flags, "-o", str(oracle), str(out_dir / "_own.cpp")], check=True)

    def gen_in(i):
        b, x = bytearray(), (i * 2654435761 + 7) & 0xFFFFFFFF
        for _ in range(8):
            x = (1103515245 * x + 12345) & 0xFFFFFFFF
            b.append((x >> 16) & 0xFF)
        return bytes(b)
    vectors = [(gen_in(i), subprocess.run([str(oracle)], input=gen_in(i),
               capture_output=True).stdout) for i in range(n_vectors)]
    if not any(v for _, v in vectors):
        raise ValueError("no-oracle: heap harness produced empty contents")

    crate = out_dir / crate_name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname="%s"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n'
        '[profile.dev]\noverflow-checks = false\n[profile.test]\noverflow-checks = false\n' % crate_name)
    macro_rs, _ = emit_macro_helpers(src_all)
    tables_rs = "\n".join(t.rust_const() for t in tables.values())
    sigs = owned_signatures(api)
    fill_seq = [n for n in (a.name, api.free_fn) if n]
    stubs = "\n".join(sigs[n] + " { unimplemented!() }" for n in fill_seq)
    # test: size + scalar args derived exactly as the C harness does
    other_lets = "".join("            let %s: u8 = if inp.len()>%d { inp[%d] } else { 0 };\n"
                         % (nm, 2 + i, 2 + i) for i, (nm, _) in enumerate(a.other_params))
    call_args = "".join(", %s as _" % nm for nm, _ in a.other_params)
    vec_lits = ",\n        ".join("(&[%s], &[%s])" % (", ".join(map(str, s)), ", ".join(map(str, c)))
                                  for s, c in vectors)
    test = ("#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn fuzz_%s() {\n"
            "        let vectors: &[(&[u8], &[u8])] = &[\n        %s];\n"
            "        for (inp, expected) in vectors {\n"
            "            let sz = (*inp.get(0).unwrap_or(&0) as usize) + 1;\n"
            "%s"
            "            let v = %s(sz%s);\n"
            "            assert_eq!(v.as_slice(), *expected);  // CONTENTS byte-exact\n"
            "        }\n    }\n}\n"
            % (crate_name, vec_lits, other_lets, a.name, call_args))
    (crate / "src" / "lib.rs").write_text(
        "#![allow(dead_code, non_snake_case, unused_variables, clippy::needless_range_loop)]\n"
        + tables_rs + "\n\n" + macro_rs + "\n\n" + stubs + "\n\n" + test)
    return StatefulResult(crate, fill_seq, None, len(vectors), plan.stubbed, [])
