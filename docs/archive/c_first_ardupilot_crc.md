# Real-world C, TRACTOR-aligned: ArduPilot's crc.cpp -> safe Rust

## Why this one matters
DARPA **TRACTOR** ("TRanslating All C TO Rust") is a **C-only** program — the
DoD's legacy-C memory-safety problem, not C++. So the north star is *flawless,
autonomous translation of any C*, and C++ (full ArduPilot vehicles/`Vector3<T>`)
is a later upgrade, explicitly out of TRACTOR scope.

ArduPilot's `libraries/AP_Math/crc.cpp` is a perfect C-first target: it's *real*
defense-relevant code, and despite the `.cpp` extension it's **pure C** (no
classes/templates; one trivial default-arg). It's also messier than our clean
subjects (base64/jsmn), which is the point.

## Result: 15 functions, 180/180 differential tests byte-exact, autonomous
`crc_crc8, crc8_maxim, crc8_sae, crc8_rds02uf, crc_xor_of_bytes, crc_xmodem
(+crc_xmodem_update), calc_crc_modbus, crc_fletcher16, crc_crc24,
crc_sum8_with_carry, crc_sum_of_bytes_16, crc_sum_of_bytes, crc_crc32,
crc32_small, crc16_ccitt` — filled from the C first-shot at temperature 0,
verified against the compiled ArduPilot C across 12 inputs each (edges + random).

## The real lesson: the MODEL is ready; the ONBOARDING is the gap
The translation itself was first-shot. What failed twice was the **harness I
hand-wrote** — real-world C has structure our clean subjects lacked:
1. **Multiple lookup tables** — I hardcoded 3; the file actually has **7**
   (`crc8_table`, `_maxim`, `_sae`, `_rds02uf`, `crc32_tab`, `crc16tab`,
   `crc_table`). Fix: auto-extract *every* `static const T name[] = {...}`.
2. **Inter-function dependencies** — `crc_xmodem` calls `crc_xmodem_update`;
   picking a "subset" broke the call graph. Fix: pull in helper deps.

Both are exactly what **WS1 (oracle synthesis) + WS5 (harness/build generation)**
must automate. **For "any C, flawlessly, autonomously," the remaining work is
automating the onboarding — table/dependency/signature discovery — not the
translation.** The model handles the code; the pipeline must handle the codebase.

Artifacts: `lib.rs` (verified) + `setup_apcrc.py` (reproducible harness).
