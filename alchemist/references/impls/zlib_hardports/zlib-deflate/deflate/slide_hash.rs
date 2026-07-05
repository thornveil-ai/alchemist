pub fn slide_hash(s: &mut DeflateState) {
    let wsize = s.w_size as u16;
    for m in s.head.iter_mut().rev() {
        *m = if *m >= wsize { *m - wsize } else { 0 };
    }
    for m in s.prev.iter_mut().rev() {
        *m = if *m >= wsize { *m - wsize } else { 0 };
    }
}
