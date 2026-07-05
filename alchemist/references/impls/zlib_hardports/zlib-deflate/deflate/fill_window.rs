pub fn fill_window(strm: &mut DeflateStream) {
    loop {
        let mut more = strm.state.window_size as usize - strm.state.lookahead - strm.state.strstart;
        let w_size = strm.state.w_size;
        let max_dist = w_size - 262;

        if strm.state.strstart >= w_size + max_dist {
            strm.state.window.copy_within(w_size..w_size + (w_size - more), 0);
            strm.state.match_start -= w_size;
            strm.state.strstart -= w_size;
            strm.state.block_start -= w_size as i64;
            if strm.state.insert as usize > strm.state.strstart {
                strm.state.insert = strm.state.strstart as u32;
            }
            slide_hash(&mut strm.state);
            more += w_size;
        }

        if strm.avail_in == 0 {
            break;
        }

        let start = strm.state.strstart + strm.state.lookahead;
        let n = strm.avail_in.min(more);
        if n > 0 {
            strm.state.window[start..start + n].copy_from_slice(&strm.next_in[..n]);
            match strm.state.wrap {
                1 => strm.adler = zlib_checksum::adler32_z(strm.adler, &strm.state.window[start..start + n], n),
                2 => strm.adler = zlib_checksum::crc32(strm.adler, &strm.state.window[start..start + n], n),
                _ => {}
            }
            strm.next_in.drain(0..n);
            strm.avail_in -= n;
            strm.total_in += n as u64;
        }
        strm.state.lookahead += n;

        if strm.state.lookahead + strm.state.insert as usize >= 3 {
            let mut str_idx = strm.state.strstart - strm.state.insert as usize;
            strm.state.ins_h = strm.state.window[str_idx] as u32;
            strm.state.ins_h = ((strm.state.ins_h << strm.state.hash_shift) ^ (strm.state.window[str_idx + 1] as u32)) & strm.state.hash_mask;
            while strm.state.insert > 0 {
                strm.state.ins_h = ((strm.state.ins_h << strm.state.hash_shift) ^ (strm.state.window[str_idx + 2] as u32)) & strm.state.hash_mask;
                strm.state.prev[str_idx & strm.state.w_mask] = strm.state.head[strm.state.ins_h as usize];
                strm.state.head[strm.state.ins_h as usize] = str_idx as u16;
                str_idx += 1;
                strm.state.insert -= 1;
                if strm.state.lookahead + (strm.state.insert as usize) < 3 {
                    break;
                }
            }
        }

        if !(strm.state.lookahead < 262 && strm.avail_in != 0) {
            break;
        }
    }

    let curr = strm.state.strstart + strm.state.lookahead;
    let win_size_u64 = strm.state.window_size as u64;
    if strm.state.high_water < win_size_u64 {
        if (strm.state.high_water as usize) < curr {
            let init = (win_size_u64 - curr as u64).min(258) as usize;
            strm.state.window[curr..curr + init].fill(0);
            strm.state.high_water = (curr + init) as u64;
        } else if strm.state.high_water < (curr + 258) as u64 {
            let init = ((curr + 258) as u64 - strm.state.high_water).min(win_size_u64 - strm.state.high_water) as usize;
            strm.state.window[strm.state.high_water as usize..strm.state.high_water as usize + init].fill(0);
            strm.state.high_water += init as u64;
        }
    }
}
