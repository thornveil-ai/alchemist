import os, subprocess, random
from pathlib import Path
random.seed(1234)  # deterministic (Math.random forbidden anyway)
base = Path("/data/rigrun/projects/alchemist/subjects/base64")
crate = base/"base64-rs"; (crate/"src").mkdir(parents=True, exist_ok=True)

# --- C reference oracle: stdin bytes -> stdout base64 (encode) ---
(base/"base64_ref.c").write_text(r'''
#include <stdio.h>
#include "base64.h"
int main(void){
    static unsigned char in[65536];
    unsigned int n = (unsigned int)fread(in,1,sizeof(in),stdin);
    static char out[87400];
    unsigned int outlen = base64_encode(in,n,out);
    fwrite(out,1,outlen,stdout);
    return 0;
}
''')
subprocess.run(["gcc","-O2","-o",str(base/"b64ref"),str(base/"base64_ref.c"),str(base/"base64.c")],check=True,cwd=str(base))

# --- differential vectors: varied lengths incl padding edges (0,1,2,3,4,5,6) ---
inputs = [b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar",
          bytes([0,255,128,1,2]), bytes(range(20)),
          b"Many hands make light work."]
inputs += [bytes(random.randrange(256) for _ in range(random.randrange(1,40))) for _ in range(6)]
vecs=[]
for inp in inputs:
    r = subprocess.run([str(base/"b64ref")],input=inp,capture_output=True)
    vecs.append((inp, r.stdout))

def rs_bytes(b): return "&[" + ",".join(str(x) for x in b) + "]"

# decode table (standard base64, matches base64.c base64de), 255 = invalid
de=[255]*128
for i,c in enumerate(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"): de[c]=i

(crate/"Cargo.toml").write_text('[package]\nname="base64-rs"\nversion="0.1.0"\nedition="2021"\n[lib]\npath="src/lib.rs"\n')

tests="\n".join(
f'''    #[test]
    fn test_encode_{i}() {{ assert_eq!(base64_encode({rs_bytes(inp)}), {rs_bytes(exp)}); }}
    #[test]
    fn test_roundtrip_{i}() {{ let e=base64_encode({rs_bytes(inp)}); assert_eq!(base64_decode(&e), {rs_bytes(inp)}); }}'''
    for i,(inp,exp) in enumerate(vecs))

(crate/"src"/"lib.rs").write_text(f'''#![allow(dead_code, clippy::needless_range_loop)]
// base64 (public domain, WEI Zhicheng) — coherent Rust skeleton.
// Tables + constants provided (pure data); the 2 FUNCTIONS are for the model.
pub const BASE64_PAD: u8 = b'=';
pub const BASE64EN: [u8; 64] = *b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
pub const BASE64DE: [u8; 128] = [{",".join(str(x) for x in de)}];

// C: unsigned int base64_encode(const unsigned char *in, unsigned int inlen, char *out)
//   -> coherent: take the input slice, RETURN the encoded bytes (the C `out`).
pub fn base64_encode(input: &[u8]) -> Vec<u8> {{
    unimplemented!()
}}

// C: unsigned int base64_decode(const char *in, unsigned int inlen, unsigned char *out)
pub fn base64_decode(input: &[u8]) -> Vec<u8> {{
    unimplemented!()
}}

#[cfg(test)]
mod tests {{
    use super::*;
{tests}
}}
''')
print("=== setup done. vectors:", len(vecs), "| build check ===")
r=subprocess.run(["cargo","build"],cwd=str(crate),capture_output=True,text=True)
print("compiles:", r.returncode==0, "|", (r.stderr.strip().splitlines() or [""])[-1])
