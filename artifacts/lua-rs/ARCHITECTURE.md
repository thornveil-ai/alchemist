# Rust-Lua — architecture decisions (Phase C)

Byte-exact-or-refused reimplementation of Lua 5.4.7 in safe Rust, verified
end-to-end against reference C-lua via the C2 oracle (`subjects/lua/oracle/`).

## ADR-1: Value representation — `TValue` (C tagged union) → Rust enum
C: `struct TValue { Value value_; lu_byte tt_; }` where `Value` is a union.
Rust: a `#[derive(Clone)]` enum `LuaValue`. This is the safe, idiomatic mapping —
the tag becomes the discriminant, the union becomes the payload. **Observably
equivalent**, and the compiler enforces that every access matches the tag (the
class of bug — reading the wrong union member — becomes impossible).

```
Nil | Boolean(bool) | Integer(i64) | Number(f64)
| String(LuaStr) | Table(LuaTable) | Function(LuaFn) | UserData(..) | Thread(..)
```
Lua's subtype distinction (`LUA_VNUMINT` vs `LUA_VNUMFLT`) is preserved as
`Integer` vs `Number` — this is observable (`math.type`, `//`, `tostring`,
`3==3.0` but `math.type` differs) and MUST be exact.

## ADR-2: GC — mark-sweep → `Rc<RefCell<..>>` (reference counting)
Lua uses an incremental mark-and-sweep collector over `GCObject` lists. Rust
uses `Rc<RefCell<..>>` for shared mutable GC objects (strings, tables, closures).

- **Observably equivalent** for the vast majority of programs — object identity,
  aliasing, mutation-through-shared-references all hold.
- **NOT byte-exact** for programs that *observe the collector*: `collectgarbage`
  byte counts, `__gc` finalizer timing, weak-table (`__mode`) reclamation, cyclic
  garbage (Rc leaks cycles). These are explicitly **out of the byte-exact core**
  in the first cut and are REFUSED (honest) rather than faked. A later pass can
  replace `Rc` with an arena + mark-sweep for full GC-observable exactness.

## ADR-3: Numbers — the byte-exact-hard surface
`lua_Integer` = `i64` (wrapping on overflow, exactly like C's two's-complement
`maxinteger+1 == mininteger`). `lua_Number` = `f64`. Formatting reproduces
`lua_number2str` = `"%.14g"` + append `.0` when the result reads as an integer
(so `1024.0`, not `1024`). `inf`/`-inf`/`nan` match C's `printf`. `//` is floor
division, `%` is `a - floor(a/b)*b`, `^` is always float. **Verified against the
oracle** in `lua-value` tests.

## ADR-4: Strings — interned byte strings
Lua strings are immutable byte sequences (not UTF-8) with interning for short
strings (via `luaS_hash`, already conquered). Rust: `LuaStr = Rc<[u8]>` with an
intern table. Hashing/equality byte-exact to `luaS_hash`.

## Build / verify
Cargo workspace under this dir. Each core module (C3–C5) lands as a crate,
verified against C2. The 100% gate (A2/A3) runs the official Lua 5.4 test suite
through the assembled `lua` binary and requires byte-identical output.

## Honest scope of "byte-exact"
In scope: all pure computation, control flow, closures, metatables, string lib
(format/patterns), table ops, numeric semantics, error messages, bytecode.
Out of first cut (refused, not faked): GC-observable behavior (see ADR-2),
`os`/`io` platform-dependent output, `os.time`/random seeding.
