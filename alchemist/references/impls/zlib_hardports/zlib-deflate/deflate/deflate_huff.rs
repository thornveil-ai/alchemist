pub fn deflate_huff(strm: &mut DeflateStream, flush: i32) -> BlockState {
    loop {
        if strm.state.lookahead == 0 {
            fill_window(strm);
            if strm.state.lookahead == 0 {
                if flush == 0 {
                    return BlockState::NeedMore;
                }
                break;
            }
        }
        strm.state.match_length = 0;
        let _byte = strm.state.window[strm.state.strstart] as u32;
        let bflush = _tr_tally(&mut strm.state, 0, _byte);
        strm.state.lookahead -= 1;
        strm.state.strstart += 1;
        if bflush {
            flush_block_only(strm, 0);
            if strm.avail_out == 0 {
                return BlockState::NeedMore;
            }
        }
    }
    strm.state.insert = 0;
    if flush == 4 {
        flush_block_only(strm, 1);
        if strm.avail_out == 0 {
            return BlockState::FinishStarted;
        }
        return BlockState::FinishDone;
    }
    if strm.state.sym_next != 0 {
        flush_block_only(strm, 0);
        if strm.avail_out == 0 {
            return BlockState::NeedMore;
        }
    }
    BlockState::BlockDone
}
