# C2 — Lua whole-interpreter oracle

The Lua core (~600 mutually-recursive functions over `lua_State`/`TValue`/`Table`)
**cannot be verified per-function** — there is no clean byte-in/byte-out interface
and you can't FFI-marshal a `lua_State`. So the core is verified **end-to-end**:

> Run an identical script corpus through reference **C-lua** and the translated
> **Rust-lua**, and require **byte-identical observable behavior** (stdout + exit
> status + error text). Byte-exact-or-refused, at the interpreter level.

This is the verification substrate for all of Phase C — every core module (C3–C5)
is validated against this oracle as it lands, and A2/A3 (the 100% gate) run the
official Lua 5.4 test suite through it.

## Usage
```
oracle.sh build-ref <lua_src_dir>   # compile reference C-lua -> ./lua_ref
oracle.sh capture                   # run corpus through lua_ref -> expected/  (golden)
oracle.sh diff <rust_lua_binary>    # run corpus through Rust-lua, diff vs golden — THE GATE
```

## What the corpus exercises (and why it's byte-exact-hard)
| Script | Covers | Byte-exact traps |
|--------|--------|------------------|
| `01_arith` | int/float arith, bitwise, coercion | integer-vs-float subtype (`2^10`→`1024.0`), overflow wrap, `inf`/`nan`, `%.14g` |
| `02_strings` | format, patterns, sub/find/gsub | `string.format` printf parity, Lua-pattern engine, `%q` quoting |
| `03_tables` | array/hash, sort/insert/concat, pairs | hash iteration order, length op, stable sort |
| `04_control_fn` | closures, varargs, recursion, goto | upvalue capture, multi-return arity, `goto`/labels |
| `05_meta_coro_err` | metatables/OO, coroutines, pcall | metamethod dispatch, coroutine yield/resume, error object identity |

`expected/*.out` are the golden reference outputs (stdout+stderr, terminated by
`exit=N`) captured from C-lua 5.4.7. The Rust-lua build must reproduce them
byte-for-byte to pass the gate.
