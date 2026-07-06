"""Stateful struct APIs (Tier 2 #1) — the init/update/final pattern.

Most real, security-critical C is stateful: a context struct threaded through
`init` -> `update(data)` -> `final(digest)` (streaming hashes, HMACs, ciphers,
parsers). This onboards that shape: detect the ctx struct + the init/update/final
trio, emit a coherent Rust struct (fixed C arrays -> Rust arrays), and drive a
SEQUENCE oracle (run the three calls on a shared state, capture the output) at
fuzz depth (thousands of random inputs). Also exercises two new signature shapes
(Tier 2 #2): `&mut Ctx` state receivers and a fixed-size output buffer.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from alchemist.autonomy.onboard import discover_functions, extract_tables, c_to_rust_scalar
from alchemist.autonomy.c_struct import _find_struct_body, resolve_c_defines
from alchemist.autonomy.build_discovery import discover_build


def resolve_typedefs(src: str) -> dict[str, str]:
    """`typedef <base> <alias>;` -> {alias: base}. Simple scalar typedefs only."""
    td: dict[str, str] = {}
    for m in re.finditer(r"typedef\s+([\w ]+?)\s+(\w+)\s*;", src):
        td[m.group(2)] = m.group(1).strip()
    return td


def _rust_scalar(c_type: str, typedefs: dict[str, str]) -> str:
    t = c_type.strip()
    seen: set = set()
    while t in typedefs and t not in seen:
        seen.add(t)
        t = typedefs[t].strip()
    return c_to_rust_scalar(t)


def rust_struct_name(c_name: str) -> str:
    return "".join(w.capitalize() for w in c_name.split("_")) or c_name


@dataclass
class CtxField:
    name: str
    rust_type: str
    default: str


def parse_ctx_fields(src: str, struct_name: str, typedefs: dict[str, str],
                     defines: dict[str, int]) -> list[CtxField]:
    body = _find_struct_body(src, struct_name)
    if not body:
        return []
    fields: list[CtxField] = []
    for stmt in body.split(";"):
        stmt = re.sub(r"//.*", "", stmt).strip()
        if not stmt:
            continue
        m = re.match(r"(.+?)\s+(\w+)\s*(?:\[\s*(\w+)\s*\])?$", stmt)
        if not m:
            continue
        base, name, dim = m.group(1), m.group(2), m.group(3)
        rty = _rust_scalar(base, typedefs)
        if dim:
            n = int(dim) if dim.isdigit() else defines.get(dim, 0)
            fields.append(CtxField(name, "[%s; %d]" % (rty, n), "[0; %d]" % n))
        else:
            fields.append(CtxField(name, rty, "0"))
    return fields


def emit_ctx_struct(rust_name: str, fields: list[CtxField]) -> str:
    field_lines = "\n".join("    pub %s: %s," % (f.name, f.rust_type) for f in fields)
    default_lines = ", ".join("%s: %s" % (f.name, f.default) for f in fields)
    return (
        "#[derive(Clone)]\npub struct %s {\n%s\n}\n"
        "impl Default for %s {\n    fn default() -> Self { Self { %s } }\n}\n"
        % (rust_name, field_lines, rust_name, default_lines))


@dataclass
class StatefulAPI:
    ctx_c: str
    ctx_rust: str
    init: str | None
    update: str | None
    final: str | None
    helpers: list[str] = field(default_factory=list)
    digest_len: int = 32
    typedefs: dict = field(default_factory=dict)


_NON_CTX_TYPES = {"void", "char", "uint8_t", "uint16_t", "uint32_t", "uint64_t",
                  "int", "unsigned", "long", "short", "size_t", "BYTE", "WORD",
                  "u8", "u16", "u32", "u64", "uchar", "uint", "ulong"}


def _ptr_types(params: str) -> list[str]:
    """Struct/typedef pointer-param types (ctx candidates), from ANY position —
    not just the first param (some finals put the ctx second: `final(md, ctx)`)."""
    out = []
    for p in [x.strip() for x in params.split(",") if x.strip()]:
        p = re.sub(r"([A-Za-z_]\w*)\s*\[\s*\w*\s*\]", r"* \1", p)  # array -> ptr
        if "*" in p:
            ty = re.sub(r"[\*\s]+\w+$", "", p).replace("const", "").strip()
            toks = ty.split()
            if toks:
                out.append(toks[-1])
    return out


def detect_stateful_api(funcs: dict, defines: dict[str, int],
                        typedefs: dict | None = None) -> StatefulAPI | None:
    ctx_counts: Counter = Counter()
    for f in funcs.values():
        for t in _ptr_types(f.params):
            if t not in _NON_CTX_TYPES:  # the ctx is a struct/typedef, not a scalar
                ctx_counts[t] += 1
    if not ctx_counts:
        return None
    ctx_c, _ = ctx_counts.most_common(1)[0]
    on_ctx = [n for n, f in funcs.items() if ctx_c in _ptr_types(f.params)]

    def find(keys):
        for n in on_ctx:
            if any(k in n.lower() for k in keys):
                return n
        return None
    init = find(["init", "reset", "start", "begin"])
    update = find(["update", "add", "write", "absorb"])
    final = find(["final", "finish", "digest", "result", "end", "done"])
    if not (init and update and final):
        return None
    helpers = [n for n in on_ctx if n not in (init, update, final)]
    # digest length from a *_SIZE / *_LEN #define with a plausible value
    digest_len = 32
    for k, v in defines.items():
        if re.search(r"(DIGEST|BLOCK|HASH|OUT).*(SIZE|LEN)|_SIZE$", k) and 8 <= v <= 128:
            digest_len = v
            break
    return StatefulAPI(ctx_c, rust_struct_name(ctx_c), init, update, final,
                       helpers, digest_len, typedefs or {})


def stateful_signature(fn: str, funcs: dict, api: StatefulAPI) -> str:
    """Coherent Rust signature for a ctx-taking function: `ctx: &mut CtxRust`
    plus the classified remaining params (buffer->&[u8], out-buffer->Vec return),
    with C `void` mapping to no return."""
    from alchemist.autonomy.oracle_gen import classify_signature
    from alchemist.autonomy.onboard import CFunc
    f = funcs[fn]
    parts = [p.strip() for p in f.params.split(",") if p.strip()]
    rest = ", ".join(parts[1:])
    spec = classify_signature(CFunc(name=fn, ret=f.ret, params=rest, body=f.body),
                              typedefs=api.typedefs)
    args = ["ctx: &mut %s" % api.ctx_rust]
    buffer_done = False
    for p in spec.params:
        if p.role == "buffer" and not buffer_done:
            args.append("data: &[u8]")
            buffer_done = True
        elif p.role in ("len", "out_buffer"):
            continue
        elif p.role == "scalar":
            args.append("%s: %s" % (p.name, p.rust_type))
    if spec.buffer_output:
        ret = " -> Vec<u8>"
    elif "void" in f.ret:
        ret = ""
    else:
        ret = " -> %s" % spec.ret_rust
    return "pub fn %s(%s)%s" % (fn, ", ".join(args), ret)


def _harness_call(fn: str, funcs: dict, api: StatefulAPI) -> str:
    """C call for a ctx function, filling each param by ROLE (ctx -> &ctx, input
    buffer -> in, length -> n, output buffer -> out, size scalar -> digest_len),
    so it works regardless of param ORDER (e.g. `final(md, ctx)`)."""
    parts = [p.strip() for p in funcs[fn].params.split(",") if p.strip()]
    args, buf_seen = [], False
    for p in parts:
        p = re.sub(r"([A-Za-z_]\w*)\s*\[\s*\w*\s*\]", r"* \1", p)  # array -> ptr
        m = re.search(r"([A-Za-z_]\w*)\s*$", p)
        name = m.group(1) if m else ""
        ctype = (p[:m.start()] if m else p)
        is_ptr = "*" in p
        byte_ptr = bool(re.search(r"\b(char|uint8_t|void|BYTE|u8|unsigned char)\b", ctype))
        if is_ptr and api.ctx_c in _ptr_types(p):
            args.append("&ctx")
        elif is_ptr and "const" in ctype and byte_ptr:
            args.append("in"); buf_seen = True
        elif is_ptr and byte_ptr:                       # mutable byte/void ptr = output
            args.append("out")
        elif not is_ptr and (name.lower() in {"len", "length", "size", "count", "inlen",
                                              "mdlen", "outlen", "n"} or re.search(r"(len|size)$", name.lower())):
            args.append("n" if buf_seen else str(api.digest_len))
        else:
            args.append("0")
    return "%s(%s)" % (fn, ", ".join(args))


def generate_sequence_harness(api: StatefulAPI, funcs: dict, headers: list[str]) -> str:
    """C harness: read stdin, run init -> update(data,len) -> final(out), dump the
    digest. Calls are built by param ROLE so any arg order works."""
    incs = "".join('#include "%s"\n' % h for h in headers)
    return (
        "#include <cstdio>\n#include <cstring>\n#include <cstdint>\n%s"
        "int main(){\n"
        "  static unsigned char in[65536]; unsigned char out[256];\n"
        "  size_t n = fread(in,1,sizeof(in),stdin);\n"
        "  %s ctx;\n  %s;\n  %s;\n  %s;\n"
        "  fwrite(out,1,%d,stdout);\n  return 0;\n}\n"
        % (incs, api.ctx_c, _harness_call(api.init, funcs, api),
           _harness_call(api.update, funcs, api), _harness_call(api.final, funcs, api),
           api.digest_len))


def emit_macro_helpers(src: str) -> tuple[str, list[str]]:
    """Function-like `#define NAME(args) body` -> Rust helper fns (keeping the C
    names so a translation that calls them just works). Rotations map to
    rotate_left/right (avoids Rust's shift-by-width panic); other bodies map `~`
    to `!`. Common in crypto (ROTRIGHT/CH/MAJ/EP0/SIG0...)."""
    from collections import OrderedDict
    # join `\`-continued lines first (MD5/SHA round macros span multiple lines)
    src = re.sub(r"\\[ \t]*\r?\n", " ", src)
    macros: OrderedDict = OrderedDict()
    for m in re.finditer(r"^[ \t]*#[ \t]*define[ \t]+(\w+)\(([^)]*)\)[ \t]+(.+)$", src, re.M):
        macros[m.group(1)] = ([a.strip() for a in m.group(2).split(",")], m.group(3).strip())
    macro_set = set(macros)
    out, emitted = [], []
    for name, (args, body) in macros.items():
        # STATEMENT macros (block bodies, or mutating an arg like `a += ...`) are
        # NOT pure functions -- skip them; the model inlines them from the C. Only
        # EXPRESSION macros become helper fns.
        if "{" in body or ";" in body or re.search(r"\b\w+\s*[-+*^|&]?=[^=]", body):
            continue
        # ALIAS macros that call a real function (e.g. shake128_init(c) ->
        # sha3_init(c,16)) are API aliases, not arithmetic -- skip them, else we
        # emit a bogus `fn shake128_init(c: u32) -> u32` that miscalls sha3_init.
        if set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", body)) - macro_set:
            continue
        emitted.append(name)
        if "<<" in body and ">>" in body and "32" in body and len(args) == 2:
            op = "rotate_left" if body.index("<<") < body.index(">>") else "rotate_right"
            out.append("#[allow(non_snake_case)] fn %s(%s: u32, %s: u32) -> u32 { (%s).%s(%s) }"
                       % (name, args[0], args[1], args[0], op, args[1]))
        else:
            params = ", ".join("%s: u32" % a for a in args)
            out.append("#[allow(non_snake_case)] fn %s(%s) -> u32 { %s }"
                       % (name, params, body.replace("~", "!")))
    return "\n".join(out), emitted


@dataclass
class ArrayCipher:
    """A stream cipher whose state is a byte ARRAY (not a struct): key-setup(state,
    key, len) then generate(state, out, len). RC4/arcfour is the canonical shape."""
    init: str
    gen: str
    state_size: int


def detect_array_cipher(funcs: dict) -> ArrayCipher | None:
    def first_is_byte_array(f) -> bool:
        parts = [p.strip() for p in f.params.split(",") if p.strip()]
        return bool(parts) and "[" in parts[0] and \
            bool(re.search(r"\b(BYTE|uint8_t|u8|unsigned char)\b", parts[0]))
    on_state = [n for n, f in funcs.items() if first_is_byte_array(funcs[n])]
    if len(on_state) < 2:
        return None
    init = next((n for n in on_state if any(k in n.lower()
                 for k in ("setup", "init", "schedule", "ksa"))), None)
    gen = next((n for n in on_state if any(k in n.lower()
                for k in ("generate", "stream", "crypt", "prga", "keystream"))), None)
    if not (init and gen):
        return None
    # infer the state array size from the init body (`< 256`, `state[255]`), else 256
    body = funcs[init].body
    m = re.search(r"[<]=?\s*(\d{2,4})|\[\s*(\d{2,4})\s*\]", body)
    size = int(next((g for g in (m.groups() if m else ()) if g), 256))
    return ArrayCipher(init, gen, size if size >= 16 else 256)


@dataclass
class StatefulResult:
    crate_dir: Path
    fill_order: list[str]
    api: StatefulAPI
    num_vectors: int
    stubbed: list[str] = field(default_factory=list)
    macro_names: list[str] = field(default_factory=list)


def build_array_cipher_crate(paths: list[Path], out_dir: Path, crate_name: str,
                             key_lengths: list[int], gcc: str = "g++",
                             keystream_len: int = 64) -> StatefulResult:
    """Onboard an array-state stream cipher (RC4/arcfour): key_setup(state,key,len)
    then generate(state,out,len). State modelled as `[u8; N]`; the fuzz input is the
    KEY; the oracle generates a fixed keystream and compares byte-exact."""
    from alchemist.autonomy.onboard import fill_order, extract_char_defines
    out_dir = Path(out_dir).resolve()
    sources = []
    for p in [Path(x) for x in paths]:
        sources += (sorted(p.rglob("*.c")) + sorted(p.rglob("*.cpp"))) if p.is_dir() else [p]
    sources = [s for s in sources if out_dir not in s.resolve().parents
               and s.name not in ("_seq.cpp", "_oracle.cpp")]
    headers = sorted({h for s in sources for h in s.parent.glob("*.h")})
    src_all = "\n".join(s.read_text(errors="replace") for s in sources + headers)
    funcs, tables, typedefs = {}, {}, {}
    for s in sources + headers:
        txt = s.read_text(errors="replace")
        funcs.update(discover_functions(txt)); tables.update(extract_tables(txt))
        typedefs.update(resolve_typedefs(txt))
    cipher = detect_array_cipher(funcs)
    if not cipher:
        raise ValueError("no-oracle: no array-state cipher (init+generate) detected")
    N, K = cipher.state_size, keystream_len

    out_dir.mkdir(parents=True, exist_ok=True)
    plan = discover_build(sources, list({s.parent for s in sources}), out_dir, gcc=gcc)
    incs = "".join('#include "%s"\n' % h.name for h in headers)
    harness = (
        "#include <cstdio>\n#include <cstring>\n#include <cstdint>\n%s"
        "int main(){ static unsigned char in[65536]; int l=(int)fread(in,1,sizeof(in),stdin);\n"
        "  unsigned char state[%d]; unsigned char out[%d];\n"
        "  %s(state, in, l); %s(state, out, %d);\n"
        "  fwrite(out,1,%d,stdout); return 0; }\n"
        % (incs, N, K, cipher.init, cipher.gen, K, K))
    (out_dir / "_seq.cpp").write_text(harness)
    oracle = out_dir / "_seq"
    subprocess.run(plan.compile_cmd([out_dir / "_seq.cpp"], oracle), check=True)

    def gen_key(length, seed):
        b, x = bytearray(), (seed * 2654435761 + 1) & 0xFFFFFFFF
        for _ in range(length):
            x = (1103515245 * x + 12345) & 0xFFFFFFFF
            b.append((x >> 16) & 0xFF)
        return bytes(b)
    vectors = []
    for i, L in enumerate(key_lengths):
        k = gen_key(max(1, L), i)  # key must be non-empty for RC4
        ks = subprocess.run([str(oracle)], input=k, capture_output=True).stdout
        vectors.append((k, ks))
    if not any(v for _, v in vectors):
        raise ValueError("no-oracle: array-cipher harness produced empty output")

    crate = out_dir / crate_name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname="%s"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n'
        '[profile.dev]\noverflow-checks = false\n[profile.test]\noverflow-checks = false\n' % crate_name)
    macro_rs, _ = emit_macro_helpers(src_all)
    tables_rs = "\n".join(t.rust_const() for t in tables.values())
    consts = "\n".join("pub const %s: u8 = %d;" % (n.upper(), v)
                       for n, v in extract_char_defines(src_all).items())
    aliases = "\n".join("#[allow(non_camel_case_types)] pub type %s = %s;" % (a, _rust_scalar(a, typedefs))
                        for a in typedefs if _rust_scalar(a, typedefs) in ("u8", "u16", "u32", "u64"))
    sig = {cipher.init: "pub fn %s(state: &mut [u8; %d], key: &[u8])" % (cipher.init, N),
           cipher.gen: "pub fn %s(state: &mut [u8; %d], out_len: usize) -> Vec<u8>" % (cipher.gen, N)}
    fill_seq = [cipher.init, cipher.gen]
    stubs = "\n".join("%s { unimplemented!() }" % sig[n] for n in fill_seq)
    vec_lits = ",\n        ".join("(&[%s], &[%s])" % (", ".join(map(str, k)), ", ".join(map(str, ks)))
                                  for k, ks in vectors)
    test = ("#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn fuzz_%s() {\n"
            "        let vectors: &[(&[u8], &[u8])] = &[\n        %s];\n"
            "        for (key, expected) in vectors {\n"
            "            let mut state = [0u8; %d];\n"
            "            %s(&mut state, key);\n"
            "            assert_eq!(%s(&mut state, %d).as_slice(), *expected, \"keylen {}\", key.len());\n"
            "        }\n    }\n}\n"
            % (crate_name, vec_lits, N, cipher.init, cipher.gen, K))
    (crate / "src" / "lib.rs").write_text(
        "#![allow(dead_code, non_snake_case, clippy::needless_range_loop, unused_variables)]\n"
        + aliases + "\n" + consts + "\n" + tables_rs + "\n\n" + macro_rs + "\n\n" + stubs + "\n\n" + test)
    return StatefulResult(crate, fill_seq, None, len(vectors), plan.stubbed, [])


def build_stateful_crate(paths: list[Path], out_dir: Path, crate_name: str,
                         input_lengths: list[int], gcc: str = "g++") -> StatefulResult:
    from alchemist.autonomy.onboard import fill_order, extract_char_defines
    out_dir = Path(out_dir).resolve()
    sources = []
    for p in [Path(x) for x in paths]:
        sources += (sorted(p.rglob("*.c")) + sorted(p.rglob("*.cpp"))) if p.is_dir() else [p]
    # never pick up our own generated oracle/crate files (they live under out_dir)
    sources = [s for s in sources
               if out_dir not in s.resolve().parents
               and s.name not in ("_seq.cpp", "_oracle.cpp")]
    # scan .c AND .h — the ctx struct, typedefs, #defines and macros usually live
    # in the header, not the .c we compile.
    header_files = sorted({h for s in sources for h in s.parent.glob("*.h")})
    scan_files = sources + header_files
    src_all = "\n".join(s.read_text(errors="replace") for s in scan_files)

    funcs, tables, typedefs, defines = {}, {}, {}, {}
    for s in scan_files:
        txt = s.read_text(errors="replace")
        funcs.update(discover_functions(txt))  # bodies are in .c; headers are decls (skipped)
        tables.update(extract_tables(txt))
        typedefs.update(resolve_typedefs(txt))
        defines.update(resolve_c_defines(txt))
    macro_helpers, macro_names = emit_macro_helpers(src_all)
    names = set(funcs)
    for f in funcs.values():
        f.calls = {c for c in re.findall(r"\b(\w+)\s*\(", f.body) if c in names and c != f.name}

    api = detect_stateful_api(funcs, defines, typedefs)
    if not api:
        raise ValueError("no init/update/final stateful API detected")
    fields = parse_ctx_fields(src_all, api.ctx_c, typedefs, defines)
    fill_seq = [n for n in fill_order(funcs)
                if n in {api.init, api.update, api.final, *api.helpers}]

    # --- oracle: build (auto includes/stubs) + sequence harness ---
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = discover_build(sources, list({s.parent for s in sources}), out_dir, gcc=gcc)
    headers = sorted({h.name for s in sources for h in s.parent.glob("*.h")})
    (out_dir / "_seq.cpp").write_text(generate_sequence_harness(api, funcs, headers))
    oracle = out_dir / "_seq"
    subprocess.run(plan.compile_cmd([out_dir / "_seq.cpp"], oracle), check=True)

    # --- fuzz vectors: (input -> digest) across many lengths ---
    def run(inp: bytes) -> bytes:
        return subprocess.run([str(oracle)], input=inp, capture_output=True).stdout
    # deterministic pseudo-random bytes (no RNG allowed): a simple LCG per length
    def gen(length: int, seed: int) -> bytes:
        b, x = bytearray(), (seed * 2654435761 + 1) & 0xFFFFFFFF
        for _ in range(length):
            x = (1103515245 * x + 12345) & 0xFFFFFFFF
            b.append((x >> 16) & 0xFF)
        return bytes(b)
    vectors = [(gen(L, i), run(gen(L, i))) for i, L in enumerate(input_lengths)]
    # INTEGRITY: if the sequence oracle produced no bytes for any input, it's
    # broken (wrong API shape) -> refuse rather than ship a vacuous green.
    if not any(dig for _, dig in vectors):
        raise ValueError("no-oracle: sequence harness produced empty output "
                         "(check init/update/final signatures for %s)" % api.ctx_c)

    # --- crate: ctx struct + tables + stateful stubs + one deep fuzz test ---
    crate = out_dir / crate_name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    (crate / "Cargo.toml").write_text(
        # overflow-checks=false: C unsigned arithmetic is DEFINED to wrap (hashes/
        # ciphers rely on it); this gives byte-identical semantics while the
        # differential oracle still catches any real logic bug.
        '[package]\nname="%s"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n'
        '[profile.dev]\noverflow-checks = false\n[profile.test]\noverflow-checks = false\n' % crate_name)
    consts = "\n".join("pub const %s: u8 = %d;" % (n.upper(), v)
                       for n, v in extract_char_defines(src_all).items())
    tables_rs = "\n".join(t.rust_const() for t in tables.values())
    struct_rs = emit_ctx_struct(api.ctx_rust, fields)
    # type aliases so the model may use the C names verbatim (ctx type + scalar
    # typedefs) -- kills the "cannot find type MD2_CTX / BYTE / WORD" (E0425) class.
    alias_lines = ["#[allow(non_camel_case_types)] pub type %s = %s;" % (api.ctx_c, api.ctx_rust)]
    for alias in typedefs:
        rt = _rust_scalar(alias, typedefs)
        if rt in ("u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64", "usize", "bool"):
            alias_lines.append("#[allow(non_camel_case_types)] pub type %s = %s;" % (alias, rt))
    struct_rs = "\n".join(alias_lines) + "\n" + struct_rs
    stubs = "\n".join("%s { unimplemented!() }" % stateful_signature(n, funcs, api) for n in fill_seq)
    vec_lits = ",\n        ".join(
        "(&[%s], &[%s])" % (", ".join(map(str, inp)), ", ".join(map(str, dig)))
        for inp, dig in vectors)
    test = (
        "#[cfg(test)]\nmod tests {\n    use super::*;\n"
        "    #[test]\n    fn fuzz_%s() {\n"
        "        let vectors: &[(&[u8], &[u8])] = &[\n        %s];\n"
        "        for (input, expected) in vectors {\n"
        "            let mut ctx = %s::default();\n"
        "            %s(&mut ctx);\n"
        "            %s(&mut ctx, input);\n"
        "            assert_eq!(%s(&mut ctx).as_slice(), *expected, \"len {}\", input.len());\n"
        "        }\n    }\n}\n"
        % (crate_name, vec_lits, api.ctx_rust, api.init, api.update, api.final))
    (crate / "src" / "lib.rs").write_text(
        "#![allow(dead_code, non_snake_case, clippy::needless_range_loop, unused_variables)]\n"
        + consts + "\n" + tables_rs + "\n\n" + macro_helpers + "\n\n"
        + struct_rs + "\n" + stubs + "\n\n" + test)
    return StatefulResult(crate, fill_seq, api, len(vectors), plan.stubbed, macro_names)
