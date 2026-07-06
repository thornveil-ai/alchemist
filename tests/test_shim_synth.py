"""Tests for WS1 oracle-shim synthesis (docs/PATH_TO_AUTONOMY.md).

Locks the generator's honesty guarantees: it only claims a shim as reproducible
when its hand-written body is a pure field access / call-through, and the
regenerated body is equivalent.
"""

from alchemist.autonomy.shim_synth import (
    synthesize,
    parse_accessors,
    generate_accessor,
    reproduces,
)


def test_setter_getter_reproduced():
    src = (
        "EXPORT void shim_set_bi_buf(unsigned short v) { g_state.bi_buf = v; }\n"
        "EXPORT unsigned short shim_get_bi_buf(void) { return g_state.bi_buf; }\n"
    )
    accs, _ = parse_accessors(src)
    assert len(accs) == 2
    assert all(reproduces(a) for a in accs)
    gen = generate_accessor(accs[0])
    assert "g_state.bi_buf = v" in gen


def test_cast_is_value_preserving_equivalence():
    # hand-written has a redundant cast to the field type; generator's essence matches
    src = "EXPORT void shim_set_wbits(int v) { g_state.wbits = (unsigned)v; }\n"
    accs, _ = parse_accessors(src)
    assert len(accs) == 1 and reproduces(accs[0])


def test_pointer_target_getter():
    src = "EXPORT unsigned shim_fw_g_strstart(void) { return g_fw_s->strstart; }\n"
    accs, _ = parse_accessors(src)
    assert len(accs) == 1
    assert accs[0].target == "g_fw_s->" and accs[0].field == "strstart"
    assert reproduces(accs[0])


def test_nullary_call_through_runner():
    src = "EXPORT void shim_run_bi_flush(void) { bi_flush(&g_state); }\n"
    accs, _ = parse_accessors(src)
    runs = [a for a in accs if a.kind == "run"]
    assert len(runs) == 1 and runs[0].field == "bi_flush"
    assert reproduces(runs[0])
    assert "bi_flush(&g_state)" in generate_accessor(runs[0])


def test_non_pure_body_not_claimed():
    # a shim with real logic must NOT be classified as a mechanical accessor
    src = (
        "EXPORT void shim_fw_init(int level) {\n"
        "    memset(&g_state, 0, sizeof(g_state));\n"
        "    g_state.level = level; lm_init(&g_state); g_fw_s = &g_state;\n"
        "}\n"
    )
    accs, others = parse_accessors(src)
    assert "shim_fw_init" in others  # falls to 'other', not claimed
    assert all(a.name != "shim_fw_init" for a in accs)


def test_loop_array_copy_generates_matching_loop():
    # element-wise loop over a u16 array must regenerate as the SAME loop (not a
    # memcpy, which would copy bytes not elements).
    src = ("EXPORT void shim_fw_g_head(unsigned short *out, unsigned n)"
           "{ for(unsigned i=0;i<n;i++) out[i]=g_fw_s->head[i]; }\n")
    accs, _ = parse_accessors(src)
    arr = [a for a in accs if a.kind == "arr"]
    assert len(arr) == 1 and reproduces(arr[0])
    assert "for(unsigned i=0;i<n;i++) out[i]=g_fw_s->head[i]" in generate_accessor(arr[0])


def test_memcpy_array_not_confused_with_loop():
    src = ("EXPORT void shim_fw_g_window(unsigned char *out, unsigned n)"
           "{ memcpy(out, g_fw_s->window, n); }\n")
    accs, _ = parse_accessors(src)
    arr = [a for a in accs if a.kind == "arr"]
    assert len(arr) == 1 and reproduces(arr[0])
    assert "memcpy(out, g_fw_s->window, n)" in generate_accessor(arr[0])


def test_synthesize_reports_reproducible_and_others():
    src = (
        "EXPORT void shim_set_level(int v) { g_state.level = v; }\n"
        "EXPORT void shim_run_init_block(void) { init_block(&g_state); }\n"
        "EXPORT void shim_weird(void) { do_a(); do_b(); return; }\n"
    )
    r = synthesize(src)
    names = {a.name for a in r["reproducible"]}
    assert "shim_set_level" in names
    assert "shim_run_init_block" in names
    assert "shim_weird" in r["runner_and_other_shims"]
