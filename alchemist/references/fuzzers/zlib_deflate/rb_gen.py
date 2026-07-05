import ctypes, random, re
from pathlib import Path
D=ctypes.CDLL("/data/rigrun/projects/alchemist/subjects/zlib/shim/libzlib_state_shim.so")
D.shim_run_read_buf.restype=ctypes.c_uint
# fix gemma checksum calls
body=Path("/tmp/rb_gemma.rs").read_text().strip()
if body.startswith(chr(96)*3): body=re.sub(r"^[\`]{3}\w*|[\`]{3}$","",body,flags=re.M).strip()
body=body.replace("zlib_checksum::adler32(strm.adler, &buf[..actual_len])","zlib_checksum::adler32_z(strm.adler, &buf[..actual_len], actual_len)")
body=body.replace("zlib_checksum::crc32(strm.adler, &buf[..actual_len])","zlib_checksum::crc32(strm.adler, &buf[..actual_len], actual_len)")
Path("/tmp/rb_fixed.rs").write_text(body)
# generate oracle tests
tests=[]
for i in range(12):
    rng=random.Random(i*53+7)
    avail=rng.randint(0,200); size=rng.randint(0,220); wrap=rng.choice([0,1,2])
    adler_in= 1 if wrap==1 else (0 if wrap==2 else rng.randint(0,2**32-1))
    inp=[rng.randint(0,255) for _ in range(avail)]
    ina=(ctypes.c_ubyte*max(avail,1))(*(inp if inp else [0]))
    ao=ctypes.c_uint(); avo=ctypes.c_uint(); to=ctypes.c_uint(); cons=ctypes.c_uint()
    out=(ctypes.c_ubyte*max(size,1))()
    ln=D.shim_run_read_buf(ina,avail,size,wrap,adler_in,ctypes.byref(ao),ctypes.byref(avo),ctypes.byref(to),ctypes.byref(cons),out)
    outv="vec!["+", ".join(str(out[j]) for j in range(ln))+"]"
    inpv="vec!["+", ".join(str(x) for x in inp)+"]"
    rem="vec!["+", ".join(str(inp[j]) for j in range(ln,avail))+"]"
    body_t=(f"let mut strm = zlib_types::DeflateStream::default();\n"
      f"strm.next_in = {inpv}; strm.avail_in = {avail}usize; strm.total_in = 0; strm.adler = {adler_in}u32; strm.state.wrap = {wrap}i32;\n"
      f"let mut buf = vec![0u8; {size}];\n"
      f"let ret = super::read_buf(&mut strm, &mut buf, {size}usize);\n"
      f"assert_eq!(ret, {ln}usize, \"rb ret {i}\");\n"
      f"assert_eq!(&buf[..ret], &{outv}[..], \"rb out {i}\");\n"
      f"assert_eq!(strm.avail_in, {avo.value}usize, \"rb avail {i}\");\n"
      f"assert_eq!(strm.total_in, {to.value}u64, \"rb total {i}\");\n"
      f"assert_eq!(strm.adler, {ao.value}u32, \"rb adler {i}\");\n"
      f"assert_eq!(strm.next_in, {rem}, \"rb next_in {i}\");")
    tests.append("    #[test]\n    fn test_rb_"+str(i)+"() {\n"+"\n".join("        "+l for l in body_t.splitlines())+"\n    }")
Path("/tmp/rb_tests.rs").write_text("\n".join(tests)); print("wrote",len(tests),"read_buf tests")
