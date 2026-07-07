"""Fill quality — best-of-N gating + verified-example retrieval."""

from alchemist.autonomy.fill_quality import (
    best_of_n, VerifiedExampleStore, PersistentExampleStore,
)


def test_best_of_n_returns_first_that_verifies():
    # only candidate #2 is good; verify accepts "good"
    cand, attempts = best_of_n(lambda i: "good" if i == 2 else "bad", lambda c: c == "good", n=5)
    assert cand == "good" and attempts == 3


def test_best_of_n_gives_up_after_n():
    cand, attempts = best_of_n(lambda i: "bad", lambda c: False, n=4)
    assert cand is None and attempts == 4


def test_best_of_n_never_returns_unverified():
    # generate always yields something, but nothing verifies -> None (oracle is law)
    cand, _ = best_of_n(lambda i: "whatever", lambda c: False, n=3)
    assert cand is None


def test_retrieval_ranks_by_idiom_overlap():
    s = VerifiedExampleStore()
    s.add("p = malloc(n); free(p);", "let v = vec![0u8; n];")
    s.add("for (i=0;i<n;i++) acc ^= s[i];", "s.iter().fold(0u8, |a, &b| a ^ b)")
    got = s.retrieve("q = malloc(sz); free(q);", k=1)
    assert got and "malloc" in got[0][0]           # malloc query -> malloc example


def test_retrieval_context_and_empty_on_no_overlap():
    s = VerifiedExampleStore()
    s.add("x <<= 3;", "x <<= 3;")
    ctx = s.as_context("y <<= 1;", k=1)
    assert "verified" in ctx and "<<=" in ctx        # shift query -> shift example in context
    assert s.retrieve("plain_call(a, b, c)") == []   # no shared idioms -> nothing


def test_persistent_store_survives_reload(tmp_path):
    p = tmp_path / "examples.json"
    s = PersistentExampleStore(p)
    s.add("p = malloc(n); free(p);", "let v = vec![0u8; n];")
    # a fresh run reloads what the last run learned
    reloaded = PersistentExampleStore(p)
    got = reloaded.retrieve("q = malloc(sz); free(q);", k=1)
    assert got and "malloc" in got[0][0]           # learned idiom retrieved across runs
