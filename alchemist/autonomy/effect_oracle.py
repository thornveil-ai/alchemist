"""Pillar 1 — the effect-footprint oracle.

The pure-function oracle verifies `input -> output bytes`. That's why crypto/codecs
work and anything touching global state is out of scope. This generalizes the
differential to the FULL OBSERVABLE FOOTPRINT of a call sequence:

    footprint = [captured return values] ++ [final bytes of every global/static]

C keeps its state in implicit file-scope globals; the coherent Rust model makes
that state EXPLICIT (a `GlobalState` struct threaded as `&mut`). Both run the same
driver over the same input and dump the same footprint; byte-exact-or-refused now
holds for effectful code, not just pure functions.

This is the moat: an oracle that verifies effectful C is what lets "verified-or-
refused" scale past the deterministic slice toward arbitrary C — model-agnostically.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from alchemist.autonomy.onboard import c_to_rust_scalar


@dataclass
class Global:
    name: str
    c_type: str
    rust_type: str
    array_len: int | None
    init: str


def _depth0(src: str) -> str:
    """Only the characters at brace depth 0 — strips function/struct/init bodies so
    what remains is file-scope declarations."""
    out, depth = [], 0
    for ch in src:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


_SKIP = ("typedef", "struct", "enum", "union", "extern", "#", "return", "}")


def detect_globals(src: str, defines: dict[str, int] | None = None) -> list[Global]:
    """File-scope mutable globals/statics (the implicit state effectful C carries).
    Skips typedefs, prototypes (contain `(`), consts, and struct/enum defs."""
    defines = defines or {}
    out: list[Global] = []
    src = re.sub(r"^[ \t]*#.*$", "", src, flags=re.M)   # drop preprocessor lines (no ';')
    for stmt in _depth0(src).split(";"):
        s = re.sub(r"//.*", "", stmt).strip()
        if not s or "(" in s or s.startswith(_SKIP) or "const" in s.split("=")[0]:
            continue
        m = re.match(r"(?:static\s+)?((?:unsigned\s+|signed\s+)*[A-Za-z_]\w*"
                     r"(?:\s+(?:int|long|char|short))*)\s+(\w+)\s*"
                     r"(?:\[\s*(\w+)\s*\])?\s*(?:=\s*(.+))?$", s)
        if not m:
            continue
        c_type, name, dim, init = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
        if c_type in ("void",) or not c_type:
            continue
        n = None
        if dim is not None:
            n = int(dim) if dim.isdigit() else defines.get(dim, 0)
        out.append(Global(name, c_type, c_to_rust_scalar(c_type), n, (init or "").strip()))
    return out


def emit_c_footprint_dump(globals_: list[Global], stream: str = "stdout") -> str:
    """C statements that append every global's raw bytes to the footprint stream."""
    lines = []
    for g in globals_:
        if g.array_len is not None:
            lines.append("fwrite(%s, sizeof(%s), 1, %s);" % (g.name, g.name, stream))
        else:
            lines.append("fwrite(&%s, sizeof(%s), 1, %s);" % (g.name, g.name, stream))
    return "\n  ".join(lines)


def emit_rust_state_struct(globals_: list[Global], name: str = "GlobalState") -> str:
    """Rust struct making the C globals explicit + a matching footprint dumper."""
    fields, defaults, dumps = [], [], []
    for g in globals_:
        if g.array_len is not None:
            fields.append("    pub %s: [%s; %d]," % (g.name, g.rust_type, g.array_len))
            defaults.append("%s: [0; %d]" % (g.name, g.array_len))
            dumps.append("for v in self.%s.iter() { out.extend_from_slice(&v.to_ne_bytes()); }" % g.name)
        else:
            fields.append("    pub %s: %s," % (g.name, g.rust_type))
            defaults.append("%s: %s" % (g.name, g.init or "0"))
            dumps.append("out.extend_from_slice(&self.%s.to_ne_bytes());" % g.name)
    return (
        "#[derive(Clone)]\npub struct %s {\n%s\n}\n"
        "impl Default for %s {\n    fn default() -> Self { Self { %s } }\n}\n"
        "impl %s {\n    pub fn footprint(&self) -> Vec<u8> {\n        let mut out = Vec::new();\n"
        "        %s\n        out\n    }\n}\n"
        % (name, "\n".join(fields), name, ", ".join(defaults), name, "\n        ".join(dumps)))


@dataclass
class GlobalStateAPI:
    init: str | None      # sets globals from input (void return)
    step: str             # mutates globals, returns a value
    step_ret: str         # Rust return type of step


def detect_global_state_api(funcs: dict, globals_: list[Global]) -> GlobalStateAPI | None:
    """A seed/step pair over implicit global state: `init` (void, takes input, sets
    globals) then `step` (returns a value, mutates globals). PRNGs, running hashers,
    global accumulators."""
    gnames = {g.name for g in globals_}
    if not gnames:
        return None
    touch = {n: f for n, f in funcs.items()
             if gnames & set(re.findall(r"\b\w+\b", getattr(f, "body", "")))}
    step = next((n for n, f in touch.items() if f.ret.strip() != "void"), None)
    if not step:
        return None
    init = next((n for n, f in touch.items()
                 if f.ret.strip() == "void" and f.params.strip() not in ("", "void")), None)
    return GlobalStateAPI(init, step, c_to_rust_scalar(funcs[step].ret))


def build_effectful_crate(paths, out_dir, crate_name, gcc="g++", steps=8, n_vectors=40):
    """Onboard a global-state (effectful) function as a first-class shape: implicit
    C globals -> explicit `GlobalState`, verified on the full footprint (step returns
    ++ final globals). This is the moat made usable."""
    from alchemist.autonomy.onboard import discover_functions, extract_tables
    from alchemist.autonomy.stateful import resolve_typedefs, StatefulResult, emit_macro_helpers
    from alchemist.autonomy.build_discovery import discover_build
    from alchemist.autonomy.c_struct import resolve_c_defines
    out_dir = Path(out_dir).resolve()
    sources = [s for p in [Path(x) for x in paths]
               for s in ([p] if p.is_file() else sorted(p.rglob("*.c")))
               if out_dir not in s.resolve().parents and s.name != "_eff.cpp"]
    headers = sorted({h for s in sources for h in s.parent.glob("*.h")})
    src_all = "\n".join(s.read_text(errors="replace") for s in sources + headers)
    funcs, tables, defines = {}, {}, {}
    for s in sources + headers:
        txt = s.read_text(errors="replace")
        funcs.update(discover_functions(txt)); tables.update(extract_tables(txt))
        defines.update(resolve_c_defines(txt))
    globals_ = detect_globals(src_all, defines)
    api = detect_global_state_api(funcs, globals_)
    if not api:
        raise ValueError("no-oracle: no global-state (init/step over globals) API detected")
    step_c_ret = funcs[api.step].ret.strip()

    out_dir.mkdir(parents=True, exist_ok=True)
    plan = discover_build(sources, list({s.parent for s in sources}), out_dir, gcc=gcc)
    # include the .c SOURCES directly (one TU) so file-static globals are visible to
    # the footprint dump -- an external harness can't see `static` internal linkage
    incs = "".join('#include "%s"\n' % s.name for s in sources)
    init_call = ("%s(seed);" % api.init) if api.init else ""
    harness = (
        "#include <cstdio>\n#include <cstdint>\n#include <cstring>\n%s"
        "int main(){ unsigned char in[64]; int n=(int)fread(in,1,sizeof(in),stdin);\n"
        "  unsigned long seed=0; for(int i=0;i<n&&i<8;i++) seed=(seed<<8)|in[i];\n"
        "  %s\n"
        "  for(int i=0;i<%d;i++){ %s r=%s(); fwrite(&r,sizeof(r),1,stdout); }\n"
        "  %s\n  return 0; }\n"
        % (incs, init_call, steps, step_c_ret, api.step, emit_c_footprint_dump(globals_)))
    (out_dir / "_eff.cpp").write_text(harness)
    oracle = out_dir / "_eff"
    inc_flags = ["-I" + d for d in {str(s.parent) for s in sources}]
    if (out_dir / "_stubs").exists():
        inc_flags.append("-I" + str(out_dir / "_stubs"))
    subprocess.run([gcc, "-O2", *inc_flags, "-o", str(oracle), str(out_dir / "_eff.cpp")], check=True)

    def gen_seed(i):
        b, x = bytearray(), (i * 2654435761 + 1) & 0xFFFFFFFF
        for _ in range(8):
            x = (1103515245 * x + 12345) & 0xFFFFFFFF
            b.append((x >> 16) & 0xFF)
        return bytes(b)
    vectors = [(gen_seed(i), subprocess.run([str(oracle)], input=gen_seed(i),
               capture_output=True).stdout) for i in range(n_vectors)]
    if not any(v for _, v in vectors):
        raise ValueError("no-oracle: effectful harness produced empty footprint")

    crate = out_dir / crate_name
    (crate / "src").mkdir(parents=True, exist_ok=True)
    (crate / "Cargo.toml").write_text(
        '[package]\nname="%s"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n'
        '[profile.dev]\noverflow-checks = false\n[profile.test]\noverflow-checks = false\n' % crate_name)
    state_rs = emit_rust_state_struct(globals_)
    macro_rs, _ = emit_macro_helpers(src_all)
    tables_rs = "\n".join(t.rust_const() for t in tables.values())
    init_scalar = ""
    if api.init:
        p0 = [x.strip() for x in funcs[api.init].params.split(",") if x.strip()][0]
        init_scalar = ", %s: %s" % (p0.split()[-1], c_to_rust_scalar(" ".join(p0.split()[:-1])))
    sigs = {}
    if api.init:
        sigs[api.init] = "pub fn %s(st: &mut GlobalState%s)" % (api.init, init_scalar)
    sigs[api.step] = "pub fn %s(st: &mut GlobalState) -> %s" % (api.step, api.step_ret)
    fill_seq = [n for n in (api.init, api.step) if n]
    stubs = "\n".join(sigs[n] + " { unimplemented!() }" for n in fill_seq)
    vec_lits = ",\n        ".join("(&[%s], &[%s])" % (", ".join(map(str, s)), ", ".join(map(str, fp)))
                                  for s, fp in vectors)
    seed_line = "let mut seed: u64 = 0; for &b in inp.iter().take(8) { seed = (seed<<8)|(b as u64); }"
    init_line = ("%s(&mut st, seed as _);" % api.init) if api.init else "let _ = seed;"
    test = ("#[cfg(test)]\nmod tests {\n    use super::*;\n    #[test]\n    fn fuzz_%s() {\n"
            "        let vectors: &[(&[u8], &[u8])] = &[\n        %s];\n"
            "        for (inp, expected) in vectors {\n"
            "            let mut st = GlobalState::default();\n            %s\n            %s\n"
            "            let mut fp = Vec::new();\n"
            "            for _ in 0..%d { fp.extend_from_slice(&%s(&mut st).to_ne_bytes()); }\n"
            "            fp.extend_from_slice(&st.footprint());\n"
            "            assert_eq!(fp.as_slice(), *expected);\n        }\n    }\n}\n"
            % (crate_name, vec_lits, seed_line, init_line, steps, api.step))
    (crate / "src" / "lib.rs").write_text(
        "#![allow(dead_code, non_snake_case, unused_variables, clippy::needless_range_loop)]\n"
        + tables_rs + "\n\n" + state_rs + "\n" + macro_rs + "\n\n" + stubs + "\n\n" + test)
    return StatefulResult(crate, fill_seq, None, len(vectors), plan.stubbed, [])
