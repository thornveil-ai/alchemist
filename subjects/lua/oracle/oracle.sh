#!/bin/bash
# C2 whole-interpreter oracle for the Lua core.
#
# The Lua core (~600 SCC functions over lua_State/TValue/Table) cannot be
# verified per-function — you can't FFI-marshal a lua_State. It is verified
# END-TO-END: run an identical script corpus through reference C-lua and the
# translated Rust-lua, and require byte-identical observable behavior (stdout +
# exit status + error text). Byte-exact-or-refused, at the interpreter level.
#
# Usage:
#   oracle.sh build-ref <lua_src_dir>     # compile reference C-lua -> ./lua_ref
#   oracle.sh capture                     # run corpus through lua_ref -> expected/
#   oracle.sh diff <rust_lua_binary>      # run corpus through Rust-lua, diff vs expected (THE GATE)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
CORPUS="$HERE/corpus"
EXPECTED="$HERE/expected"
REF="$HERE/lua_ref"

build_ref() {
  local src="$1"
  # Exclude the interpreter/compiler drivers (multiple `main`) and the
  # amalgamation/test files; lua.c provides the standalone `main`.
  local srcs=$(ls "$src"/*.c | grep -vE '/(luac|ltests|onelua)\.c$')
  gcc -O2 -DLUA_USE_LINUX -o "$REF" $srcs -lm -ldl 2>/dev/null \
    || gcc -O2 -o "$REF" $srcs -lm 2>&1 | tail -3
  [ -x "$REF" ] && echo "built $REF" || { echo "BUILD FAILED"; exit 1; }
}

capture() {
  mkdir -p "$EXPECTED"
  for f in "$CORPUS"/*.lua; do
    local name=$(basename "$f" .lua)
    "$REF" "$f" > "$EXPECTED/$name.out" 2>&1
    echo "exit=$?" >> "$EXPECTED/$name.out"
    echo "captured $name"
  done
}

diff_rust() {
  local rust="$1"
  local pass=0 fail=0
  for f in "$CORPUS"/*.lua; do
    local name=$(basename "$f" .lua)
    local got=$("$rust" "$f" 2>&1; echo "exit=$?")
    if diff -q <(printf '%s' "$got") "$EXPECTED/$name.out" >/dev/null 2>&1 \
       || [ "$got" = "$(cat "$EXPECTED/$name.out")" ]; then
      pass=$((pass+1)); echo "PASS $name"
    else
      fail=$((fail+1)); echo "FAIL $name"
      diff <(printf '%s\n' "$got") "$EXPECTED/$name.out" | head -8
    fi
  done
  echo "===== oracle: $pass PASS / $fail FAIL ====="
  [ "$fail" -eq 0 ]
}

case "${1:-}" in
  build-ref) build_ref "$2" ;;
  capture)   capture ;;
  diff)      diff_rust "$2" ;;
  *) echo "usage: oracle.sh {build-ref <src>|capture|diff <rust-lua>}"; exit 2 ;;
esac
