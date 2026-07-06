"""Automated diagnosis loop — control flow (fake LLM, no model needed).

The end-to-end 'crack a real bug autonomously' proof runs on the box; here we lock
that the loop applies fixes, honours run_test as ground truth, and never claims
success without a passing test.
"""

from alchemist.autonomy.diagnose import diagnose_and_fix, Diagnosis


class _Resp:
    def __init__(self, d):
        self.structured = d


class _FakeLLM:
    """Returns a scripted diagnosis per call."""
    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.calls = 0

    def call_structured(self, **kw):
        d = self.scripts[min(self.calls, len(self.scripts) - 1)]
        self.calls += 1
        return _Resp(d)


def test_fix_first_round():
    applied = []
    llm = _FakeLLM([{"root_cause": "off by one", "general_rule": "increment at end",
                     "fixed_function": "pub fn f() {}"}])
    diag = diagnose_and_fix(
        "c", "wrong", "expected 1 got 2", llm,
        apply_fixed=applied.append,
        run_test=lambda: (True, ""),
    )
    assert diag.fixed and diag.rounds == 1
    assert applied == ["pub fn f() {}"]
    assert diag.general_rule == "increment at end"


def test_iterates_then_fixes():
    results = iter([(False, "still wrong"), (True, "")])
    llm = _FakeLLM([
        {"root_cause": "a", "general_rule": "r1", "fixed_function": "pub fn f() { v1 }"},
        {"root_cause": "b", "general_rule": "r2", "fixed_function": "pub fn f() { v2 }"},
    ])
    diag = diagnose_and_fix("c", "wrong", "fail", llm,
                            apply_fixed=lambda code: None,
                            run_test=lambda: next(results),
                            max_rounds=3)
    assert diag.fixed and diag.rounds == 2
    assert llm.calls == 2


def test_refuses_false_success():
    # run_test never passes -> must report fixed=False, never green-wash
    llm = _FakeLLM([{"root_cause": "x", "general_rule": "r", "fixed_function": "pub fn f() {}"}])
    diag = diagnose_and_fix("c", "wrong", "fail", llm,
                            apply_fixed=lambda code: None,
                            run_test=lambda: (False, "nope"),
                            max_rounds=3)
    assert diag.fixed is False
    assert diag.rounds == 3


def test_reverts_fix_that_makes_it_worse():
    # a fix that INTRODUCES more errors (e.g. invents a helper) must be reverted
    applied = []
    llm = _FakeLLM([{"root_cause": "x", "general_rule": "r",
                     "fixed_function": "pub fn f() { transform_internal() }"}])
    diag = diagnose_and_fix(
        "c", "pub fn f() {}", "error[E0308]", llm,
        apply_fixed=applied.append,
        run_test=lambda: (False, "error[E0425]: cannot find function `transform_internal`\nerror[E0061]"),
        max_rounds=3)
    assert diag.fixed is False
    assert applied[-1] == "pub fn f() {}"  # reverted to the original, not left broken


def test_empty_fix_stops():
    llm = _FakeLLM([{"root_cause": "x", "general_rule": "r", "fixed_function": ""}])
    diag = diagnose_and_fix("c", "wrong", "fail", llm,
                            apply_fixed=lambda code: None,
                            run_test=lambda: (False, "nope"))
    assert diag.fixed is False
