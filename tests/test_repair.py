"""Tests for WS4 autonomous diagnose-and-repair (docs/PATH_TO_AUTONOMY.md).

Covers the four parts: discrepancy extraction (bytes + state), fault
localization, guidance rendering, and the bounded repair loop — including an
end-to-end simulation that reproduces a zlib-style integration bug and repairs
it with no human in the loop.
"""

from alchemist.autonomy.repair import (
    describe_bytes,
    describe_state,
    localize,
    render_repair_guidance,
    parse_rust_diff_failures,
    RepairLoop,
    Suspect,
)


# --- cargo-output bridge ---------------------------------------------------
_CARGO_FAIL = """
running 3 tests
test test_deflate_l6_0 ... ok
test test_deflate_l6_3 ... FAILED
test test_inflate_rt_1 ... ok

failures:

---- test_deflate_l6_3 stdout ----
thread 'test_deflate_l6_3' panicked at tests/differential.rs:42:5:
assertion `left == right` failed: deflate L6 case 3
  left: [26, 43, 0, 77]
 right: [26, 43, 60, 77]
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

failures:
    test_deflate_l6_3

test result: FAILED. 2 passed; 1 failed; 0 ignored
"""


def test_parse_cargo_diff_failure_extracts_bytes_and_message():
    fails = parse_rust_diff_failures(_CARGO_FAIL)
    assert len(fails) == 1
    f = fails[0]
    assert f.test == "test_deflate_l6_3"
    assert f.message == "deflate L6 case 3"
    # right is the reference (C) -> expected; left is Rust -> actual
    assert f.discrepancy.kind == "value"
    assert f.discrepancy.location == "byte 2"
    assert f.discrepancy.expected == "0x3c"  # 60 = reference
    assert f.discrepancy.actual == "0x00"    # 0  = Rust impl


def test_parse_cargo_no_failures_returns_empty():
    ok = "running 2 tests\ntest a ... ok\ntest b ... ok\n\ntest result: ok. 2 passed;"
    assert parse_rust_diff_failures(ok) == []


def test_parse_cargo_handles_length_divergence():
    out = (
        "---- test_x stdout ----\n"
        "thread 'x' panicked at t.rs:1:1:\n"
        "assertion `left == right` failed\n"
        "  left: [1, 2, 3]\n"
        " right: [1, 2, 3, 4, 5]\n"
    )
    fails = parse_rust_diff_failures(out)
    assert len(fails) == 1
    assert fails[0].discrepancy.kind == "length"


# --- discrepancy extraction ------------------------------------------------
def test_describe_bytes_equal():
    d = describe_bytes(b"abc", b"abc")
    assert d.is_equal and d.summary == "byte-identical"


def test_describe_bytes_value_divergence():
    # like the scan_tree bug: a byte in the middle of the block is wrong
    exp = bytes([0x1a, 0x2b, 0x3c, 0x4d])
    act = bytes([0x1a, 0x2b, 0x00, 0x4d])
    d = describe_bytes(exp, act)
    assert d.kind == "value"
    assert d.location == "byte 2"
    assert d.expected == "0x3c" and d.actual == "0x00"
    assert "byte 2" in d.summary
    assert "first divergence at byte 2" in d.context


def test_describe_bytes_length_divergence():
    d = describe_bytes(b"abcdef", b"abc")
    assert d.kind == "length"
    assert "truncated" in d.summary
    assert "expected 6, got 3" in d.summary


def test_describe_state_field_divergence():
    # like a stateful-fn effect mismatch
    exp = {"strstart": 262, "lookahead": 3, "match_length": 5}
    act = {"strstart": 261, "lookahead": 3, "match_length": 5}
    d = describe_state(exp, act)
    assert d.kind == "field"
    assert "strstart" in d.location
    assert d.expected == "262" and d.actual == "261"


def test_describe_state_extra_field():
    d = describe_state({"a": 1}, {"a": 1, "b": 2})
    assert d.kind == "missing"
    assert "b" in d.actual


# --- localization ----------------------------------------------------------
def test_localize_prefers_footprint_owner_of_diverged_field():
    d = describe_state({"strstart": 262}, {"strstart": 261})
    footprints = {
        "fill_window": {"strstart", "lookahead", "window"},
        "init_block": {"dyn_ltree", "opt_len"},
        "adler32": {"adler"},
    }
    ranked = localize(d, ["fill_window", "init_block", "adler32"], footprints)
    assert ranked[0].function == "fill_window"
    assert "strstart" in ranked[0].reason


def test_localize_uses_recency_when_no_footprints():
    d = describe_bytes(b"abc", b"abd")
    ranked = localize(d, ["f1", "f2"], effect_footprints={"f1": {"x"}, "f2": {"y"}},
                      recently_changed=["f2"])
    # f2 was recently changed -> should outrank f1 for a value diff
    assert ranked[0].function == "f2"


def test_localize_propagates_to_callers():
    d = describe_state({"dyn_ltree": 1}, {"dyn_ltree": 0})
    footprints = {"build_tree": {"dyn_ltree"}}
    call_graph = {"_tr_flush_block": {"build_tree"}}
    ranked = localize(
        d, ["build_tree", "_tr_flush_block"], footprints, call_graph
    )
    fns = [s.function for s in ranked]
    assert fns[0] == "build_tree"           # prime suspect (owns the field)
    assert "_tr_flush_block" in fns          # caller pulled in as a suspect


# --- guidance --------------------------------------------------------------
def test_render_guidance_has_cause_not_symptom_language():
    d = describe_bytes(bytes([1, 2, 3]), bytes([1, 9, 3]))
    g = render_repair_guidance(d, Suspect("scan_tree", 10.0, "writes bl_tree"))
    assert "do not special-case" in g.lower() or "do not hard-code" in g.lower()
    assert "scan_tree" in g
    assert "byte 1" in g


def test_render_guidance_empty_when_equal():
    assert render_repair_guidance(describe_bytes(b"x", b"x")) == ""


# --- the repair loop (end-to-end simulation) -------------------------------
def test_repair_loop_fixes_a_zlib_style_bug_autonomously():
    """Simulate: compressed output diverges; the fault is in scan_tree; the loop
    localizes to it, re-injects, and the oracle then passes — no human."""
    state = {"scan_tree_fixed": False}
    good = bytes([0x1a, 0x2b, 0x3c, 0x4d])
    bad = bytes([0x1a, 0x2b, 0x00, 0x4d])  # scan_tree emits a wrong byte

    def run_oracle():
        actual = good if state["scan_tree_fixed"] else bad
        return (actual == good, good, actual)

    reinjected: list[str] = []

    def reinject(fn, guidance):
        reinjected.append(fn)
        if fn == "scan_tree":
            state["scan_tree_fixed"] = True
        return True  # body changed

    def revert(fn):
        if fn == "scan_tree":
            state["scan_tree_fixed"] = False

    loop = RepairLoop(
        run_oracle=run_oracle,
        reinject=reinject,
        revert=revert,
        candidates=["init_block", "scan_tree", "deflate"],
        effect_footprints={
            "init_block": {"dyn_ltree"},
            "scan_tree": {"bl_tree", "compressed_len"},
            "deflate": {"pending", "next_out"},
        },
        max_attempts=4,
    )
    result = loop.run()
    assert result.ok
    assert result.function == "scan_tree"
    assert "scan_tree" in reinjected


def test_repair_loop_refuses_rather_than_fake_green():
    """If nothing fixes it, the loop REFUSES — never claims a false success."""
    good = b"\x01\x02\x03"
    bad = b"\x01\x09\x03"

    def run_oracle():
        return (False, good, bad)  # never passes

    def reinject(fn, guidance):
        return True  # pretends to change, but oracle still fails

    reverted: list[str] = []

    loop = RepairLoop(
        run_oracle=run_oracle,
        reinject=reinject,
        revert=lambda fn: reverted.append(fn),
        candidates=["a", "b"],
        effect_footprints={"a": {"x"}, "b": {"y"}},
        max_attempts=3,
    )
    result = loop.run()
    assert result.status == "refused"
    assert not result.ok
    # every non-helping change was reverted -> no drift
    assert set(reverted) == {"a", "b"}


def test_repair_loop_short_circuits_when_already_green():
    def run_oracle():
        return (True, b"", b"")
    loop = RepairLoop(run_oracle, lambda *a: True, lambda *a: None, candidates=[])
    r = loop.run()
    assert r.ok and r.attempts == 0


def test_repair_loop_accepts_discrepancy_shaped_oracle():
    from alchemist.autonomy.repair import Discrepancy
    calls = {"n": 0}

    def run_oracle():
        calls["n"] += 1
        if calls["n"] == 1:
            return (False, Discrepancy("field", "field 'strstart'", "262", "261",
                                       summary="strstart off by one"))
        return (True, None)

    loop = RepairLoop(
        run_oracle=run_oracle,
        reinject=lambda fn, g: True,
        revert=lambda fn: None,
        candidates=["fill_window"],
        effect_footprints={"fill_window": {"strstart"}},
    )
    r = loop.run()
    assert r.ok and r.function == "fill_window"


# --- the pipeline wiring adapter (with real files) -------------------------
def test_make_repair_loop_wires_cargo_and_snapshots_files(tmp_path):
    from alchemist.autonomy.repair import make_repair_loop

    # A fake Rust source file for the buggy function.
    src = tmp_path / "trees.rs"
    src.write_text("fn scan_tree() { /* buggy */ }\n", encoding="utf-8")

    fail_output = (
        "---- test_deflate stdout ----\n"
        "thread 'x' panicked at t.rs:1:1:\n"
        "assertion `left == right` failed\n"
        "  left: [1, 2, 0, 4]\n"
        " right: [1, 2, 3, 4]\n"
    )
    state = {"fixed": False}

    def run_differential():
        return (state["fixed"], "" if state["fixed"] else fail_output)

    def refill(fn, guidance):
        # simulate the model rewriting the body; record that guidance was byte-precise
        assert "byte 2" in guidance
        if fn == "scan_tree":
            src.write_text("fn scan_tree() { /* fixed */ }\n", encoding="utf-8")
            state["fixed"] = True
        return True

    loop = make_repair_loop(
        run_differential=run_differential,
        refill=refill,
        workspace_files={"scan_tree": src},
        candidates=["init_block", "scan_tree"],
        effect_footprints={"init_block": {"dyn_ltree"}, "scan_tree": {"bl_tree"}},
    )
    result = loop.run()
    assert result.ok
    assert result.function == "scan_tree"
    assert "fixed" in src.read_text(encoding="utf-8")


def test_make_repair_loop_reverts_file_on_non_helping_change(tmp_path):
    from alchemist.autonomy.repair import make_repair_loop

    src = tmp_path / "a.rs"
    original = "fn a() { original }\n"
    src.write_text(original, encoding="utf-8")

    def run_differential():
        return (False, "---- t stdout ----\nassertion `left == right` failed\n"
                       "  left: [0]\n right: [1]\n")  # never passes

    def refill(fn, guidance):
        src.write_text("fn a() { mangled }\n", encoding="utf-8")
        return True

    loop = make_repair_loop(
        run_differential=run_differential,
        refill=refill,
        workspace_files={"a": src},
        candidates=["a"],
        effect_footprints={"a": {"x"}},
        max_attempts=2,
    )
    result = loop.run()
    assert result.status == "refused"
    # the non-helping change was reverted -> file restored to original
    assert src.read_text(encoding="utf-8") == original
