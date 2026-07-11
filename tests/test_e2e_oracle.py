"""The whole-program differential gate: byte-exact-or-refused at program level."""
import sys
from pathlib import Path

from alchemist.verifier.e2e_oracle import (
    E2EOracleSpec, run_e2e_oracle, spec_from_corpus_dir,
)


def _corpus(tmp_path: Path, n: int = 3) -> list[Path]:
    files = []
    for i in range(n):
        p = tmp_path / f"in{i}.txt"
        p.write_text(f"hello {i}\n")
        files.append(p)
    return files


def test_identical_programs_pass(tmp_path):
    # Reference and candidate both echo the file's contents -> byte-identical.
    cat = [sys.executable, "-c",
           "import sys;sys.stdout.write(open(sys.argv[1]).read())", "{input}"]
    spec = E2EOracleSpec("cat", reference_cmd=cat, candidate_cmd=cat,
                         corpus=_corpus(tmp_path))
    res = run_e2e_oracle(spec)
    assert res.passed
    assert res.npass == res.total == 3


def test_divergent_candidate_fails_with_diff(tmp_path):
    ref = [sys.executable, "-c",
           "import sys;sys.stdout.write(open(sys.argv[1]).read())", "{input}"]
    # Candidate uppercases -> diverges on every input.
    cand = [sys.executable, "-c",
            "import sys;sys.stdout.write(open(sys.argv[1]).read().upper())", "{input}"]
    spec = E2EOracleSpec("cat", reference_cmd=ref, candidate_cmd=cand,
                         corpus=_corpus(tmp_path))
    res = run_e2e_oracle(spec)
    assert not res.passed
    assert res.npass == 0
    # The failure names the first differing line — actionable feedback.
    assert any("line 1" in c.detail for c in res.cases if not c.passed)


def test_exit_status_mismatch_is_caught(tmp_path):
    ok = [sys.executable, "-c", "print('x')"]
    fail = [sys.executable, "-c", "print('x'); import sys; sys.exit(1)"]
    spec = E2EOracleSpec("rc", reference_cmd=ok, candidate_cmd=fail,
                         corpus=[tmp_path / "any"])
    (tmp_path / "any").write_text("")
    res = run_e2e_oracle(spec)
    assert not res.passed
    assert any("exit" in c.detail for c in res.cases)


def test_empty_corpus_does_not_falsely_pass(tmp_path):
    # No inputs must NOT read as success (that would be a false green).
    spec = E2EOracleSpec("empty", reference_cmd=["true"], candidate_cmd=["true"],
                         corpus=[])
    assert not run_e2e_oracle(spec).passed


def test_corpus_dir_helper(tmp_path):
    _corpus(tmp_path, 2)
    cat = sys.executable  # not a real cat, but both sides identical -> pass
    spec = spec_from_corpus_dir(
        "d",
        reference_bin=cat, candidate_bin=cat,
        corpus_dir=tmp_path, glob="*.txt",
        reference_cmd_override=None,
    ) if False else spec_from_corpus_dir(
        "d", reference_bin=cat, candidate_bin=cat, corpus_dir=tmp_path, glob="*.txt")
    # Both invoke the same interpreter on the same file -> identical.
    spec.reference_cmd = [sys.executable, "-c", "import sys;print(open(sys.argv[1]).read())", "{input}"]
    spec.candidate_cmd = list(spec.reference_cmd)
    res = run_e2e_oracle(spec)
    assert res.total == 2 and res.passed
