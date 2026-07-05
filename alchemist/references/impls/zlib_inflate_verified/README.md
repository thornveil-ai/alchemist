# zlib inflate — verified Rust implementations (Phase 3)

Model-written (Gemma 4 31B), byte-exact against the compiled-C inflate shim
differential oracle. Kept git-tracked because the generated workspace is
untracked.

## Verified (9/9 differential vectors, isolated crate)

- `inflate_table` (inftrees.c, 266 lines) — canonical-Huffman decode-table
  construction with root + sub-tables. The single hardest inflate function
  besides the driver. The C's advancing `code **table` pointer is remodeled
  into offset-indexing on a flat `&mut [CodeEntry]` slice (sub-table entries
  store `val = next_offset`). Validated across LENS/DISTS/CODES types with
  valid complete Huffman-length inputs generated via the deflate shim's
  build_tree. Landed one compile-iteration (array-ref → slice types).

Oracle: `shim_run_inflate_table` in `references/shims/zlib/zlib_inflate_shim.c`.

## Not yet done

`inflate_fast`, the `inflate()` driver, and the inflate* APIs — need
stream/window-snapshot oracles.

NOTE: landing into the workspace is currently blocked by pre-existing regen
damage in the zlib-checksum crate (`make_crc_table -> CrcTables` undefined),
a dependency — a separate restoration item, not an inflate_table issue.
