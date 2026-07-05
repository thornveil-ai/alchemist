import ctypes, random
from pathlib import Path
D=ctypes.CDLL("/data/rigrun/projects/alchemist/subjects/zlib/shim/libzlib_state_shim.so")
D.shim_run_tr_tally.restype=ctypes.c_int; D.shim_get_sym_next.restype=ctypes.c_uint; D.shim_get_matches.restype=ctypes.c_uint
D.shim_get_bi_buf.restype=ctypes.c_ushort; D.shim_get_bi_valid.restype=ctypes.c_int; D.shim_get_pending_len.restype=ctypes.c_uint; D.shim_get_bi_used.restype=ctypes.c_int
def us(n,v): return (ctypes.c_ushort*n)(*v)
# ---- _tr_tally ----
tt=[]
for i in range(12):
    rng=random.Random(i*41+3)
    L=286; Dn=30
    lfreq=[rng.randint(0,50) for _ in range(L)]; dfreq=[rng.randint(0,50) for _ in range(Dn)]
    sn=rng.randint(0,60)*3; se=sn+3*rng.randint(1,20); matches=rng.randint(0,100)
    symbuf=[rng.randint(0,255) for _ in range(8192)]
    if rng.random()<0.5: dist=0; lc=rng.randint(0,255)
    else: dist=rng.randint(1,4096); lc=rng.randint(0,255)
    D.shim_reset()
    D.shim_set_tree_fc(0,us(L,lfreq),L); D.shim_set_tree_fc(1,us(Dn,dfreq),Dn)
    D.shim_set_sym_buf((ctypes.c_ubyte*8192)(*symbuf),8192); D.shim_set_sym_next(sn); D.shim_set_matches(matches)
    r=D.shim_run_tr_tally(dist,lc,se)
    osn=D.shim_get_sym_next(); om=D.shim_get_matches()
    ob=(ctypes.c_ubyte*8192)(); D.shim_get_sym_buf(ob,8192)
    olf=us(L,[0]*L); D.shim_get_tree_fc(0,olf,L); odf=us(Dn,[0]*Dn); D.shim_get_tree_fc(1,odf,Dn)
    ltl="vec!["+", ".join(f"zlib_types::TreeElement{{freq:{lfreq[j]},..Default::default()}}" for j in range(L))+"]"
    dtl="vec!["+", ".join(f"zlib_types::TreeElement{{freq:{dfreq[j]},..Default::default()}}" for j in range(Dn))+"]"
    sbinit="vec!["+", ".join(str(x) for x in symbuf)+"]"
    symout="vec!["+", ".join(str(ob[j]) for j in range(osn))+"]"
    olfv="vec!["+", ".join(str(olf[j]) for j in range(L))+"]"; odfv="vec!["+", ".join(str(odf[j]) for j in range(Dn))+"]"
    body=(f"let mut s = zlib_types::DeflateState::default();\n"
      f"s.dyn_ltree = {ltl}; s.dyn_dtree = {dtl};\n"
      f"s.sym_buf = {sbinit}; s.sym_next = {sn}u32; s.sym_end = {se}u32; s.matches = {matches}u32;\n"
      f"let r = super::_tr_tally(&mut s, {dist}u32, {lc}u32);\n"
      f"assert_eq!(r, {str(r==1).lower()}, \"tt ret {i}\");\n"
      f"assert_eq!(s.sym_next, {osn}u32, \"tt sym_next {i}\");\n"
      f"assert_eq!(s.matches, {om}u32, \"tt matches {i}\");\n"
      f"assert_eq!(&s.sym_buf[..{osn}], &{symout}[..], \"tt symbuf {i}\");\n"
      f"let lf: Vec<u16> = s.dyn_ltree.iter().map(|e|e.freq).collect(); assert_eq!(lf, {olfv}, \"tt ltree {i}\");\n"
      f"let df: Vec<u16> = s.dyn_dtree.iter().map(|e|e.freq).collect(); assert_eq!(df, {odfv}, \"tt dtree {i}\");")
    tt.append("    #[test]\n    fn test_tt_"+str(i)+"() {\n"+"\n".join("        "+l for l in body.splitlines())+"\n    }")
Path("/tmp/tt_tests.rs").write_text("\n".join(tt))
# ---- _tr_stored_block ----
sbt=[]
for i in range(10):
    rng=random.Random(i*57+9)
    bib=rng.randint(0,65535); biv=rng.randint(0,16); last=rng.choice([0,1])
    slen=rng.randint(0,200); buf=[rng.randint(0,255) for _ in range(slen)]
    D.shim_reset(); D.shim_set_bi_buf(bib); D.shim_set_bi_valid(biv); D.shim_set_pending((ctypes.c_ubyte*1)(0),0)
    D.shim_run_tr_stored_block((ctypes.c_ubyte*max(slen,1))(*(buf if buf else [0])),slen,last)
    pl=D.shim_get_pending_len(); pb=(ctypes.c_ubyte*pl)(); D.shim_get_pending(pb,pl)
    obib=D.shim_get_bi_buf(); obiv=D.shim_get_bi_valid()
    pend="vec!["+", ".join(str(pb[j]) for j in range(pl))+"]"; bufv="vec!["+", ".join(str(x) for x in buf)+"]"
    body=(f"let mut s = zlib_types::DeflateState::default();\n"
      f"s.bi_buf = {bib}u16; s.bi_valid = {biv}i32; s.pending = vec![];\n"
      f"let buf: Vec<u8> = {bufv};\n"
      f"super::_tr_stored_block(&mut s, &buf, {slen}u32, {last}i32);\n"
      f"assert_eq!(s.pending, {pend}, \"sb pending {i}\");\n"
      f"assert_eq!(s.bi_buf, {obib}u16, \"sb bi_buf {i}\");\n"
      f"assert_eq!(s.bi_valid, {obiv}i32, \"sb bi_valid {i}\");")
    sbt.append("    #[test]\n    fn test_sbk_"+str(i)+"() {\n"+"\n".join("        "+l for l in body.splitlines())+"\n    }")
Path("/tmp/sbk_tests.rs").write_text("\n".join(sbt))
print("wrote",len(tt),"tally +",len(sbt),"stored_block tests")
