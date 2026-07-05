import ctypes, random
from pathlib import Path
D=ctypes.CDLL("/data/rigrun/projects/alchemist/subjects/zlib/shim/libzlib_state_shim.so")
D.shim_fw_wsize.restype=ctypes.c_uint; D.shim_run_longest_match.restype=ctypes.c_uint
D.shim_fw_init(6,-9,1,0); wsize=D.shim_fw_wsize(); winsize=1024; MAX_DIST=wsize-262
tests=[]
for i in range(14):
    rng=random.Random(i*89+5)
    strstart=rng.randint(280,320); lookahead=rng.randint(3,258)
    alpha=rng.randint(2,5)
    ndata=strstart+lookahead+260
    windata=[rng.randint(0,alpha) for _ in range(ndata)]
    limit=strstart-MAX_DIST if strstart>MAX_DIST else 0
    ncand=rng.randint(1,8)
    cands=sorted(rng.sample(range(max(limit+1,1),strstart),min(ncand,strstart-max(limit+1,1))))
    prev=[0]*wsize
    for k in range(1,len(cands)): prev[cands[k]]=cands[k-1]
    cur_match=cands[-1] if cands else 1
    prev_length=rng.randint(2,6); good_match=rng.randint(4,32); nice_match=rng.randint(8,258); max_chain=rng.randint(1,64)
    D.shim_fw_init(6,-9,1,0)
    D.shim_lm_setup(strstart,lookahead,prev_length,good_match,nice_match,max_chain,
        (ctypes.c_ubyte*ndata)(*windata),ndata,(ctypes.c_ushort*wsize)(*prev),wsize)
    ms=ctypes.c_uint()
    r=D.shim_run_longest_match(cur_match,ctypes.byref(ms))
    wd="vec!["+", ".join(str(x) for x in windata)+"]"
    prevv="vec!["+", ".join(str(prev[j]) for j in range(strstart+1))+"]"  # prev up to strstart
    body=(f"let mut s = zlib_types::DeflateState::default();\n"
      f"s.w_size = {wsize}usize; s.w_mask = {wsize-1}usize;\n"
      f"let mut window = vec![0u8; {winsize}]; {{ let wd: Vec<u8> = {wd}; window[..wd.len()].copy_from_slice(&wd); }} s.window = window;\n"
      f"let mut prev = vec![0u16; {wsize}]; {{ let pv: Vec<u16> = {prevv}; prev[..pv.len()].copy_from_slice(&pv); }} s.prev = prev;\n"
      f"s.strstart = {strstart}usize; s.lookahead = {lookahead}usize; s.prev_length = {prev_length}u32; s.good_match = {good_match}u32; s.nice_match = {nice_match}i32; s.max_chain_length = {max_chain}u32; s.match_start = 0usize;\n"
      f"let r = super::longest_match(&mut s, {cur_match}usize);\n"
      f"assert_eq!(r, {r}u32, \"lm ret {i}\");\n"
      f"assert_eq!(s.match_start, {ms.value}usize, \"lm match_start {i}\");")
    tests.append("    #[test]\n    fn test_lm_"+str(i)+"() {\n"+"\n".join("        "+l for l in body.splitlines())+"\n    }")
Path("/tmp/lm_tests.rs").write_text("\n".join(tests)); print("wrote",len(tests),"lm tests")
