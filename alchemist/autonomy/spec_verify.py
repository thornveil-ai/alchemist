"""Algorithmic verification — correctness, not just equivalence-to-C.

Byte-exact differential verification proves "behaves like this C" — the right floor
for MIGRATION, but it inherits the C's bugs and conforms to the C, not the spec. This
adds the layer that gives CORRECTNESS and the freedom to improve on the C:

  kat_verify        — verify against STANDARD known-answer vectors (FIPS KATs, RFC test
                      vectors). Independent of the C: if the C deviates from the spec,
                      byte-exact copies the bug; KATs catch it. Verifies *correct*.

  property_verify   — verify INVARIANTS that hold beyond the sampled inputs: a codec
                      roundtrips (decode(encode(x))==x), a transform is idempotent, a
                      sort produces a sorted permutation. Semantic correctness, not
                      sample-matching.

  divergence_verdict — when the Rust differs from the C, decide WHICH is wrong: if the
                      C exhibits undefined behavior on the diverging input, the C is
                      buggy and the Rust is allowed (indeed correct) to differ.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_test(crate_dir: Path, lib_extra: str, env) -> bool:
    """Append a test module to a crate's lib.rs, run `cargo test`, restore the lib."""
    lib = Path(crate_dir) / "src" / "lib.rs"
    original = lib.read_text(encoding="utf-8")
    try:
        lib.write_text(original + "\n" + lib_extra, encoding="utf-8")
        o = subprocess.run(["cargo", "test", "--lib"], cwd=str(crate_dir),
                           capture_output=True, text=True, env=env)
        return "test result: ok" in (o.stdout + o.stderr)
    finally:
        lib.write_text(original, encoding="utf-8")


def kat_test_source(call_expr: str, kats: list[tuple], name: str = "kat") -> str:
    """A #[test] asserting `call_expr` matches each known-answer vector. `call_expr`
    uses `input` (the KAT input); each kat is (input_literal, expected_literal)."""
    cases = ",\n        ".join("(%s, %s)" % (i, e) for i, e in kats)
    return ("#[cfg(test)]\nmod %s_spec {\n    use super::*;\n    #[test]\n    fn %s() {\n"
            "        let kats: &[(&[u8], &[u8])] = &[\n        %s];\n"
            "        for (input, expected) in kats {\n"
            "            assert_eq!(%s.as_slice(), *expected, \"KAT mismatch\");\n"
            "        }\n    }\n}\n" % (name, name, cases, call_expr))


def kat_verify(crate_dir: Path, call_expr: str, kats: list[tuple], env) -> bool:
    """True iff the fn matches the STANDARD vectors — independent of the C."""
    return _run_test(Path(crate_dir), kat_test_source(call_expr, kats), env)


def property_verify(crate_dir: Path, property_test_rust: str, env) -> bool:
    """Run a property test (an invariant checked over many generated inputs)."""
    return _run_test(Path(crate_dir), property_test_rust, env)


def roundtrip_property(encode: str, decode: str, name: str = "roundtrip", n: int = 256) -> str:
    """decode(encode(x)) == x for pseudo-random x -- holds beyond the differential samples."""
    return ("#[cfg(test)]\nmod %s_prop {\n    use super::*;\n    #[test]\n    fn %s() {\n"
            "        let mut x: u32 = 0x9e3779b9;\n"
            "        for len in 0..%d {\n"
            "            let mut v = Vec::new();\n"
            "            for _ in 0..len { x = x.wrapping_mul(1103515245).wrapping_add(12345); v.push((x>>16) as u8); }\n"
            "            assert_eq!(%s(&%s(&v)), v, \"roundtrip broken at len {}\", len);\n"
            "        }\n    }\n}\n" % (name, name, n, decode, encode))


def divergence_verdict(c_source: str, driver_main: str, diverging_inputs: list[bytes],
                       work: Path, gcc: str = "gcc") -> str:
    """When Rust != C on some input, decide which is wrong. If the C exhibits UB on the
    diverging input, the verdict is 'c-buggy' (the Rust is allowed to differ / is the
    correct one); else 'inconclusive' (treat the Rust as the regression)."""
    from alchemist.autonomy.sanitizer import sanitizer_check
    findings = sanitizer_check(c_source, driver_main, diverging_inputs, work, gcc)
    real = [f for f in findings if not f.startswith("<")]
    return "c-buggy" if real else "inconclusive"
