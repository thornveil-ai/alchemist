"""Pillar 1 — effect-footprint oracle: detect globals + emit the footprint model.

The end-to-end differential (C footprint == correct-Rust footprint, wrong-Rust
diverges) is proven on the box with gcc+rustc; here we lock the detection/emission.
"""

from alchemist.autonomy.effect_oracle import (
    detect_globals, emit_c_footprint_dump, emit_rust_state_struct,
)

PRNG = """
static unsigned long _seed = 1;
static int _count;
unsigned char _table[256];
void prng_seed(unsigned long s) { _seed = s; _count = 0; }
unsigned long prng_next(void) { _seed = _seed * 6364136223846793005UL + 1; _count++; return _seed >> 33; }
"""


def test_detect_globals_finds_file_scope_state():
    gs = {g.name: g for g in detect_globals(PRNG)}
    assert set(gs) == {"_seed", "_count", "_table"}
    assert gs["_seed"].rust_type == "u64" and gs["_seed"].init == "1"
    assert gs["_count"].rust_type == "i32"
    assert gs["_table"].rust_type == "u8" and gs["_table"].array_len == 256


def test_detect_globals_skips_prototypes_and_consts():
    # function prototypes and const tables are not mutable state
    src = "const int LIMIT = 5; int helper(int x, int y); static int counter;"
    names = {g.name for g in detect_globals(src)}
    assert names == {"counter"}


def test_c_footprint_dump_scalars_and_arrays():
    gs = detect_globals(PRNG)
    dump = emit_c_footprint_dump(gs)
    assert "fwrite(&_seed, sizeof(_seed), 1, stdout);" in dump   # scalar: address
    assert "fwrite(_table, sizeof(_table), 1, stdout);" in dump  # array: bare name


def test_rust_state_struct_makes_globals_explicit():
    rs = emit_rust_state_struct(detect_globals(PRNG))
    assert "pub struct GlobalState" in rs
    assert "pub _seed: u64," in rs
    assert "pub _table: [u8; 256]," in rs
    assert "_seed: 1" in rs                       # C initializer preserved
    assert "fn footprint(&self) -> Vec<u8>" in rs  # matching footprint dumper
    assert "to_ne_bytes()" in rs                   # native-endian, matches C fwrite
