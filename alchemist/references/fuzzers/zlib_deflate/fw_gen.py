import ctypes, random
from pathlib import Path
D=ctypes.CDLL("/data/rigrun/projects/alchemist/subjects/zlib/shim/libzlib_state_shim.so")
for f in ["shim_fw_wsize","shim_fw_hashsize","shim_fw_windowsize","shim_fw_hashbits","shim_fw_hashshift","shim_fw_g_strstart","shim_fw_g_lookahead","shim_fw_g_insert","shim_fw_g_ins_h"]:
    getattr(D,f).restype=ctypes.c_uint
D.shim_fw_g_high_water.restype=ctypes.c_long; D.shim_fw_g_block_start.restype=ctypes.c_long
D.shim_fw_init(6,-9,1,0)  # raw (wrap=0), memlevel=1
wsize=D.shim_fw_wsize(); hsize=D.shim_fw_hashsize(); winsize=D.shim_fw_windowsize()
hbits=D.shim_fw_hashbits(); hshift=D.shim_fw_hashshift(); hmask=hsize-1
tests=[]
for i in range(12):
    rng=random.Random(i*71+3)
    strstart=rng.randint(0,80); lookahead=rng.randint(0,4); insert=rng.randint(0,min(strstart,6))
    ndata=strstart+lookahead+8
    windata=[rng.randint(0,255) for _ in range(ndata)]
    avail=rng.randint(0,300); inp=[rng.randint(0,255) for _ in range(avail)]
    D.shim_fw_init(6,-9,1,0)
    D.shim_fw_set_mutable(strstart,lookahead,insert,0,0,(ctypes.c_ubyte*max(ndata,1))(*(windata if windata else [0])),ndata)
    D.shim_fw_run((ctypes.c_ubyte*max(avail,1))(*(inp if inp else [0])),avail)
    o_ss=D.shim_fw_g_strstart(); o_la=D.shim_fw_g_lookahead(); o_ins=D.shim_fw_g_insert()
    o_ih=D.shim_fw_g_ins_h(); o_hw=D.shim_fw_g_high_water(); o_bs=D.shim_fw_g_block_start()
    ol=o_ss+o_la
    win=(ctypes.c_ubyte*winsize)(); D.shim_fw_g_window(win,winsize)
    head=(ctypes.c_ushort*hsize)(); D.shim_fw_g_head(head,hsize)
    prev=(ctypes.c_ushort*wsize)(); D.shim_fw_g_prev(prev,wsize)
    winv="vec!["+", ".join(str(win[j]) for j in range(ol))+"]"
    headv="vec!["+", ".join(str(head[j]) for j in range(hsize))+"]"
    prevv="vec!["+", ".join(str(prev[j]) for j in range(wsize))+"]"
    inpv="vec!["+", ".join(str(x) for x in inp)+"]"
    wd="vec!["+", ".join(str(x) for x in windata)+"]"
    body=(f"let mut strm = zlib_types::DeflateStream::default();\n"
      f"strm.state.w_size = {wsize}usize; strm.state.w_mask = {wsize-1}usize; strm.state.window_size = {winsize}u32;\n"
      f"strm.state.hash_size = {hsize}u32; strm.state.hash_mask = {hmask}u32; strm.state.hash_shift = {hshift}u32; strm.state.hash_bits = {hbits}u32;\n"
      f"strm.state.wrap = 0i32;\n"
      f"let mut window = vec![0u8; {winsize}]; {{ let wd: Vec<u8> = {wd}; window[..wd.len()].copy_from_slice(&wd); }} strm.state.window = window;\n"
      f"strm.state.head = vec![0u16; {hsize}]; strm.state.prev = vec![0u16; {wsize}];\n"
      f"strm.state.strstart = {strstart}usize; strm.state.lookahead = {lookahead}usize; strm.state.insert = {insert}u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;\n"
      f"strm.next_in = {inpv}; strm.avail_in = {avail}usize; strm.total_in = 0; strm.adler = 0;\n"
      f"super::fill_window(&mut strm);\n"
      f"assert_eq!(strm.state.strstart, {o_ss}usize, \"fw strstart {i}\");\n"
      f"assert_eq!(strm.state.lookahead, {o_la}usize, \"fw lookahead {i}\");\n"
      f"assert_eq!(strm.state.insert, {o_ins}u32, \"fw insert {i}\");\n"
      f"assert_eq!(strm.state.ins_h, {o_ih}u32, \"fw ins_h {i}\");\n"
      f"assert_eq!(strm.state.high_water, {o_hw}u64, \"fw high_water {i}\");\n"
      f"assert_eq!(&strm.state.window[..{ol}], &{winv}[..], \"fw window {i}\");\n"
      f"assert_eq!(strm.state.head, {headv}, \"fw head {i}\");\n"
      f"assert_eq!(strm.state.prev, {prevv}, \"fw prev {i}\");")
    tests.append("    #[test]\n    fn test_fw_"+str(i)+"() {\n"+"\n".join("        "+l for l in body.splitlines())+"\n    }")
Path("/tmp/fw_tests.rs").write_text("\n".join(tests)); print("wrote",len(tests),"fw tests; wsize",wsize,"hsize",hsize)
