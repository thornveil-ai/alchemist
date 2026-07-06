import os, re, subprocess, random
from pathlib import Path
random.seed(7)
base = Path("/data/rigrun/projects/alchemist/subjects/ardupilot_probe")
crate = base/"apcrc-rs"; (crate/"src").mkdir(parents=True, exist_ok=True)
(base/"AP_HAL").mkdir(exist_ok=True); (base/"AP_HAL"/"AP_HAL_Boards.h").write_text("")
src = (base/"crc.cpp").read_text()

# --- auto-extract ALL static-const lookup tables (generic, not hardcoded) ---
_CTY2RTY = {"uint8_t": "u8", "uint16_t": "u16", "uint32_t": "u32", "uint64_t": "u64"}
def all_tables(s):
    out = {}
    for m in re.finditer(r"static\s+const\s+(\w[\w ]*?)\s+(\w+)\s*\[[^\]]*\]\s*=\s*\{(.*?)\}", s, re.S):
        cty, name, body = m.group(1).strip().split()[-1], m.group(2), m.group(3)
        rty = _CTY2RTY.get(cty, "u32")
        vals = [int(v, 0) for v in re.findall(r"0x[0-9a-fA-F]+|\d+", body)]
        out[name] = (rty, vals)
    return out
tabs = all_tables(src)

# tested functions (name, rust_ret, kind); helpers are filled but not directly tested
FUNCS = [
 ("crc_crc8", "u8", "data_len"), ("crc8_maxim", "u8", "data_len"), ("crc8_sae", "u8", "data_len"),
 ("crc8_rds02uf", "u8", "data_len"), ("crc_xor_of_bytes", "u8", "data_len"), ("crc_xmodem", "u16", "data_len"),
 ("calc_crc_modbus", "u16", "data_len"), ("crc_fletcher16", "u16", "data_len"), ("crc_crc24", "u32", "data_len"),
 ("crc_sum8_with_carry", "u8", "data_len"), ("crc_sum_of_bytes_16", "u16", "data_len"),
 ("crc_sum_of_bytes", "u8", "data_len"), ("crc_crc32", "u32", "crc_data"), ("crc32_small", "u32", "crc_data"),
 ("crc16_ccitt", "u16", "data_crc"),
]
# helper deps called by tested fns (filled by the model, covered transitively)
HELPERS = [("crc_xmodem_update", "crc: u16, data: u8", "u16")]

def c_args(k):
    return "in,l" if k == "data_len" else ("0,in,l" if k == "crc_data" else "in,l,0")
calls = "\n".join(
    '    if(!strcmp(n,"%s")) { printf("%%llu",(unsigned long long)%s(%s)); return 0; }' % (nm, nm, c_args(k))
    for nm, _, k in FUNCS)
ref = (
    "#include <cstdio>\n#include <cstring>\n#include <cstdint>\n#include \"crc.h\"\n"
    "int main(int argc,char**argv){\n"
    "  const char*n=argv[1]; static uint8_t in[64];\n"
    "  uint16_t l=(uint16_t)fread(in,1,sizeof(in),stdin);\n"
    + calls + "\n  return 1;\n}\n")
(base/"apcrc_ref.cpp").write_text(ref)
subprocess.run(["g++", "-O2", "-I", str(base), "-o", str(base/"apcrcref"),
                str(base/"apcrc_ref.cpp"), str(base/"crc.cpp")], check=True)

inputs = [b"", b"\x00", b"1", b"123456789", bytes(range(16)), bytes([255]*10), b"ArduPilot"]
inputs += [bytes(random.randrange(256) for _ in range(random.randrange(1, 32))) for _ in range(5)]
def run(nm, inp):
    r = subprocess.run([str(base/"apcrcref"), nm], input=inp, capture_output=True)
    return int(r.stdout or b"0")

def rb(b): return "&[" + ",".join(map(str, b)) + "]"
def rt(name, ty, vals): return "pub const %s: [%s;%d] = [%s];" % (name.upper(), ty, len(vals), ",".join(map(str, vals)))

sigs = {"data_len": "data: &[u8]", "crc_data": "crc: {R}, data: &[u8]", "data_crc": "data: &[u8], crc: {R}"}
stubs = "\n".join(
    "// C: %s(...) in crc.cpp\npub fn %s(%s) -> %s { unimplemented!() }\n" % (nm, nm, sigs[k].format(R=r), r)
    for nm, r, k in FUNCS)
stubs += "\n" + "\n".join(
    "// helper called by a tested fn\npub fn %s(%s) -> %s { unimplemented!() }\n" % (nm, sig, r)
    for nm, sig, r in HELPERS)
tests = []
for nm, r, k in FUNCS:
    for i, inp in enumerate(inputs):
        exp = run(nm, inp)
        if k == "data_len":
            call = "%s(%s)" % (nm, rb(inp))
        elif k == "crc_data":
            call = "%s(0,%s)" % (nm, rb(inp))
        else:
            call = "%s(%s,0)" % (nm, rb(inp))
        tests.append("    #[test]\n    fn t_%s_%d(){ assert_eq!(%s, %d); }" % (nm, i, call, exp))
tables_rs = "\n".join(rt(n, ty, vals) for n, (ty, vals) in tabs.items())
(crate/"Cargo.toml").write_text('[package]\nname="apcrc-rs"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n')
(crate/"src"/"lib.rs").write_text(
    "#![allow(dead_code, clippy::needless_range_loop)]\n"
    "// ArduPilot libraries/AP_Math/crc.cpp -> safe Rust. Tables provided; functions for the model.\n"
    + tables_rs + "\n\n"
    + stubs + "\n#[cfg(test)]\nmod tests {\n    use super::*;\n" + "\n".join(tests) + "\n}\n")
print("=== %d funcs + %d helpers, %d inputs, %d tests. tables: %s" %
      (len(FUNCS), len(HELPERS), len(inputs), len(tests), {n: len(v[1]) for n, v in tabs.items()}))
r = subprocess.run(["cargo", "build"], cwd=str(crate), capture_output=True, text=True)
print("skeleton compiles:", r.returncode == 0, "|", (r.stderr.strip().splitlines() or [""])[-1])
