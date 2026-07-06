"""Tests for WS2 type-model inference (docs/PATH_TO_AUTONOMY.md).

Locks the mechanical classification decisions and the review flags. Grounded in
the zlib coherent model the inference reproduces.
"""

from alchemist.autonomy.type_infer import infer_struct_model, classify_field


def _model(src, name, known=None):
    return infer_struct_model(src, name, known_structs=known or set())


def test_pointer_scalar_becomes_owned_vec():
    m = _model("typedef struct { Bytef *window; Posf *prev; } S;", "S")
    by = {f.name: f for f in m.fields}
    assert by["window"].rust_type == "Vec<u8>" and by["window"].kind == "buffer"
    assert by["prev"].rust_type == "Vec<u16>"


def test_fixed_array_becomes_owned_vec():
    m = _model("typedef struct { int heap[600]; ush bl_count[16]; } S;", "S")
    by = {f.name: f for f in m.fields}
    assert by["heap"].rust_type == "Vec<i32>" and by["heap"].kind == "array"
    assert by["bl_count"].rust_type == "Vec<u16>"


def test_index_like_scalars_become_usize():
    m = _model("typedef struct { uInt strstart; uInt lookahead; uInt w_size; int level; } S;", "S")
    by = {f.name: f for f in m.fields}
    assert by["strstart"].rust_type == "usize"
    assert by["lookahead"].rust_type == "usize"
    assert by["w_size"].rust_type == "usize"
    # a plain flag/level is NOT an index -> stays i32
    assert by["level"].rust_type == "i32"


def test_plain_scalars_map_correctly():
    m = _model("typedef struct { int a; ush b; unsigned long c; unsigned char d; } S;", "S")
    by = {f.name: f for f in m.fields}
    assert by["a"].rust_type == "i32"
    assert by["b"].rust_type == "u16"
    assert by["c"].rust_type == "u64"
    assert by["d"].rust_type == "u8"


def test_back_pointer_flagged_for_review():
    m = _model("typedef struct { z_streamp strm; int x; } S;", "S")
    by = {f.name: f for f in m.fields}
    assert by["strm"].kind == "back_ptr"
    assert by["strm"].review is True
    assert by["x"].review is False


def test_buffer_ptr_len_pair_detected():
    m = _model("typedef struct { Bytef *window; ulg window_size; } S;", "S")
    assert ("window", "window_size") in m.buffer_pairs


def test_sub_struct_owned_by_value():
    m = _model("typedef struct { struct tree_desc_s l_desc; } S;", "S",
               known={"tree_desc_s"})
    by = {f.name: f for f in m.fields}
    assert by["l_desc"].kind == "sub_struct"
    assert by["l_desc"].rust_type == "TreeDesc"


def test_review_fields_surface_not_silently_guessed():
    m = _model("typedef struct { z_streamp strm; void *opaque; int n; } S;", "S")
    review = {f.name for f in m.review_fields()}
    assert "strm" in review        # back-ref direction
    assert "opaque" in review       # opaque pointer
    assert "n" not in review        # plain scalar is decided, not flagged
