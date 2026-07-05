pub fn flush_pending(strm: &mut DeflateStream) {
    _tr_flush_bits(&mut strm.state);
    let len = strm.state.pending.len().min(strm.avail_out);
    if len == 0 {
        return;
    }
    strm.next_out.extend_from_slice(&strm.state.pending[..len]);
    strm.state.pending.drain(0..len);
    strm.avail_out -= len;
    strm.total_out += len as u64;
}
