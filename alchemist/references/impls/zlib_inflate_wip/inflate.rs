//! Inflate
//!
//! Module containing 15 functions: inflateBackInit_, inflateBack, inflateBackEnd,
//! inflate_fast, inflateStateCheck, inflateResetKeep, inflateReset, inflateReset2,
//! inflateInit2_, inflatePrime, updatewindow, inflate_table, buildtables,
//! inflate_fixed, main (inftrees.c generator)

#![allow(unused_variables, unused_imports, dead_code)]

use zlib_types::*;
use zlib_checksum::*;

use crate::*;

/// Inflatebackinit 
/// Initializes the internal state for the 'inflate back' decompression algorithm,
/// setting up the sliding window and memory allocation.
///
/// Standards: zlib specification
#[allow(clippy::unimplemented)]
const M_LENLENS: u32 = 16197; const M_CODELENS: u32 = 16198; const M_LEN: u32 = 16200; const M_LENEXT: u32 = 16201; const M_DIST: u32 = 16202; const M_DISTEXT: u32 = 16203; const M_MATCH: u32 = 16204; const M_LIT: u32 = 16205;
const ORDER: [u16; 19] = [16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15];
const HEAD: u32 = 16180;
const SYNC: u32 = 16211;
const Z_OK: i32 = 0;
const Z_STREAM_ERROR: i32 = -2;
const Z_MEM_ERROR: i32 = -4;
const Z_VERSION_ERROR: i32 = -6;

pub fn inflate_back_init_(strm: &mut InflateStream, window_bits: u32, window: &mut [u8], version: &str, stream_size: usize) -> Result<(), ZlibError> {
    let _ = strm;
    let _ = window_bits;
    let _ = window;
    let _ = version;
    let _ = stream_size;
    unimplemented!("skeleton: inflate_back_init_ not yet implemented")
}

/// Inflateback
/// Decompresses a DEFLATE-encoded stream using a state machine that handles
/// stored, fixed, and dynamic Huffman blocks.
///
/// Standards: RFC 1950 (ZLIB), RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]
pub fn inflate_back(strm: &mut InflateStream, r#in: fn(), in_desc: Option<Context>, out: fn(), out_desc: Option<Context>) -> Result<DecompressionStatus, ZlibError> {
    let _ = strm;
    let _ = r#in;
    unimplemented!("skeleton: inflate_back not yet implemented")
}

/// Inflatebackend
/// Terminates an inflate operation by deallocating the internal decompression
/// state associated with a stream.
#[allow(clippy::unimplemented)]
pub fn inflate_back_end(strm: &mut InflateStream) -> Result<(), ZlibError> {
    let _ = strm;
    unimplemented!("skeleton: inflate_back_end not yet implemented")
}

/// Inflate Fast
/// Performs high-speed DEFLATE decompression by decoding Huffman-coded literals
/// and length/distance pairs using optimized lookup tables.
///
/// Standards: RFC 1950 (ZLIB), RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]
pub fn inflate_fast(strm: &mut InflateStream, start: usize) {
    let _ = strm;
    let _ = start;
    unimplemented!("skeleton: inflate_fast not yet implemented")
}

/// Inflatestatecheck
/// Validates the integrity and consistency of a zlib inflation stream and its
/// associated internal state.
///
/// Standards: zlib
#[allow(clippy::unimplemented)]
pub fn inflate_state_check(strm: &InflateStream) -> bool {
    strm.state.mode < HEAD || strm.state.mode > SYNC
}

/// Inflateresetkeep
/// Resets the internal decompression state of an inflate stream to its initial
/// configuration while preserving certain configuration parameters like the wrap
/// mode.
///
/// Standards: RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]
pub fn inflate_reset_keep(strm: &mut InflateStream) -> i32 {
    if inflate_state_check(strm) {
        return Z_STREAM_ERROR;
    }
    strm.total_in = 0;
    strm.total_out = 0;
    strm.state.total = 0;
    if strm.state.wrap != 0 {
        strm.adler = (strm.state.wrap & 1) as u32;
    }
    strm.state.mode = HEAD;
    strm.state.last = false;
    strm.state.havedict = false;
    strm.state.flags = -1;
    strm.state.dmax = 32768;
    strm.state.hold = 0;
    strm.state.bits = 0;
    strm.state.next = 0;
    strm.state.lencode = Vec::new();
    strm.state.distcode = Vec::new();
    strm.state.sane = true;
    strm.state.back = -1;
    Z_OK
}

/// Inflatereset
/// Resets the internal state of a decompression stream to its initial
/// configuration while preserving certain configuration parameters.
///
/// Standards: zlib
#[allow(clippy::unimplemented)]
pub fn inflate_reset(strm: &mut InflateStream) -> i32 {
    if inflate_state_check(strm) {
        return Z_STREAM_ERROR;
    }
    strm.state.wsize = 0;
    strm.state.whave = 0;
    strm.state.wnext = 0;
    inflate_reset_keep(strm)
}

/// Inflatereset2
/// Resets the decompression state and reconfigures the window size and wrap format
/// (zlib/gzip/raw) based on the provided windowBits parameter.
///
/// Standards: RFC 1950, RFC 1951
#[allow(clippy::unimplemented)]
pub fn inflate_reset2(strm: &mut InflateStream, window_bits: i32) -> i32 {
    if inflate_state_check(strm) {
        return Z_STREAM_ERROR;
    }
    let mut wb = window_bits;
    let wrap;
    if wb < 0 {
        if wb < -15 {
            return Z_STREAM_ERROR;
        }
        wrap = 0;
        wb = -wb;
    } else {
        wrap = (wb >> 4) + 5;
        if wb < 48 {
            wb &= 15;
        }
    }
    if wb != 0 && (wb < 8 || wb > 15) {
        return Z_STREAM_ERROR;
    }
    if !strm.state.window.is_empty() && strm.state.wbits != wb as u32 {
        strm.state.window = Vec::new();
    }
    strm.state.wrap = wrap;
    strm.state.wbits = wb as u32;
    inflate_reset(strm)
}

/// Inflateinit2 
/// Initializes a decompression stream with a specific window size and validates
/// version compatibility.
///
/// Standards: RFC 1950, RFC 1951
#[allow(clippy::unimplemented)]
pub fn inflate_init2_(strm: &mut InflateStream, window_bits: i32, version: &str, stream_size: usize) -> Result<(), ZlibError> {
    let _ = strm;
    let _ = window_bits;
    let _ = version;
    let _ = stream_size;
    unimplemented!("skeleton: inflate_init2_ not yet implemented")
}

/// Inflateprime
/// Injects a specific number of bits from a value into the internal bit buffer of
/// a decompression stream.
///
/// Standards: DEFLATE
#[allow(clippy::unimplemented)]
pub fn inflate_prime(strm: &mut InflateStream, bits: i32, value: u32) -> Result<(), ZlibError> {
    let _ = strm;
    let _ = bits;
    let _ = value;
    unimplemented!("skeleton: inflate_prime not yet implemented")
}

/// Updatewindow
/// Maintains a circular sliding window buffer used for DEFLATE decompression by
/// copying recent output data into the window.
///
/// Standards: RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]

pub fn updatewindow(strm: &mut InflateState, end: &[u8], copy: usize) -> Result<(), MemoryError> {
    // Port of inflate.c:updatewindow.
    // Copies up to wsize of `end`'s last `copy` bytes into the sliding
    // window at wnext. Used to maintain the 32KB window for back-references
    // across streaming decompression calls.

    // Lazy-allocate the window if empty.
    if strm.window.is_empty() {
        let size = 1usize << strm.wbits;
        strm.window = vec![0u8; size];
    }
    // Initialize wsize / wnext / whave on first use.
    if strm.wsize == 0 {
        strm.wsize = 1u32 << strm.wbits;
        strm.wnext = 0;
        strm.whave = 0;
    }

    let wsize = strm.wsize as usize;
    // If we have more than wsize bytes to copy, only the last wsize matter.
    let (src_start, copy) = if copy >= wsize {
        (end.len().saturating_sub(wsize), wsize)
    } else {
        (end.len().saturating_sub(copy), copy)
    };

    let dist = (wsize - strm.wnext as usize).min(copy);
    // Copy `dist` bytes from &end[src_start..] into window[wnext..wnext+dist]
    let wnext = strm.wnext as usize;
    for i in 0..dist {
        if src_start + i < end.len() && wnext + i < strm.window.len() {
            strm.window[wnext + i] = end[src_start + i];
        }
    }
    let remaining = copy - dist;
    if remaining > 0 {
        // Wrap: second half starts at window[0]
        for i in 0..remaining {
            if src_start + dist + i < end.len() && i < strm.window.len() {
                strm.window[i] = end[src_start + dist + i];
            }
        }
        strm.wnext = remaining as u32;
        strm.whave = wsize as u32;
    } else {
        strm.wnext = (strm.wnext + dist as u32) % strm.wsize;
        if strm.wnext == 0 {
            strm.whave = wsize as u32;
        } else if strm.whave < strm.wsize {
            strm.whave += dist as u32;
        }
    }
    Ok(())
}



/// Inflate Table
/// Constructs canonical Huffman decoding tables from a set of code lengths to
/// enable efficient symbol lookup during decompression.
///
/// Standards: RFC 1103 (Huffman Coding), RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]

pub fn inflate_table(r#type: CodeType, lens: &[u16], codes: usize, table: &mut [CodeEntry], bits: &mut u32, work: &mut [u16]) -> Result<usize, ZlibError> {
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
        return Ok(2);
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
    Ok(used as usize)
}



/// Buildtables
/// Initializes the static Huffman decoding lookup tables for fixed-length codes
/// used in DEFLATE decompression.
///
/// Standards: RFC 1951
#[allow(clippy::unimplemented)]

pub fn buildtables() {
    // Port of inflate.c:makefixed / buildtables.
    // In the C code, this is a BUILD-TIME utility that prints the fixed
    // inflate tables (the ones inflate_fixed installs at runtime) to
    // stdout for inclusion in inffixed.h. Not part of the decompression
    // runtime. In the Rust port it's a no-op — fixed tables are built
    // inline by inflate_fixed when needed.
}



/// Inflate Fixed
/// Initializes the decompression state with precomputed lookup tables and
/// bit-widths specifically for fixed Huffman code decoding.
///
/// Standards: RFC 1951
#[allow(clippy::unimplemented)]

pub fn inflate_fixed(state: &mut InflateState) {
    if state.codes_tbl.is_empty() { state.codes_tbl = vec![zlib_types::CodeEntry::default(); 1444]; }
    if state.lens.len() < 320 { state.lens = vec![0u16; 320]; }
    if state.work.len() < 288 { state.work = vec![0u16; 288]; }
    for i in 0..144 { state.lens[i] = 8; }
    for i in 144..256 { state.lens[i] = 9; }
    for i in 256..280 { state.lens[i] = 7; }
    for i in 280..288 { state.lens[i] = 8; }
    let lens = core::mem::take(&mut state.lens);
    let mut work = core::mem::take(&mut state.work);
    let mut lenbits = 9u32;
    let u = inflate_table(zlib_types::CodeType::Lens, &lens[..288], 288, &mut state.codes_tbl, &mut lenbits, &mut work).unwrap();
    state.lencode_off = 0; state.lenbits = 9;
    let dist_lens = [5u16; 32];
    let mut distbits = 5u32;
    inflate_table(zlib_types::CodeType::Dists, &dist_lens, 32, &mut state.codes_tbl[u..], &mut distbits, &mut work).unwrap();
    state.distcode_off = u as u32; state.distbits = 5;
    state.lens = lens; state.work = work;
}



/// Main (Inftrees.C Generator)
/// Generates a C header file containing static lookup tables for fixed Huffman
/// code decoding (lengths and distances) used in zlib decompression.
///
/// Standards: zlib
#[allow(clippy::unimplemented)]
pub fn main_inftrees_c_generator_() {
    unimplemented!("skeleton: main_inftrees_c_generator_ not yet implemented")
}

pub fn inflate_init2(strm: &mut InflateStream, window_bits: i32) -> i32 {
    strm.state.window = Vec::new();
    strm.state.mode = HEAD;
    inflate_reset2(strm, window_bits)
}

const M_HEAD: u32 = 16180; const M_TYPE: u32 = 16191; const M_TYPEDO: u32 = 16192;
const M_STORED: u32 = 16193; const M_COPY_: u32 = 16194; const M_COPY: u32 = 16195;
const M_TABLE: u32 = 16196; const M_LEN_: u32 = 16199;
const M_CHECK: u32 = 16206; const M_LENGTH: u32 = 16207; const M_DONE: u32 = 16208;
const M_BAD: u32 = 16209; const M_MEM: u32 = 16210;
const Z_STREAM_END: i32 = 1; const Z_BUF_ERROR: i32 = -5; const Z_DATA_ERROR: i32 = -3; const Z_FINISH: i32 = 4;

pub fn inflate(strm: &mut InflateStream, flush: i32) -> i32 {
    if inflate_state_check(strm) { return Z_STREAM_ERROR; }
    if strm.state.mode == M_TYPE { strm.state.mode = M_TYPEDO; }
    let mut hold: u64 = strm.state.hold;
    let mut bits: u32 = strm.state.bits;
    let mut nin: usize = 0;
    let mut have: usize = strm.avail_in;
    let mut left: usize = strm.avail_out;
    let in0 = have; let out0 = left;
    let mut ret: i32 = Z_OK;
    // window start marker: where this call's output begins in next_out
    let out_begin = strm.next_out.len();

    'inf_leave: loop {
        match strm.state.mode {
            M_HEAD => {
                if strm.state.wrap == 0 { strm.state.mode = M_TYPEDO; continue; }
                // zlib header (wrap & 1)
                while bits < 16 { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                if ((( (hold & 0xff) << 8) + ((hold >> 8) & 0xff)) % 31) != 0 { strm.state.mode = M_BAD; continue; }
                if (hold & 0x0f) != 8 { strm.state.mode = M_BAD; continue; }
                let dictid = (hold >> 4) & 0x0f;
                if strm.state.wbits == 0 { strm.state.wbits = 8 + dictid as u32; }
                strm.adler = 1; strm.state.check = 1;
                hold = 0; bits = 0;
                strm.state.mode = M_TYPEDO;
                continue;
            }
            M_TYPE => { strm.state.mode = M_TYPEDO; continue; }
            M_TYPEDO => {
                if strm.state.last {
                    let r = bits & 7; hold >>= r; bits -= r;
                    strm.state.mode = M_CHECK; continue;
                }
                while bits < 3 { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                strm.state.last = (hold & 1) != 0; hold >>= 1; bits -= 1;
                match hold & 3 {
                    0 => { strm.state.mode = M_STORED; }
                    1 => { inflate_fixed(&mut strm.state); strm.state.mode = M_LEN_; }
                    2 => { strm.state.mode = M_TABLE; }
                    _ => { strm.state.mode = M_BAD; }
                }
                hold >>= 2; bits -= 2;
                continue;
            }
            M_STORED => {
                let r = bits & 7; hold >>= r; bits -= r;
                while bits < 32 { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                if (hold & 0xffff) != ((hold >> 16) ^ 0xffff) & 0xffff { strm.state.mode = M_BAD; continue; }
                strm.state.length = (hold & 0xffff) as u32;
                hold = 0; bits = 0;
                strm.state.mode = M_COPY_;
                continue;
            }
            M_COPY_ => { strm.state.mode = M_COPY; continue; }
            M_COPY => {
                let mut copy = strm.state.length as usize;
                if copy != 0 {
                    if copy > have { copy = have; }
                    if copy > left { copy = left; }
                    if copy == 0 { break 'inf_leave; }
                    for k in 0..copy { let b = strm.next_in[nin + k]; strm.next_out.push(b); }
                    nin += copy; have -= copy; left -= copy;
                    strm.state.length -= copy as u32;
                    continue;
                }
                strm.state.mode = M_TYPE;
                continue;
            }
            M_TABLE => {
                while bits < 14 { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                strm.state.nlen = ((hold & 0x1f) + 257) as u32; hold >>= 5; bits -= 5;
                strm.state.ndist = ((hold & 0x1f) + 1) as u32; hold >>= 5; bits -= 5;
                strm.state.ncode = ((hold & 0x0f) + 4) as u32; hold >>= 4; bits -= 4;
                if strm.state.nlen > 286 || strm.state.ndist > 30 { strm.state.mode = M_BAD; continue; }
                strm.state.have = 0;
                strm.state.mode = M_LENLENS; continue;
            }
            M_LENLENS => {
                if strm.state.codes_tbl.is_empty() { strm.state.codes_tbl = vec![zlib_types::CodeEntry::default(); 1444]; }
                if strm.state.lens.len() < 320 { strm.state.lens = vec![0u16; 320]; }
                if strm.state.work.len() < 288 { strm.state.work = vec![0u16; 288]; }
                while strm.state.have < strm.state.ncode {
                    while bits < 3 { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                    let oi = ORDER[strm.state.have as usize] as usize;
                    strm.state.lens[oi] = (hold & 7) as u16; strm.state.have += 1;
                    hold >>= 3; bits -= 3;
                }
                while strm.state.have < 19 { let oi = ORDER[strm.state.have as usize] as usize; strm.state.lens[oi] = 0; strm.state.have += 1; }
                strm.state.lencode_off = 0; strm.state.distcode_off = 0;
                let mut lenbits = 7u32;
                let lens = core::mem::take(&mut strm.state.lens);
                let mut work = core::mem::take(&mut strm.state.work);
                let r = inflate_table(zlib_types::CodeType::Codes, &lens[..19], 19, &mut strm.state.codes_tbl, &mut lenbits, &mut work);
                strm.state.lens = lens; strm.state.work = work; strm.state.lenbits = lenbits;
                match r { Ok(u) => strm.state.next_off = u as u32, Err(_) => { strm.state.mode = M_BAD; continue; } }
                strm.state.have = 0;
                strm.state.mode = M_CODELENS; continue;
            }
            M_CODELENS => {
                while strm.state.have < strm.state.nlen + strm.state.ndist {
                    let here;
                    loop {
                        let idx = strm.state.lencode_off as usize + (hold & ((1u64 << strm.state.lenbits) - 1)) as usize;
                        let h = strm.state.codes_tbl[idx];
                        if (h.bits as u32) <= bits { here = h; break; }
                        if have == 0 { break 'inf_leave; }
                        hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8;
                    }
                    if here.val < 16 {
                        hold >>= here.bits; bits -= here.bits as u32;
                        strm.state.lens[strm.state.have as usize] = here.val; strm.state.have += 1;
                    } else {
                        let mut copy; let cval;
                        if here.val == 16 {
                            while bits < (here.bits as u32 + 2) { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                            hold >>= here.bits; bits -= here.bits as u32;
                            if strm.state.have == 0 { strm.state.mode = M_BAD; break; }
                            cval = strm.state.lens[strm.state.have as usize - 1];
                            copy = 3 + (hold & 3) as u32; hold >>= 2; bits -= 2;
                        } else if here.val == 17 {
                            while bits < (here.bits as u32 + 3) { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                            hold >>= here.bits; bits -= here.bits as u32;
                            cval = 0; copy = 3 + (hold & 7) as u32; hold >>= 3; bits -= 3;
                        } else {
                            while bits < (here.bits as u32 + 7) { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                            hold >>= here.bits; bits -= here.bits as u32;
                            cval = 0; copy = 11 + (hold & 0x7f) as u32; hold >>= 7; bits -= 7;
                        }
                        if strm.state.have + copy > strm.state.nlen + strm.state.ndist { strm.state.mode = M_BAD; break; }
                        while copy > 0 { strm.state.lens[strm.state.have as usize] = cval; strm.state.have += 1; copy -= 1; }
                    }
                }
                if strm.state.mode == M_BAD { continue; }
                if strm.state.lens[256] == 0 { strm.state.mode = M_BAD; continue; }
                let mut lenbits = 9u32;
                let nlen = strm.state.nlen as usize; let ndist = strm.state.ndist as usize;
                let lens = core::mem::take(&mut strm.state.lens);
                let mut work = core::mem::take(&mut strm.state.work);
                let r1 = inflate_table(zlib_types::CodeType::Lens, &lens[..nlen], nlen, &mut strm.state.codes_tbl, &mut lenbits, &mut work);
                let used1 = match r1 { Ok(u) => u, Err(_) => { strm.state.lens = lens; strm.state.work = work; strm.state.mode = M_BAD; continue; } };
                strm.state.lencode_off = 0; strm.state.lenbits = lenbits; strm.state.distcode_off = used1 as u32;
                let mut distbits = 6u32;
                let r2 = inflate_table(zlib_types::CodeType::Dists, &lens[nlen..nlen+ndist], ndist, &mut strm.state.codes_tbl[used1..], &mut distbits, &mut work);
                strm.state.lens = lens; strm.state.work = work;
                if r2.is_err() { strm.state.mode = M_BAD; continue; }
                strm.state.distbits = distbits;
                strm.state.mode = M_LEN_; continue;
            }
            M_LEN_ => { strm.state.mode = M_LEN; continue; }
            M_LEN => {
                let mut here;
                loop {
                    let idx = strm.state.lencode_off as usize + (hold & ((1u64 << strm.state.lenbits) - 1)) as usize;
                    let h = strm.state.codes_tbl[idx];
                    if (h.bits as u32) <= bits { here = h; break; }
                    if have == 0 { break 'inf_leave; }
                    hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8;
                }
                if here.op != 0 && (here.op & 0xf0) == 0 {
                    let last = here;
                    loop {
                        let idx = strm.state.lencode_off as usize + last.val as usize + ((hold & ((1u64 << (last.bits + last.op)) - 1)) >> last.bits) as usize;
                        let h = strm.state.codes_tbl[idx];
                        if (last.bits as u32 + h.bits as u32) <= bits { here = h; break; }
                        if have == 0 { break 'inf_leave; }
                        hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8;
                    }
                    hold >>= last.bits; bits -= last.bits as u32;
                }
                hold >>= here.bits; bits -= here.bits as u32;
                strm.state.length = here.val as u32;
                if here.op == 0 { strm.state.mode = M_LIT; continue; }
                if here.op & 32 != 0 { strm.state.mode = M_TYPE; continue; }
                if here.op & 64 != 0 { strm.state.mode = M_BAD; continue; }
                strm.state.extra = (here.op & 15) as u32;
                strm.state.mode = M_LENEXT; continue;
            }
            M_LENEXT => {
                if strm.state.extra != 0 {
                    while bits < strm.state.extra { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                    strm.state.length += (hold & ((1u64 << strm.state.extra) - 1)) as u32; hold >>= strm.state.extra; bits -= strm.state.extra;
                }
                strm.state.mode = M_DIST; continue;
            }
            M_DIST => {
                let mut here;
                loop {
                    let idx = strm.state.distcode_off as usize + (hold & ((1u64 << strm.state.distbits) - 1)) as usize;
                    let h = strm.state.codes_tbl[idx];
                    if (h.bits as u32) <= bits { here = h; break; }
                    if have == 0 { break 'inf_leave; }
                    hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8;
                }
                if (here.op & 0xf0) == 0 {
                    let last = here;
                    loop {
                        let idx = strm.state.distcode_off as usize + last.val as usize + ((hold & ((1u64 << (last.bits + last.op)) - 1)) >> last.bits) as usize;
                        let h = strm.state.codes_tbl[idx];
                        if (last.bits as u32 + h.bits as u32) <= bits { here = h; break; }
                        if have == 0 { break 'inf_leave; }
                        hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8;
                    }
                    hold >>= last.bits; bits -= last.bits as u32;
                }
                hold >>= here.bits; bits -= here.bits as u32;
                if here.op & 64 != 0 { strm.state.mode = M_BAD; continue; }
                strm.state.offset = here.val as u32;
                strm.state.extra = (here.op & 15) as u32;
                strm.state.mode = M_DISTEXT; continue;
            }
            M_DISTEXT => {
                if strm.state.extra != 0 {
                    while bits < strm.state.extra { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                    strm.state.offset += (hold & ((1u64 << strm.state.extra) - 1)) as u32; hold >>= strm.state.extra; bits -= strm.state.extra;
                }
                strm.state.mode = M_MATCH; continue;
            }
            M_MATCH => {
                if left == 0 { break 'inf_leave; }
                let out_so_far = out0 - left;
                let offset = strm.state.offset as usize;
                let mut copy;
                let mut from_window = false;
                let mut win_idx = 0usize;
                if offset > out_so_far {
                    copy = offset - out_so_far;
                    if copy > strm.state.whave as usize { strm.state.mode = M_BAD; continue; }
                    from_window = true;
                    let wnext = strm.state.wnext as usize; let wsize = strm.state.wsize as usize;
                    if copy > wnext { copy -= wnext; win_idx = wsize - copy; } else { win_idx = wnext - copy; }
                    if copy > strm.state.length as usize { copy = strm.state.length as usize; }
                } else {
                    copy = strm.state.length as usize;
                }
                if copy > left { copy = left; }
                left -= copy;
                strm.state.length -= copy as u32;
                if from_window {
                    for k in 0..copy { let b = strm.state.window[win_idx + k]; strm.next_out.push(b); }
                } else {
                    for _ in 0..copy { let b = strm.next_out[strm.next_out.len() - offset]; strm.next_out.push(b); }
                }
                if strm.state.length == 0 { strm.state.mode = M_LEN; }
                continue;
            }
            M_LIT => {
                if left == 0 { break 'inf_leave; }
                strm.next_out.push(strm.state.length as u8); left -= 1;
                strm.state.mode = M_LEN; continue;
            }
            M_CHECK => {
                if strm.state.wrap != 0 {
                    while bits < 32 { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                    let outc = out0 - left;
                    strm.state.total += outc as u64;
                    let swapped = ((hold & 0xff) << 24) | ((hold & 0xff00) << 8) | ((hold >> 8) & 0xff00) | ((hold >> 24) & 0xff);
                    if (strm.state.wrap & 4) != 0 && outc != 0 {
                        let prod: Vec<u8> = strm.next_out[out_begin..out_begin + outc].to_vec();
                        strm.state.check = zlib_checksum::adler32_z(strm.state.check, &prod, prod.len());
                        strm.adler = strm.state.check;
                    }
                    if (strm.state.wrap & 4) != 0 && (swapped as u32) != strm.state.check { strm.state.mode = M_BAD; continue; }
                    hold = 0; bits = 0;
                }
                strm.state.mode = M_LENGTH;
                continue;
            }
            M_LENGTH => {
                if strm.state.wrap != 0 && strm.state.flags > 0 {
                    while bits < 32 { if have == 0 { break 'inf_leave; } hold |= (strm.next_in[nin] as u64) << bits; nin += 1; have -= 1; bits += 8; }
                    if (strm.state.wrap & 4) != 0 && (hold & 0xffffffff) as u64 != (strm.state.total & 0xffffffff) { strm.state.mode = M_BAD; continue; }
                    hold = 0; bits = 0;
                }
                strm.state.mode = M_DONE;
                continue;
            }
            M_DONE => { ret = Z_STREAM_END; break 'inf_leave; }
            M_BAD => { ret = Z_DATA_ERROR; break 'inf_leave; }
            M_MEM => { strm.avail_in = have; strm.state.hold = hold; strm.state.bits = bits; return -4; }
            _ => { return Z_STREAM_ERROR; }
        }
    }
    // inf_leave: RESTORE
    strm.next_in.drain(0..nin);
    strm.avail_in = have;
    strm.avail_out = left;
    strm.state.hold = hold;
    strm.state.bits = bits;
    let inc = in0 - have; let outc = out0 - left;
    // update window with produced output
    if strm.state.wsize != 0 || (outc != 0 && strm.state.mode < M_BAD) {
        let produced: Vec<u8> = strm.next_out[out_begin..].to_vec();
        updatewindow(&mut strm.state, &produced, outc);
    }
    strm.total_in += inc as u64;
    strm.total_out += outc as u64;
    strm.state.total += outc as u64;
    if ((inc == 0 && outc == 0) || flush == Z_FINISH) && ret == Z_OK { ret = Z_BUF_ERROR; }
    ret
}


#[cfg(test)]
mod tests {
    #![allow(unused_imports, unused_variables, unused_macros)]
    extern crate alloc;
    use alloc::format;
    use alloc::string::String;

    #[test]
    fn test_zlibrt_0() {
        let input: Vec<u8> = vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111];
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, 15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, 15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        let r = super::inflate(&mut s, 4);
        assert_eq!(s.next_out, input, "zlib rt 0");
        assert_eq!(r, 1, "zlib iret 0");
    }
    #[test]
    fn test_zlibrt_1() {
        let input: Vec<u8> = vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32];
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, 15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, 15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        let r = super::inflate(&mut s, 4);
        assert_eq!(s.next_out, input, "zlib rt 1");
        assert_eq!(r, 1, "zlib iret 1");
    }
    #[test]
    fn test_zlibrt_2() {
        let input: Vec<u8> = vec![130, 183, 14, 238, 127, 26, 80, 57, 190, 240, 126, 194, 52, 127, 6, 110, 208, 143, 93, 199, 81, 36, 71, 227, 64, 67, 0, 2, 107, 110, 84, 85, 148, 160, 101, 104, 93, 100, 196, 152, 11, 184, 212, 84, 74, 135, 33, 169, 154, 1, 173, 33, 158, 181, 156, 246, 161, 94, 246, 241, 90, 29, 131, 11, 183, 206, 9, 214, 187, 192, 4, 231, 23, 92, 100, 60, 125, 236, 176, 181, 128, 236, 55, 188, 151, 18, 221, 46, 106, 174, 185, 75, 174, 141, 47, 159, 162, 156, 90, 40, 76, 158, 247, 82, 24, 41, 207, 16, 121, 176, 128, 233, 215, 74, 28, 16, 252, 171, 106, 66, 67, 211, 54, 86, 222, 190, 76, 30, 215, 150, 72, 232, 86, 232, 249, 162, 245, 140, 149, 240, 206, 75, 57, 193, 91, 255, 173, 92, 45, 251, 139, 184, 32, 182, 17, 156, 186, 143, 248, 135, 150, 174, 91, 5, 242, 128, 166, 140, 237, 147, 182, 178, 140, 176, 209, 179, 88, 230, 186, 171, 72, 85, 101, 185, 244, 144, 40, 213, 87, 215, 154, 138, 14, 100, 81, 225, 92, 112, 92, 21, 241, 115, 84, 27, 68, 56, 162, 92, 247, 99, 18, 212, 238, 179, 194, 36, 104, 121, 191, 0, 179, 207, 142, 209, 58, 191, 18, 154, 48, 151, 173, 150, 180, 66, 214, 209, 189, 239, 72, 80, 195, 244, 101, 68, 46, 179, 0, 195, 55, 166, 72, 166, 192, 219, 221, 115, 252, 149, 245, 194, 196, 81, 133, 154, 254, 128, 212, 10, 163, 157, 251, 146, 73, 244, 12, 62, 227, 125, 150, 20, 69, 200, 6, 245, 140, 124, 242, 18, 125, 250, 137, 79, 146, 150, 252, 243, 60, 8, 64, 153];
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, 15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, 15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        let r = super::inflate(&mut s, 4);
        assert_eq!(s.next_out, input, "zlib rt 2");
        assert_eq!(r, 1, "zlib iret 2");
    }

    #[test]
    fn test_rt_0() {
        let input: Vec<u8> = vec![];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 1, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L1 0");
    }
    #[test]
    fn test_rt_1() {
        let input: Vec<u8> = vec![97];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 1, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L1 1");
    }
    #[test]
    fn test_rt_2() {
        let input: Vec<u8> = vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 1, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L1 2");
    }
    #[test]
    fn test_rt_3() {
        let input: Vec<u8> = vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 1, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L1 3");
    }
    #[test]
    fn test_rt_4() {
        let input: Vec<u8> = vec![129, 166, 101, 123, 98, 58, 149, 243, 121, 74, 1, 143, 14, 254, 88, 97, 198, 93, 169, 164, 60, 44, 133, 240, 104, 115, 98, 36, 41, 102, 224, 39, 51, 108, 168, 44, 48, 236, 40, 54, 139, 227, 62, 179, 28, 206, 126, 112, 241, 206, 70, 196, 6, 17, 26, 253, 20, 183, 221, 60, 131, 250, 28, 241, 48, 75, 152, 47, 8, 248, 180, 212, 0, 31, 246, 74, 13, 4, 122, 45, 238, 58, 199, 243, 52, 69, 122, 133, 107, 44, 82, 84, 76, 12, 25, 119, 194, 213, 250, 137, 52, 241, 212, 151, 141, 147, 232, 96, 9, 249, 36, 18, 9, 72, 4, 46, 55, 104, 42, 217, 84, 55, 196, 145, 235, 250, 205, 99, 219, 128, 145, 44, 165, 161, 99, 143, 188, 244, 201, 205, 130, 193, 158, 40, 140, 52, 74, 70, 184, 25, 108, 29, 11, 61, 65, 138, 82, 175, 30, 192, 44, 153, 40, 184, 232, 2, 24, 230, 76, 253, 207, 39, 220, 2, 56, 16, 192, 64, 19, 133, 130, 89, 44, 35, 23, 198, 36, 91, 246, 104, 165, 166, 240, 117, 97, 248, 223, 197, 100, 205, 49, 108, 157, 169, 173, 219, 97, 180, 109, 130, 181, 115, 80, 176, 74, 135, 228, 149, 154, 252, 122, 48, 245, 34, 142, 148, 88, 4, 151, 214, 221, 216, 204, 52, 225, 182, 242, 250, 195, 86, 197, 198, 219, 133, 12, 156, 145, 224, 226, 10, 39, 198, 169, 191, 136, 56, 179, 182, 74, 63, 228, 73, 84, 24, 252, 150, 175, 182, 47, 131, 70, 88, 168, 218, 12, 242, 51, 221, 118, 102, 18, 247, 54, 217, 11, 46, 15, 29, 183, 249, 239, 142, 207, 39, 99, 185, 118, 16, 84, 91, 109, 142, 179, 155, 26, 44, 96, 187, 230, 245, 125, 58, 245, 229, 196, 210, 236, 49, 189, 86, 62, 254, 119, 145, 160, 134, 168, 244, 187, 161, 117, 15, 22, 13, 127, 12, 216, 46, 105, 218, 116, 249, 126, 156, 169, 120, 59, 170, 250, 254, 92, 204, 247, 209, 77, 95, 15, 18, 25, 87, 8, 187, 251, 130, 239, 46, 143, 216, 49, 239, 18, 69, 188, 236, 93, 53, 83, 137, 151, 58, 188, 131, 7, 81, 148, 137, 226, 114, 211, 129, 174, 88, 3, 247, 95, 16, 15, 223, 197, 108];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 1, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L1 4");
    }
    #[test]
    fn test_rt_5() {
        let input: Vec<u8> = vec![109, 103, 99, 98, 101, 109, 98, 110, 102, 101, 100, 107, 106, 104, 100, 105, 101, 107, 103, 98, 99, 107, 109, 97, 98, 105, 106, 97, 99, 101, 103, 98, 104, 101, 106, 99, 100, 107, 110, 105, 99, 109, 104, 109, 98, 108, 102, 106, 108, 105, 100, 109, 108, 103, 103, 103, 108, 103, 97, 100, 100, 97, 106, 100, 103, 103, 98, 98, 105, 99, 105, 110, 106, 109, 102, 106, 105, 106, 105, 108, 99, 99, 101, 104, 108, 99, 98, 105, 98, 98, 97, 103, 109, 109, 109, 101, 103, 101, 99, 105, 100, 108, 104, 110, 97, 103, 110, 104, 103, 103, 101, 102, 110, 108, 107, 97, 110, 98, 100, 101, 97, 105, 106, 109, 98, 101, 110, 101, 98, 104, 109, 103, 100, 110, 103, 102, 98, 97, 101, 103, 102, 107, 101, 101, 97, 101, 108, 107, 101, 102, 98, 100, 107, 97, 104, 105, 104, 98, 108, 110, 102, 110, 103, 109, 107, 97, 108, 106, 109, 110, 103, 110, 101, 100, 107, 107, 110, 105, 108, 99, 106, 100, 97, 103, 104, 97, 103, 107, 103, 102, 106, 109, 101, 98, 97, 97, 105, 108, 110, 100, 103, 105, 110, 101, 97, 100, 103, 102, 104, 107, 110, 105, 102, 108, 103, 109, 110, 109, 105, 106, 97, 103, 107, 107, 110, 106, 103, 103, 100, 97, 106, 110, 110, 97, 98, 98, 109, 104, 101, 100, 102, 102, 101, 100, 104, 105, 109, 99, 102, 99, 109, 105, 102, 102, 106, 97, 99, 103, 99, 103, 103, 109, 103, 99, 97, 109, 106, 105, 98, 110, 109, 109, 105, 106, 108, 103, 99, 109, 109, 108, 100, 106, 105, 110, 99, 99, 103, 98, 107, 99, 105, 97, 108, 102, 100, 107, 109, 100, 103, 97, 107, 97, 110, 107, 106, 109, 108, 104, 110, 104, 105, 104, 104, 98, 97, 106, 101, 99, 104, 101, 97, 97, 98, 108, 106, 110, 99, 104, 98, 102, 101, 98, 108, 103, 97, 105, 106, 100, 99, 98, 98, 104, 102, 106, 98, 101, 101, 103, 104, 102, 101, 108, 98, 107, 108, 107, 110, 104, 104, 107, 98, 99, 110, 97, 101, 98, 97, 97, 102, 104, 103, 98, 105, 104, 100, 106, 100, 101, 107, 104, 105, 103, 102, 98, 105, 97, 108, 105, 99, 99, 99, 99, 105, 104, 105, 107, 100, 106, 98, 99, 110, 102, 100, 99, 102, 106, 101, 97, 103, 97, 103, 102, 102, 99, 98, 107, 110, 106, 106, 105, 100, 109, 109, 107, 97, 108, 102, 103, 109, 100, 109, 102, 98, 102, 102, 107, 97, 97, 106, 109, 110, 97, 97, 99, 105, 102, 97, 97, 110, 104, 99, 103, 107, 101, 107, 107, 99, 98, 101, 108, 104, 98, 101, 104, 107, 105, 109, 99, 107, 97, 110, 104, 103, 105, 108, 107, 98, 100, 104, 98, 110, 104, 99, 104, 102, 105, 101, 102, 99, 106, 104, 103, 104, 105, 104, 107, 107, 105, 105, 105];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 1, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L1 5");
    }
    #[test]
    fn test_rt_6() {
        let input: Vec<u8> = vec![97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 1, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L1 6");
    }
    #[test]
    fn test_rt_7() {
        let input: Vec<u8> = vec![];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L6 7");
    }
    #[test]
    fn test_rt_8() {
        let input: Vec<u8> = vec![97];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L6 8");
    }
    #[test]
    fn test_rt_9() {
        let input: Vec<u8> = vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L6 9");
    }
    #[test]
    fn test_rt_10() {
        let input: Vec<u8> = vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L6 10");
    }
    #[test]
    fn test_rt_11() {
        let input: Vec<u8> = vec![90, 223, 192, 157, 64, 242, 165, 118, 142, 230, 89, 248, 162, 11, 49, 147, 203, 119, 126, 219, 44, 244, 83, 7, 91, 65, 9, 170, 117, 239, 217, 198, 169, 84, 186, 75, 231, 230, 205, 2, 172, 6, 243, 149, 132, 183, 120, 254, 218, 34, 28, 102, 212, 106, 50, 219, 19, 121, 73, 24, 143, 233, 82, 40, 213, 40, 213, 4, 93, 141, 178, 62, 166, 181, 197, 72, 164, 166, 11, 223, 251, 36, 134, 214, 42, 151, 144, 54, 166, 52, 120, 7, 63, 106, 31, 251, 217, 150, 229, 235, 198, 49, 144, 232, 172, 115, 147, 73, 144, 114, 62, 68, 75, 217, 58, 179, 202, 255, 114, 208, 76, 151, 160, 43, 170, 14, 153, 28, 22, 94, 233, 103, 120, 69, 38, 82, 45, 0, 148, 163, 220, 173, 132, 115, 13, 94, 125, 50, 204, 165, 114, 86, 127, 9, 89, 123, 66, 28, 129, 81, 203, 98, 128, 182, 58, 237, 149, 36, 48, 151, 225, 4, 133, 99, 191, 206, 142, 218, 208, 22, 14, 4, 250, 12, 238, 15, 16, 57, 69, 241, 23, 80, 106, 244, 15, 86, 30, 154, 102, 132, 192, 232, 224, 16, 63, 47, 73, 37, 172, 172, 40, 66, 11, 44, 110, 12, 92, 238, 135, 139, 226, 190, 26, 49, 20, 42, 65, 34, 121, 206, 138, 144, 170, 232, 209, 205, 128, 206, 4, 142, 233, 0, 39, 101, 221, 135, 186, 44, 190, 162, 141, 163, 216, 85, 229, 54, 180, 71, 228, 223, 189, 1, 200, 129, 16, 16, 205, 194, 30, 5, 148, 61, 144, 130, 190, 135, 144, 191, 89, 1, 61, 61, 63, 183, 83, 13, 189, 189, 129, 76, 205, 61, 67, 156, 183, 196, 168, 245, 63, 0, 76, 33, 137, 184, 141, 150, 17, 237, 115, 86, 50, 228, 64, 234, 232, 44, 165, 54, 138, 72, 255, 14, 5, 188, 159, 246, 214, 28, 79, 154, 141, 68, 106, 211, 87, 35, 95, 115, 210, 112, 105, 91, 55, 160, 195, 170, 174, 255, 165, 151, 214, 133, 143, 196, 223, 103, 125, 16, 183, 158, 133, 242, 80, 7, 3, 67, 73, 164, 252, 142, 104, 14, 54, 249, 92, 203, 31, 213, 192, 134, 99, 0, 224, 122, 80, 43, 118, 215, 166, 43, 128, 91, 179, 213, 200, 68, 74, 61, 198, 195];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L6 11");
    }
    #[test]
    fn test_rt_12() {
        let input: Vec<u8> = vec![108, 108, 110, 102, 107, 98, 101, 103, 98, 107, 106, 98, 102, 97, 106, 98, 98, 99, 108, 100, 104, 110, 103, 102, 99, 109, 105, 108, 105, 97, 97, 98, 98, 101, 102, 103, 101, 104, 97, 110, 107, 100, 108, 105, 101, 109, 99, 103, 99, 108, 110, 109, 101, 101, 101, 100, 99, 107, 103, 100, 102, 98, 107, 104, 97, 107, 98, 110, 98, 100, 110, 100, 97, 106, 99, 109, 104, 102, 102, 106, 106, 98, 98, 109, 109, 102, 106, 105, 101, 99, 107, 100, 97, 103, 98, 108, 101, 97, 105, 108, 107, 99, 107, 100, 104, 101, 103, 110, 101, 110, 99, 105, 104, 110, 108, 107, 105, 99, 108, 110, 101, 98, 102, 99, 104, 109, 101, 108, 106, 109, 102, 101, 105, 103, 110, 106, 103, 98, 102, 101, 99, 98, 102, 102, 110, 100, 97, 102, 98, 107, 101, 98, 97, 102, 97, 98, 105, 105, 104, 103, 108, 104, 101, 106, 105, 98, 104, 110, 98, 105, 104, 106, 98, 110, 104, 109, 108, 109, 97, 98, 103, 108, 101, 97, 106, 98, 110, 98, 107, 99, 99, 108, 97, 105, 99, 103, 106, 99, 103, 98, 100, 101, 103, 99, 107, 108, 109, 107, 107, 100, 99, 102, 97, 110, 98, 104, 97, 107, 110, 109, 108, 106, 106, 102, 102, 99, 104, 101, 103, 104, 107, 97, 107, 100, 97, 105, 110, 100, 107, 99, 105, 98, 104, 110, 101, 100, 98, 101, 101, 106, 97, 105, 97, 102, 107, 106, 105, 109, 108, 110, 97, 101, 104, 110, 103, 101, 108, 104, 103, 98, 98, 107, 99, 107, 108, 109, 110, 106, 99, 105, 98, 97, 106, 105, 107, 101, 110, 102, 110, 103, 105, 108, 105, 104, 97, 101, 101, 100, 106, 97, 101, 106, 100, 103, 98, 99, 107, 106, 104, 104, 106, 110, 104, 97, 100, 97, 102, 100, 107, 107, 97, 105, 103, 109, 102, 104, 110, 110, 101, 106, 100, 100, 108, 109, 103, 108, 100, 97, 99, 101, 100, 106, 107, 100, 101, 99, 100, 110, 110, 102, 100, 97, 103, 104, 108, 98, 108, 102, 108, 109, 97, 107, 105, 108, 110, 108, 110, 102, 100, 97, 98, 108, 100, 105, 108, 104, 106, 110, 106, 99, 99, 104, 101, 99, 104, 106, 101, 105, 100, 109, 109, 101, 97, 102, 101, 109, 101, 109, 103, 107, 108, 100, 102, 100, 110, 100, 99, 108, 105, 106, 97, 108, 97, 106, 109, 101, 107, 104, 108, 102, 99, 107, 104, 105, 107, 108, 105, 102, 101, 105, 97, 97, 98, 108, 99, 99, 98, 100, 100, 101, 107, 104, 110, 105, 106, 109, 105, 107, 104, 99, 102, 101, 107, 103, 102, 105, 109, 104, 104, 109, 101, 99, 98, 100, 97, 106, 103, 103, 106, 105, 107, 104, 101, 103, 102, 105, 109, 105, 104, 100, 101, 101, 104, 103, 106, 104, 104, 99, 104, 103, 99, 100, 109, 102, 105, 105, 102, 100, 110, 99];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L6 12");
    }
    #[test]
    fn test_rt_13() {
        let input: Vec<u8> = vec![97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 6, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L6 13");
    }
    #[test]
    fn test_rt_14() {
        let input: Vec<u8> = vec![];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 9, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L9 14");
    }
    #[test]
    fn test_rt_15() {
        let input: Vec<u8> = vec![97];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 9, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L9 15");
    }
    #[test]
    fn test_rt_16() {
        let input: Vec<u8> = vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 9, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L9 16");
    }
    #[test]
    fn test_rt_17() {
        let input: Vec<u8> = vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 46, 32];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 9, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L9 17");
    }
    #[test]
    fn test_rt_18() {
        let input: Vec<u8> = vec![18, 164, 117, 163, 137, 3, 105, 139, 178, 204, 19, 109, 45, 68, 148, 47, 234, 185, 28, 14, 196, 243, 115, 225, 50, 17, 238, 66, 189, 30, 45, 55, 11, 231, 216, 133, 228, 122, 151, 2, 143, 239, 234, 125, 221, 104, 140, 188, 218, 169, 185, 131, 146, 60, 21, 61, 169, 175, 130, 20, 253, 105, 120, 83, 225, 110, 146, 66, 61, 11, 67, 70, 233, 203, 196, 185, 87, 1, 209, 44, 231, 48, 244, 120, 189, 222, 47, 214, 13, 0, 205, 131, 165, 219, 217, 212, 68, 208, 157, 144, 164, 216, 141, 96, 11, 251, 205, 54, 235, 151, 143, 99, 65, 101, 176, 137, 50, 250, 71, 162, 241, 21, 172, 202, 194, 72, 166, 58, 239, 94, 194, 58, 182, 129, 210, 247, 217, 100, 208, 144, 134, 241, 124, 136, 132, 196, 220, 228, 110, 20, 193, 222, 135, 4, 235, 16, 67, 152, 174, 65, 71, 195, 97, 216, 153, 13, 93, 13, 225, 212, 87, 104, 206, 22, 55, 222, 3, 172, 137, 60, 99, 134, 39, 81, 30, 91, 62, 15, 5, 0, 242, 80, 126, 85, 137, 69, 245, 124, 26, 164, 160, 188, 169, 88, 241, 45, 249, 231, 154, 253, 200, 20, 57, 139, 203, 180, 200, 148, 17, 198, 168, 170, 250, 223, 78, 75, 175, 186, 4, 111, 73, 21, 193, 133, 221, 118, 67, 35, 18, 85, 202, 187, 245, 147, 27, 15, 10, 124, 45, 108, 70, 240, 221, 82, 58, 25, 185, 135, 207, 33, 109, 39, 159, 235, 124, 44, 201, 175, 14, 191, 94, 102, 138, 185, 90, 80, 207, 221, 187, 190, 72, 252, 100, 203, 74, 37, 199, 15, 44, 99, 114, 250, 45, 3, 125, 90, 10, 117, 219, 175, 56, 97, 14, 154, 164, 118, 178, 26, 93, 14, 19, 88, 207, 166, 178, 246, 225, 166, 20, 195, 233, 52, 14, 94, 69, 105, 16, 242, 64, 154, 247, 158, 42, 158, 48, 151, 68, 39, 56, 149, 144, 215, 46, 137, 231, 238, 76, 169, 37, 165, 56, 58, 7, 76, 132, 251, 28, 22, 195, 233, 46, 135, 97, 6, 224, 137, 59, 89, 228, 47, 91, 222, 88, 19, 3, 6, 175, 3, 186, 12, 204, 120, 120, 8, 2, 142, 234, 187, 95, 196, 170, 30, 157, 192, 239, 223, 225, 36, 159, 76];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 9, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L9 18");
    }
    #[test]
    fn test_rt_19() {
        let input: Vec<u8> = vec![110, 98, 108, 98, 99, 105, 99, 100, 107, 110, 108, 103, 99, 102, 107, 104, 102, 105, 103, 101, 97, 101, 108, 100, 105, 101, 107, 110, 99, 98, 100, 110, 109, 105, 109, 97, 98, 105, 107, 109, 106, 103, 102, 105, 101, 109, 102, 104, 107, 97, 104, 110, 99, 107, 101, 105, 107, 99, 106, 103, 99, 107, 99, 102, 108, 107, 97, 106, 108, 99, 109, 103, 106, 109, 109, 97, 106, 97, 107, 108, 104, 109, 99, 100, 105, 106, 107, 100, 109, 104, 109, 106, 107, 108, 110, 109, 108, 108, 103, 97, 100, 104, 106, 100, 106, 105, 108, 105, 110, 103, 110, 106, 100, 104, 97, 104, 110, 99, 105, 110, 103, 99, 108, 110, 99, 103, 106, 97, 104, 97, 100, 102, 102, 102, 106, 104, 101, 110, 100, 109, 104, 105, 101, 99, 102, 99, 98, 110, 99, 103, 102, 97, 103, 104, 110, 107, 97, 97, 98, 101, 101, 108, 98, 104, 99, 98, 106, 103, 99, 103, 102, 103, 108, 110, 105, 102, 103, 101, 107, 109, 105, 100, 108, 100, 106, 107, 100, 100, 102, 98, 109, 99, 100, 107, 106, 101, 99, 98, 99, 110, 99, 106, 108, 106, 106, 100, 99, 102, 106, 100, 109, 99, 100, 107, 100, 99, 100, 106, 100, 105, 105, 108, 109, 105, 102, 102, 109, 103, 108, 102, 103, 101, 103, 100, 105, 99, 110, 107, 104, 104, 109, 98, 108, 100, 104, 106, 102, 100, 99, 104, 107, 98, 103, 100, 101, 102, 108, 99, 110, 108, 102, 99, 110, 110, 99, 105, 99, 108, 99, 109, 98, 109, 98, 104, 98, 106, 103, 100, 107, 101, 104, 98, 106, 98, 100, 106, 105, 105, 107, 109, 108, 102, 104, 108, 106, 107, 101, 107, 98, 106, 100, 100, 98, 105, 104, 100, 110, 104, 103, 102, 99, 100, 108, 104, 104, 104, 102, 108, 100, 107, 100, 98, 97, 98, 105, 107, 107, 107, 107, 99, 97, 106, 104, 101, 109, 103, 109, 109, 104, 99, 105, 105, 100, 102, 98, 106, 103, 108, 107, 99, 109, 104, 98, 103, 101, 108, 99, 106, 110, 97, 106, 101, 101, 104, 98, 99, 104, 99, 103, 104, 99, 105, 102, 107, 108, 110, 110, 99, 104, 103, 100, 99, 101, 101, 102, 107, 109, 109, 103, 103, 101, 101, 101, 110, 104, 97, 102, 107, 110, 106, 99, 107, 110, 110, 106, 107, 99, 104, 101, 104, 107, 99, 99, 106, 99, 108, 99, 102, 101, 102, 102, 101, 103, 108, 101, 97, 97, 107, 108, 98, 105, 101, 107, 97, 102, 99, 110, 99, 108, 99, 103, 104, 97, 104, 107, 104, 102, 98, 106, 106, 101, 100, 109, 97, 109, 107, 103, 108, 103, 107, 105, 98, 110, 110, 106, 107, 102, 97, 108, 99, 101, 109, 99, 100, 104, 103, 105, 108, 109, 104, 103, 109, 101, 99, 106, 108, 105, 109, 101, 104, 100, 101, 109, 110, 103, 97, 107, 104, 100, 98];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 9, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L9 19");
    }
    #[test]
    fn test_rt_20() {
        let input: Vec<u8> = vec![97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99];
        // Rust deflate
        let mut d = zlib_types::DeflateStream::default();
        zlib_deflate::deflate_init2(&mut d, 9, 8, -15, 8, 0);
        d.next_in = input.clone(); d.avail_in = input.len(); d.next_out = vec![]; d.avail_out = 4000000;
        assert_eq!(zlib_deflate::deflate(&mut d, 4), 1, "dret");
        let comp = d.next_out;
        // Rust inflate
        let mut s = zlib_types::InflateStream::default();
        super::inflate_init2(&mut s, -15);
        s.next_in = comp.clone(); s.avail_in = comp.len(); s.next_out = vec![]; s.avail_out = 4000000;
        assert_eq!(super::inflate(&mut s, 4), 1, "iret");
        assert_eq!(s.next_out, input, "roundtrip L9 20");
    }

    #[test]
    fn test_ihuff_huff_0() {
        let comp: Vec<u8> = vec![203, 72, 205, 201, 201, 87, 40, 207, 47, 202, 73, 81, 200, 72, 205, 201, 201, 87, 40, 207, 47, 202, 73, 81, 200, 72, 205, 201, 201, 7, 0];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111], "ihuff 0");
    }
    #[test]
    fn test_ihuff_huff_1() {
        let comp: Vec<u8> = vec![5, 193, 9, 1, 128, 32, 16, 0, 193, 42, 155, 128, 52, 22, 16, 61, 64, 124, 14, 249, 68, 211, 59, 51, 5, 225, 110, 219, 178, 99, 179, 62, 23, 78, 7, 177, 157, 169, 160, 93, 50, 53, 8, 199, 252, 189, 172, 234, 13, 83, 16, 238, 182, 45, 59, 54, 235, 115, 225, 116, 16, 219, 153, 10, 218, 37, 83, 131, 112, 204, 223, 203, 170, 222, 48, 5, 225, 110, 219, 178, 99, 179, 62, 23, 78, 7, 177, 157, 169, 160, 93, 50, 53, 8, 199, 252, 189, 172, 234, 13, 83, 16, 238, 182, 45, 59, 54, 235, 115, 225, 116, 16, 219, 153, 10, 218, 37, 83, 131, 112, 204, 223, 203, 170, 222, 240, 3];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32], "ihuff 1");
    }
    #[test]
    fn test_ihuff_huff_2() {
        let comp: Vec<u8> = vec![5, 193, 139, 2, 4, 17, 8, 0, 192, 111, 93, 54, 138, 214, 35, 162, 235, 235, 111, 134, 202, 57, 158, 20, 15, 160, 90, 130, 40, 217, 202, 211, 224, 236, 135, 32, 186, 59, 117, 107, 224, 196, 56, 126, 178, 218, 225, 166, 85, 95, 222, 174, 116, 187, 108, 131, 126, 172, 75, 42, 57, 77, 38, 238, 180, 233, 131, 53, 4, 23, 230, 203, 16, 155, 106, 255, 30, 107, 1, 97, 248, 237, 74, 201, 154, 209, 207, 57, 95, 229, 121, 15, 220, 141, 54, 242, 14, 235, 174, 192, 203, 86, 77, 37, 39, 63, 242, 98, 138, 77, 183, 184, 220, 208, 171, 198, 249, 64, 121, 91, 161, 181, 111, 28, 147, 195, 83, 43, 12, 145, 57, 240, 228, 226, 225, 155, 127];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![105, 106, 118, 118, 122, 102, 117, 104, 118, 101, 104, 117, 120, 102, 101, 99, 114, 103, 120, 106, 97, 110, 101, 118, 116, 97, 105, 101, 99, 122, 122, 122, 105, 111, 120, 110, 101, 122, 105, 108, 104, 112, 121, 114, 115, 110, 118, 108, 110, 117, 107, 117, 100, 108, 116, 122, 117, 105, 119, 111, 114, 116, 120, 101, 111, 118, 120, 111, 114, 102, 106, 103, 102, 113, 108, 105, 108, 111, 105, 116, 105, 109, 101, 115, 112, 114, 104, 115, 104, 103, 119, 108, 101, 99, 110, 117, 117, 111, 109, 97, 120, 110, 98, 104, 101, 112, 122, 119, 111, 117, 105, 102, 120, 110, 120, 105, 121, 122, 108, 103, 119, 117, 108, 113, 119, 118, 101, 119, 116, 104, 120, 112, 103, 116, 98, 115, 119, 115, 98, 108, 115, 120, 115, 107, 102, 106, 103, 102, 122, 118, 114, 100, 104, 102, 99, 110, 117, 116, 114, 122, 114, 119, 98, 111, 107, 117, 99, 113, 97, 101, 106, 100, 110, 106, 105, 115, 116, 119, 99, 112, 113, 108, 98, 97, 107, 107, 101, 112, 114, 114, 113, 112, 104, 118, 103, 106, 122, 98, 109, 113], "ihuff 2");
    }
    #[test]
    fn test_ihuff_huff_3() {
        let comp: Vec<u8> = vec![5, 193, 1, 1, 0, 0, 0, 64, 160, 173, 248, 255, 65, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 97, 24, 134, 13];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99], "ihuff 3");
    }
    #[test]
    fn test_ihuff_huff_4() {
        let comp: Vec<u8> = vec![1, 44, 1, 211, 254, 80, 74, 132, 217, 110, 132, 217, 120, 182, 125, 147, 219, 104, 179, 217, 19, 162, 203, 235, 44, 35, 23, 2, 156, 97, 230, 246, 199, 170, 31, 148, 222, 70, 75, 26, 57, 188, 80, 111, 157, 155, 198, 148, 17, 177, 65, 51, 184, 251, 226, 222, 22, 179, 151, 66, 25, 165, 85, 64, 2, 127, 76, 45, 245, 190, 36, 176, 135, 109, 24, 121, 122, 225, 99, 201, 27, 26, 59, 70, 189, 203, 153, 76, 152, 133, 44, 190, 26, 15, 85, 7, 54, 138, 46, 170, 217, 82, 148, 20, 56, 48, 157, 207, 198, 241, 199, 137, 77, 76, 230, 154, 1, 14, 132, 141, 169, 115, 126, 191, 213, 80, 247, 209, 133, 79, 236, 237, 99, 192, 243, 97, 14, 17, 246, 91, 64, 52, 2, 68, 157, 41, 254, 28, 109, 219, 13, 11, 73, 152, 78, 27, 219, 131, 115, 249, 11, 48, 124, 161, 4, 230, 174, 112, 26, 218, 120, 6, 51, 188, 75, 238, 180, 68, 176, 116, 145, 47, 131, 68, 64, 91, 53, 28, 72, 13, 236, 182, 195, 255, 211, 34, 227, 143, 173, 194, 63, 105, 167, 192, 39, 244, 212, 153, 13, 229, 199, 210, 246, 31, 40, 128, 110, 1, 74, 166, 153, 106, 220, 150, 5, 104, 45, 57, 65, 34, 197, 108, 160, 81, 8, 81, 94, 25, 28, 118, 223, 91, 209, 41, 249, 79, 57, 27, 178, 26, 89, 46, 218, 156, 215, 152, 125, 134, 144, 213, 144, 143, 108, 49, 43, 82, 24, 61, 130, 76, 112, 156, 51, 52, 252, 226, 53, 23, 215, 70, 244, 119, 244, 169, 186, 63, 1, 250, 45, 51, 137, 229, 7, 215, 71, 0, 71, 124, 178, 77, 219, 223, 9, 182, 185];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![80, 74, 132, 217, 110, 132, 217, 120, 182, 125, 147, 219, 104, 179, 217, 19, 162, 203, 235, 44, 35, 23, 2, 156, 97, 230, 246, 199, 170, 31, 148, 222, 70, 75, 26, 57, 188, 80, 111, 157, 155, 198, 148, 17, 177, 65, 51, 184, 251, 226, 222, 22, 179, 151, 66, 25, 165, 85, 64, 2, 127, 76, 45, 245, 190, 36, 176, 135, 109, 24, 121, 122, 225, 99, 201, 27, 26, 59, 70, 189, 203, 153, 76, 152, 133, 44, 190, 26, 15, 85, 7, 54, 138, 46, 170, 217, 82, 148, 20, 56, 48, 157, 207, 198, 241, 199, 137, 77, 76, 230, 154, 1, 14, 132, 141, 169, 115, 126, 191, 213, 80, 247, 209, 133, 79, 236, 237, 99, 192, 243, 97, 14, 17, 246, 91, 64, 52, 2, 68, 157, 41, 254, 28, 109, 219, 13, 11, 73, 152, 78, 27, 219, 131, 115, 249, 11, 48, 124, 161, 4, 230, 174, 112, 26, 218, 120, 6, 51, 188, 75, 238, 180, 68, 176, 116, 145, 47, 131, 68, 64, 91, 53, 28, 72, 13, 236, 182, 195, 255, 211, 34, 227, 143, 173, 194, 63, 105, 167, 192, 39, 244, 212, 153, 13, 229, 199, 210, 246, 31, 40, 128, 110, 1, 74, 166, 153, 106, 220, 150, 5, 104, 45, 57, 65, 34, 197, 108, 160, 81, 8, 81, 94, 25, 28, 118, 223, 91, 209, 41, 249, 79, 57, 27, 178, 26, 89, 46, 218, 156, 215, 152, 125, 134, 144, 213, 144, 143, 108, 49, 43, 82, 24, 61, 130, 76, 112, 156, 51, 52, 252, 226, 53, 23, 215, 70, 244, 119, 244, 169, 186, 63, 1, 250, 45, 51, 137, 229, 7, 215, 71, 0, 71, 124, 178, 77, 219, 223, 9, 182, 185], "ihuff 4");
    }
    #[test]
    fn test_ihuff_deflt_5() {
        let comp: Vec<u8> = vec![203, 72, 205, 201, 201, 87, 40, 207, 47, 202, 73, 81, 200, 64, 103, 3, 0];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111], "ideflt 5");
    }
    #[test]
    fn test_ihuff_deflt_6() {
        let comp: Vec<u8> = vec![11, 201, 72, 85, 40, 44, 205, 76, 206, 86, 72, 42, 202, 47, 207, 83, 72, 203, 175, 80, 200, 42, 205, 45, 40, 86, 200, 47, 75, 45, 82, 40, 1, 74, 231, 36, 86, 85, 42, 164, 228, 167, 235, 41, 132, 12, 14, 197, 0];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32], "ideflt 6");
    }
    #[test]
    fn test_ihuff_deflt_7() {
        let comp: Vec<u8> = vec![13, 205, 71, 2, 196, 32, 8, 0, 192, 183, 138, 34, 166, 80, 108, 17, 125, 253, 238, 113, 78, 243, 236, 215, 41, 161, 231, 158, 167, 192, 25, 178, 147, 73, 35, 28, 124, 2, 31, 126, 132, 239, 216, 10, 231, 177, 27, 28, 213, 212, 118, 117, 117, 252, 171, 57, 133, 34, 96, 151, 192, 126, 201, 149, 71, 214, 77, 178, 59, 3, 115, 57, 159, 83, 23, 2, 88, 65, 171, 127, 131, 185, 162, 70, 179, 62, 53, 182, 186, 106, 128, 117, 108, 230, 226, 41, 200, 106, 164, 6, 2, 116, 249, 177, 138, 136, 199, 67, 238, 241, 206, 203, 232, 179, 48, 86, 137, 186, 83, 244, 17, 185, 174, 76, 29, 60, 240, 248, 143, 223, 121, 80, 231, 152, 59, 99, 249, 1];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![107, 121, 108, 120, 103, 100, 101, 120, 102, 115, 102, 117, 110, 98, 122, 116, 110, 121, 100, 112, 110, 114, 103, 101, 116, 109, 122, 97, 109, 122, 109, 107, 110, 109, 106, 99, 114, 104, 109, 102, 116, 121, 114, 98, 122, 111, 111, 100, 114, 121, 113, 120, 111, 120, 101, 121, 114, 98, 114, 120, 103, 97, 104, 110, 98, 112, 105, 110, 98, 121, 108, 103, 120, 111, 109, 116, 102, 111, 121, 103, 110, 121, 115, 109, 98, 109, 109, 104, 122, 118, 120, 103, 115, 110, 103, 98, 98, 119, 97, 111, 113, 120, 118, 116, 109, 109, 113, 101, 111, 99, 112, 112, 115, 117, 111, 99, 114, 113, 119, 113, 97, 98, 119, 122, 112, 117, 102, 104, 120, 100, 97, 110, 119, 114, 103, 111, 112, 98, 110, 98, 103, 105, 120, 122, 112, 113, 101, 101, 101, 122, 120, 97, 102, 115, 99, 106, 102, 119, 112, 103, 118, 112, 97, 116, 119, 104, 99, 111, 121, 100, 99, 120, 116, 99, 109, 113, 119, 102, 103, 115, 98, 120, 97, 109, 116, 103, 120, 111, 118, 122, 107, 101, 111, 117, 116, 117, 121, 102, 101, 104], "ideflt 7");
    }
    #[test]
    fn test_ihuff_deflt_8() {
        let comp: Vec<u8> = vec![75, 76, 74, 78, 28, 106, 8, 0];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99], "ideflt 8");
    }
    #[test]
    fn test_ihuff_deflt_9() {
        let comp: Vec<u8> = vec![1, 44, 1, 211, 254, 39, 219, 86, 204, 211, 125, 158, 146, 231, 3, 54, 226, 234, 120, 94, 135, 10, 237, 111, 141, 0, 65, 216, 169, 123, 225, 9, 204, 138, 51, 70, 18, 168, 226, 14, 36, 38, 56, 186, 43, 90, 248, 239, 0, 238, 9, 173, 176, 40, 208, 209, 42, 107, 174, 79, 60, 79, 38, 198, 149, 253, 146, 213, 101, 254, 99, 52, 196, 154, 23, 39, 156, 231, 101, 241, 4, 24, 218, 36, 242, 156, 107, 62, 165, 5, 154, 241, 10, 84, 168, 19, 149, 220, 0, 216, 68, 216, 25, 189, 78, 85, 186, 196, 127, 153, 245, 105, 11, 49, 160, 86, 28, 126, 112, 144, 182, 204, 146, 5, 7, 97, 132, 33, 123, 70, 53, 213, 201, 226, 150, 161, 130, 33, 216, 145, 116, 222, 62, 246, 125, 53, 34, 105, 59, 170, 111, 86, 46, 177, 204, 126, 97, 163, 63, 40, 167, 210, 239, 215, 198, 204, 38, 187, 211, 91, 133, 151, 192, 245, 34, 74, 33, 180, 6, 170, 182, 213, 212, 198, 80, 55, 109, 203, 53, 105, 63, 202, 209, 250, 105, 206, 36, 138, 229, 224, 3, 187, 97, 145, 254, 140, 92, 191, 147, 172, 134, 93, 22, 161, 44, 75, 118, 132, 150, 187, 15, 244, 45, 90, 194, 237, 216, 179, 212, 50, 10, 133, 90, 122, 35, 4, 8, 54, 212, 121, 88, 104, 232, 95, 169, 54, 221, 40, 61, 216, 204, 27, 228, 150, 32, 159, 130, 104, 57, 245, 37, 239, 18, 150, 226, 86, 187, 254, 101, 132, 239, 212, 162, 137, 192, 78, 165, 16, 42, 250, 106, 217, 149, 176, 218, 104, 198, 25, 245, 208, 5, 169, 142, 156, 39, 217, 41, 27, 156, 123, 107, 37, 225, 10, 65];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "iret");
        assert_eq!(strm.next_out, vec![39, 219, 86, 204, 211, 125, 158, 146, 231, 3, 54, 226, 234, 120, 94, 135, 10, 237, 111, 141, 0, 65, 216, 169, 123, 225, 9, 204, 138, 51, 70, 18, 168, 226, 14, 36, 38, 56, 186, 43, 90, 248, 239, 0, 238, 9, 173, 176, 40, 208, 209, 42, 107, 174, 79, 60, 79, 38, 198, 149, 253, 146, 213, 101, 254, 99, 52, 196, 154, 23, 39, 156, 231, 101, 241, 4, 24, 218, 36, 242, 156, 107, 62, 165, 5, 154, 241, 10, 84, 168, 19, 149, 220, 0, 216, 68, 216, 25, 189, 78, 85, 186, 196, 127, 153, 245, 105, 11, 49, 160, 86, 28, 126, 112, 144, 182, 204, 146, 5, 7, 97, 132, 33, 123, 70, 53, 213, 201, 226, 150, 161, 130, 33, 216, 145, 116, 222, 62, 246, 125, 53, 34, 105, 59, 170, 111, 86, 46, 177, 204, 126, 97, 163, 63, 40, 167, 210, 239, 215, 198, 204, 38, 187, 211, 91, 133, 151, 192, 245, 34, 74, 33, 180, 6, 170, 182, 213, 212, 198, 80, 55, 109, 203, 53, 105, 63, 202, 209, 250, 105, 206, 36, 138, 229, 224, 3, 187, 97, 145, 254, 140, 92, 191, 147, 172, 134, 93, 22, 161, 44, 75, 118, 132, 150, 187, 15, 244, 45, 90, 194, 237, 216, 179, 212, 50, 10, 133, 90, 122, 35, 4, 8, 54, 212, 121, 88, 104, 232, 95, 169, 54, 221, 40, 61, 216, 204, 27, 228, 150, 32, 159, 130, 104, 57, 245, 37, 239, 18, 150, 226, 86, 187, 254, 101, 132, 239, 212, 162, 137, 192, 78, 165, 16, 42, 250, 106, 217, 149, 176, 218, 104, 198, 25, 245, 208, 5, 169, 142, 156, 39, 217, 41, 27, 156, 123, 107, 37, 225, 10, 65], "ideflt 9");
    }

    #[test]
    fn test_inf_stored_0() {
        let comp: Vec<u8> = vec![1, 0, 0, 255, 255];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "inf ret 0");
        assert_eq!(strm.next_out, vec![], "inf stored 0");
    }
    #[test]
    fn test_inf_stored_1() {
        let comp: Vec<u8> = vec![1, 1, 0, 254, 255, 97];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "inf ret 1");
        assert_eq!(strm.next_out, vec![97], "inf stored 1");
    }
    #[test]
    fn test_inf_stored_2() {
        let comp: Vec<u8> = vec![1, 11, 0, 244, 255, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "inf ret 2");
        assert_eq!(strm.next_out, vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100], "inf stored 2");
    }
    #[test]
    fn test_inf_stored_3() {
        let comp: Vec<u8> = vec![1, 200, 0, 55, 255, 121, 66, 189, 242, 33, 6, 240, 132, 119, 98, 240, 243, 203, 77, 118, 77, 199, 7, 32, 81, 21, 154, 15, 137, 242, 198, 218, 202, 227, 68, 187, 49, 18, 69, 253, 111, 132, 223, 154, 215, 197, 179, 208, 118, 172, 14, 143, 83, 167, 53, 108, 136, 145, 63, 32, 246, 247, 45, 176, 34, 210, 77, 10, 150, 218, 212, 60, 22, 23, 193, 169, 142, 120, 18, 158, 3, 39, 55, 16, 101, 208, 149, 134, 79, 21, 173, 160, 184, 70, 193, 192, 235, 197, 52, 138, 220, 121, 154, 223, 132, 155, 173, 5, 212, 161, 10, 192, 68, 30, 170, 238, 180, 180, 142, 250, 11, 31, 10, 189, 128, 233, 152, 163, 90, 186, 94, 160, 189, 135, 153, 193, 53, 13, 67, 158, 113, 137, 122, 167, 95, 222, 49, 52, 164, 170, 114, 224, 86, 40, 172, 111, 230, 138, 115, 61, 17, 97, 161, 93, 142, 174, 43, 176, 66, 215, 149, 138, 237, 177, 213, 148, 214, 209, 18, 211, 79, 102, 2, 244, 222, 113, 16, 233, 147, 174, 116, 34, 146, 61, 125, 23, 17, 101, 220, 25, 6, 246, 61, 87, 153];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "inf ret 3");
        assert_eq!(strm.next_out, vec![121, 66, 189, 242, 33, 6, 240, 132, 119, 98, 240, 243, 203, 77, 118, 77, 199, 7, 32, 81, 21, 154, 15, 137, 242, 198, 218, 202, 227, 68, 187, 49, 18, 69, 253, 111, 132, 223, 154, 215, 197, 179, 208, 118, 172, 14, 143, 83, 167, 53, 108, 136, 145, 63, 32, 246, 247, 45, 176, 34, 210, 77, 10, 150, 218, 212, 60, 22, 23, 193, 169, 142, 120, 18, 158, 3, 39, 55, 16, 101, 208, 149, 134, 79, 21, 173, 160, 184, 70, 193, 192, 235, 197, 52, 138, 220, 121, 154, 223, 132, 155, 173, 5, 212, 161, 10, 192, 68, 30, 170, 238, 180, 180, 142, 250, 11, 31, 10, 189, 128, 233, 152, 163, 90, 186, 94, 160, 189, 135, 153, 193, 53, 13, 67, 158, 113, 137, 122, 167, 95, 222, 49, 52, 164, 170, 114, 224, 86, 40, 172, 111, 230, 138, 115, 61, 17, 97, 161, 93, 142, 174, 43, 176, 66, 215, 149, 138, 237, 177, 213, 148, 214, 209, 18, 211, 79, 102, 2, 244, 222, 113, 16, 233, 147, 174, 116, 34, 146, 61, 125, 23, 17, 101, 220, 25, 6, 246, 61, 87, 153], "inf stored 3");
    }
    #[test]
    fn test_inf_stored_4() {
        let comp: Vec<u8> = vec![1, 180, 0, 75, 255, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32];
        let mut strm = zlib_types::InflateStream::default();
        super::inflate_init2(&mut strm, -15);
        strm.next_in = comp.clone(); strm.avail_in = comp.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::inflate(&mut strm, 4);
        assert_eq!(r, 1, "inf ret 4");
        assert_eq!(strm.next_out, vec![115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32, 115, 116, 111, 114, 101, 100, 32, 98, 108, 111, 99, 107, 32, 116, 101, 115, 116, 32], "inf stored 4");
    }

    #[test]
    fn test_inflate_table_body_0() {
        let lens: Vec<u16> = vec![7u16, 8u16, 8u16, 9u16, 8u16, 7u16, 8u16, 7u16, 10u16, 7u16, 9u16, 8u16, 9u16, 10u16, 7u16, 7u16, 8u16, 9u16, 10u16, 8u16, 9u16, 8u16, 9u16, 7u16, 11u16, 12u16, 8u16, 8u16, 8u16, 7u16, 8u16, 7u16, 10u16, 9u16, 7u16, 8u16, 10u16, 8u16, 9u16, 8u16, 9u16, 8u16, 0u16, 7u16, 8u16, 7u16, 8u16, 8u16, 9u16, 8u16, 9u16, 8u16, 8u16, 8u16, 8u16, 10u16, 12u16, 9u16, 10u16, 12u16, 13u16, 8u16, 9u16, 9u16, 8u16, 7u16, 7u16, 0u16, 12u16, 8u16, 8u16, 7u16, 8u16, 9u16, 8u16, 8u16, 8u16, 8u16, 8u16, 10u16, 7u16, 8u16, 12u16, 9u16, 8u16, 8u16, 8u16, 8u16, 9u16, 9u16, 8u16, 9u16, 7u16, 8u16, 8u16, 8u16, 8u16, 7u16, 7u16, 8u16, 8u16, 10u16, 8u16, 10u16, 10u16, 11u16, 8u16, 7u16, 0u16, 8u16, 11u16, 9u16, 8u16, 8u16, 8u16, 8u16, 7u16, 9u16, 11u16, 8u16, 10u16, 8u16, 8u16, 8u16, 9u16, 9u16, 10u16, 11u16, 7u16, 10u16, 8u16, 8u16, 10u16, 9u16, 8u16, 7u16, 8u16, 7u16, 7u16, 7u16, 10u16, 7u16, 8u16, 9u16, 11u16, 7u16, 9u16, 8u16, 10u16, 13u16, 8u16, 9u16, 7u16, 9u16, 8u16, 9u16, 8u16, 8u16, 7u16, 10u16, 8u16, 7u16, 8u16, 11u16, 8u16, 8u16, 8u16, 8u16, 8u16, 8u16, 9u16, 0u16, 9u16, 8u16, 10u16, 10u16, 9u16, 7u16, 8u16, 8u16, 7u16, 8u16, 10u16, 9u16, 7u16, 9u16, 8u16, 7u16, 9u16, 8u16, 8u16, 10u16, 0u16, 8u16, 7u16, 8u16, 8u16, 8u16, 8u16, 12u16, 8u16, 8u16, 13u16, 10u16, 8u16, 8u16, 10u16, 11u16, 10u16, 9u16, 8u16, 9u16, 7u16, 8u16, 8u16, 8u16, 10u16, 7u16, 8u16, 12u16, 10u16, 8u16, 8u16, 8u16, 8u16, 10u16, 9u16, 8u16, 11u16, 8u16, 8u16, 8u16, 8u16, 8u16, 8u16, 9u16, 9u16, 8u16, 9u16, 7u16, 8u16, 8u16, 8u16, 8u16, 7u16, 7u16, 9u16, 9u16, 8u16, 13u16, 9u16, 7u16, 11u16, 8u16, 9u16, 9u16, 8u16, 8u16, 8u16, 8u16, 11u16, 9u16, 8u16, 8u16, 7u16, 8u16, 10u16, 8u16, 9u16, 8u16, 8u16, 8u16, 10u16, 9u16, 7u16, 12u16, 9u16, 9u16, 8u16, 8u16, 7u16, 0u16, 7u16, 8u16, 9u16, 9u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 9;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Lens, &lens, 286usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 0");
        assert_eq!(bits, 9u32, "inflate_table bits 0");
        let got: Vec<(u8,u8,u16)> = table[..574].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(0,7,0), (0,8,85), (0,7,180), (0,8,227), (0,7,92), (0,8,162), (0,8,11), (0,9,40), (0,7,31), (0,8,115), (0,7,245), (16,8,4), (0,7,138), (0,8,196), (0,8,51), (0,9,238), (0,7,14), (0,8,99), (0,7,212), (0,8,240), (0,7,116), (0,8,178), (0,8,35), (0,9,143), (0,7,65), (0,8,136), (20,7,115), (18,8,27), (0,7,152), (0,8,213), (0,8,72), (1,9,518), (0,7,7), (0,8,93), (0,7,187), (0,8,232), (0,7,98), (0,8,167), (0,8,26), (0,9,88), (0,7,43), (0,8,123), (16,7,10), (17,8,11), (0,7,141), (0,8,201), (0,8,61), (19,9,35), (0,7,23), (0,8,109), (0,7,239), (0,8,248), (0,7,135), (0,8,189), (0,8,44), (0,9,183), (0,7,71), (0,8,154), (0,8,1), (0,9,3), (0,7,161), (0,8,221), (0,8,77), (1,9,534), (0,7,5), (0,8,87), (0,7,184), (0,8,230), (0,7,97), (0,8,165), (0,8,19), (0,9,62), (0,7,34), (0,8,121), (0,7,251), (16,8,8), (0,7,139), (0,8,198), (0,8,53), (0,9,254), (0,7,15), (0,8,102), (0,7,217), (0,8,242), (0,7,128), (0,8,181), (0,8,39), (0,9,155), (0,7,66), (0,8,147), (21,7,163), (20,8,99), (0,7,158), (0,8,215), (0,8,75), (1,9,526), (0,7,9), (0,8,95), (0,7,194), (0,8,234), (0,7,107), (0,8,169), (0,8,28), (0,9,117), (0,7,45), (0,8,131), (19,7,43), (18,8,19), (0,7,145), (0,8,205), (0,8,69), (16,9,258), (0,7,29), (0,8,113), (0,7,244), (96,8,0), (0,7,137), (0,8,193), (0,8,47), (0,9,211), (0,7,80), (0,8,157), (0,8,4), (0,9,20), (0,7,177), (0,8,223), (0,8,81), (2,9,542), (0,7,0), (0,8,86), (0,7,180), (0,8,229), (0,7,92), (0,8,164), (0,8,16), (0,9,50), (0,7,31), (0,8,119), (0,7,245), (16,8,5), (0,7,138), (0,8,197), (0,8,52), (0,9,247), (0,7,14), (0,8,100), (0,7,212), (0,8,241), (0,7,116), (0,8,179), (0,8,37), (0,9,151), (0,7,65), (0,8,142), (20,7,115), (20,8,83), (0,7,152), (0,8,214), (0,8,74), (1,9,522), (0,7,7), (0,8,94), (0,7,187), (0,8,233), (0,7,98), (0,8,168), (0,8,27), (0,9,91), (0,7,43), (0,8,130), (16,7,10), (17,8,15), (0,7,141), (0,8,204), (0,8,64), (20,9,67), (0,7,23), (0,8,112), (0,7,239), (0,8,253), (0,7,135), (0,8,190), (0,8,46), (0,9,188), (0,7,71), (0,8,156), (0,8,2), (0,9,12), (0,7,161), (0,8,222), (0,8,78), (1,9,538), (0,7,5), (0,8,90), (0,7,184), (0,8,231), (0,7,97), (0,8,166), (0,8,21), (0,9,73), (0,7,34), (0,8,122), (0,7,251), (16,8,9), (0,7,139), (0,8,200), (0,8,54), (16,9,7), (0,7,15), (0,8,106), (0,7,217), (0,8,243), (0,7,128), (0,8,186), (0,8,41), (0,9,172), (0,7,66), (0,8,150), (21,7,163), (21,8,195), (0,7,158), (0,8,218), (0,8,76), (1,9,530), (0,7,9), (0,8,96), (0,7,194), (0,8,237), (0,7,107), (0,8,173), (0,8,30), (0,9,125), (0,7,45), (0,8,134), (19,7,43), (18,8,23), (0,7,145), (0,8,210), (0,8,70), (1,9,514), (0,7,29), (0,8,114), (0,7,244), (16,8,3), (0,7,137), (0,8,195), (0,8,49), (0,9,235), (0,7,80), (0,8,160), (0,8,6), (0,9,33), (0,7,177), (0,8,224), (0,8,84), (3,9,550), (0,7,0), (0,8,85), (0,7,180), (0,8,227), (0,7,92), (0,8,162), (0,8,11), (0,9,48), (0,7,31), (0,8,115), (0,7,245), (16,8,4), (0,7,138), (0,8,196), (0,8,51), (0,9,246), (0,7,14), (0,8,99), (0,7,212), (0,8,240), (0,7,116), (0,8,178), (0,8,35), (0,9,146), (0,7,65), (0,8,136), (20,7,115), (18,8,27), (0,7,152), (0,8,213), (0,8,72), (1,9,520), (0,7,7), (0,8,93), (0,7,187), (0,8,232), (0,7,98), (0,8,167), (0,8,26), (0,9,89), (0,7,43), (0,8,123), (16,7,10), (17,8,11), (0,7,141), (0,8,201), (0,8,61), (19,9,59), (0,7,23), (0,8,109), (0,7,239), (0,8,248), (0,7,135), (0,8,189), (0,8,44), (0,9,185), (0,7,71), (0,8,154), (0,8,1), (0,9,10), (0,7,161), (0,8,221), (0,8,77), (1,9,536), (0,7,5), (0,8,87), (0,7,184), (0,8,230), (0,7,97), (0,8,165), (0,8,19), (0,9,63), (0,7,34), (0,8,121), (0,7,251), (16,8,8), (0,7,139), (0,8,198), (0,8,53), (0,9,255), (0,7,15), (0,8,102), (0,7,217), (0,8,242), (0,7,128), (0,8,181), (0,8,39), (0,9,170), (0,7,66), (0,8,147), (21,7,163), (20,8,99), (0,7,158), (0,8,215), (0,8,75), (1,9,528), (0,7,9), (0,8,95), (0,7,194), (0,8,234), (0,7,107), (0,8,169), (0,8,28), (0,9,124), (0,7,45), (0,8,131), (19,7,43), (18,8,19), (0,7,145), (0,8,205), (0,8,69), (1,9,512), (0,7,29), (0,8,113), (0,7,244), (96,8,0), (0,7,137), (0,8,193), (0,8,47), (0,9,226), (0,7,80), (0,8,157), (0,8,4), (0,9,22), (0,7,177), (0,8,223), (0,8,81), (2,9,546), (0,7,0), (0,8,86), (0,7,180), (0,8,229), (0,7,92), (0,8,164), (0,8,16), (0,9,57), (0,7,31), (0,8,119), (0,7,245), (16,8,5), (0,7,138), (0,8,197), (0,8,52), (0,9,250), (0,7,14), (0,8,100), (0,7,212), (0,8,241), (0,7,116), (0,8,179), (0,8,37), (0,9,153), (0,7,65), (0,8,142), (20,7,115), (20,8,83), (0,7,152), (0,8,214), (0,8,74), (1,9,524), (0,7,7), (0,8,94), (0,7,187), (0,8,233), (0,7,98), (0,8,168), (0,8,27), (0,9,111), (0,7,43), (0,8,130), (16,7,10), (17,8,15), (0,7,141), (0,8,204), (0,8,64), (21,9,227), (0,7,23), (0,8,112), (0,7,239), (0,8,253), (0,7,135), (0,8,190), (0,8,46), (0,9,209), (0,7,71), (0,8,156), (0,8,2), (0,9,17), (0,7,161), (0,8,222), (0,8,78), (1,9,540), (0,7,5), (0,8,90), (0,7,184), (0,8,231), (0,7,97), (0,8,166), (0,8,21), (0,9,83), (0,7,34), (0,8,122), (0,7,251), (16,8,9), (0,7,139), (0,8,200), (0,8,54), (17,9,17), (0,7,15), (0,8,106), (0,7,217), (0,8,243), (0,7,128), (0,8,186), (0,8,41), (0,9,176), (0,7,66), (0,8,150), (21,7,163), (21,8,195), (0,7,158), (0,8,218), (0,8,76), (1,9,532), (0,7,9), (0,8,96), (0,7,194), (0,8,237), (0,7,107), (0,8,173), (0,8,30), (0,9,133), (0,7,45), (0,8,134), (19,7,43), (18,8,23), (0,7,145), (0,8,210), (0,8,70), (1,9,516), (0,7,29), (0,8,114), (0,7,244), (16,8,3), (0,7,137), (0,8,195), (0,8,49), (0,9,236), (0,7,80), (0,8,160), (0,8,6), (0,9,38), (0,7,177), (0,8,224), (0,8,84), (4,9,558), (0,1,8), (0,1,13), (0,1,18), (0,1,32), (0,1,36), (0,1,55), (0,1,58), (0,1,79), (0,1,101), (0,1,103), (0,1,104), (0,1,120), (0,1,126), (0,1,129), (0,1,132), (0,1,140), (0,1,148), (0,1,159), (0,1,174), (0,1,175), (0,1,182), (0,1,191), (0,1,203), (0,1,206), (0,1,208), (0,1,216), (0,1,220), (0,1,225), (17,1,13), (18,1,31), (0,2,24), (0,2,110), (0,2,105), (0,2,118), (0,2,127), (0,2,163), (0,2,144), (0,2,207), (0,2,228), (16,2,6), (0,2,252), (0,3,25), (0,2,228), (16,2,6), (0,2,252), (0,3,56), (0,3,59), (0,3,219), (0,3,82), (0,4,60), (0,3,68), (19,3,51), (0,3,199), (0,4,202), (0,3,59), (0,3,219), (0,3,82), (0,4,149), (0,3,68), (19,3,51), (0,3,199), (0,4,249)], "inflate_table table 0");
    }

    #[test]
    fn test_inflate_table_body_1() {
        let lens: Vec<u16> = vec![5u16, 5u16, 4u16, 5u16, 4u16, 4u16, 4u16, 4u16, 4u16, 8u16, 6u16, 7u16, 6u16, 7u16, 8u16, 4u16, 5u16, 5u16, 4u16, 7u16, 5u16, 5u16, 7u16, 6u16, 5u16, 5u16, 5u16, 5u16, 4u16, 7u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 6;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Dists, &lens, 30usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 1");
        assert_eq!(bits, 6u32, "inflate_table bits 1");
        let got: Vec<(u8,u8,u16)> = table[..72].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(16,4,3), (29,4,16385), (18,4,13), (25,5,1537), (17,4,7), (16,5,4), (22,4,193), (28,5,12289), (17,4,5), (16,5,1), (19,4,17), (27,5,6145), (18,4,9), (23,5,385), (24,4,513), (26,6,3073), (16,4,3), (29,4,16385), (18,4,13), (27,5,4097), (17,4,7), (23,5,257), (22,4,193), (20,6,33), (17,4,5), (16,5,2), (19,4,17), (28,5,8193), (18,4,9), (25,5,1025), (24,4,513), (1,6,66), (16,4,3), (29,4,16385), (18,4,13), (25,5,1537), (17,4,7), (16,5,4), (22,4,193), (28,5,12289), (17,4,5), (16,5,1), (19,4,17), (27,5,6145), (18,4,9), (23,5,385), (24,4,513), (1,6,64), (16,4,3), (29,4,16385), (18,4,13), (27,5,4097), (17,4,7), (23,5,257), (22,4,193), (21,6,65), (17,4,5), (16,5,2), (19,4,17), (28,5,8193), (18,4,9), (25,5,1025), (24,4,513), (2,6,68), (20,1,49), (21,1,97), (24,1,769), (26,1,2049), (29,1,24577), (19,2,25), (29,1,24577), (22,2,129)], "inflate_table table 1");
    }

    #[test]
    fn test_inflate_table_body_2() {
        let lens: Vec<u16> = vec![5u16, 4u16, 4u16, 4u16, 5u16, 4u16, 5u16, 4u16, 4u16, 6u16, 3u16, 4u16, 5u16, 4u16, 5u16, 7u16, 7u16, 3u16, 4u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 7;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Codes, &lens, 19usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 2");
        assert_eq!(bits, 7u32, "inflate_table bits 2");
        let got: Vec<(u8,u8,u16)> = table[..128].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(0,3,10), (0,4,7), (0,4,1), (0,4,18), (0,3,17), (0,4,11), (0,4,3), (0,5,6), (0,3,10), (0,4,8), (0,4,2), (0,5,0), (0,3,17), (0,4,13), (0,4,5), (0,5,14), (0,3,10), (0,4,7), (0,4,1), (0,4,18), (0,3,17), (0,4,11), (0,4,3), (0,5,12), (0,3,10), (0,4,8), (0,4,2), (0,5,4), (0,3,17), (0,4,13), (0,4,5), (0,6,9), (0,3,10), (0,4,7), (0,4,1), (0,4,18), (0,3,17), (0,4,11), (0,4,3), (0,5,6), (0,3,10), (0,4,8), (0,4,2), (0,5,0), (0,3,17), (0,4,13), (0,4,5), (0,5,14), (0,3,10), (0,4,7), (0,4,1), (0,4,18), (0,3,17), (0,4,11), (0,4,3), (0,5,12), (0,3,10), (0,4,8), (0,4,2), (0,5,4), (0,3,17), (0,4,13), (0,4,5), (0,7,15), (0,3,10), (0,4,7), (0,4,1), (0,4,18), (0,3,17), (0,4,11), (0,4,3), (0,5,6), (0,3,10), (0,4,8), (0,4,2), (0,5,0), (0,3,17), (0,4,13), (0,4,5), (0,5,14), (0,3,10), (0,4,7), (0,4,1), (0,4,18), (0,3,17), (0,4,11), (0,4,3), (0,5,12), (0,3,10), (0,4,8), (0,4,2), (0,5,4), (0,3,17), (0,4,13), (0,4,5), (0,6,9), (0,3,10), (0,4,7), (0,4,1), (0,4,18), (0,3,17), (0,4,11), (0,4,3), (0,5,6), (0,3,10), (0,4,8), (0,4,2), (0,5,0), (0,3,17), (0,4,13), (0,4,5), (0,5,14), (0,3,10), (0,4,7), (0,4,1), (0,4,18), (0,3,17), (0,4,11), (0,4,3), (0,5,12), (0,3,10), (0,4,8), (0,4,2), (0,5,4), (0,3,17), (0,4,13), (0,4,5), (0,7,16)], "inflate_table table 2");
    }

    #[test]
    fn test_inflate_table_body_3() {
        let lens: Vec<u16> = vec![13u16, 8u16, 8u16, 8u16, 8u16, 9u16, 12u16, 7u16, 10u16, 8u16, 9u16, 8u16, 7u16, 9u16, 8u16, 8u16, 7u16, 8u16, 8u16, 8u16, 7u16, 8u16, 8u16, 0u16, 9u16, 9u16, 12u16, 9u16, 11u16, 8u16, 8u16, 9u16, 9u16, 8u16, 11u16, 9u16, 8u16, 8u16, 8u16, 8u16, 8u16, 8u16, 7u16, 8u16, 0u16, 8u16, 11u16, 11u16, 7u16, 11u16, 7u16, 10u16, 8u16, 9u16, 9u16, 8u16, 9u16, 8u16, 8u16, 8u16, 8u16, 8u16, 8u16, 9u16, 9u16, 9u16, 8u16, 8u16, 8u16, 8u16, 7u16, 9u16, 8u16, 9u16, 8u16, 9u16, 9u16, 8u16, 12u16, 8u16, 8u16, 7u16, 7u16, 8u16, 7u16, 7u16, 10u16, 7u16, 8u16, 9u16, 9u16, 9u16, 8u16, 10u16, 0u16, 10u16, 12u16, 10u16, 8u16, 9u16, 8u16, 12u16, 9u16, 10u16, 8u16, 10u16, 8u16, 8u16, 8u16, 8u16, 8u16, 8u16, 7u16, 8u16, 8u16, 7u16, 9u16, 11u16, 8u16, 8u16, 0u16, 7u16, 7u16, 7u16, 12u16, 8u16, 7u16, 8u16, 9u16, 7u16, 7u16, 8u16, 11u16, 9u16, 7u16, 9u16, 8u16, 8u16, 10u16, 11u16, 9u16, 8u16, 8u16, 8u16, 8u16, 10u16, 8u16, 9u16, 8u16, 7u16, 8u16, 8u16, 8u16, 7u16, 8u16, 7u16, 8u16, 10u16, 7u16, 8u16, 13u16, 9u16, 7u16, 9u16, 7u16, 9u16, 11u16, 9u16, 8u16, 9u16, 7u16, 9u16, 9u16, 9u16, 9u16, 8u16, 7u16, 7u16, 7u16, 11u16, 10u16, 8u16, 7u16, 8u16, 13u16, 8u16, 9u16, 8u16, 9u16, 7u16, 7u16, 11u16, 9u16, 8u16, 8u16, 10u16, 7u16, 9u16, 7u16, 11u16, 11u16, 12u16, 11u16, 9u16, 9u16, 8u16, 8u16, 8u16, 8u16, 8u16, 8u16, 7u16, 8u16, 8u16, 8u16, 9u16, 9u16, 11u16, 10u16, 7u16, 11u16, 7u16, 8u16, 9u16, 9u16, 9u16, 11u16, 8u16, 7u16, 12u16, 8u16, 9u16, 7u16, 9u16, 8u16, 9u16, 7u16, 8u16, 9u16, 7u16, 8u16, 7u16, 10u16, 8u16, 7u16, 9u16, 9u16, 11u16, 7u16, 13u16, 11u16, 12u16, 8u16, 11u16, 8u16, 9u16, 8u16, 7u16, 12u16, 8u16, 9u16, 8u16, 8u16, 10u16, 8u16, 8u16, 9u16, 10u16, 8u16, 8u16, 10u16, 9u16, 10u16, 9u16, 8u16, 7u16, 8u16, 10u16, 7u16, 7u16, 9u16, 8u16, 10u16, 7u16, 9u16, 8u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 9;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Lens, &lens, 286usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 3");
        assert_eq!(bits, 9u32, "inflate_table bits 3");
        let got: Vec<(u8,u8,u16)> = table[..576].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(0,7,7), (0,8,52), (0,7,182), (0,8,212), (0,7,122), (0,8,119), (19,7,51), (0,9,73), (0,7,81), (0,8,80), (0,7,228), (16,8,10), (0,7,155), (0,8,156), (0,8,17), (0,9,224), (0,7,42), (0,8,66), (0,7,198), (0,8,240), (0,7,130), (0,8,143), (0,8,1), (0,9,165), (0,7,87), (0,8,107), (0,7,241), (0,9,5), (0,7,170), (0,8,193), (0,8,36), (1,9,514), (0,7,16), (0,8,59), (0,7,190), (0,8,227), (0,7,126), (0,8,136), (20,7,99), (0,9,116), (0,7,84), (0,8,98), (0,7,236), (19,8,43), (0,7,162), (0,8,181), (0,8,22), (0,9,255), (0,7,50), (0,8,72), (0,7,219), (96,8,0), (0,7,149), (0,8,150), (0,8,9), (0,9,188), (0,7,115), (0,8,111), (0,7,248), (0,9,35), (0,7,177), (0,8,207), (0,8,40), (1,9,530), (0,7,12), (0,8,57), (0,7,189), (0,8,214), (0,7,123), (0,8,127), (20,7,83), (0,9,90), (0,7,82), (0,8,88), (0,7,232), (17,8,17), (0,7,158), (0,8,168), (0,8,19), (0,9,235), (0,7,48), (0,8,68), (0,7,211), (0,8,252), (0,7,134), (0,8,146), (0,8,3), (0,9,172), (0,7,112), (0,8,109), (0,7,244), (0,9,25), (0,7,176), (0,8,205), (0,8,38), (1,9,522), (0,7,20), (0,8,61), (0,7,196), (0,8,234), (0,7,129), (0,8,141), (21,7,195), (0,9,140), (0,7,85), (0,8,104), (0,7,239), (21,8,131), (0,7,164), (0,8,185), (0,8,30), (19,9,35), (0,7,70), (0,8,77), (0,7,221), (16,8,7), (0,7,153), (0,8,152), (0,8,14), (0,9,204), (0,7,121), (0,8,114), (16,7,3), (0,9,63), (0,7,178), (0,8,209), (0,8,43), (2,9,544), (0,7,7), (0,8,55), (0,7,182), (0,8,213), (0,7,122), (0,8,125), (19,7,51), (0,9,76), (0,7,81), (0,8,83), (0,7,228), (17,8,11), (0,7,155), (0,8,159), (0,8,18), (0,9,231), (0,7,42), (0,8,67), (0,7,198), (0,8,243), (0,7,130), (0,8,144), (0,8,2), (0,9,169), (0,7,87), (0,8,108), (0,7,241), (0,9,13), (0,7,170), (0,8,194), (0,8,37), (1,9,518), (0,7,16), (0,8,60), (0,7,190), (0,8,230), (0,7,126), (0,8,137), (20,7,99), (0,9,133), (0,7,84), (0,8,100), (0,7,236), (19,8,59), (0,7,162), (0,8,183), (0,8,29), (17,9,13), (0,7,50), (0,8,74), (0,7,219), (16,8,5), (0,7,149), (0,8,151), (0,8,11), (0,9,197), (0,7,115), (0,8,113), (0,7,248), (0,9,54), (0,7,177), (0,8,208), (0,8,41), (2,9,536), (0,7,12), (0,8,58), (0,7,189), (0,8,222), (0,7,123), (0,8,131), (20,7,83), (0,9,99), (0,7,82), (0,8,92), (0,7,232), (18,8,19), (0,7,158), (0,8,175), (0,8,21), (0,9,245), (0,7,48), (0,8,69), (0,7,211), (0,8,254), (0,7,134), (0,8,148), (0,8,4), (0,9,174), (0,7,112), (0,8,110), (0,7,244), (0,9,31), (0,7,176), (0,8,206), (0,8,39), (1,9,526), (0,7,20), (0,8,62), (0,7,196), (0,8,237), (0,7,129), (0,8,142), (21,7,195), (0,9,161), (0,7,85), (0,8,106), (0,7,239), (16,8,258), (0,7,164), (0,8,187), (0,8,33), (21,9,227), (0,7,70), (0,8,79), (0,7,221), (16,8,8), (0,7,153), (0,8,154), (0,8,15), (0,9,216), (0,7,121), (0,8,118), (16,7,3), (0,9,65), (0,7,178), (0,8,210), (0,8,45), (3,9,552), (0,7,7), (0,8,52), (0,7,182), (0,8,212), (0,7,122), (0,8,119), (19,7,51), (0,9,75), (0,7,81), (0,8,80), (0,7,228), (16,8,10), (0,7,155), (0,8,156), (0,8,17), (0,9,225), (0,7,42), (0,8,66), (0,7,198), (0,8,240), (0,7,130), (0,8,143), (0,8,1), (0,9,167), (0,7,87), (0,8,107), (0,7,241), (0,9,10), (0,7,170), (0,8,193), (0,8,36), (1,9,516), (0,7,16), (0,8,59), (0,7,190), (0,8,227), (0,7,126), (0,8,136), (20,7,99), (0,9,128), (0,7,84), (0,8,98), (0,7,236), (19,8,43), (0,7,162), (0,8,181), (0,8,22), (16,9,6), (0,7,50), (0,8,72), (0,7,219), (96,8,0), (0,7,149), (0,8,150), (0,8,9), (0,9,192), (0,7,115), (0,8,111), (0,7,248), (0,9,53), (0,7,177), (0,8,207), (0,8,40), (2,9,532), (0,7,12), (0,8,57), (0,7,189), (0,8,214), (0,7,123), (0,8,127), (20,7,83), (0,9,91), (0,7,82), (0,8,88), (0,7,232), (17,8,17), (0,7,158), (0,8,168), (0,8,19), (0,9,238), (0,7,48), (0,8,68), (0,7,211), (0,8,252), (0,7,134), (0,8,146), (0,8,3), (0,9,173), (0,7,112), (0,8,109), (0,7,244), (0,9,27), (0,7,176), (0,8,205), (0,8,38), (1,9,524), (0,7,20), (0,8,61), (0,7,196), (0,8,234), (0,7,129), (0,8,141), (21,7,195), (0,9,147), (0,7,85), (0,8,104), (0,7,239), (21,8,131), (0,7,164), (0,8,185), (0,8,30), (20,9,115), (0,7,70), (0,8,77), (0,7,221), (16,8,7), (0,7,153), (0,8,152), (0,8,14), (0,9,215), (0,7,121), (0,8,114), (16,7,3), (0,9,64), (0,7,178), (0,8,209), (0,8,43), (2,9,548), (0,7,7), (0,8,55), (0,7,182), (0,8,213), (0,7,122), (0,8,125), (19,7,51), (0,9,89), (0,7,81), (0,8,83), (0,7,228), (17,8,11), (0,7,155), (0,8,159), (0,8,18), (0,9,233), (0,7,42), (0,8,67), (0,7,198), (0,8,243), (0,7,130), (0,8,144), (0,8,2), (0,9,171), (0,7,87), (0,8,108), (0,7,241), (0,9,24), (0,7,170), (0,8,194), (0,8,37), (1,9,520), (0,7,16), (0,8,60), (0,7,190), (0,8,230), (0,7,126), (0,8,137), (20,7,99), (0,9,135), (0,7,84), (0,8,100), (0,7,236), (19,8,59), (0,7,162), (0,8,183), (0,8,29), (18,9,27), (0,7,50), (0,8,74), (0,7,219), (16,8,5), (0,7,149), (0,8,151), (0,8,11), (0,9,203), (0,7,115), (0,8,113), (0,7,248), (0,9,56), (0,7,177), (0,8,208), (0,8,41), (2,9,540), (0,7,12), (0,8,58), (0,7,189), (0,8,222), (0,7,123), (0,8,131), (20,7,83), (0,9,102), (0,7,82), (0,8,92), (0,7,232), (18,8,19), (0,7,158), (0,8,175), (0,8,21), (0,9,246), (0,7,48), (0,8,69), (0,7,211), (0,8,254), (0,7,134), (0,8,148), (0,8,4), (0,9,186), (0,7,112), (0,8,110), (0,7,244), (0,9,32), (0,7,176), (0,8,206), (0,8,39), (1,9,528), (0,7,20), (0,8,62), (0,7,196), (0,8,237), (0,7,129), (0,8,142), (21,7,195), (0,9,163), (0,7,85), (0,8,106), (0,7,239), (16,8,258), (0,7,164), (0,8,187), (0,8,33), (1,9,512), (0,7,70), (0,8,79), (0,7,221), (16,8,8), (0,7,153), (0,8,154), (0,8,15), (0,9,223), (0,7,121), (0,8,118), (16,7,3), (0,9,71), (0,7,178), (0,8,210), (0,8,45), (4,9,560), (0,1,8), (0,1,51), (0,1,86), (0,1,93), (0,1,95), (0,1,97), (0,1,103), (0,1,105), (0,1,138), (0,1,145), (0,1,157), (0,1,180), (0,1,195), (0,1,218), (0,1,242), (16,1,9), (17,1,15), (18,1,23), (18,1,31), (20,1,67), (21,1,163), (0,2,28), (21,1,163), (0,2,34), (0,2,46), (0,2,49), (0,2,47), (0,2,117), (0,2,132), (0,2,166), (0,2,139), (0,2,179), (0,2,191), (0,2,200), (0,2,199), (0,2,202), (0,2,217), (0,2,226), (0,2,220), (0,2,247), (0,2,250), (0,3,6), (0,2,253), (0,3,78), (0,2,250), (0,3,26), (0,2,253), (0,3,96), (0,3,101), (0,3,251), (0,3,201), (0,4,0), (0,3,124), (16,3,4), (0,3,229), (0,4,184), (0,3,101), (0,3,251), (0,3,201), (0,4,160), (0,3,124), (16,3,4), (0,3,229), (0,4,249)], "inflate_table table 3");
    }

    #[test]
    fn test_inflate_table_body_4() {
        let lens: Vec<u16> = vec![4u16, 8u16, 5u16, 0u16, 5u16, 6u16, 6u16, 6u16, 5u16, 4u16, 4u16, 6u16, 4u16, 5u16, 7u16, 5u16, 4u16, 5u16, 5u16, 5u16, 8u16, 5u16, 5u16, 4u16, 4u16, 6u16, 5u16, 4u16, 5u16, 5u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 6;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Dists, &lens, 30usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 4");
        assert_eq!(bits, 6u32, "inflate_table bits 4");
        let got: Vec<(u8,u8,u16)> = table[..68].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(16,4,1), (16,5,3), (23,4,257), (25,5,1537), (20,4,33), (22,5,193), (27,4,4097), (29,5,24577), (19,4,25), (19,5,17), (26,4,3073), (28,5,8193), (21,4,65), (24,5,513), (28,4,12289), (18,6,13), (16,4,1), (17,5,5), (23,4,257), (26,5,2049), (20,4,33), (23,5,385), (27,4,4097), (17,6,7), (19,4,25), (21,5,97), (26,4,3073), (29,5,16385), (21,4,65), (24,5,769), (28,4,12289), (27,6,6145), (16,4,1), (16,5,3), (23,4,257), (25,5,1537), (20,4,33), (22,5,193), (27,4,4097), (29,5,24577), (19,4,25), (19,5,17), (26,4,3073), (28,5,8193), (21,4,65), (24,5,513), (28,4,12289), (20,6,49), (16,4,1), (17,5,5), (23,4,257), (26,5,2049), (20,4,33), (23,5,385), (27,4,4097), (18,6,9), (19,4,25), (21,5,97), (26,4,3073), (29,5,16385), (21,4,65), (24,5,769), (28,4,12289), (2,6,64), (22,1,129), (16,2,2), (22,1,129), (25,2,1025)], "inflate_table table 4");
    }

    #[test]
    fn test_inflate_table_body_5() {
        let lens: Vec<u16> = vec![4u16, 4u16, 5u16, 4u16, 6u16, 3u16, 5u16, 4u16, 3u16, 5u16, 4u16, 5u16, 4u16, 5u16, 5u16, 5u16, 4u16, 4u16, 6u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 7;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Codes, &lens, 19usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 5");
        assert_eq!(bits, 6u32, "inflate_table bits 5");
        let got: Vec<(u8,u8,u16)> = table[..64].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(0,3,5), (0,4,10), (0,4,0), (0,5,2), (0,3,8), (0,4,16), (0,4,3), (0,5,13), (0,3,5), (0,4,12), (0,4,1), (0,5,9), (0,3,8), (0,4,17), (0,4,7), (0,5,15), (0,3,5), (0,4,10), (0,4,0), (0,5,6), (0,3,8), (0,4,16), (0,4,3), (0,5,14), (0,3,5), (0,4,12), (0,4,1), (0,5,11), (0,3,8), (0,4,17), (0,4,7), (0,6,4), (0,3,5), (0,4,10), (0,4,0), (0,5,2), (0,3,8), (0,4,16), (0,4,3), (0,5,13), (0,3,5), (0,4,12), (0,4,1), (0,5,9), (0,3,8), (0,4,17), (0,4,7), (0,5,15), (0,3,5), (0,4,10), (0,4,0), (0,5,6), (0,3,8), (0,4,16), (0,4,3), (0,5,14), (0,3,5), (0,4,12), (0,4,1), (0,5,11), (0,3,8), (0,4,17), (0,4,7), (0,6,18)], "inflate_table table 5");
    }

    #[test]
    fn test_inflate_table_body_6() {
        let lens: Vec<u16> = vec![10u16, 10u16, 0u16, 8u16, 7u16, 8u16, 13u16, 9u16, 7u16, 8u16, 9u16, 8u16, 8u16, 8u16, 8u16, 8u16, 7u16, 7u16, 7u16, 11u16, 9u16, 7u16, 9u16, 12u16, 7u16, 9u16, 8u16, 8u16, 8u16, 0u16, 9u16, 8u16, 9u16, 9u16, 8u16, 10u16, 7u16, 0u16, 7u16, 8u16, 0u16, 8u16, 7u16, 9u16, 11u16, 8u16, 9u16, 9u16, 10u16, 8u16, 7u16, 8u16, 8u16, 12u16, 7u16, 0u16, 9u16, 7u16, 8u16, 8u16, 7u16, 9u16, 10u16, 11u16, 8u16, 8u16, 8u16, 0u16, 8u16, 11u16, 8u16, 7u16, 8u16, 8u16, 8u16, 8u16, 8u16, 7u16, 8u16, 8u16, 8u16, 8u16, 8u16, 9u16, 8u16, 8u16, 10u16, 7u16, 8u16, 8u16, 8u16, 0u16, 12u16, 7u16, 9u16, 8u16, 7u16, 12u16, 7u16, 8u16, 9u16, 12u16, 9u16, 8u16, 9u16, 8u16, 7u16, 8u16, 8u16, 9u16, 7u16, 9u16, 0u16, 10u16, 9u16, 10u16, 9u16, 7u16, 8u16, 10u16, 9u16, 9u16, 7u16, 8u16, 7u16, 8u16, 0u16, 10u16, 8u16, 8u16, 8u16, 10u16, 0u16, 11u16, 7u16, 9u16, 7u16, 8u16, 8u16, 9u16, 8u16, 8u16, 9u16, 8u16, 8u16, 7u16, 9u16, 7u16, 8u16, 9u16, 9u16, 11u16, 7u16, 8u16, 8u16, 7u16, 8u16, 8u16, 8u16, 7u16, 7u16, 9u16, 10u16, 7u16, 7u16, 7u16, 10u16, 9u16, 8u16, 8u16, 7u16, 9u16, 8u16, 7u16, 9u16, 8u16, 8u16, 8u16, 10u16, 8u16, 9u16, 8u16, 8u16, 10u16, 12u16, 9u16, 8u16, 8u16, 7u16, 8u16, 13u16, 7u16, 7u16, 12u16, 9u16, 9u16, 7u16, 8u16, 8u16, 8u16, 10u16, 10u16, 8u16, 10u16, 8u16, 8u16, 9u16, 0u16, 8u16, 10u16, 8u16, 8u16, 0u16, 8u16, 8u16, 9u16, 8u16, 10u16, 12u16, 7u16, 9u16, 9u16, 7u16, 11u16, 8u16, 9u16, 8u16, 8u16, 11u16, 7u16, 8u16, 9u16, 9u16, 8u16, 9u16, 8u16, 10u16, 8u16, 8u16, 11u16, 8u16, 9u16, 7u16, 10u16, 9u16, 9u16, 10u16, 8u16, 7u16, 8u16, 11u16, 8u16, 7u16, 7u16, 9u16, 9u16, 9u16, 10u16, 7u16, 7u16, 10u16, 13u16, 8u16, 8u16, 8u16, 11u16, 8u16, 8u16, 8u16, 8u16, 10u16, 13u16, 10u16, 8u16, 8u16, 9u16, 8u16, 8u16, 8u16, 8u16, 10u16, 9u16, 8u16, 8u16, 8u16, 8u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 9;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Lens, &lens, 286usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 6");
        assert_eq!(bits, 9u32, "inflate_table bits 6");
        let got: Vec<(u8,u8,u16)> = table[..572].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(0,7,4), (0,8,72), (0,7,160), (0,8,226), (0,7,87), (0,8,144), (0,7,253), (0,9,43), (0,7,38), (0,8,99), (0,7,192), (17,8,17), (0,7,124), (0,8,186), (0,8,28), (0,9,220), (0,7,18), (0,8,81), (0,7,170), (0,8,247), (0,7,106), (0,8,169), (0,8,9), (0,9,135), (0,7,57), (0,8,128), (0,7,229), (21,8,163), (0,7,147), (0,8,205), (0,8,52), (1,9,516), (0,7,16), (0,8,76), (0,7,164), (0,8,235), (0,7,96), (0,8,156), (16,7,5), (0,9,102), (0,7,50), (0,8,108), (0,7,219), (19,8,59), (0,7,136), (0,8,198), (0,8,41), (0,9,245), (0,7,24), (0,8,88), (0,7,188), (16,8,9), (0,7,117), (0,8,177), (0,8,14), (0,9,171), (0,7,71), (0,8,138), (0,7,248), (0,9,7), (0,7,155), (0,8,213), (0,8,65), (1,9,532), (0,7,8), (0,8,74), (0,7,163), (0,8,230), (0,7,93), (0,8,153), (16,7,4), (0,9,61), (0,7,42), (0,8,105), (0,7,196), (19,8,35), (0,7,134), (0,8,189), (0,8,34), (0,9,232), (0,7,21), (0,8,84), (0,7,173), (0,8,251), (0,7,110), (0,8,175), (0,8,12), (0,9,149), (0,7,60), (0,8,130), (0,7,242), (21,8,227), (0,7,152), (0,8,210), (0,8,59), (1,9,524), (0,7,17), (0,8,79), (0,7,165), (0,8,238), (0,7,98), (0,8,158), (0,8,3), (0,9,114), (0,7,54), (0,8,123), (0,7,222), (20,8,83), (0,7,145), (0,8,202), (0,8,49), (19,9,51), (0,7,36), (0,8,90), (0,7,191), (17,8,13), (0,7,122), (0,8,181), (0,8,26), (0,9,194), (0,7,77), (0,8,141), (0,7,252), (0,9,25), (0,7,159), (0,8,216), (0,8,68), (2,9,540), (0,7,4), (0,8,73), (0,7,160), (0,8,227), (0,7,87), (0,8,148), (0,7,253), (0,9,47), (0,7,38), (0,8,103), (0,7,192), (18,8,19), (0,7,124), (0,8,187), (0,8,31), (0,9,225), (0,7,18), (0,8,82), (0,7,170), (0,8,249), (0,7,106), (0,8,172), (0,8,11), (0,9,142), (0,7,57), (0,8,129), (0,7,229), (21,8,195), (0,7,147), (0,8,208), (0,8,58), (1,9,520), (0,7,16), (0,8,78), (0,7,164), (0,8,237), (0,7,96), (0,8,157), (16,7,5), (0,9,109), (0,7,50), (0,8,118), (0,7,219), (20,8,67), (0,7,136), (0,8,199), (0,8,45), (0,9,255), (0,7,24), (0,8,89), (0,7,188), (16,8,10), (0,7,117), (0,8,179), (0,8,15), (0,9,180), (0,7,71), (0,8,140), (0,7,248), (0,9,20), (0,7,155), (0,8,214), (0,8,66), (1,9,536), (0,7,8), (0,8,75), (0,7,163), (0,8,233), (0,7,93), (0,8,154), (16,7,4), (0,9,94), (0,7,42), (0,8,107), (0,7,196), (19,8,43), (0,7,134), (0,8,197), (0,8,39), (0,9,241), (0,7,21), (0,8,85), (0,7,173), (16,8,8), (0,7,110), (0,8,176), (0,8,13), (0,9,161), (0,7,60), (0,8,137), (0,7,242), (16,8,258), (0,7,152), (0,8,211), (0,8,64), (1,9,528), (0,7,17), (0,8,80), (0,7,165), (0,8,240), (0,7,98), (0,8,168), (0,8,5), (0,9,120), (0,7,54), (0,8,125), (0,7,222), (20,8,99), (0,7,145), (0,8,204), (0,8,51), (1,9,512), (0,7,36), (0,8,95), (0,7,191), (17,8,15), (0,7,122), (0,8,182), (0,8,27), (0,9,206), (0,7,77), (0,8,143), (0,7,252), (0,9,32), (0,7,159), (0,8,224), (0,8,70), (3,9,548), (0,7,4), (0,8,72), (0,7,160), (0,8,226), (0,7,87), (0,8,144), (0,7,253), (0,9,46), (0,7,38), (0,8,99), (0,7,192), (17,8,17), (0,7,124), (0,8,186), (0,8,28), (0,9,221), (0,7,18), (0,8,81), (0,7,170), (0,8,247), (0,7,106), (0,8,169), (0,8,9), (0,9,139), (0,7,57), (0,8,128), (0,7,229), (21,8,163), (0,7,147), (0,8,205), (0,8,52), (1,9,518), (0,7,16), (0,8,76), (0,7,164), (0,8,235), (0,7,96), (0,8,156), (16,7,5), (0,9,104), (0,7,50), (0,8,108), (0,7,219), (19,8,59), (0,7,136), (0,8,198), (0,8,41), (0,9,254), (0,7,24), (0,8,88), (0,7,188), (16,8,9), (0,7,117), (0,8,177), (0,8,14), (0,9,174), (0,7,71), (0,8,138), (0,7,248), (0,9,10), (0,7,155), (0,8,213), (0,8,65), (1,9,534), (0,7,8), (0,8,74), (0,7,163), (0,8,230), (0,7,93), (0,8,153), (16,7,4), (0,9,83), (0,7,42), (0,8,105), (0,7,196), (19,8,35), (0,7,134), (0,8,189), (0,8,34), (0,9,234), (0,7,21), (0,8,84), (0,7,173), (0,8,251), (0,7,110), (0,8,175), (0,8,12), (0,9,150), (0,7,60), (0,8,130), (0,7,242), (21,8,227), (0,7,152), (0,8,210), (0,8,59), (1,9,526), (0,7,17), (0,8,79), (0,7,165), (0,8,238), (0,7,98), (0,8,158), (0,8,3), (0,9,116), (0,7,54), (0,8,123), (0,7,222), (20,8,83), (0,7,145), (0,8,202), (0,8,49), (21,9,131), (0,7,36), (0,8,90), (0,7,191), (17,8,13), (0,7,122), (0,8,181), (0,8,26), (0,9,195), (0,7,77), (0,8,141), (0,7,252), (0,9,30), (0,7,159), (0,8,216), (0,8,68), (2,9,544), (0,7,4), (0,8,73), (0,7,160), (0,8,227), (0,7,87), (0,8,148), (0,7,253), (0,9,56), (0,7,38), (0,8,103), (0,7,192), (18,8,19), (0,7,124), (0,8,187), (0,8,31), (0,9,231), (0,7,18), (0,8,82), (0,7,170), (0,8,249), (0,7,106), (0,8,172), (0,8,11), (0,9,146), (0,7,57), (0,8,129), (0,7,229), (21,8,195), (0,7,147), (0,8,208), (0,8,58), (1,9,522), (0,7,16), (0,8,78), (0,7,164), (0,8,237), (0,7,96), (0,8,157), (16,7,5), (0,9,111), (0,7,50), (0,8,118), (0,7,219), (20,8,67), (0,7,136), (0,8,199), (0,8,45), (96,9,0), (0,7,24), (0,8,89), (0,7,188), (16,8,10), (0,7,117), (0,8,179), (0,8,15), (0,9,185), (0,7,71), (0,8,140), (0,7,248), (0,9,22), (0,7,155), (0,8,214), (0,8,66), (1,9,538), (0,7,8), (0,8,75), (0,7,163), (0,8,233), (0,7,93), (0,8,154), (16,7,4), (0,9,100), (0,7,42), (0,8,107), (0,7,196), (19,8,43), (0,7,134), (0,8,197), (0,8,39), (0,9,244), (0,7,21), (0,8,85), (0,7,173), (16,8,8), (0,7,110), (0,8,176), (0,8,13), (0,9,167), (0,7,60), (0,8,137), (0,7,242), (16,8,258), (0,7,152), (0,8,211), (0,8,64), (1,9,530), (0,7,17), (0,8,80), (0,7,165), (0,8,240), (0,7,98), (0,8,168), (0,8,5), (0,9,121), (0,7,54), (0,8,125), (0,7,222), (20,8,99), (0,7,145), (0,8,204), (0,8,51), (1,9,514), (0,7,36), (0,8,95), (0,7,191), (17,8,15), (0,7,122), (0,8,182), (0,8,27), (0,9,215), (0,7,77), (0,8,143), (0,7,252), (0,9,33), (0,7,159), (0,8,224), (0,8,70), (4,9,556), (0,1,0), (0,1,1), (0,1,35), (0,1,48), (0,1,62), (0,1,86), (0,1,113), (0,1,115), (0,1,119), (0,1,127), (0,1,131), (0,1,162), (0,1,166), (0,1,178), (0,1,183), (0,1,200), (0,1,201), (0,1,203), (0,1,209), (0,1,217), (0,1,236), (0,1,243), (0,1,246), (16,1,3), (16,1,6), (18,1,23), (18,1,31), (20,1,115), (0,2,19), (0,2,63), (0,2,44), (0,2,69), (0,2,133), (0,2,223), (0,2,151), (0,2,228), (0,2,239), (17,2,11), (0,2,250), (0,3,23), (0,2,239), (17,2,11), (0,2,250), (0,3,53), (0,3,92), (0,3,193), (0,3,101), (0,4,6), (0,3,97), (0,3,218), (0,3,184), (16,4,7), (0,3,92), (0,3,193), (0,3,101), (0,4,190), (0,3,97), (0,3,218), (0,3,184), (18,4,27)], "inflate_table table 6");
    }

    #[test]
    fn test_inflate_table_body_7() {
        let lens: Vec<u16> = vec![5u16, 4u16, 7u16, 6u16, 6u16, 5u16, 5u16, 7u16, 5u16, 5u16, 4u16, 4u16, 4u16, 5u16, 4u16, 5u16, 6u16, 4u16, 6u16, 5u16, 6u16, 4u16, 4u16, 5u16, 5u16, 5u16, 5u16, 7u16, 6u16, 7u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 6;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Dists, &lens, 30usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 7");
        assert_eq!(bits, 6u32, "inflate_table bits 7");
        let got: Vec<(u8,u8,u16)> = table[..68].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(16,4,2), (16,5,1), (22,4,129), (26,5,3073), (20,4,49), (19,5,25), (25,4,1537), (16,6,4), (20,4,33), (18,5,9), (23,4,385), (27,5,6145), (21,4,65), (22,5,193), (26,4,2049), (25,6,1025), (16,4,2), (17,5,7), (22,4,129), (27,5,4097), (20,4,49), (21,5,97), (25,4,1537), (23,6,257), (20,4,33), (19,5,17), (23,4,385), (28,5,8193), (21,4,65), (24,5,769), (26,4,2049), (1,6,64), (16,4,2), (16,5,1), (22,4,129), (26,5,3073), (20,4,49), (19,5,25), (25,4,1537), (17,6,5), (20,4,33), (18,5,9), (23,4,385), (27,5,6145), (21,4,65), (22,5,193), (26,4,2049), (29,6,16385), (16,4,2), (17,5,7), (22,4,129), (27,5,4097), (20,4,49), (21,5,97), (25,4,1537), (24,6,513), (20,4,33), (19,5,17), (23,4,385), (28,5,8193), (21,4,65), (24,5,769), (26,4,2049), (1,6,66), (16,1,3), (18,1,13), (28,1,12289), (29,1,24577)], "inflate_table table 7");
    }

    #[test]
    fn test_inflate_table_body_8() {
        let lens: Vec<u16> = vec![4u16, 5u16, 5u16, 4u16, 7u16, 8u16, 4u16, 4u16, 3u16, 4u16, 3u16, 3u16, 5u16, 8u16, 4u16, 5u16, 4u16, 5u16, 6u16];
        let mut table = vec![zlib_types::CodeEntry::default(); 1444];
        let mut bits: u32 = 7;
        let mut work = vec![0u16; 320];
        let r = super::inflate_table(zlib_types::CodeType::Codes, &lens, 19usize, &mut table, &mut bits, &mut work);
        assert!(r.is_ok(), "inflate_table ret 8");
        assert_eq!(bits, 7u32, "inflate_table bits 8");
        let got: Vec<(u8,u8,u16)> = table[..130].iter().map(|e|(e.op,e.bits,e.val)).collect();
        assert_eq!(got, vec![(0,3,8), (0,4,6), (0,3,11), (0,4,16), (0,3,10), (0,4,9), (0,4,0), (0,5,12), (0,3,8), (0,4,7), (0,3,11), (0,5,1), (0,3,10), (0,4,14), (0,4,3), (0,5,17), (0,3,8), (0,4,6), (0,3,11), (0,4,16), (0,3,10), (0,4,9), (0,4,0), (0,5,15), (0,3,8), (0,4,7), (0,3,11), (0,5,2), (0,3,10), (0,4,14), (0,4,3), (0,6,18), (0,3,8), (0,4,6), (0,3,11), (0,4,16), (0,3,10), (0,4,9), (0,4,0), (0,5,12), (0,3,8), (0,4,7), (0,3,11), (0,5,1), (0,3,10), (0,4,14), (0,4,3), (0,5,17), (0,3,8), (0,4,6), (0,3,11), (0,4,16), (0,3,10), (0,4,9), (0,4,0), (0,5,15), (0,3,8), (0,4,7), (0,3,11), (0,5,2), (0,3,10), (0,4,14), (0,4,3), (0,7,4), (0,3,8), (0,4,6), (0,3,11), (0,4,16), (0,3,10), (0,4,9), (0,4,0), (0,5,12), (0,3,8), (0,4,7), (0,3,11), (0,5,1), (0,3,10), (0,4,14), (0,4,3), (0,5,17), (0,3,8), (0,4,6), (0,3,11), (0,4,16), (0,3,10), (0,4,9), (0,4,0), (0,5,15), (0,3,8), (0,4,7), (0,3,11), (0,5,2), (0,3,10), (0,4,14), (0,4,3), (0,6,18), (0,3,8), (0,4,6), (0,3,11), (0,4,16), (0,3,10), (0,4,9), (0,4,0), (0,5,12), (0,3,8), (0,4,7), (0,3,11), (0,5,1), (0,3,10), (0,4,14), (0,4,3), (0,5,17), (0,3,8), (0,4,6), (0,3,11), (0,4,16), (0,3,10), (0,4,9), (0,4,0), (0,5,15), (0,3,8), (0,4,7), (0,3,11), (0,5,2), (0,3,10), (0,4,14), (0,4,3), (1,7,128), (0,1,5), (0,1,13)], "inflate_table table 8");
    }

}
