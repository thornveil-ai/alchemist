pub fn inflate_table(r#type: CodeType, lens: &[u16], codes: usize, table: &mut [CodeEntry], bits: &mut u32, work: &mut [u16]) -> Result<(), ZlibError> {
    let mut count = [0u16; 16];
    let mut offs = [0u16; 16];
    
    for sym in 0..codes {
        count[lens[sym] as usize] += 1;
    }

    let mut root = *bits;
    let mut max = 15;
    while max >= 1 && count[max] == 0 {
        max -= 1;
    }
    if root > max as u32 { root = max as u32; }
    if max == 0 {
        let here = CodeEntry { op: 64, bits: 1, val: 0 };
        table[0] = here;
        table[1] = here;
        *bits = 1;
        return Ok(());
    }
    let mut min = 1;
    while min < max && count[min] == 0 {
        min += 1;
    }
    if root < min as u32 { root = min as u32; }

    let mut left: i32 = 1;
    for len in 1..=15 {
        left <<= 1;
        left -= count[len] as i32;
        if left < 0 { return Err(ZlibError::DataError); }
    }
    if left > 0 && (matches!(r#type, CodeType::Codes) || max != 1) {
        return Err(ZlibError::DataError);
    }

    offs[1] = 0;
    for len in 1..15 {
        offs[len + 1] = offs[len] + count[len];
    }

    for sym in 0..codes {
        if lens[sym] != 0 {
            let len = lens[sym] as usize;
            work[offs[len] as usize] = sym as u16;
            offs[len] += 1;
        }
    }

    const LBASE: [u16; 31] = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258, 0, 0];
    const LEXT: [u16; 31] = [16, 16, 16, 16, 16, 16, 16, 16, 17, 17, 17, 17, 18, 18, 18, 18, 19, 19, 19, 19, 20, 20, 20, 20, 21, 21, 21, 21, 16, 68, 193];
    const DBASE: [u16; 32] = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577, 0, 0];
    const DEXT: [u16; 32] = [16, 16, 16, 16, 17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 23, 24, 24, 25, 25, 26, 26, 27, 27, 28, 28, 29, 29, 64, 64];

    let (base, extra, match_) = match r#type {
        CodeType::Codes => (None, None, 20u16),
        CodeType::Lens => (Some(&LBASE[..]), Some(&LEXT[..]), 257u16),
        CodeType::Dists => (Some(&DBASE[..]), Some(&DEXT[..]), 0u16),
    };

    let mut huff = 0u32;
    let mut sym = 0usize;
    let mut len = min as u32;
    let mut next_off = 0usize;
    let mut curr = root as u32;
    let mut drop = 0u32;
    let mut low = u32::MAX;
    let mut used = 1u32 << root;
    let mask = used - 1;

    if (matches!(r#type, CodeType::Lens) && used > 852) || (matches!(r#type, CodeType::Dists) && used > 592) {
        return Err(ZlibError::DataError);
    }

    loop {
        let mut here = CodeEntry { op: 0, bits: 0, val: 0 };
        here.bits = (len - drop) as u8;
        let work_val = work[sym];
        if work_val + 1 < match_ {
            here.op = 0;
            here.val = work_val;
        } else if work_val >= match_ {
            let idx = (work_val - match_) as usize;
            here.op = extra.unwrap()[idx] as u8;
            here.val = base.unwrap()[idx];
        } else {
            here.op = 32 + 64;
            here.val = 0;
        }

        let incr = 1u32 << (len - drop);
        let mut fill = 1u32 << curr;
        let min_off = fill;
        loop {
            fill -= incr;
            table[next_off + ((huff >> drop) as usize + fill as usize)] = here;
            if fill == 0 { break; }
        }

        let mut incr_huff = 1u32 << (len - 1);
        while huff & incr_huff != 0 {
            incr_huff >>= 1;
        }
        if incr_huff != 0 {
            huff &= incr_huff - 1;
            huff += incr_huff;
        } else {
            huff = 0;
        }

        sym += 1;
        count[len as usize] -= 1;
        if count[len as usize] == 0 {
            if len == max as u32 { break; }
            len = lens[work[sym] as usize] as u32;
        }

        if len > root && (huff & mask) != low {
            if drop == 0 { drop = root; }
            next_off += min_off as usize;
            curr = len - drop;
            let mut left_sub = (1i32 << curr) as i32;
            while curr + drop < max as u32 {
                left_sub -= count[(curr + drop) as usize] as i32;
                if left_sub <= 0 { break; }
                curr += 1;
                left_sub <<= 1;
            }
            used += 1u32 << curr;
            if (matches!(r#type, CodeType::Lens) && used > 852) || (matches!(r#type, CodeType::Dists) && used > 592) {
                return Err(ZlibError::DataError);
            }
            low = huff & mask;
            table[low as usize].op = curr as u8;
            table[low as usize].bits = root as u8;
            table[low as usize].val = next_off as u16;
        }
    }

    if huff != 0 {
        let here = CodeEntry { op: 64, bits: (len - drop) as u8, val: 0 };
        table[next_off + huff as usize] = here;
    }

    *bits = root;
    Ok(())
}