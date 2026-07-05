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
    // Port of inflate.c:inflate_fixed helper — populates lencode/distcode
    // with the fixed Huffman tables per RFC 1951 §3.2.6.
    //
    // Fixed literal/length tree (LITERAL):
    //   0-143:  8 bits, codes 00110000..10111111
    //   144-255: 9 bits, codes 110010000..111111111
    //   256-279: 7 bits, codes 0000000..0010111
    //   280-287: 8 bits, codes 11000000..11000111
    //
    // Fixed distance tree:
    //   0-31: 5 bits each (all 32 distance codes the same length)
    //
    // Our Rust port computes the tables inline. CodeEntry is
    // (op: u8, bits: u8, val: u16) per the types.
    let mut lenfix: Vec<(u8, u8, u16)> = Vec::with_capacity(512);
    for sym in 0..288 {
        let bits = if sym < 144 { 8 }
                   else if sym < 256 { 9 }
                   else if sym < 280 { 7 }
                   else { 8 };
        // op=0 means literal-or-length; inflate_table fills the actual op
        // field with LITERAL/LENGTH/END_BLOCK/INVALID based on sym range.
        // Rough equivalent:
        let op = if sym < 256 { 0u8 } else if sym == 256 { 32u8 } else { 16u8 };
        lenfix.push((op, bits, sym as u16));
    }
    let distfix: Vec<(u8, u8, u16)> =
        (0..32).map(|sym: u16| (16u8, 5u8, sym)).collect();

    state.lencode = lenfix;
    state.distcode = distfix;
    state.lenbits = 9;
    state.distbits = 5;
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

#[cfg(test)]
mod tests {
    #![allow(unused_imports, unused_variables, unused_macros)]
    extern crate alloc;
    use alloc::format;
    use alloc::string::String;

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
