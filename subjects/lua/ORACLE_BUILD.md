# Lua differential-oracle build (proven 2026-07-10)

Individual Lua modules do NOT link standalone (lobject.c references luaS_newlstr,
luaV_*, luai_ctype_, luaT_trybinTM from sibling modules). The differential oracle
must therefore compile the WHOLE library into one shared lib, then each function's
harness FFI-calls its exported symbol — the same pattern zlib used.

Proven build (Strawberry gcc / MinGW), 32 lib .c files -> 393KB DLL, target
symbols exported (luaO_hexavalue, luaO_ceillog2, luaO_utf8esc, luaS_hash, ...):

    SRCS=$(ls *.c | grep -vE '^(lua|onelua|ltests)\.c$')
    gcc -shared -O2 -fPIC -I. $SRCS -o liblua_ref.dll

Excluded: lua.c (CLI main), onelua.c (amalgamation), ltests.c (test harness).
Alchemist's discover_c_build should compile all subject .c together; if it tries
per-module it will fail linking — the whole-lib oracle is mandatory for Lua.
