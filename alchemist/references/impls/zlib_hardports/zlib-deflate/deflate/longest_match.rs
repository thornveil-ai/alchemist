pub fn longest_match(s: &mut DeflateState, cur_match: usize) -> u32 {
    let mut chain_length = s.max_chain_length;
    let mut best_len = s.prev_length;
    let mut nice_match = s.nice_match;
    let limit = if s.strstart > s.w_size - 262 { s.strstart - (s.w_size - 262) } else { 0 };
    let wmask = s.w_mask;

    if s.prev_length >= s.good_match {
        chain_length >>= 2;
    }
    if (nice_match as usize) > s.lookahead {
        nice_match = s.lookahead as i32;
    }

    let mut cur = cur_match;
    loop {
        let mut len = 0usize;
        while len < 258 && s.window[s.strstart + len] == s.window[cur + len] {
            len += 1;
        }

        if len > best_len as usize {
            s.match_start = cur;
            best_len = len as u32;
            if len >= nice_match as usize {
                break;
            }
        }

        cur = s.prev[cur & wmask] as usize;
        chain_length -= 1;
        if !(cur > limit && chain_length != 0) {
            break;
        }
    }

    if (best_len as usize) <= s.lookahead {
        best_len
    } else {
        s.lookahead as u32
    }
}
