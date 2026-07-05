pub fn read_buf(strm: &mut DeflateStream, buf: &mut [u8], size: usize) -> usize {
    let mut len = strm.avail_in;
    if len > size { len = size; }
    if len == 0 { return 0; }
    
    let actual_len = len.min(buf.len());
    if actual_len == 0 { return 0; }
    
    let data: Vec<u8> = strm.next_in.drain(0..actual_len).collect();
    buf[..actual_len].copy_from_slice(&data);
    
    strm.avail_in -= actual_len;
    
    if strm.state.wrap == 1 {
        strm.adler = zlib_checksum::adler32_z(strm.adler, &buf[..actual_len], actual_len);
    } else if strm.state.wrap == 2 {
        strm.adler = zlib_checksum::crc32(strm.adler, &buf[..actual_len], actual_len);
    }
    
    strm.total_in += actual_len as u64;
    actual_len
}
