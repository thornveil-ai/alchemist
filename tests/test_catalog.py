"""Tests for the C-idiom pattern catalog (WS6).

These lock the seed patterns from the zlib translation so future edits can't
silently drop guidance the model relies on. See docs/PATH_TO_AUTONOMY.md.
"""

from alchemist.catalog import (
    IDIOMS,
    CATALOG_VERSION,
    match_idioms,
    render_prompt_hints,
    idiom_by_id,
)


def test_catalog_nonempty_and_versioned():
    assert CATALOG_VERSION
    assert len(IDIOMS) >= 10
    # ids are unique + kebab-case
    ids = [i.id for i in IDIOMS]
    assert len(ids) == len(set(ids))
    for i in IDIOMS:
        assert i.id.islower() and " " not in i.id
        assert i.name and i.rust_model and i.rationale and i.example
        assert i.c_signals  # every idiom must be detectable


def test_inflate_state_machine_matches_expected_idioms():
    # A representative slice of inflate()'s decode loop.
    c = """
    for (;;) switch (state->mode) {
    case LEN:
        NEEDBITS(15);
        here = state->lencode[BITS(state->lenbits)];
        if (here.op) goto inf_leave;
        hold += (unsigned long)(*next++) << bits;
        state->length = (unsigned)here.val;
    }
    """
    hits = {i.id for i in match_idioms(c)}
    assert "goto-to-labeled-loop" in hits
    assert "bit-accumulator-macros" in hits
    assert "advancing-input-pointer" in hits


def test_deflate_tree_aliasing_and_union_match():
    c = """
    static void build_tree(deflate_state *s, tree_desc *desc) {
        ct_data *tree = desc->dyn_tree;
        tree[n].Freq = tree[m].fc.freq;
        s->opt_len += (ulg)f * (unsigned)(tree[n].dl.len + xbits);
    }
    """
    hits = {i.id for i in match_idioms(c)}
    assert "pointer-aliasing-same-memory" in hits
    assert "union-fields" in hits


def test_shift_overflow_signal():
    c = "for (n = 0; n < 32; n++) block_mask |= (unsigned long)(1 << n);"
    hits = {i.id for i in match_idioms(c)}
    assert "shift-width-overflow" in hits


def test_no_false_negative_on_plain_arithmetic():
    # A function with no gnarly idioms should match few/none of the risky ones.
    c = "unsigned add(unsigned a, unsigned b) { return a + b; }"
    hits = {i.id for i in match_idioms(c)}
    assert "goto-to-labeled-loop" not in hits
    assert "pointer-aliasing-same-memory" not in hits


def test_render_prompt_hints_shape():
    hits = match_idioms("goto done; NEEDBITS(3);")
    block = render_prompt_hints(hits)
    assert block  # non-empty
    assert CATALOG_VERSION in block
    # every rendered idiom shows its id and the Do/When guidance
    for i in hits:
        assert f"[{i.id}]" in block
    assert "**Do:**" in block and "**When:**" in block


def test_render_empty_when_no_matches():
    assert render_prompt_hints([]) == ""


def test_idiom_by_id_roundtrip():
    for i in IDIOMS:
        assert idiom_by_id(i.id) is i
    assert idiom_by_id("does-not-exist") is None
