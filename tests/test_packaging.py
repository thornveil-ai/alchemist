"""Item 4 — crash-proof pipeline + signed project manifest + cargo workspace."""

from pathlib import Path

from alchemist.autonomy.packaging import (
    FunctionOutcome, ProjectManifest, translate_safely, emit_workspace,
)


def test_translate_safely_turns_crash_into_refused():
    def boom():
        raise ValueError("no-oracle: unsupported shape")
    out = translate_safely("weird_fn", boom)
    assert out.verdict == "refused" and out.function == "weird_fn"
    assert "no-oracle" in out.reason               # reason preserved, no exception escaped


def test_translate_safely_passes_success_through():
    out = translate_safely("f", lambda: FunctionOutcome("f", "verified", sha256="abc"))
    assert out.verdict == "verified" and out.sha256 == "abc"


def test_manifest_summary_digest_and_attest():
    m = ProjectManifest("mylib")
    m.add(FunctionOutcome("a", "verified", sha256="1"))
    m.add(FunctionOutcome("b", "verified", sha256="2"))
    m.add(FunctionOutcome("c", "refused", reason="oos: uses I/O"))
    s = m.summary()
    assert s["total"] == 3 and s["by_verdict"]["verified"] == 2
    assert s["verified_fraction"] == round(2 / 3, 3)
    assert len(m.digest()) == 64 and m.digest() == m.digest()   # stable content hash
    att = m.attest()
    assert att["summary"]["total"] == 3 and "signature" in att and att["sha256"] == m.digest()


def test_manifest_digest_is_order_independent():
    m1, m2 = ProjectManifest("p"), ProjectManifest("p")
    m1.add(FunctionOutcome("a", "verified")); m1.add(FunctionOutcome("b", "partial"))
    m2.add(FunctionOutcome("b", "partial")); m2.add(FunctionOutcome("a", "verified"))
    assert m1.digest() == m2.digest()             # canonicalized by function name


def test_emit_workspace(tmp_path):
    toml = emit_workspace(tmp_path / "ws", [Path("x/crate_a"), Path("y/crate_b")])
    txt = toml.read_text()
    assert "[workspace]" in txt and '"crate_a"' in txt and '"crate_b"' in txt
