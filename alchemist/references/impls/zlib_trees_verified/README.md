# zlib trees — verified Rust implementations (Phase 2)

Model-written (Gemma 4 31B Dense), byte-exact against the compiled-C
`libzlib_state_shim` differential oracle. Snapshot of the coherent
`zlib-trees` crate after Phase 2 (state-mutator oracle for the Huffman
tree machinery). Kept git-tracked because the generated workspace under
`subjects/zlib/.alchemist/` is untracked and a skeleton regen would
otherwise discard these.

## Verified (10/10 differential vectors each, in the real workspace)

Tree-builders:
- `pqdownheap` — heap sift (the `smaller` tie-break must use `<=` in both
  comparisons, matching zlib; a strict `<` produced a valid-but-different
  tree that `build_tree` caught)
- `gen_codes` — canonical Huffman code assignment (RFC 1951 reflected codes)
- `gen_bitlen` — optimal bit lengths + overflow redistribution (C unsigned
  wrapping; the recompute `continue` must NOT decrement the leaf counter)
- `build_tree` — full Huffman construction; the keystone (transitively
  exercises pqdownheap + gen_bitlen + gen_codes)
- `build_bl_tree` — scans the L/D trees, builds the bit-length tree; uses
  `std::mem::take` to reconcile zlib aliasing `bl_desc.dyn_tree` to
  `s.bl_tree` that the coherent types separate; returns `max_blindex`

Mutators (state shim oracle): `bi_flush`, `bi_windup`, `send_bits`,
`_tr_init`, `init_block`, `_tr_align`, `detect_data_type`, `bi_reverse`.
`tr_static_init` is a no-op (static tables are compile-time consts, see
`static_tables.rs`).

## Not yet done (the moonshot)

`compress_block`, `send_all_trees` — bitstream emission.

## How they were produced

Injected the C source (+ expanded macros) into the model, iterated on the
differential oracle's exact discrepancies (unsigned-wrap panics, tie-break
`<` vs `<=`, counter semantics). Every green is byte-exact vs compiled zlib;
no green was ever asserted without the oracle agreeing.
