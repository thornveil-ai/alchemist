//! Deflate
//!
//! Module containing 14 functions: slide_hash, read_buf, fill_window,
//! deflateInit_, deflateInit2_, deflate_state_check, deflateGetDictionary,
//! zlibCompileFlags, zmemcpy, zmemcmp, zmemzero, zcalloc, zcfree, zcalloc

#![allow(unused_variables, unused_imports, dead_code)]

use zlib_types::*;
use zlib_checksum::*;
use zlib_trees::*;

use crate::*;

/// Slide Hash
/// Updates hash chain pointers and previous position indices to maintain the
/// sliding window invariant during DEFLATE compression.
///
/// Standards: RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BlockState { NeedMore, BlockDone, FinishStarted, FinishDone }

// zlib constants
const INIT_STATE: i32 = 42; const BUSY_STATE: i32 = 113; const FINISH_STATE: i32 = 666;
const GZIP_STATE: i32 = 57; const EXTRA_STATE: i32 = 69; const NAME_STATE: i32 = 73;
const COMMENT_STATE: i32 = 91; const HCRC_STATE: i32 = 103;
const Z_NO_FLUSH: i32 = 0; const Z_PARTIAL_FLUSH: i32 = 1; const Z_SYNC_FLUSH: i32 = 2;
const Z_FULL_FLUSH: i32 = 3; const Z_FINISH: i32 = 4; const Z_BLOCK: i32 = 5;
const Z_OK: i32 = 0; const Z_STREAM_END: i32 = 1; const Z_STREAM_ERROR: i32 = -2;
const Z_BUF_ERROR: i32 = -5; const Z_MEM_ERROR: i32 = -4;
const Z_DEFAULT_STRATEGY: i32 = 0; const Z_HUFFMAN_ONLY: i32 = 2; const Z_RLE: i32 = 3; const Z_FIXED: i32 = 4;
const Z_DEFLATED: i32 = 8; const Z_DEFAULT_COMPRESSION: i32 = -1; const Z_UNKNOWN: i32 = 2;
/// configuration_table: (good_length, max_lazy, nice_length, max_chain) per level 0..9.
const CONFIG_TABLE: [(u32,u32,u32,u32); 10] = [
    (0,0,0,0),(4,4,8,4),(4,5,16,8),(4,6,32,32),(4,4,16,16),
    (8,16,32,32),(8,16,128,128),(8,32,128,256),(32,128,258,1024),(32,258,258,4096)];

const MIN_MATCH: usize = 3;
const MAX_MATCH: usize = 258;
const MIN_LOOKAHEAD: usize = 262;
const TOO_FAR: usize = 4096;
const NIL: u16 = 0;
const Z_FILTERED: i32 = 1;

fn insert_string(s: &mut DeflateState, str_idx: usize) -> u16 {
    let c = s.window[str_idx + 2] as u32;
    s.ins_h = ((s.ins_h << s.hash_shift) ^ c) & s.hash_mask;
    let hh = s.head[s.ins_h as usize];
    s.prev[str_idx & s.w_mask] = hh;
    s.head[s.ins_h as usize] = str_idx as u16;
    hh
}
fn _tr_tally_lit(strm: &mut DeflateStream, c: u32) -> bool { _tr_tally(&mut strm.state, 0, c) }
fn _tr_tally_dist(strm: &mut DeflateStream, dist: u32, len: u32) -> bool { _tr_tally(&mut strm.state, dist, len) }

pub fn slide_hash(s: &mut DeflateState) {
    let wsize = s.w_size as u16;
    for m in s.head.iter_mut().rev() {
        *m = if *m >= wsize { *m - wsize } else { 0 };
    }
    for m in s.prev.iter_mut().rev() {
        *m = if *m >= wsize { *m - wsize } else { 0 };
    }
}



/// Read Buf
/// Consumes a chunk of data from the input stream's buffer, copies it to a
/// destination, and updates checksums and stream progress counters.
///
/// Standards: RFC 1950, RFC 1952, variant:ieee_reflected
#[allow(clippy::unimplemented)]
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

/// Fill Window
/// Refills the LZ77 sliding window buffer with new data from the input stream and
/// updates the hash table with the new data to facilitate match searching.
///
/// Standards: RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]
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

/// Deflateinit 
/// Initializes a deflate compression stream with default settings for the DEFLATE
/// compression method.
///
/// Standards: RFC 1951
#[allow(clippy::unimplemented)]
pub fn deflate_init_(strm: &mut DeflateStream, level: i32, version: &str, stream_size: usize) -> Result<(), ZlibError> {
    let _ = strm;
    let _ = level;
    let _ = version;
    let _ = stream_size;
    unimplemented!("skeleton: deflate_init_ not yet implemented")
}

/// Deflateinit2 
/// Initializes the internal state and memory buffers required for the Deflate
/// compression algorithm, supporting various window sizes, memory levels, and
/// wrapper types (zlib or gzip).
///
/// Standards: RFC 1951 (Deflate), RFC 1952 (zlib)
#[allow(clippy::unimplemented)]
pub fn deflate_init2_(strm: &mut DeflateStream, level: i32, method: i32, windowBits: i32, memLevel: i32, strategy: i32, version: &str, stream_size: usize) -> Result<(), ZlibError> {
    let _ = strm;
    let _ = level;
    let _ = method;
    let _ = windowBits;
    let _ = memLevel;
    let _ = strategy;
    let _ = version;
    let _ = stream_size;
    unimplemented!("skeleton: deflate_init2_ not yet implemented")
}

/// Deflate State Check
/// Validates the integrity and consistency of a deflate stream's internal state
/// and its associated memory management functions.
///
/// Standards: RFC 1951
#[allow(clippy::unimplemented)]
/// Deflategetdictionary
/// Retrieves the current sliding window contents used as a dictionary for the
/// DEFLATE compression algorithm.
///
/// Standards: RFC 1951
#[allow(clippy::unimplemented)]
pub fn deflate_get_dictionary(strm: &mut DeflateStream, dictionary: Option<&mut [u8]>, dict_length: Option<&mut usize>) -> Result<(), ZlibError> {
    let _ = strm;
    let _ = dictionary;
    let _ = dict_length;
    unimplemented!("skeleton: deflate_get_dictionary not yet implemented")
}

/// Zlibcompileflags
/// Generates a bitmask representing the compile-time configuration, target
/// architecture data model, and enabled feature flags of the zlib library.
#[allow(clippy::unimplemented)]
pub fn zlib_compile_flags() -> u32 {
    unimplemented!("skeleton: zlib_compile_flags not yet implemented")
}

/// Zmemcpy
/// Copies a specified number of bytes from a source memory buffer to a destination
/// memory buffer.
///
/// Standards: C standard library memcpy
#[allow(clippy::unimplemented)]

pub fn zmemcpy(dst: &mut [u8], src: &[u8], n: usize) {
    for i in 0..n {
        dst[i] = src[i];
    }
}



/// Zmemcmp
/// Compares two memory regions byte-by-byte up to a specified length and returns
/// the difference between the first non-matching bytes.
#[allow(clippy::unimplemented)]

pub fn zmemcmp(s1: &[u8], s2: &[u8], n: usize) -> i32 {
    for i in 0..n {
        if s1[i] != s2[i] {
            return (s1[i] as i32) - (s2[i] as i32);
        }
    }
    0
}



/// Zmemzero
/// Sets all bytes in a specified memory region to zero.
#[allow(clippy::unimplemented)]

pub fn zmemzero(buffer: &mut [u8], len: usize) {
    for i in 0..len {
        buffer[i] = 0;
    }
}



/// Zcalloc
/// A custom memory allocator that wraps a base allocator (farmalloc) and maintains
/// a tracking table for pointer normalization and deallocation tracking.
#[allow(clippy::unimplemented)]

pub fn zcalloc(
    _opaque: Option<&dyn std::any::Any>,
    items: usize,
    size: usize,
) -> Box<[u8]> {
    // Port of zutil.c:zcalloc.
    // Safe-Rust equivalent of `calloc(items, size)`: allocate
    // items*size bytes, zero-initialized, return boxed slice.
    // The `opaque` parameter is the C allocator-callback context; Rust
    // uses the global allocator so we ignore it. All Alchemist-generated
    // code assumes Vec<u8>/Box<[u8]> backing.
    let total = items.saturating_mul(size);
    vec![0u8; total].into_boxed_slice()
}


/// Zcfree
/// Deallocates memory pointed to by a given pointer, handling both direct
/// allocations and pointers that are part of a tracking table for remapped memory.
#[allow(clippy::unimplemented)]

pub fn zcfree(
    _opaque: Option<&mut dyn std::any::Any>,
    _ptr: Box<dyn std::any::Any>,
) {
    // Port of zutil.c:zcfree.
    // No-op in safe Rust: the Box is dropped when this function returns,
    // deallocating the buffer via the global allocator. The C code calls
    // free(ptr); taking ownership by-value here is the equivalent.
}

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

fn flush_block_only(strm: &mut DeflateStream, last: i32) {
    let stored_len = (strm.state.strstart as i64 - strm.state.block_start) as u32;
    let buf: Option<Vec<u8>> = if strm.state.block_start >= 0 {
        let bs = strm.state.block_start as usize;
        Some(strm.state.window[bs..bs + stored_len as usize].to_vec())
    } else { None };
    _tr_flush_block(strm, buf.as_deref(), stored_len, last);
    strm.state.block_start = strm.state.strstart as i64;
    flush_pending(strm);
}

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

pub fn deflate_state_check(strm: &DeflateStream) -> bool {
    let status = strm.state.status;
    !(status == INIT_STATE
        || status == GZIP_STATE
        || status == EXTRA_STATE
        || status == NAME_STATE
        || status == COMMENT_STATE
        || status == HCRC_STATE
        || status == BUSY_STATE
        || status == FINISH_STATE)
}

pub fn lm_init(s: &mut DeflateState) {
    s.window_size = (2 * s.w_size) as u32;
    s.head.fill(0);
    let config = CONFIG_TABLE[s.level as usize];
    s.good_match = config.0;
    s.max_lazy_match = config.1;
    s.nice_match = config.2 as i32;
    s.max_chain_length = config.3;
    s.strstart = 0;
    s.block_start = 0;
    s.lookahead = 0;
    s.insert = 0;
    s.match_length = 2;
    s.prev_length = 2;
    s.match_available = 0;
    s.ins_h = 0;
}

pub fn deflate_reset_keep(strm: &mut DeflateStream) -> i32 {
    if deflate_state_check(strm) {
        return Z_STREAM_ERROR;
    }
    strm.total_in = 0;
    strm.total_out = 0;
    strm.state.data_type = Z_UNKNOWN;
    strm.state.pending.clear();
    if strm.state.wrap < 0 {
        strm.state.wrap = -strm.state.wrap;
    }
    strm.state.status = INIT_STATE;
    strm.adler = if strm.state.wrap == 2 { 0 } else { 1 };
    strm.state.last_flush = -2;
    _tr_init(&mut strm.state);
    Z_OK
}

pub fn deflate_reset(strm: &mut DeflateStream) -> i32 {
    let ret = deflate_reset_keep(strm);
    if ret == Z_OK {
        lm_init(&mut strm.state);
    }
    ret
}

pub fn deflate_init2(strm: &mut DeflateStream, level: i32, method: i32, window_bits: i32, mem_level: i32, strategy: i32) -> i32 {
    let mut level = level;
    if level == Z_DEFAULT_COMPRESSION {
        level = 6;
    }

    let mut window_bits = window_bits;
    let mut wrap = 1i32;
    if window_bits < 0 {
        wrap = 0;
        if window_bits < -15 {
            return Z_STREAM_ERROR;
        }
        window_bits = -window_bits;
    } else if window_bits > 15 {
        wrap = 2;
        window_bits -= 16;
    }

    if mem_level < 1 || mem_level > 9 || method != Z_DEFLATED || window_bits < 8 || window_bits > 15 || level < 0 || level > 9 || strategy < 0 || strategy > Z_FIXED || (window_bits == 8 && wrap != 1) {
        return Z_STREAM_ERROR;
    }

    if window_bits == 8 {
        window_bits = 9;
    }

    let s = &mut strm.state;
    s.status = INIT_STATE;
    s.wrap = wrap;
    s.w_bits = window_bits as u32;
    s.w_size = 1usize << s.w_bits;
    s.w_mask = s.w_size - 1;

    s.hash_bits = (mem_level as u32) + 7;
    s.hash_size = 1u32 << s.hash_bits;
    s.hash_mask = s.hash_size - 1;
    s.hash_shift = (s.hash_bits + 3 - 1) / 3;

    s.window = vec![0u8; 2 * s.w_size];
    s.prev = vec![0u16; s.w_size];
    s.head = vec![0u16; s.hash_size as usize];
    s.dyn_ltree = vec![zlib_types::TreeElement::default(); 573];
    s.dyn_dtree = vec![zlib_types::TreeElement::default(); 61];
    s.bl_tree = vec![zlib_types::TreeElement::default(); 39];
    s.bl_count = vec![0u16; 16];
    s.heap = vec![0i32; 573];
    s.depth = vec![0u8; 573];

    s.lit_bufsize = 1u32 << (mem_level + 6);
    s.sym_buf = vec![0u8; s.lit_bufsize as usize * 3];
    s.sym_end = (s.lit_bufsize - 1) * 3;

    s.level = level;
    s.strategy = strategy;
    s.method = method as u8;

    deflate_reset(strm)
}

pub fn deflate(strm: &mut DeflateStream, flush: i32) -> i32 {
    let rank = |f: i32| -> i32 {
        f * 2 - (if f > 4 { 9 } else { 0 })
    };

    if deflate_state_check(strm) || flush > Z_BLOCK || flush < 0 {
        return Z_STREAM_ERROR;
    }
    if strm.state.status == FINISH_STATE && flush != Z_FINISH {
        return Z_STREAM_ERROR;
    }
    if strm.avail_out == 0 {
        return Z_BUF_ERROR;
    }

    let old_flush = strm.state.last_flush;
    strm.state.last_flush = flush;

    if !strm.state.pending.is_empty() {
        flush_pending(strm);
        if strm.avail_out == 0 {
            strm.state.last_flush = -1;
            return Z_OK;
        }
    } else if strm.avail_in == 0 && rank(flush) <= rank(old_flush) && flush != Z_FINISH {
        return Z_BUF_ERROR;
    }

    if strm.state.status == INIT_STATE {
        if strm.state.wrap == 0 {
            strm.state.status = BUSY_STATE;
        } else if strm.state.wrap == 1 {
            let mut header = (Z_DEFLATED + ((strm.state.w_bits as i32 - 8) << 4)) << 8;
            let level_flags = if strm.state.strategy >= Z_HUFFMAN_ONLY || strm.state.level < 2 {
                0
            } else if strm.state.level < 6 {
                1
            } else if strm.state.level == 6 {
                2
            } else {
                3
            };
            header |= level_flags << 6;
            if strm.state.strstart != 0 {
                header |= 0x20;
            }
            header += 31 - (header % 31);
            strm.state.status = BUSY_STATE;
            strm.state.pending.push((header >> 8) as u8);
            strm.state.pending.push((header & 0xff) as u8);
            if strm.state.strstart != 0 {
                // Push adler high/low 4 bytes MSB
                strm.state.pending.push((strm.adler >> 24) as u8);
                strm.state.pending.push((strm.adler >> 16) as u8);
                strm.state.pending.push((strm.adler >> 8) as u8);
                strm.state.pending.push(strm.adler as u8);
            }
            strm.adler = 1;
        }
    }

    if strm.avail_in != 0 || strm.state.lookahead != 0 || (flush != Z_NO_FLUSH && strm.state.status != FINISH_STATE) {
        let bstate = if strm.state.level == 0 {
            deflate_stored(strm, flush)
        } else if strm.state.strategy == Z_HUFFMAN_ONLY {
            deflate_huff(strm, flush)
        } else if strm.state.strategy == Z_RLE {
            deflate_rle(strm, flush)
        } else if strm.state.level < 4 {
            deflate_fast(strm, flush)
        } else {
            deflate_slow(strm, flush)
        };

        if bstate == BlockState::FinishStarted || bstate == BlockState::FinishDone {
            strm.state.status = FINISH_STATE;
        }

        if bstate == BlockState::NeedMore || bstate == BlockState::FinishStarted {
            if strm.avail_out == 0 {
                strm.state.last_flush = -1;
            }
            return Z_OK;
        }

        if bstate == BlockState::BlockDone {
            if flush == Z_PARTIAL_FLUSH {
                _tr_align(&mut strm.state);
            } else if flush != Z_BLOCK {
                _tr_stored_block(&mut strm.state, &[], 0, 0);
                if flush == Z_FULL_FLUSH {
                    strm.state.head.fill(0);
                    if strm.state.lookahead == 0 {
                        strm.state.strstart = 0;
                        strm.state.block_start = 0;
                        strm.state.insert = 0;
                    }
                }
            }
            flush_pending(strm);
            if strm.avail_out == 0 {
                strm.state.last_flush = -1;
                return Z_OK;
            }
        }
    }

    if flush != Z_FINISH {
        return Z_OK;
    }

    if strm.state.wrap <= 0 {
        return Z_STREAM_END;
    }

    strm.state.pending.push(((strm.adler >> 24) & 0xff) as u8);
    strm.state.pending.push(((strm.adler >> 16) & 0xff) as u8);
    strm.state.pending.push(((strm.adler >> 8) & 0xff) as u8);
    strm.state.pending.push((strm.adler & 0xff) as u8);

    flush_pending(strm);
    if strm.state.wrap > 0 {
        strm.state.wrap = -strm.state.wrap;
    }

    if !strm.state.pending.is_empty() {
        Z_OK
    } else {
        Z_STREAM_END
    }
}

pub fn deflate_end(strm: &mut DeflateStream) -> i32 {
    if deflate_state_check(strm) {
        return Z_STREAM_ERROR;
    }
    let status = strm.state.status;
    strm.state.window = Vec::new();
    strm.state.prev = Vec::new();
    strm.state.head = Vec::new();
    strm.state.pending = Vec::new();
    strm.state.sym_buf = Vec::new();
    if status == BUSY_STATE { -3 } else { Z_OK }
}

pub fn deflate_stored(strm: &mut DeflateStream, flush: i32) -> BlockState { let _ = (strm, flush); unimplemented!("deflate_stored") }

pub fn deflate_fast(strm: &mut DeflateStream, flush: i32) -> BlockState {
    let mut bflush = false;
    loop {
        let mut lookahead = strm.state.lookahead;
        if lookahead < MIN_LOOKAHEAD {
            fill_window(strm);
            lookahead = strm.state.lookahead;
            if lookahead < MIN_LOOKAHEAD && flush == Z_NO_FLUSH {
                return BlockState::NeedMore;
            }
            if lookahead == 0 {
                break;
            }
        }

        let mut hash_head = 0u16;
        let strstart = strm.state.strstart;
        if lookahead >= MIN_MATCH {
            hash_head = insert_string(&mut strm.state, strstart);
        }

        let mut match_length = 0u32;
        if hash_head != 0 && (strstart as i32 - hash_head as i32) <= (strm.state.w_size as i32 - 262) {
            match_length = longest_match(&mut strm.state, hash_head as usize);
        }

        if match_length >= MIN_MATCH as u32 {
            let match_start = strm.state.match_start;
            let dist = strstart - match_start;
            let len = match_length - MIN_MATCH as u32;
            bflush = _tr_tally_dist(strm, dist as u32, len);
            
            strm.state.lookahead -= match_length as usize;
            let max_insert_length = strm.state.max_lazy_match;
            
            if match_length <= max_insert_length && strm.state.lookahead >= MIN_MATCH {
                match_length -= 1;
                let mut current_strstart = strstart + 1;
                while match_length != 0 {
                    insert_string(&mut strm.state, current_strstart);
                    current_strstart += 1;
                    match_length -= 1;
                }
                strm.state.strstart = current_strstart;
            } else {
                let new_strstart = strstart + match_length as usize;
                strm.state.strstart = new_strstart;
                let window_ref = &strm.state.window;
                let ins_h_val = window_ref[new_strstart] as u32;
                let c_val = window_ref[new_strstart + 1];
                let hash_shift = strm.state.hash_shift;
                let hash_mask = strm.state.hash_mask;
                strm.state.ins_h = ((ins_h_val << hash_shift) ^ (c_val as u32)) & hash_mask;
            }
        } else {
            let window_ref = &strm.state.window;
            let byte = window_ref[strstart];
            bflush = _tr_tally_lit(strm, byte as u32);
            strm.state.lookahead -= 1;
            strm.state.strstart += 1;
        }

        if bflush {
            flush_block_only(strm, 0);
            if strm.avail_out == 0 {
                return BlockState::NeedMore;
            }
        }
    }

    let strstart = strm.state.strstart;
    strm.state.insert = if strstart < MIN_MATCH - 1 { strstart as u32 } else { (MIN_MATCH - 1) as u32 };

    if flush == Z_FINISH {
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

pub fn deflate_slow(strm: &mut DeflateStream, flush: i32) -> BlockState {
    loop {
        if strm.state.lookahead < MIN_LOOKAHEAD {
            fill_window(strm);
            if strm.state.lookahead < MIN_LOOKAHEAD && flush == Z_NO_FLUSH {
                return BlockState::NeedMore;
            }
            if strm.state.lookahead == 0 {
                break;
            }
        }

        let mut hash_head = NIL;
        if strm.state.lookahead >= MIN_MATCH {
            let ss = strm.state.strstart;
            hash_head = insert_string(&mut strm.state, ss);
        }

        strm.state.prev_length = strm.state.match_length;
        strm.state.prev_match = strm.state.match_start as u32;
        strm.state.match_length = (MIN_MATCH - 1) as u32;

        let max_dist = strm.state.w_size - 262;
        if hash_head != NIL
            && strm.state.prev_length < strm.state.max_lazy_match
            && (strm.state.strstart - hash_head as usize) <= max_dist
        {
            let hh = hash_head as usize;
            strm.state.match_length = longest_match(&mut strm.state, hh);
            if strm.state.match_length <= 5
                && (strm.state.strategy == Z_FILTERED
                    || (strm.state.match_length == MIN_MATCH as u32
                        && (strm.state.strstart - strm.state.match_start) > TOO_FAR))
            {
                strm.state.match_length = (MIN_MATCH - 1) as u32;
            }
        }

        let mut bflush = false;
        if strm.state.prev_length >= MIN_MATCH as u32
            && strm.state.match_length <= strm.state.prev_length
        {
            let max_insert = strm.state.strstart + strm.state.lookahead - MIN_MATCH;
            let dist = (strm.state.strstart as u32).wrapping_sub(1).wrapping_sub(strm.state.prev_match);
            let len = strm.state.prev_length - (MIN_MATCH as u32);
            bflush = _tr_tally_dist(strm, dist, len);

            strm.state.lookahead -= (strm.state.prev_length as usize) - 1;
            strm.state.prev_length -= 2;

            while strm.state.prev_length != 0 {
                strm.state.strstart += 1;
                if strm.state.strstart <= max_insert {
                    let ss = strm.state.strstart;
                    insert_string(&mut strm.state, ss);
                }
                strm.state.prev_length -= 1;
            }

            strm.state.match_available = 0;
            strm.state.match_length = (MIN_MATCH - 1) as u32;
            strm.state.strstart += 1;

            if bflush {
                flush_block_only(strm, 0);
                if strm.avail_out == 0 {
                    return BlockState::NeedMore;
                }
            }
        } else if strm.state.match_available != 0 {
            let byte = strm.state.window[strm.state.strstart - 1];
            bflush = _tr_tally_lit(strm, byte as u32);
            if bflush {
                flush_block_only(strm, 0);
                if strm.avail_out == 0 {
                    return BlockState::NeedMore;
                }
            }
            strm.state.strstart += 1;
            strm.state.lookahead -= 1;
            if strm.avail_out == 0 {
                return BlockState::NeedMore;
            }
        } else {
            strm.state.match_available = 1;
            strm.state.strstart += 1;
            strm.state.lookahead -= 1;
        }
    }

    if strm.state.match_available != 0 {
        let byte = strm.state.window[strm.state.strstart - 1];
        _tr_tally_lit(strm, byte as u32);
        strm.state.match_available = 0;
    }

    strm.state.insert = if strm.state.strstart < MIN_MATCH - 1 {
        strm.state.strstart as u32
    } else {
        (MIN_MATCH - 1) as u32
    };

    if flush == Z_FINISH {
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

pub fn deflate_rle(strm: &mut DeflateStream, flush: i32) -> BlockState {
    let mut bflush = false;
    loop {
        if strm.state.lookahead <= MAX_MATCH {
            fill_window(strm);
            if strm.state.lookahead <= MAX_MATCH && flush == Z_NO_FLUSH {
                return BlockState::NeedMore;
            }
            if strm.state.lookahead == 0 {
                break;
            }
        }

        strm.state.match_length = 0;
        if strm.state.lookahead >= MIN_MATCH && strm.state.strstart > 0 {
            let prev = strm.state.window[strm.state.strstart - 1];
            if strm.state.window[strm.state.strstart] == prev
                && strm.state.window[strm.state.strstart + 1] == prev
                && strm.state.window[strm.state.strstart + 2] == prev
            {
                let mut ml = 0usize;
                while ml < MAX_MATCH && strm.state.window[strm.state.strstart + ml] == prev {
                    ml += 1;
                }
                if ml > strm.state.lookahead {
                    ml = strm.state.lookahead;
                }
                strm.state.match_length = ml as u32;
            }
        }

        if strm.state.match_length >= MIN_MATCH as u32 {
            bflush = _tr_tally_dist(strm, 1, strm.state.match_length - MIN_MATCH as u32);
            strm.state.lookahead -= strm.state.match_length as usize;
            strm.state.strstart += strm.state.match_length as usize;
            strm.state.match_length = 0;
        } else {
            bflush = _tr_tally_lit(strm, strm.state.window[strm.state.strstart] as u32);
            strm.state.lookahead -= 1;
            strm.state.strstart += 1;
        }

        if bflush {
            flush_block_only(strm, 0);
            if strm.avail_out == 0 {
                return BlockState::NeedMore;
            }
        }
    }

    strm.state.insert = 0;
    if flush == Z_FINISH {
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

#[cfg(test)]
mod tests {
    #![allow(unused_imports, unused_variables, unused_macros)]
    extern crate alloc;
    use alloc::format;
    use alloc::string::String;

    #[test]
    fn test_rle_0() {
        let input: Vec<u8> = vec![];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 3);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![3, 0], "rle 0");
    }
    #[test]
    fn test_rle_1() {
        let input: Vec<u8> = vec![97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 3);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![75, 4, 0], "rle 1");
    }
    #[test]
    fn test_rle_2() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 3);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![75, 68, 3, 0], "rle 2");
    }
    #[test]
    fn test_rle_3() {
        let input: Vec<u8> = vec![97, 97, 98, 98, 99, 99, 100, 100, 97, 97, 98, 98, 99, 99];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 3);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![75, 76, 76, 74, 74, 78, 78, 73, 73, 76, 76, 74, 74, 78, 6, 0], "rle 3");
    }
    #[test]
    fn test_rle_4() {
        let input: Vec<u8> = vec![130, 183, 14, 238, 127, 26, 80, 57, 190, 240, 126, 194, 52, 127, 6, 110, 208, 143, 93, 199, 81, 36, 71, 227, 64, 67, 0, 2, 107, 110, 84, 85, 148, 160, 101, 104, 93, 100, 196, 152, 11, 184, 212, 84, 74, 135, 33, 169, 154, 1, 173, 33, 158, 181, 156, 246, 161, 94, 246, 241, 90, 29, 131, 11, 183, 206, 9, 214, 187, 192, 4, 231, 23, 92, 100, 60, 125, 236, 176, 181, 128, 236, 55, 188, 151, 18, 221, 46, 106, 174, 185, 75, 174, 141, 47, 159, 162, 156, 90, 40, 76, 158, 247, 82, 24, 41, 207, 16, 121, 176, 128, 233, 215, 74, 28, 16, 252, 171, 106, 66, 67, 211, 54, 86, 222, 190, 76, 30, 215, 150, 72, 232, 86, 232, 249, 162, 245, 140, 149, 240, 206, 75, 57, 193, 91, 255, 173, 92, 45, 251, 139, 184, 32, 182, 17, 156, 186, 143, 248, 135, 150, 174, 91, 5, 242, 128, 166, 140, 237, 147, 182, 178, 140, 176, 209, 179, 88, 230, 186, 171, 72, 85, 101, 185, 244, 144, 40, 213, 87, 215, 154, 138, 14, 100, 81, 225, 92, 112, 92, 21];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 3);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![1, 200, 0, 55, 255, 130, 183, 14, 238, 127, 26, 80, 57, 190, 240, 126, 194, 52, 127, 6, 110, 208, 143, 93, 199, 81, 36, 71, 227, 64, 67, 0, 2, 107, 110, 84, 85, 148, 160, 101, 104, 93, 100, 196, 152, 11, 184, 212, 84, 74, 135, 33, 169, 154, 1, 173, 33, 158, 181, 156, 246, 161, 94, 246, 241, 90, 29, 131, 11, 183, 206, 9, 214, 187, 192, 4, 231, 23, 92, 100, 60, 125, 236, 176, 181, 128, 236, 55, 188, 151, 18, 221, 46, 106, 174, 185, 75, 174, 141, 47, 159, 162, 156, 90, 40, 76, 158, 247, 82, 24, 41, 207, 16, 121, 176, 128, 233, 215, 74, 28, 16, 252, 171, 106, 66, 67, 211, 54, 86, 222, 190, 76, 30, 215, 150, 72, 232, 86, 232, 249, 162, 245, 140, 149, 240, 206, 75, 57, 193, 91, 255, 173, 92, 45, 251, 139, 184, 32, 182, 17, 156, 186, 143, 248, 135, 150, 174, 91, 5, 242, 128, 166, 140, 237, 147, 182, 178, 140, 176, 209, 179, 88, 230, 186, 171, 72, 85, 101, 185, 244, 144, 40, 213, 87, 215, 154, 138, 14, 100, 81, 225, 92, 112, 92, 21], "rle 4");
    }
    #[test]
    fn test_rle_5() {
        let input: Vec<u8> = vec![1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 2, 0, 1, 1, 1, 1, 2, 2, 0, 2, 0, 0, 2, 1, 0, 1, 1, 1, 1, 0, 2, 2, 1, 0, 2, 2, 1, 0, 1, 2, 2, 1, 2, 1, 1, 0, 1, 1, 2, 2, 2, 1, 1, 0, 0, 2, 1, 2, 1, 0, 0, 2, 0, 1, 2, 0, 1, 0, 1, 2, 2, 2, 0, 1, 2, 2, 1, 1, 1, 0, 1, 1, 1, 2, 1, 1, 0, 2, 2, 1, 2, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 0, 0, 2, 2, 1, 0, 1, 0, 0, 1, 0, 1, 2, 2, 1, 0, 1, 0, 0, 1, 1, 0, 2, 1, 1, 1, 2, 1, 2, 2, 2, 2, 0, 0, 0, 1, 1, 2, 2, 1, 2, 1, 2, 2, 0, 1, 1, 1, 2, 2, 2, 0, 0, 0, 1, 2, 1, 2, 0, 2, 2, 0, 0, 1, 1, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 2, 2, 0, 1, 1, 0, 1, 0, 2, 1, 2, 1, 2, 1, 1, 0, 0, 1, 2, 2, 1, 1, 2, 0, 1, 2, 2, 0, 0, 2, 0, 1, 0, 0, 2, 0, 1, 2, 1, 0, 1, 2, 1, 0, 0, 0, 0, 2, 2, 0, 2, 0, 1, 2, 1, 0, 0, 2, 0, 1, 0, 0, 2, 0, 0, 2, 0, 2, 1, 2, 0, 1, 0, 2, 2, 0, 2, 1, 2, 0, 0, 1, 0, 1, 2, 2, 1, 1, 1, 2, 1, 0, 0, 2, 1, 0, 2, 2, 2, 2, 1, 2, 2, 2, 0, 1, 0, 2, 0, 1, 1, 2, 0, 0, 1, 1, 2, 1, 0, 0, 2, 0, 2];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 3);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![29, 193, 1, 1, 0, 48, 12, 131, 48, 192, 191, 232, 245, 79, 228, 17, 9, 167, 8, 18, 135, 146, 18, 203, 20, 173, 20, 50, 33, 12, 177, 194, 82, 81, 83, 202, 28, 28, 132, 18, 65, 44, 17, 148, 212, 108, 0, 45, 179, 80, 43, 192, 140, 2, 237, 115, 10, 69, 50, 83, 176, 52, 44, 8, 33, 76, 76, 166, 8, 19, 66, 8, 34, 67, 138, 12, 196, 82, 19, 146, 198, 10, 9, 13, 52, 33, 58], "rle 5");
    }
    #[test]
    fn test_rle_6() {
        let input: Vec<u8> = vec![120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122, 120, 121, 122];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 3);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![5, 193, 1, 1, 0, 0, 0, 64, 160, 219, 88, 175, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 48, 12, 195, 6], "rle 6");
    }
    #[test]
    fn test_rle_7() {
        let input: Vec<u8> = vec![1, 1, 3, 1, 1, 1, 3, 3, 2, 1, 2, 2, 2, 1, 1, 3, 1, 3, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 3, 2, 1, 1, 1, 1, 3, 1, 2, 2, 1, 1, 1, 2, 1, 3, 1, 3, 3, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 2, 2, 1, 3, 2, 1, 2, 2, 1, 1, 1, 1, 1, 1, 2, 2, 1, 3, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 2, 2, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 3, 1, 1, 3, 2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1, 1, 1, 3, 2, 1, 1, 2, 1, 2, 2, 1, 1, 1, 3, 3, 3, 1, 1, 1, 1, 2, 1, 2, 1, 1, 1, 2, 2, 1, 1, 1, 2, 2, 1, 1, 1, 1, 1, 3, 2, 1, 3, 1, 1, 1, 1, 1, 3, 1, 3, 1, 1, 3, 1, 2, 3, 1, 2, 2, 3, 2, 3, 1, 1, 1, 2, 1, 3, 1, 1, 1, 2, 1, 1, 2, 1, 1, 1, 3, 1, 2, 1, 1, 2, 3, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 2, 1, 2, 3, 1, 1, 1, 3, 1, 2, 1, 1, 1, 2, 1, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 3, 3];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 3);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![45, 193, 129, 17, 3, 33, 0, 4, 161, 97, 175, 255, 158, 163, 111, 128, 97, 75, 197, 44, 66, 44, 199, 20, 50, 27, 249, 43, 202, 82, 62, 101, 158, 124, 202, 145, 107, 44, 132, 92, 139, 20, 182, 57, 18, 10, 229, 90, 230, 154, 49, 77, 173, 33, 67, 132, 137, 134, 60, 105, 152, 16, 205, 147, 99, 251, 1], "rle 7");
    }

    #[test]
    fn test_all_0() {
        let input: Vec<u8> = vec![194, 102, 91, 117, 127, 68, 44, 128, 196, 45, 250, 102, 215, 110, 191, 198, 108, 77, 236, 91, 173, 42, 44, 240, 161, 206, 21, 137, 3, 217, 104, 185, 41, 236, 101, 236, 26, 183, 66, 110, 82, 226, 90, 90, 18, 56, 11, 87, 242, 214, 41, 217, 44, 73, 158, 2, 195, 168, 69, 207, 102, 28, 108, 226, 131, 206, 64, 181, 243, 28, 67, 77, 209, 63, 49, 60, 73, 151, 89, 90, 209, 74, 106, 163, 255, 119, 131, 60, 185, 95, 37, 147, 5, 24, 172, 110, 193, 204, 172, 204, 197, 212, 189, 47, 92, 19, 190, 204, 227, 117, 159, 115, 159, 54, 160, 111, 127, 196, 151, 224, 41, 224, 215, 131, 35, 150, 164, 244, 65, 131, 220, 148, 209, 81, 144, 194, 225, 99, 194, 172, 101, 176, 2, 181, 151, 98, 87, 133, 213, 118, 209, 176, 204, 1, 57, 103, 0, 158, 85, 227, 105, 135, 213, 239, 147, 102, 10, 53, 157, 38, 16, 29, 213, 153, 189, 151, 99, 51, 202, 204, 88, 135, 235, 168, 65, 66, 228, 199, 214, 91, 184, 128, 106, 140, 237, 195, 94, 245, 243, 86, 38, 122, 235, 7, 58, 168, 252, 36, 171, 2, 140, 6, 163, 211, 133, 84, 69, 24, 203, 18, 24, 175, 117, 149, 81, 224, 29, 213, 117, 96, 59, 248, 87, 139, 141, 186, 36, 101, 88, 181, 41, 58, 64, 70, 76, 44, 16, 194, 85, 181, 118, 82, 174, 27, 175, 223, 96, 157, 91, 56, 75, 254, 6, 118, 192, 49, 120, 227, 41, 82, 85, 227, 191, 129, 160, 23, 203, 10, 153, 81, 67, 5, 146, 151, 148, 63, 252, 218, 37, 20, 181, 83, 162, 171, 167, 17, 192, 138, 116, 77, 9, 147, 204, 214, 116, 89, 208, 27, 108, 123, 133, 83, 48, 222, 2, 14, 103, 67, 92, 153, 31, 130, 93, 220, 76, 1, 18, 202, 228, 37, 84, 119, 174, 222, 67, 244, 46, 189, 81, 119, 248, 106, 51, 223, 103, 88, 68, 243, 127, 88, 131, 85, 39, 120, 123, 116, 215, 202, 37, 123, 128, 165, 171, 253, 96, 49, 15, 19, 223, 31, 161, 97, 25, 149, 94, 137, 130, 5, 151, 100, 186, 58, 81, 176, 199, 72, 156, 133, 101, 231, 28, 13, 181, 118, 72, 40, 194, 9, 183, 162, 192, 125, 78, 37, 11, 14, 90, 108, 113, 175, 131, 36, 0];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![1, 157, 1, 98, 254, 194, 102, 91, 117, 127, 68, 44, 128, 196, 45, 250, 102, 215, 110, 191, 198, 108, 77, 236, 91, 173, 42, 44, 240, 161, 206, 21, 137, 3, 217, 104, 185, 41, 236, 101, 236, 26, 183, 66, 110, 82, 226, 90, 90, 18, 56, 11, 87, 242, 214, 41, 217, 44, 73, 158, 2, 195, 168, 69, 207, 102, 28, 108, 226, 131, 206, 64, 181, 243, 28, 67, 77, 209, 63, 49, 60, 73, 151, 89, 90, 209, 74, 106, 163, 255, 119, 131, 60, 185, 95, 37, 147, 5, 24, 172, 110, 193, 204, 172, 204, 197, 212, 189, 47, 92, 19, 190, 204, 227, 117, 159, 115, 159, 54, 160, 111, 127, 196, 151, 224, 41, 224, 215, 131, 35, 150, 164, 244, 65, 131, 220, 148, 209, 81, 144, 194, 225, 99, 194, 172, 101, 176, 2, 181, 151, 98, 87, 133, 213, 118, 209, 176, 204, 1, 57, 103, 0, 158, 85, 227, 105, 135, 213, 239, 147, 102, 10, 53, 157, 38, 16, 29, 213, 153, 189, 151, 99, 51, 202, 204, 88, 135, 235, 168, 65, 66, 228, 199, 214, 91, 184, 128, 106, 140, 237, 195, 94, 245, 243, 86, 38, 122, 235, 7, 58, 168, 252, 36, 171, 2, 140, 6, 163, 211, 133, 84, 69, 24, 203, 18, 24, 175, 117, 149, 81, 224, 29, 213, 117, 96, 59, 248, 87, 139, 141, 186, 36, 101, 88, 181, 41, 58, 64, 70, 76, 44, 16, 194, 85, 181, 118, 82, 174, 27, 175, 223, 96, 157, 91, 56, 75, 254, 6, 118, 192, 49, 120, 227, 41, 82, 85, 227, 191, 129, 160, 23, 203, 10, 153, 81, 67, 5, 146, 151, 148, 63, 252, 218, 37, 20, 181, 83, 162, 171, 167, 17, 192, 138, 116, 77, 9, 147, 204, 214, 116, 89, 208, 27, 108, 123, 133, 83, 48, 222, 2, 14, 103, 67, 92, 153, 31, 130, 93, 220, 76, 1, 18, 202, 228, 37, 84, 119, 174, 222, 67, 244, 46, 189, 81, 119, 248, 106, 51, 223, 103, 88, 68, 243, 127, 88, 131, 85, 39, 120, 123, 116, 215, 202, 37, 123, 128, 165, 171, 253, 96, 49, 15, 19, 223, 31, 161, 97, 25, 149, 94, 137, 130, 5, 151, 100, 186, 58, 81, 176, 199, 72, 156, 133, 101, 231, 28, 13, 181, 118, 72, 40, 194, 9, 183, 162, 192, 125, 78, 37, 11, 14, 90, 108, 113, 175, 131, 36, 0], "all L1 0");
    }
    #[test]
    fn test_all_1() {
        let input: Vec<u8> = vec![0, 5, 3, 0, 5, 5, 2, 3, 3, 4, 3, 4, 5, 2, 2, 5, 2, 0, 2, 4, 1, 0, 0, 1, 2, 2, 4, 0, 2, 2, 4, 4, 1, 1, 3, 5, 3, 4, 0, 4, 5, 2, 0, 3, 0, 5, 0, 2, 3, 5, 3, 3, 2, 4, 1, 4, 5, 4, 0, 2, 3, 1, 0, 4, 2, 3, 5, 3, 2, 4, 0, 5, 0, 0, 4, 0, 5, 1, 3, 1, 3, 5, 5, 4, 4, 0, 0, 0, 2, 1, 1, 5, 5, 0, 0, 3, 2, 1, 1, 5, 2, 1, 5, 3, 0, 2, 1, 3, 3, 5, 0, 0, 2, 4, 2, 2, 5, 1, 2, 5, 0, 0, 5, 4, 0, 2, 3, 3, 1, 2, 4, 3, 1, 4, 2, 3, 2, 4, 2, 5, 1, 3, 2, 1, 1, 2, 4, 1, 4, 1, 4, 2, 4, 4, 0, 1, 4, 3, 1, 4, 0, 2, 5, 5, 3, 4, 0, 0, 3, 0, 3, 3, 0, 0, 0, 1, 0, 1, 2, 1, 0, 1, 5, 2, 5, 2, 1, 4, 5, 5, 1, 0, 4, 0, 2, 0, 1, 2, 3, 2, 4, 0, 3, 5, 2, 3, 4, 4, 2, 1, 2, 1, 0, 5, 2, 5, 4, 5, 1, 1, 5, 4, 4];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 2, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![29, 143, 199, 1, 192, 48, 12, 2, 105, 218, 127, 229, 156, 243, 144, 11, 96, 192, 186, 234, 46, 237, 186, 75, 46, 202, 44, 57, 153, 152, 217, 189, 78, 112, 66, 168, 112, 43, 138, 29, 116, 173, 61, 0, 233, 73, 44, 46, 234, 219, 36, 197, 62, 192, 190, 61, 38, 36, 110, 1, 50, 66, 28, 78, 191, 67, 157, 213, 184, 128, 243, 28, 245, 51, 7, 192, 196, 143, 81, 238, 229, 19, 222, 98, 107, 154, 49, 71, 81, 58, 28, 5, 20, 160, 87, 161, 252, 98, 203, 227, 161, 119, 4, 111, 31], "all L2 1");
    }
    #[test]
    fn test_all_2() {
        let input: Vec<u8> = vec![114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 3, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![43, 74, 45, 72, 77, 44, 81, 200, 77, 85, 40, 26, 101, 33, 133, 1, 0], "all L3 2");
    }
    #[test]
    fn test_all_3() {
        let input: Vec<u8> = vec![65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 4, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![115, 116, 28, 5, 244, 4, 0], "all L4 3");
    }
    #[test]
    fn test_all_4() {
        let input: Vec<u8> = vec![102, 116, 108, 114, 102, 120, 113, 122, 114, 106, 97, 97, 116, 115, 108, 101, 101, 110, 98, 99, 114, 107, 118, 114, 106, 108, 102, 114, 107, 119, 121, 119, 100, 120, 114, 106, 98, 118, 107, 110, 103, 117, 102, 98, 102, 117, 99, 112, 109, 110, 114, 114, 109, 108, 115, 117, 109, 105, 100, 103, 121, 108, 101, 99, 105, 118, 100, 97, 108, 109, 107, 115, 104, 115, 100, 116, 118, 106, 105, 110, 101, 101, 118, 101, 106, 119, 118, 122, 121, 97, 114, 113, 114, 105, 101, 104, 110, 113, 114, 101, 105, 106, 110, 120, 109, 99, 108, 97, 112, 104, 112, 117, 99, 112, 106, 104, 121, 113, 98, 101, 111, 122, 122, 99, 108, 114, 101, 117, 108, 121, 120, 114, 98, 99, 97, 103, 120, 120, 97, 111, 103, 117, 113, 121, 111, 112, 117, 119, 97, 103, 120, 98, 116, 104, 101, 117, 110, 102, 101, 122, 114, 111, 106, 116, 97, 121, 120, 98, 106, 98, 117, 98, 118, 104, 115, 109, 108, 121, 112, 121, 101, 106, 115, 108, 119, 101, 119, 98, 122, 107, 115, 108, 114, 103, 118, 110, 118, 105, 102, 113, 105, 112, 99, 109, 119, 110, 120, 105, 116, 106, 112, 97, 114, 102, 121, 97, 119, 105, 104, 102, 118, 119, 97, 102, 113, 104, 106, 105, 107, 109, 108, 109, 102, 105, 108, 122, 102, 97, 101, 114, 111, 111, 105, 120];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 5, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![13, 204, 201, 1, 196, 32, 8, 0, 192, 90, 209, 64, 4, 209, 40, 222, 86, 191, 251, 156, 207, 80, 87, 163, 93, 175, 9, 64, 111, 138, 152, 157, 183, 56, 77, 148, 44, 174, 179, 158, 109, 226, 102, 204, 239, 32, 71, 195, 151, 148, 205, 146, 182, 145, 248, 121, 143, 162, 231, 249, 128, 166, 216, 66, 123, 250, 20, 206, 136, 19, 101, 205, 123, 192, 170, 49, 134, 92, 13, 89, 242, 78, 94, 161, 132, 242, 31, 36, 156, 234, 240, 187, 215, 171, 225, 208, 179, 205, 121, 120, 247, 134, 239, 29, 245, 124, 101, 172, 191, 92, 15, 56, 50, 225, 181, 79, 58, 156, 237, 196, 13, 55, 67, 75, 122, 202, 65, 105, 186, 112, 185, 27, 155, 218, 59, 243, 100, 170, 92, 124, 90, 121, 115, 151, 2, 70, 7, 22, 7, 154, 11, 168, 6, 225, 152, 52, 17, 235, 37, 64, 251, 62, 222, 63], "all L5 4");
    }
    #[test]
    fn test_all_5() {
        let input: Vec<u8> = vec![246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114, 246, 163, 90, 167, 72, 24, 204, 78, 239, 108, 60, 203, 169, 216, 161, 168, 110, 32, 45, 114];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![251, 182, 56, 106, 185, 135, 196, 25, 191, 247, 57, 54, 167, 87, 222, 88, 184, 34, 79, 65, 183, 232, 219, 48, 17, 3, 0], "all L6 5");
    }
    #[test]
    fn test_all_6() {
        let input: Vec<u8> = vec![197, 80, 125, 208, 117, 174, 41, 94, 30, 28, 44, 241, 194, 110, 134, 224, 173, 3, 93, 219, 222, 163, 141, 86, 73, 246, 191, 69, 247, 227, 237, 93, 232, 249, 153, 228, 237, 50, 247, 17, 232, 98, 62, 176, 250, 5, 195, 223, 160, 30, 100, 64, 62, 219, 0, 57, 64, 96, 68, 112, 129, 10, 177, 30, 22, 102, 19, 98, 112, 105, 109, 3, 94, 236, 135, 243, 180, 187, 177, 172, 124, 149, 8, 231, 53, 85, 21, 109, 204, 144, 188, 174, 95, 241, 171, 154, 245, 253, 7, 240, 14, 130, 46, 169, 55, 14, 217, 191, 1, 89, 190, 183, 187, 173, 138, 163, 135, 199, 85, 118, 158, 40, 44, 246, 36, 41, 103, 57, 176, 199, 164, 113, 125, 27, 67, 128, 203, 85, 3, 174, 160, 97, 193, 137, 254, 91, 86, 11, 31, 79, 16, 156, 181, 240, 74, 30, 70, 147, 181, 132, 126, 161, 122, 31, 127, 129, 220, 57, 42, 90, 0, 98, 162, 250, 196, 184, 71, 119, 109, 219, 232, 143, 213, 100, 228, 116, 144, 19, 111, 174, 239, 105, 51, 19, 89, 16, 101, 139, 223, 7, 36, 44, 86, 8, 127, 44, 63, 38, 35, 40, 9, 137, 190, 191, 89, 227, 197, 24, 219, 92, 240, 100, 237, 164, 39, 181, 89, 159, 157, 21, 110, 102, 22, 161, 120, 239, 56, 138, 213, 108, 63, 17, 83, 246, 61, 93, 103, 66, 87, 218, 39, 135, 41];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 7, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![1, 253, 0, 2, 255, 197, 80, 125, 208, 117, 174, 41, 94, 30, 28, 44, 241, 194, 110, 134, 224, 173, 3, 93, 219, 222, 163, 141, 86, 73, 246, 191, 69, 247, 227, 237, 93, 232, 249, 153, 228, 237, 50, 247, 17, 232, 98, 62, 176, 250, 5, 195, 223, 160, 30, 100, 64, 62, 219, 0, 57, 64, 96, 68, 112, 129, 10, 177, 30, 22, 102, 19, 98, 112, 105, 109, 3, 94, 236, 135, 243, 180, 187, 177, 172, 124, 149, 8, 231, 53, 85, 21, 109, 204, 144, 188, 174, 95, 241, 171, 154, 245, 253, 7, 240, 14, 130, 46, 169, 55, 14, 217, 191, 1, 89, 190, 183, 187, 173, 138, 163, 135, 199, 85, 118, 158, 40, 44, 246, 36, 41, 103, 57, 176, 199, 164, 113, 125, 27, 67, 128, 203, 85, 3, 174, 160, 97, 193, 137, 254, 91, 86, 11, 31, 79, 16, 156, 181, 240, 74, 30, 70, 147, 181, 132, 126, 161, 122, 31, 127, 129, 220, 57, 42, 90, 0, 98, 162, 250, 196, 184, 71, 119, 109, 219, 232, 143, 213, 100, 228, 116, 144, 19, 111, 174, 239, 105, 51, 19, 89, 16, 101, 139, 223, 7, 36, 44, 86, 8, 127, 44, 63, 38, 35, 40, 9, 137, 190, 191, 89, 227, 197, 24, 219, 92, 240, 100, 237, 164, 39, 181, 89, 159, 157, 21, 110, 102, 22, 161, 120, 239, 56, 138, 213, 108, 63, 17, 83, 246, 61, 93, 103, 66, 87, 218, 39, 135, 41], "all L7 6");
    }
    #[test]
    fn test_all_7() {
        let input: Vec<u8> = vec![1, 1, 4, 4, 0, 5, 4, 3, 5, 4, 3, 4, 2, 5, 4, 2, 4, 3, 1, 4, 5, 3, 4, 2, 3, 1, 4, 4, 0, 1, 0, 5, 0, 1, 4, 1, 4, 1, 4, 4, 3, 5, 2, 0, 2, 3, 1, 5, 2, 4, 0, 0, 4, 1, 4, 5, 2, 2, 1, 1, 5, 3, 2, 4, 3, 1, 2, 2, 5, 1, 1, 5, 2, 2, 1, 4, 4, 4, 0, 5, 3, 5, 4, 1, 3, 2, 5, 2, 3, 1, 1, 4, 2, 0, 4, 3, 2, 0, 2, 0, 3, 1, 4, 4, 2, 4, 0, 1, 3, 4, 4, 4, 1, 4, 2, 1, 1, 0, 4, 0, 3, 0, 4, 3, 2, 5, 4, 3, 4, 4, 5, 3, 0, 4, 0, 3, 4, 4, 4, 2, 1, 2, 2, 0, 5, 5, 0, 5, 0, 1, 5, 1, 5, 2, 4, 1, 1, 4, 3, 0, 2, 1, 3, 5, 3, 2, 5, 0, 1, 1, 4, 0, 0, 3, 1, 4, 3, 5, 4, 1, 1, 4, 3, 2, 0, 0, 0, 2, 3, 1, 1, 4, 0, 0, 3, 1, 4, 2, 3, 1, 4, 5, 2, 4, 3, 4, 4, 2, 5, 1, 3, 1, 5, 1, 1, 3, 3, 3, 2, 2, 5, 3, 2, 0, 4, 4, 0, 1, 3, 4, 5, 4, 0, 3, 5, 3, 4, 0, 5, 1, 0, 3, 4, 5, 3, 3, 0, 1, 1, 0, 1, 4, 5, 3, 1, 1, 5, 1, 2, 3, 5, 5, 5, 2, 5, 0, 4, 4, 5, 3, 0, 1, 3, 4, 3, 5, 1, 0, 2, 4, 2, 1, 2, 2, 0, 1, 3, 2, 3, 2, 4, 3, 5, 5, 1, 0, 0, 4, 4, 0, 4, 5, 2, 4, 2, 3, 0, 5, 0, 3, 1, 1, 2, 5, 3, 2, 0, 1, 5, 2, 4, 3, 4, 4, 4, 5, 3, 0, 1, 4, 0, 3, 4, 1, 1, 1, 5, 3, 2, 0, 3, 4, 0, 3, 5, 4, 5, 4, 1, 0, 4, 1, 3, 1, 1, 2, 5, 1, 5, 1, 0, 2, 2, 2, 3, 1, 3, 3, 4, 2, 0, 4, 3, 5, 5, 0, 5, 2, 1, 5, 1, 2, 0, 0, 5, 1, 3, 4, 0, 2, 4, 3, 3, 5, 2, 1, 5, 0, 2, 4, 5, 1];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 8, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![37, 144, 65, 18, 192, 48, 8, 2, 69, 228, 255, 95, 238, 146, 78, 123, 48, 6, 89, 140, 116, 55, 57, 243, 223, 230, 246, 172, 11, 165, 219, 215, 100, 116, 253, 16, 236, 208, 204, 222, 12, 231, 236, 74, 113, 229, 187, 161, 228, 124, 117, 194, 72, 222, 32, 213, 237, 156, 153, 154, 122, 49, 39, 163, 160, 43, 205, 141, 123, 87, 40, 180, 30, 185, 90, 172, 38, 41, 51, 5, 225, 224, 89, 25, 12, 45, 1, 198, 168, 254, 170, 237, 204, 99, 188, 102, 211, 50, 128, 9, 89, 8, 41, 217, 38, 23, 178, 123, 220, 64, 96, 171, 137, 32, 197, 198, 110, 186, 39, 193, 181, 78, 2, 225, 37, 65, 107, 68, 251, 135, 97, 147, 174, 24, 58, 53, 42, 99, 77, 62, 230, 158, 185, 126, 232, 27, 236, 14, 122, 111, 66, 1, 13, 38, 123, 234, 73, 85, 203, 37, 165, 253, 30, 165, 75, 110, 209, 67, 34, 212, 184, 184, 13, 138, 232, 3], "all L8 7");
    }
    #[test]
    fn test_all_8() {
        let input: Vec<u8> = vec![114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![43, 74, 45, 72, 77, 44, 81, 200, 77, 85, 40, 26, 101, 13, 2, 22, 0], "all L9 8");
    }
    #[test]
    fn test_all_9() {
        let input: Vec<u8> = vec![65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![115, 116, 164, 18, 0, 0], "all L1 9");
    }
    #[test]
    fn test_all_10() {
        let input: Vec<u8> = vec![122, 98, 114, 108, 109, 98, 107, 119, 106, 105, 101, 120, 99, 104, 118, 98, 106, 100, 114, 99, 116, 110, 113, 100, 106, 113, 100, 111, 104, 101, 120, 101, 108, 118, 100, 107, 113, 105, 110, 99, 103, 115, 121, 112, 119, 102, 108, 117, 119, 114, 115, 105, 121, 112, 117, 100];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 2, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![5, 193, 7, 2, 128, 32, 8, 0, 192, 191, 50, 74, 144, 76, 92, 104, 175, 239, 238, 131, 102, 15, 228, 80, 225, 141, 105, 129, 82, 195, 81, 156, 212, 233, 77, 188, 217, 22, 101, 151, 130, 119, 63, 53, 46, 155, 209, 186, 156, 58, 233, 7], "all L2 10");
    }
    #[test]
    fn test_all_11() {
        let input: Vec<u8> = vec![7, 82, 20, 34, 117, 176, 229, 111, 196, 228, 90, 101, 255, 172, 158, 229, 62, 0, 24, 173, 7, 82, 20, 34, 117, 176, 229, 111, 196, 228, 90, 101, 255, 172, 158, 229, 62, 0, 24, 173, 7, 82, 20, 34, 117, 176, 229, 111, 196, 228, 90, 101, 255, 172, 158, 229, 62, 0, 24, 173, 7, 82, 20, 34, 117, 176, 229, 111, 196, 228, 90, 101, 255, 172, 158, 229, 62, 0, 24, 173, 7, 82, 20, 34, 117, 176, 229, 111, 196, 228, 90, 101, 255, 172, 158, 229, 62, 0, 24, 173, 7, 82, 20, 34, 117, 176, 229, 111, 196, 228, 90, 101, 255, 172, 158, 229, 62, 0, 24, 173, 7, 82, 20, 34, 117, 176, 229, 111, 196, 228, 90, 101, 255, 172, 158, 229, 62, 0, 24, 173];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 3, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![99, 15, 18, 81, 42, 221, 240, 52, 255, 200, 147, 168, 212, 255, 107, 230, 61, 181, 99, 144, 88, 203, 62, 64, 98, 0], "all L3 11");
    }
    #[test]
    fn test_all_12() {
        let input: Vec<u8> = vec![122, 153, 155, 46, 66, 26, 36, 167, 173, 99, 92, 116, 220, 88, 107, 24, 23, 1, 166, 15, 220, 229, 132, 189, 98, 114, 215, 126, 140, 119, 54, 172, 27, 0, 42, 38, 24, 203, 93, 114, 44, 127, 178, 226, 208, 64, 131, 206, 103, 229, 157, 196, 233, 133, 178, 251, 112, 249, 71, 190, 110, 214, 135, 225, 150, 153, 156, 183, 103, 133, 89, 147, 49, 152, 25, 151, 219, 99, 229, 62, 205, 90, 200, 49, 236, 235, 118, 27, 14, 252, 111, 17, 54, 29, 161, 251, 118, 157, 123, 132, 169, 201, 61, 49, 61, 235, 88, 104, 98, 2, 74, 110, 176, 76, 151, 94, 13, 187, 173, 135, 58, 33, 99, 186, 150, 207, 96, 165, 147, 196, 138, 44, 206, 48, 171, 0, 255, 53, 181, 71, 94, 221, 238, 178, 33, 204, 94, 246, 242, 196, 164, 230, 223, 96, 247, 133, 60, 61, 79, 252, 150, 86, 227, 198, 60, 7, 158, 21, 0, 34, 3, 26, 217, 192, 158, 167, 196, 63, 74, 225, 63, 219, 231, 109, 67, 30, 247, 0, 133, 19, 38, 24, 201, 89, 16, 204, 33, 165, 111, 115, 182, 142, 61, 130, 8, 31, 171, 70, 183, 3, 228, 243, 92, 233, 49, 57, 27, 200, 137, 86, 39, 235, 200, 97, 178, 166, 13, 86, 154, 127, 199, 29, 29, 58, 160, 5, 20, 78, 191, 154, 146, 88, 191, 36, 51, 69, 192, 140, 102, 101, 143, 248, 7, 65, 79, 212, 155, 166, 13];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 4, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![1, 3, 1, 252, 254, 122, 153, 155, 46, 66, 26, 36, 167, 173, 99, 92, 116, 220, 88, 107, 24, 23, 1, 166, 15, 220, 229, 132, 189, 98, 114, 215, 126, 140, 119, 54, 172, 27, 0, 42, 38, 24, 203, 93, 114, 44, 127, 178, 226, 208, 64, 131, 206, 103, 229, 157, 196, 233, 133, 178, 251, 112, 249, 71, 190, 110, 214, 135, 225, 150, 153, 156, 183, 103, 133, 89, 147, 49, 152, 25, 151, 219, 99, 229, 62, 205, 90, 200, 49, 236, 235, 118, 27, 14, 252, 111, 17, 54, 29, 161, 251, 118, 157, 123, 132, 169, 201, 61, 49, 61, 235, 88, 104, 98, 2, 74, 110, 176, 76, 151, 94, 13, 187, 173, 135, 58, 33, 99, 186, 150, 207, 96, 165, 147, 196, 138, 44, 206, 48, 171, 0, 255, 53, 181, 71, 94, 221, 238, 178, 33, 204, 94, 246, 242, 196, 164, 230, 223, 96, 247, 133, 60, 61, 79, 252, 150, 86, 227, 198, 60, 7, 158, 21, 0, 34, 3, 26, 217, 192, 158, 167, 196, 63, 74, 225, 63, 219, 231, 109, 67, 30, 247, 0, 133, 19, 38, 24, 201, 89, 16, 204, 33, 165, 111, 115, 182, 142, 61, 130, 8, 31, 171, 70, 183, 3, 228, 243, 92, 233, 49, 57, 27, 200, 137, 86, 39, 235, 200, 97, 178, 166, 13, 86, 154, 127, 199, 29, 29, 58, 160, 5, 20, 78, 191, 154, 146, 88, 191, 36, 51, 69, 192, 140, 102, 101, 143, 248, 7, 65, 79, 212, 155, 166, 13], "all L4 12");
    }
    #[test]
    fn test_all_13() {
        let input: Vec<u8> = vec![4, 5, 1, 4, 3, 3, 3, 1, 0, 1, 2, 3, 4, 3, 4, 4, 5, 0, 1, 2, 3, 0, 0, 2, 1, 5, 5, 1, 4, 3, 4, 4, 3, 4, 3, 0, 4, 4, 2, 1, 5, 0, 0, 5, 1, 0, 4, 2, 0, 2, 5, 1, 2, 3, 1, 3, 1, 0, 5, 5, 1, 3, 0, 5, 1, 3, 2, 1, 5, 3, 2, 4, 3, 1, 5, 1, 1, 0, 5, 2, 3, 5, 5, 2, 0, 4, 1, 5, 2, 5, 0, 4, 5, 1, 3, 1, 5, 0, 3, 1, 4, 3, 1, 0, 1, 5, 5, 4, 3, 0, 3, 1, 4, 2, 2, 3, 0, 0, 1, 2, 2, 0, 5, 3, 3, 2, 1, 5, 5, 3, 1, 3, 3, 3, 0, 2, 4, 0, 1, 0, 0, 5, 5, 4, 1, 2, 5, 2, 4, 5, 2, 0, 2, 0, 1, 4, 1, 1, 0, 0, 2, 3, 4, 5, 3, 1, 3, 5, 3, 4, 1, 2, 5, 5, 5, 5, 2, 0, 0, 0, 1, 3, 3, 5, 4, 5, 4, 5, 2, 0, 5, 5, 3, 3, 0, 2, 2, 5, 0, 3, 3, 1];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 5, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![21, 143, 201, 17, 0, 48, 8, 2, 145, 163, 255, 150, 179, 153, 201, 195, 8, 172, 218, 93, 147, 156, 206, 105, 218, 253, 66, 242, 237, 11, 229, 69, 45, 95, 105, 167, 90, 30, 134, 35, 128, 33, 244, 130, 22, 55, 183, 163, 231, 108, 86, 111, 158, 138, 72, 46, 112, 192, 111, 144, 168, 253, 241, 103, 107, 249, 209, 193, 74, 228, 234, 152, 176, 158, 231, 130, 176, 174, 0, 197, 86, 223, 178, 124, 101, 31, 78, 58, 89, 247, 93, 196, 201, 50, 139, 11, 30], "all L5 13");
    }
    #[test]
    fn test_all_14() {
        let input: Vec<u8> = vec![114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![43, 74, 45, 72, 77, 44, 81, 200, 77, 85, 40, 26, 228, 44, 0], "all L6 14");
    }
    #[test]
    fn test_all_15() {
        let input: Vec<u8> = vec![65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 7, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![115, 116, 28, 158, 0, 0], "all L7 15");
    }
    #[test]
    fn test_all_16() {
        let input: Vec<u8> = vec![97, 102, 122, 106, 108, 116, 109, 109, 101, 103, 110, 117, 112, 99, 107, 110, 118, 111, 102, 114, 108, 108, 112, 102, 120, 98, 101, 98, 118, 120, 115, 107, 104, 109, 100, 122, 106, 99, 108, 105, 99, 98, 105, 101, 105, 116, 105, 111, 100, 111, 115, 116, 121, 106, 103, 109, 114, 97, 101, 119, 120, 118, 98, 108, 112, 102, 100, 104, 98, 112, 97, 113, 102, 115, 118, 105, 117, 121, 114, 99, 98, 100, 107, 107, 114, 102, 119, 103, 106, 119, 102, 122, 120, 115, 100, 105, 111, 115, 120, 97, 103, 122, 113, 122, 98, 122, 113, 101, 99, 108, 119, 98, 118, 104, 99, 110, 97, 114, 100, 107, 122, 109, 97, 112, 99, 106, 100, 98, 111, 100, 122, 112, 104, 118, 104, 108, 103, 101, 114, 97, 106, 113, 104, 102, 119, 117, 112, 116, 112, 113, 118, 97, 117, 117, 100, 115, 108, 114, 103, 121, 121, 103, 108, 110, 110, 119, 120, 103, 100, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 8, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![13, 202, 199, 1, 4, 33, 8, 0, 192, 90, 65, 20, 3, 230, 184, 84, 127, 55, 239, 1, 167, 81, 86, 206, 150, 203, 110, 38, 149, 83, 221, 16, 105, 238, 161, 197, 243, 102, 242, 153, 52, 26, 9, 6, 131, 13, 43, 84, 170, 115, 125, 145, 243, 0, 123, 223, 193, 255, 36, 143, 13, 186, 155, 39, 236, 111, 24, 164, 148, 134, 187, 28, 175, 211, 55, 41, 212, 249, 128, 181, 43, 106, 183, 70, 46, 30, 111, 10, 12, 74, 154, 161, 153, 72, 88, 73, 155, 63, 94, 216, 14, 136, 221, 187, 187, 219, 106, 253, 192, 222, 52, 101, 240, 247, 177, 148, 114, 31, 19, 252, 0], "all L8 16");
    }
    #[test]
    fn test_all_17() {
        let input: Vec<u8> = vec![189, 46, 171, 91, 191, 187, 153, 2, 80, 113, 27, 99, 176, 120, 51, 99, 203, 243, 147, 170, 189, 46, 171, 91, 191, 187, 153, 2, 80, 113, 27, 99, 176, 120, 51, 99, 203, 243, 147, 170, 189, 46, 171, 91, 191, 187, 153, 2, 80, 113, 27, 99, 176, 120, 51, 99, 203, 243, 147, 170, 189, 46, 171, 91, 191, 187, 153, 2, 80, 113, 27, 99, 176, 120, 51, 99, 203, 243, 147, 170, 189, 46, 171, 91, 191, 187, 153, 2, 80, 113, 27, 99, 176, 120, 51, 99, 203, 243, 147, 170];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![219, 171, 183, 58, 122, 255, 238, 153, 76, 1, 133, 210, 201, 27, 42, 140, 147, 79, 127, 158, 188, 106, 47, 149, 197, 0], "all L9 17");
    }
    #[test]
    fn test_all_18() {
        let input: Vec<u8> = vec![132, 213, 224, 173, 130, 109, 114, 129, 220, 24, 250, 139, 205, 225, 4, 64, 240, 118, 212, 119, 248, 130, 187, 207, 223, 131, 182, 70, 99, 74, 194, 239, 79, 230, 59, 88, 227, 151, 54, 31, 210, 207, 224, 249, 60, 89, 138, 35, 73, 167, 129, 178, 121, 11, 108, 74, 210, 126, 177, 163, 226, 95, 63, 37, 210, 207, 162, 146, 68, 0, 217, 169, 115, 31, 138, 161, 101, 9, 150, 90, 253, 189, 90, 60, 255, 93, 93, 58, 197, 206, 44, 93, 44, 253, 39, 75, 238, 134, 144, 213, 222, 186, 217, 102, 52, 74, 236, 57, 112, 119, 180, 152, 242, 87, 149, 119, 247, 239, 163, 18, 137, 127, 57, 205, 53, 82, 198, 52, 105, 235, 208, 132, 18, 106, 241, 47, 72, 80, 59, 108, 65, 135, 155, 167, 26, 247, 136, 167, 232, 79, 254, 76, 91, 138, 222, 44, 249, 54, 76, 121, 251, 150, 150, 123, 211, 23, 252, 101, 14, 127, 24, 4, 11, 53, 231, 103, 210, 228, 34, 32, 44, 53, 32, 227, 143, 139, 249, 156, 170, 199, 130, 213, 226, 159, 20, 31, 26, 145, 208, 45, 239, 68, 104, 4, 36, 114, 214, 48, 168, 183, 177, 243, 59, 69, 5, 74, 46, 187, 38, 193, 191, 146, 183, 103, 230, 21, 204, 152, 95, 36, 72, 92, 10, 210, 28, 40, 149, 203, 255, 52, 119, 49, 35, 197, 183, 96, 181, 102, 60, 180, 185, 152, 88, 220, 82, 70, 222, 25, 104, 212, 49, 20, 170, 159, 114, 129, 25, 112, 58, 235, 140, 47, 223, 87, 19, 48, 94, 8, 224, 2, 36, 33, 187, 5, 205, 20, 206, 89, 133, 118, 10, 48, 3, 186, 69, 34, 235, 240, 212, 120, 161, 103, 232, 91, 32, 243, 28, 20, 152, 89, 178, 113, 34, 132, 202, 90, 185, 108, 149, 62, 25, 120, 237, 225, 3, 12, 38, 81, 140, 231, 33, 145, 143, 73, 10, 89, 226, 76, 231, 102, 225, 120, 154, 21, 135, 93, 26, 135, 213, 166, 81, 195, 35, 231, 67, 248, 96, 43, 167, 225, 199, 242, 109, 21, 238, 65, 115, 124, 186, 91, 127, 223, 241, 99, 0, 29, 98, 137, 58, 32, 87, 194, 211, 7, 55, 170, 51, 42, 152, 213, 47, 160, 11, 176, 229, 161, 150, 145, 34, 205, 9, 111, 64, 191, 32, 21, 15, 197, 3, 31, 223, 81, 4, 190, 159, 254, 214, 6, 9, 207, 159, 110, 121, 40, 165, 164, 77, 60, 10, 136, 103, 96, 135, 217, 87, 244, 92, 103, 163, 225, 245, 168, 1, 245, 101, 234, 203, 57, 22, 30, 22, 253, 119, 206, 153, 21, 62, 129, 116, 81, 80, 180, 110, 173, 197, 193, 150, 158, 185, 126, 246, 162, 145, 10, 228, 254, 204, 192, 170, 87, 33, 197, 142, 179, 21, 198, 211, 162, 163, 221, 149, 155, 231, 140, 117, 188, 62, 9, 60, 127, 113, 29, 203, 209, 249, 221];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![1, 250, 1, 5, 254, 132, 213, 224, 173, 130, 109, 114, 129, 220, 24, 250, 139, 205, 225, 4, 64, 240, 118, 212, 119, 248, 130, 187, 207, 223, 131, 182, 70, 99, 74, 194, 239, 79, 230, 59, 88, 227, 151, 54, 31, 210, 207, 224, 249, 60, 89, 138, 35, 73, 167, 129, 178, 121, 11, 108, 74, 210, 126, 177, 163, 226, 95, 63, 37, 210, 207, 162, 146, 68, 0, 217, 169, 115, 31, 138, 161, 101, 9, 150, 90, 253, 189, 90, 60, 255, 93, 93, 58, 197, 206, 44, 93, 44, 253, 39, 75, 238, 134, 144, 213, 222, 186, 217, 102, 52, 74, 236, 57, 112, 119, 180, 152, 242, 87, 149, 119, 247, 239, 163, 18, 137, 127, 57, 205, 53, 82, 198, 52, 105, 235, 208, 132, 18, 106, 241, 47, 72, 80, 59, 108, 65, 135, 155, 167, 26, 247, 136, 167, 232, 79, 254, 76, 91, 138, 222, 44, 249, 54, 76, 121, 251, 150, 150, 123, 211, 23, 252, 101, 14, 127, 24, 4, 11, 53, 231, 103, 210, 228, 34, 32, 44, 53, 32, 227, 143, 139, 249, 156, 170, 199, 130, 213, 226, 159, 20, 31, 26, 145, 208, 45, 239, 68, 104, 4, 36, 114, 214, 48, 168, 183, 177, 243, 59, 69, 5, 74, 46, 187, 38, 193, 191, 146, 183, 103, 230, 21, 204, 152, 95, 36, 72, 92, 10, 210, 28, 40, 149, 203, 255, 52, 119, 49, 35, 197, 183, 96, 181, 102, 60, 180, 185, 152, 88, 220, 82, 70, 222, 25, 104, 212, 49, 20, 170, 159, 114, 129, 25, 112, 58, 235, 140, 47, 223, 87, 19, 48, 94, 8, 224, 2, 36, 33, 187, 5, 205, 20, 206, 89, 133, 118, 10, 48, 3, 186, 69, 34, 235, 240, 212, 120, 161, 103, 232, 91, 32, 243, 28, 20, 152, 89, 178, 113, 34, 132, 202, 90, 185, 108, 149, 62, 25, 120, 237, 225, 3, 12, 38, 81, 140, 231, 33, 145, 143, 73, 10, 89, 226, 76, 231, 102, 225, 120, 154, 21, 135, 93, 26, 135, 213, 166, 81, 195, 35, 231, 67, 248, 96, 43, 167, 225, 199, 242, 109, 21, 238, 65, 115, 124, 186, 91, 127, 223, 241, 99, 0, 29, 98, 137, 58, 32, 87, 194, 211, 7, 55, 170, 51, 42, 152, 213, 47, 160, 11, 176, 229, 161, 150, 145, 34, 205, 9, 111, 64, 191, 32, 21, 15, 197, 3, 31, 223, 81, 4, 190, 159, 254, 214, 6, 9, 207, 159, 110, 121, 40, 165, 164, 77, 60, 10, 136, 103, 96, 135, 217, 87, 244, 92, 103, 163, 225, 245, 168, 1, 245, 101, 234, 203, 57, 22, 30, 22, 253, 119, 206, 153, 21, 62, 129, 116, 81, 80, 180, 110, 173, 197, 193, 150, 158, 185, 126, 246, 162, 145, 10, 228, 254, 204, 192, 170, 87, 33, 197, 142, 179, 21, 198, 211, 162, 163, 221, 149, 155, 231, 140, 117, 188, 62, 9, 60, 127, 113, 29, 203, 209, 249, 221], "all L1 18");
    }
    #[test]
    fn test_all_19() {
        let input: Vec<u8> = vec![3, 2, 2, 1, 4, 3, 3, 1, 1, 5, 0, 4, 3, 1, 1, 4, 4, 0, 4, 1, 5, 4, 4, 4, 2, 5, 2, 3, 4, 0, 0, 0, 5, 2, 4, 5, 4, 1, 5, 5, 3, 3, 1, 4, 1, 2, 3, 2, 0, 4, 0, 5, 0, 5, 3, 1, 4, 3, 5, 2, 2, 0, 5, 0, 2, 5, 4, 0, 1, 5, 2, 1, 3, 5, 5, 3, 4, 3, 4, 1, 4, 3, 4, 5, 0, 1, 4, 4, 4, 4, 4, 3, 1, 2, 4, 5, 0, 3, 3, 3, 0, 1, 2, 5, 0, 3, 4, 1, 3, 4, 5, 1, 4, 2, 5, 3, 5, 4, 4, 2, 1, 1, 0, 1, 0, 0, 1, 0, 2, 4, 3, 4, 1, 2, 5, 0, 0, 4, 4, 1, 4, 2, 2, 5, 1, 1, 4, 2, 5, 4, 2, 3, 0, 3, 5, 2, 0, 4, 5, 1, 3, 5, 2, 0, 2, 0, 4, 3, 0, 2, 5, 2, 1, 3, 2, 0, 4, 0, 3, 1, 0, 5, 5, 4, 0, 1, 5, 2, 5, 2, 1, 0, 2];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 2, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![37, 142, 9, 14, 0, 33, 8, 3, 123, 241, 255, 47, 239, 152, 53, 68, 176, 244, 176, 137, 215, 218, 167, 113, 111, 154, 111, 91, 46, 157, 164, 203, 14, 228, 160, 204, 105, 52, 157, 142, 71, 47, 97, 204, 77, 190, 184, 80, 214, 129, 239, 132, 13, 167, 70, 171, 182, 114, 232, 51, 43, 99, 92, 252, 99, 203, 162, 242, 68, 172, 53, 180, 201, 241, 5, 44, 83, 225, 47, 248, 175, 49, 148, 32, 66, 94, 124, 173, 251, 67, 65, 148, 15], "all L2 19");
    }
    #[test]
    fn test_all_20() {
        let input: Vec<u8> = vec![114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 3, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![43, 74, 45, 72, 77, 44, 81, 200, 77, 85, 40, 26, 38, 44, 0], "all L3 20");
    }
    #[test]
    fn test_all_21() {
        let input: Vec<u8> = vec![65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 4, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![115, 116, 164, 12, 0, 0], "all L4 21");
    }
    #[test]
    fn test_all_22() {
        let input: Vec<u8> = vec![101, 99, 116, 119, 117, 113, 113, 107, 102, 102, 119, 116, 115, 112, 110, 105, 100, 114, 113, 103, 116, 108, 115, 102, 115, 119, 109, 109, 115, 106, 119, 107, 109, 114, 117, 120, 103, 121, 118, 99, 122, 117, 115, 108, 108, 115, 99, 98, 98, 110, 120, 113, 102, 115, 98, 107, 102, 97, 105, 98, 119, 120, 110, 113, 122, 111, 97, 108, 113, 107, 110, 122, 118, 117, 120, 120, 111, 113, 108, 107, 110, 101, 117, 111, 100, 99, 116, 98, 98, 122, 111, 111, 101, 106, 119, 119, 115, 108, 118, 98, 99, 104, 119, 104, 104, 98, 115, 113, 122, 108, 111, 108, 111, 120, 103, 106, 115, 110, 120, 105, 108, 112, 122, 104, 114, 117, 109, 104, 113, 112, 122, 100, 102, 118, 111, 110, 108, 98, 105, 103, 122];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 5, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![5, 193, 9, 2, 132, 32, 8, 0, 192, 183, 134, 229, 145, 8, 18, 42, 44, 175, 223, 153, 39, 45, 219, 34, 61, 103, 91, 58, 169, 221, 159, 148, 133, 154, 213, 198, 208, 215, 250, 248, 182, 151, 223, 73, 177, 21, 81, 19, 0, 185, 100, 133, 158, 175, 6, 230, 36, 193, 23, 74, 167, 56, 219, 157, 5, 59, 61, 155, 239, 180, 0, 130, 249, 121, 205, 20, 15, 164, 106, 181, 130, 74, 32, 35, 123, 121, 149, 188, 225, 140, 250, 237, 81, 101, 198, 157, 15, 19, 66, 43, 241, 7], "all L5 22");
    }
    #[test]
    fn test_all_23() {
        let input: Vec<u8> = vec![152, 245, 118, 209, 15, 111, 210, 18, 19, 62, 102, 115, 221, 195, 220, 233, 172, 131, 249, 10, 152, 245, 118, 209, 15, 111, 210, 18, 19, 62, 102, 115, 221, 195, 220, 233, 172, 131, 249, 10, 152, 245, 118, 209, 15, 111, 210, 18, 19, 62, 102, 115, 221, 195, 220, 233, 172, 131, 249, 10, 152, 245, 118, 209, 15, 111, 210, 18, 19, 62, 102, 115, 221, 195, 220, 233, 172, 131, 249, 10, 152, 245, 118, 209, 15, 111, 210, 18, 19, 62, 102, 115, 221, 195, 220, 233, 172, 131, 249, 10, 152, 245, 118, 209, 15, 111, 210, 18, 19, 62, 102, 115, 221, 195, 220, 233, 172, 131, 249, 10, 152, 245, 118, 209, 15, 111, 210, 18, 19, 62, 102, 115, 221, 195, 220, 233, 172, 131, 249, 10];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![155, 241, 181, 236, 34, 127, 254, 37, 33, 97, 187, 180, 226, 187, 135, 239, 188, 92, 211, 252, 147, 107, 198, 0, 137, 1, 0], "all L6 23");
    }
    #[test]
    fn test_all_24() {
        let input: Vec<u8> = vec![228, 248, 15, 69, 169, 25, 167, 126, 28, 110, 198, 202, 109, 109, 132, 75, 30, 152, 125, 52, 59, 69, 232, 188, 130, 62, 137, 43, 216, 60, 59, 32, 126, 9, 159, 200, 101, 122, 63, 157, 38, 243, 233, 39, 55, 29, 140, 109, 133];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 7, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![1, 49, 0, 206, 255, 228, 248, 15, 69, 169, 25, 167, 126, 28, 110, 198, 202, 109, 109, 132, 75, 30, 152, 125, 52, 59, 69, 232, 188, 130, 62, 137, 43, 216, 60, 59, 32, 126, 9, 159, 200, 101, 122, 63, 157, 38, 243, 233, 39, 55, 29, 140, 109, 133], "all L7 24");
    }
    #[test]
    fn test_all_25() {
        let input: Vec<u8> = vec![4, 0, 4, 5, 4, 4, 4, 0, 2, 2, 3, 0, 2, 0, 3, 3, 5, 3, 2, 2, 4, 2, 0, 1, 4, 5, 4, 2, 4, 3, 2, 2, 3, 0, 0, 3, 4, 1, 5, 1, 3, 5, 1, 5, 4, 5, 2, 4, 0, 1, 4, 1, 5, 0, 2, 3, 5, 3, 5, 4, 5, 3, 2, 4, 0, 4, 5, 3, 5, 1, 5, 3, 1, 3, 5, 1, 4, 1, 1, 3, 0, 4, 5, 2, 1, 3, 2, 5, 5, 4, 0, 1, 3, 5, 5, 4, 4, 0, 4, 4, 1, 2, 3, 1, 5, 1, 1, 0, 5, 2, 1, 2, 5, 2, 2, 1, 4, 3, 4, 2, 3, 2, 5, 4, 1, 3, 3, 2, 0, 4, 0, 1, 0, 5, 3, 0, 2, 4, 2, 4, 5, 5, 2, 2, 2, 3, 0, 2, 0, 1, 0, 1, 2, 2, 4, 4, 2, 4, 3, 1, 2, 2, 4, 5, 2, 2, 4, 2, 3, 5, 1];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 8, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![29, 142, 201, 17, 0, 65, 8, 2, 229, 202, 63, 229, 237, 217, 143, 22, 210, 37, 244, 186, 182, 103, 231, 124, 201, 98, 215, 39, 174, 110, 222, 245, 82, 77, 153, 214, 185, 56, 218, 25, 14, 25, 52, 19, 43, 15, 168, 20, 180, 21, 111, 144, 97, 2, 84, 14, 31, 116, 56, 158, 173, 166, 6, 169, 18, 31, 220, 141, 108, 226, 134, 249, 215, 208, 137, 22, 175, 192, 219, 123, 141, 120, 255, 1], "all L8 25");
    }
    #[test]
    fn test_all_26() {
        let input: Vec<u8> = vec![114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![43, 74, 45, 72, 77, 44, 81, 200, 77, 85, 40, 26, 38, 44, 0], "all L9 26");
    }
    #[test]
    fn test_all_27() {
        let input: Vec<u8> = vec![65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![115, 116, 28, 5, 196, 134, 0, 0], "all L1 27");
    }
    #[test]
    fn test_all_28() {
        let input: Vec<u8> = vec![106, 117, 106, 105, 99, 105, 111, 104, 110, 98, 112, 108, 115, 111, 103, 110, 105, 106, 102, 112, 98, 115, 103, 103, 112, 97, 113, 110, 108, 98, 113, 109, 116, 101, 108, 99, 105, 109, 101, 101, 118, 112, 102, 120, 97, 113, 97, 112, 118, 100, 100, 98, 122, 108, 111, 113, 118, 113, 122, 111, 110, 106, 111, 120, 103, 117, 111, 116, 111, 100, 110, 119, 97, 119, 100, 109, 118, 105, 120, 113, 115, 111, 116, 109, 102, 111, 97, 109, 105, 97, 103, 97, 105, 108, 104, 102, 120, 122, 121, 110, 104, 114, 115, 116, 97, 112, 106, 117, 122, 100, 113, 121, 103, 104, 122, 113, 117, 119, 106, 118, 121, 121, 105, 102, 122, 105, 102, 107, 101, 120, 118, 118, 97, 102, 116, 113, 114, 107, 110, 122, 119, 120, 106, 122, 105, 98, 113, 99, 115, 101, 109, 109, 113, 120, 99, 98, 103, 120, 121, 118, 121, 116, 116, 104, 114, 121, 118, 118, 101, 104, 112, 105, 122, 97, 113, 108, 108, 107, 105, 102, 121, 110, 119, 109, 104, 107, 104, 103, 98, 118, 106, 120, 122, 107, 98, 113, 107, 122, 113, 119, 104, 112, 120, 111, 108, 106, 106, 104, 116, 108, 100, 117, 115, 102, 121, 111, 111];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 2, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![5, 193, 7, 2, 3, 33, 8, 0, 176, 183, 226, 185, 112, 33, 85, 17, 121, 125, 147, 114, 10, 126, 72, 121, 184, 217, 22, 165, 129, 37, 78, 183, 82, 154, 192, 163, 57, 238, 59, 180, 15, 123, 8, 50, 163, 2, 195, 20, 239, 157, 53, 98, 97, 163, 81, 72, 211, 161, 77, 126, 92, 184, 190, 11, 42, 47, 218, 61, 18, 116, 132, 4, 216, 114, 84, 123, 35, 255, 214, 134, 89, 142, 121, 126, 41, 27, 159, 91, 228, 61, 140, 134, 177, 6, 21, 129, 184, 249, 87, 135, 93, 45, 134, 142, 191, 21, 122, 103, 253, 92, 210, 39, 111, 239, 252, 123, 34, 33, 79, 52, 224, 214, 42, 198, 55, 110, 207, 53, 39, 39, 69, 173, 58, 174, 198, 55, 79, 165, 86, 74, 222, 205, 159, 21, 31, 209, 31], "all L2 28");
    }
    #[test]
    fn test_all_29() {
        let input: Vec<u8> = vec![253, 246, 76, 228, 75, 166, 214, 84, 30, 11, 112, 194, 135, 146, 94, 34, 238, 247, 229, 88, 253, 246, 76, 228, 75, 166, 214, 84, 30, 11, 112, 194, 135, 146, 94, 34, 238, 247, 229, 88, 253, 246, 76, 228, 75, 166, 214, 84, 30, 11, 112, 194, 135, 146, 94, 34, 238, 247, 229, 88, 253, 246, 76, 228, 75, 166, 214, 84, 30, 11, 112, 194, 135, 146, 94, 34, 238, 247, 229, 88, 253, 246, 76, 228, 75, 166, 214, 84, 30, 11, 112, 194, 135, 146, 94, 34, 238, 247, 229, 88, 253, 246, 76, 228, 75, 166, 214, 84, 30, 11, 112, 194, 135, 146, 94, 34, 238, 247, 229, 88];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 3, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![251, 251, 205, 231, 137, 247, 178, 107, 33, 114, 220, 5, 135, 218, 39, 197, 41, 189, 251, 254, 52, 226, 47, 29, 196, 0], "all L3 29");
    }
    #[test]
    fn test_all_30() {
        let input: Vec<u8> = vec![77, 205, 247, 78, 70, 87, 170, 140, 134, 112, 5, 76, 248, 131, 178, 157, 65, 194, 6, 13];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 4, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![243, 61, 251, 221, 207, 45, 124, 85, 79, 91, 1, 171, 207, 143, 230, 77, 115, 29, 15, 177, 241, 2, 0], "all L4 30");
    }
    #[test]
    fn test_all_31() {
        let input: Vec<u8> = vec![0, 5, 3, 5, 2, 0, 2, 5, 5, 1, 5, 2, 1, 1, 5, 4, 5, 4, 3, 1, 3, 0, 2, 3, 2, 2, 3, 3, 5, 0, 1, 0, 2, 3, 4, 0, 0, 4, 5, 0, 2, 3, 0, 1, 1, 1, 0, 0, 3, 0, 0, 0, 0, 4, 5, 0, 1, 3, 5, 2, 5, 5, 2, 0, 2, 1, 2, 2, 4, 4, 1, 2, 3, 3, 0, 0, 5, 1, 5, 1, 1, 0, 2, 4, 2, 4, 4, 3, 4, 1, 5, 3, 2, 1, 3, 5, 0, 3, 5, 2, 1, 0, 2, 3, 5, 5, 0, 5, 3, 1, 2, 2, 3, 5, 4, 0, 4, 0, 4, 4, 2, 2, 3, 0, 0, 0, 4, 5, 3, 5, 3, 2, 3, 1, 3, 5, 0, 1, 3, 5, 1, 5, 4, 2, 5, 0, 0, 5, 4, 1, 1, 5, 3, 5, 4, 3, 1, 0, 0, 2, 2, 5, 0, 5, 0, 1, 1, 2, 3, 5, 2, 2, 4, 2, 3, 1, 4, 3, 0, 3, 2, 1, 1, 4, 0, 3, 2, 0, 3, 4, 2, 1, 3, 1, 2, 3, 1, 1, 0, 0, 1, 1, 3, 5, 4, 1, 3, 0, 1, 1, 5, 0, 1, 1, 5, 2, 1, 1, 4, 5, 3, 1, 2, 4, 5, 1, 5, 3, 0, 4, 4, 4, 2, 5, 2, 4, 1, 1, 2, 2, 1, 5, 0, 1, 4, 5, 2, 2, 5, 2, 3, 3, 1, 3, 2, 5, 3, 5, 3, 1, 4, 5, 3, 5, 5, 1, 5, 0, 3, 1, 1, 2, 1, 3, 5, 0, 5, 1, 0, 2, 2, 0, 3, 4, 5, 5, 4, 1, 3, 5, 3, 3, 1, 0, 4, 1, 2, 1, 4, 3, 1, 4, 3, 4, 5, 5, 3, 4, 5, 2, 5, 5, 2, 2, 2, 3, 4, 1, 2, 4, 3, 5, 1, 2, 2, 0, 0, 2, 3, 3, 3, 0, 3, 1, 0, 1, 5, 1, 0, 3, 4, 2, 3, 1, 1, 5, 1, 0, 5, 2, 0, 1, 3, 2, 5, 0, 5, 2, 0, 5, 1, 2, 2, 2, 3, 2, 4, 2, 0, 3, 0, 5, 4, 5, 5, 2, 5, 4, 2, 3, 3, 1, 3, 1, 0, 3, 3, 4, 2, 2, 4, 3, 2, 3, 2, 3, 2, 5, 2, 5, 1, 5, 1, 3, 1, 1, 3, 3, 2, 1, 1, 4, 4, 2, 3, 2, 1, 0, 0, 2, 5, 0, 5, 2, 0, 1, 4, 3, 0, 4, 1, 1, 0, 0, 1, 1, 3, 0, 0, 3, 5, 0, 2, 4, 3, 4, 2, 0, 1, 1, 3, 2, 0, 1, 0, 2, 1, 2, 3, 3, 3, 4, 4, 0, 3, 5, 3, 4, 1, 3, 5, 5, 5, 5, 5, 3, 1];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 5, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![45, 145, 1, 22, 192, 32, 8, 66, 81, 240, 254, 87, 222, 167, 183, 181, 182, 50, 68, 48, 157, 111, 181, 119, 115, 59, 115, 185, 120, 172, 245, 174, 125, 26, 86, 145, 114, 252, 53, 51, 146, 165, 183, 31, 210, 174, 153, 179, 155, 12, 104, 9, 14, 32, 27, 2, 206, 156, 23, 144, 192, 149, 229, 78, 103, 176, 190, 136, 17, 86, 143, 200, 192, 92, 28, 147, 242, 123, 208, 4, 33, 174, 16, 105, 9, 112, 6, 255, 81, 7, 100, 44, 120, 39, 124, 229, 80, 129, 163, 234, 26, 242, 51, 21, 89, 120, 189, 164, 245, 2, 169, 41, 7, 241, 66, 187, 219, 227, 192, 117, 40, 30, 111, 235, 23, 89, 255, 130, 232, 73, 62, 4, 151, 253, 202, 120, 224, 132, 65, 42, 243, 18, 99, 214, 57, 6, 136, 6, 213, 96, 49, 72, 3, 0, 210, 129, 202, 130, 137, 5, 237, 105, 137, 254, 139, 162, 169, 129, 22, 127, 164, 99, 181, 2, 64, 3, 135, 102, 59, 8, 147, 71, 178, 159, 71, 32, 219, 30, 60, 134, 58, 207, 239, 148, 107, 224, 70, 80, 179, 221, 109, 175, 169, 55, 224, 208, 22, 244, 33, 186, 143, 231, 3], "all L5 31");
    }
    #[test]
    fn test_all_32() {
        let input: Vec<u8> = vec![114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32, 114, 101, 112, 101, 97, 116, 32, 109, 101, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![43, 74, 45, 72, 77, 44, 81, 200, 77, 85, 40, 26, 198, 44, 0], "all L6 32");
    }
    #[test]
    fn test_all_33() {
        let input: Vec<u8> = vec![65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 7, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![115, 116, 164, 37, 0, 0], "all L7 33");
    }
    #[test]
    fn test_all_34() {
        let input: Vec<u8> = vec![116, 106, 105, 107, 104, 113, 115, 122, 122, 109, 121, 109, 118, 102, 99, 105, 115, 97, 106, 105, 104, 108, 112, 104, 116, 120, 113, 117, 119, 103, 103, 107, 101, 119, 120, 121, 99, 110, 108, 114, 104, 106, 97, 102, 103, 104, 110, 117, 102, 117, 118, 122, 116, 107, 103, 101, 106, 101, 105, 114, 118, 114, 104, 108, 106, 118, 120, 115, 119, 103, 107, 107, 111, 110, 114, 110, 100, 120, 105, 99, 109, 109, 103, 117, 119, 119, 107, 117, 119, 102, 100, 109, 115, 120, 118, 100, 107, 104, 99, 119, 108, 122, 105, 105, 103, 112, 102, 108, 110, 113, 115, 101, 111, 101, 98, 105, 104, 116, 118, 122, 120, 106, 115, 117, 101, 103, 116, 97, 103, 101, 104, 105, 122, 122, 99, 117, 114, 114, 110, 105];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 8, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![5, 193, 139, 2, 4, 17, 8, 0, 192, 111, 117, 164, 18, 118, 61, 146, 237, 235, 111, 102, 23, 22, 26, 203, 189, 125, 237, 228, 200, 43, 20, 166, 250, 210, 190, 67, 13, 81, 192, 238, 23, 123, 157, 84, 66, 70, 234, 154, 245, 248, 22, 132, 2, 60, 207, 164, 90, 206, 93, 134, 34, 79, 159, 61, 93, 142, 173, 161, 154, 137, 90, 78, 109, 221, 147, 132, 162, 85, 103, 198, 55, 215, 62, 22, 60, 240, 99, 218, 199, 111, 89, 10, 184, 3, 2, 177, 123, 212, 57, 59, 255, 1], "all L8 34");
    }
    #[test]
    fn test_all_35() {
        let input: Vec<u8> = vec![221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70, 221, 20, 230, 232, 193, 6, 134, 232, 49, 132, 100, 67, 98, 51, 170, 254, 1, 189, 96, 70];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 4000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1);
        assert_eq!(strm.next_out, vec![187, 43, 242, 236, 197, 65, 182, 182, 23, 134, 45, 41, 206, 73, 198, 171, 254, 49, 238, 77, 112, 187, 59, 194, 196, 0], "all L9 35");
    }

    #[test]
    fn test_slow_l6_0() {
        let input: Vec<u8> = vec![];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![3, 0], "slow L6 0");
    }
    #[test]
    fn test_slow_l9_0() {
        let input: Vec<u8> = vec![];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![3, 0], "slow L9 0");
    }
    #[test]
    fn test_slow_l6_1() {
        let input: Vec<u8> = vec![97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![75, 4, 0], "slow L6 1");
    }
    #[test]
    fn test_slow_l9_1() {
        let input: Vec<u8> = vec![97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![75, 4, 0], "slow L9 1");
    }
    #[test]
    fn test_slow_l6_2() {
        let input: Vec<u8> = vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![203, 72, 205, 201, 201, 87, 40, 207, 47, 202, 73, 81, 200, 64, 103, 3, 0], "slow L6 2");
    }
    #[test]
    fn test_slow_l9_2() {
        let input: Vec<u8> = vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![203, 72, 205, 201, 201, 87, 40, 207, 47, 202, 73, 81, 200, 64, 103, 3, 0], "slow L9 2");
    }
    #[test]
    fn test_slow_l6_3() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![75, 76, 196, 14, 0], "slow L6 3");
    }
    #[test]
    fn test_slow_l9_3() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![75, 76, 196, 14, 0], "slow L9 3");
    }
    #[test]
    fn test_slow_l6_4() {
        let input: Vec<u8> = vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![11, 201, 72, 85, 40, 44, 205, 76, 206, 86, 72, 42, 202, 47, 207, 83, 72, 203, 175, 80, 200, 42, 205, 45, 40, 86, 200, 47, 75, 45, 82, 40, 1, 74, 231, 36, 86, 85, 42, 164, 228, 167, 235, 41, 132, 12, 119, 197, 0], "slow L6 4");
    }
    #[test]
    fn test_slow_l9_4() {
        let input: Vec<u8> = vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![11, 201, 72, 85, 40, 44, 205, 76, 206, 86, 72, 42, 202, 47, 207, 83, 72, 203, 175, 80, 200, 42, 205, 45, 40, 86, 200, 47, 75, 45, 82, 40, 1, 74, 231, 36, 86, 85, 42, 164, 228, 167, 235, 41, 132, 12, 119, 197, 0], "slow L9 4");
    }
    #[test]
    fn test_slow_l6_5() {
        let input: Vec<u8> = vec![231, 238, 231, 97, 94, 243, 95, 48, 228, 155, 72, 46, 21, 202, 231, 80, 7, 32, 30, 18, 97, 123, 15, 237, 167, 225, 100, 119, 150, 255, 2, 43, 234, 142, 208, 42, 130, 161, 117, 147, 15, 35, 55, 205, 55, 148, 197, 34, 8, 0, 109, 107, 26, 240, 192, 203, 214, 37, 101, 138, 172, 44, 159, 170, 7, 209, 60, 68, 126, 51, 5, 30, 238, 249, 90, 96, 229, 97, 67, 214, 196, 59, 202, 215, 108, 0, 138, 155, 10, 107, 95, 201, 51, 21, 74, 109, 226, 132, 4, 168, 151, 197, 37, 38, 46, 106, 124, 7, 188, 190, 232, 65, 247, 69, 197, 93, 78, 159, 116, 127, 97, 81, 100, 198, 247, 40, 215, 24, 53, 55, 19, 130, 122, 200, 131, 215, 251, 150, 89, 35, 64, 116, 245, 37, 143, 108, 104, 8, 35, 137, 210, 228, 127, 30, 23, 90, 144, 188, 67, 47, 185, 70, 230, 169, 71, 17, 9, 243, 183, 159, 17, 10, 38, 246, 34, 159, 163, 69, 37, 38, 231, 188, 22, 66, 174, 180, 43, 242, 39, 213, 15, 255, 7, 195, 194, 6, 36, 41, 46, 59, 131, 213, 169, 198, 234, 225, 236, 42, 15, 158, 44, 246, 11, 117, 57, 254, 248, 130, 5, 188, 154, 73, 103, 86, 175, 226, 255, 123, 167, 207, 128, 101, 220, 102, 109, 196, 112, 162, 107, 69, 68, 254, 179, 20, 32, 141, 86, 57, 230, 241, 140, 109, 211, 195, 252, 161, 231, 164, 38, 16, 142, 21, 143, 181, 158, 9, 69, 207, 232, 97, 12, 136, 121, 72, 24, 59, 228, 55, 188, 39, 101, 102, 243, 131, 91, 5, 241, 18, 91, 115, 139, 177, 81, 201, 114, 44, 210, 198, 66, 230, 232, 100, 3, 192, 175, 237, 167, 104, 50, 63, 109, 124, 199, 44, 158, 164, 134, 8, 178, 42, 19, 225, 175, 215, 140, 249, 14, 111, 32, 219, 17, 88, 171, 71, 240, 76, 225, 252, 44, 113, 224, 148, 84, 131, 159, 195, 106, 155, 72, 139, 254, 102, 210, 58, 2, 193, 14, 22, 205, 62, 251, 47, 85, 33, 234, 211, 206, 137, 126, 242, 252, 65, 173, 222, 243, 162, 55, 98, 214, 15, 133, 66, 11, 18, 99, 79, 116, 6, 145, 164, 181, 125, 255, 53, 255, 62, 128, 101, 223, 11];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![1, 144, 1, 111, 254, 231, 238, 231, 97, 94, 243, 95, 48, 228, 155, 72, 46, 21, 202, 231, 80, 7, 32, 30, 18, 97, 123, 15, 237, 167, 225, 100, 119, 150, 255, 2, 43, 234, 142, 208, 42, 130, 161, 117, 147, 15, 35, 55, 205, 55, 148, 197, 34, 8, 0, 109, 107, 26, 240, 192, 203, 214, 37, 101, 138, 172, 44, 159, 170, 7, 209, 60, 68, 126, 51, 5, 30, 238, 249, 90, 96, 229, 97, 67, 214, 196, 59, 202, 215, 108, 0, 138, 155, 10, 107, 95, 201, 51, 21, 74, 109, 226, 132, 4, 168, 151, 197, 37, 38, 46, 106, 124, 7, 188, 190, 232, 65, 247, 69, 197, 93, 78, 159, 116, 127, 97, 81, 100, 198, 247, 40, 215, 24, 53, 55, 19, 130, 122, 200, 131, 215, 251, 150, 89, 35, 64, 116, 245, 37, 143, 108, 104, 8, 35, 137, 210, 228, 127, 30, 23, 90, 144, 188, 67, 47, 185, 70, 230, 169, 71, 17, 9, 243, 183, 159, 17, 10, 38, 246, 34, 159, 163, 69, 37, 38, 231, 188, 22, 66, 174, 180, 43, 242, 39, 213, 15, 255, 7, 195, 194, 6, 36, 41, 46, 59, 131, 213, 169, 198, 234, 225, 236, 42, 15, 158, 44, 246, 11, 117, 57, 254, 248, 130, 5, 188, 154, 73, 103, 86, 175, 226, 255, 123, 167, 207, 128, 101, 220, 102, 109, 196, 112, 162, 107, 69, 68, 254, 179, 20, 32, 141, 86, 57, 230, 241, 140, 109, 211, 195, 252, 161, 231, 164, 38, 16, 142, 21, 143, 181, 158, 9, 69, 207, 232, 97, 12, 136, 121, 72, 24, 59, 228, 55, 188, 39, 101, 102, 243, 131, 91, 5, 241, 18, 91, 115, 139, 177, 81, 201, 114, 44, 210, 198, 66, 230, 232, 100, 3, 192, 175, 237, 167, 104, 50, 63, 109, 124, 199, 44, 158, 164, 134, 8, 178, 42, 19, 225, 175, 215, 140, 249, 14, 111, 32, 219, 17, 88, 171, 71, 240, 76, 225, 252, 44, 113, 224, 148, 84, 131, 159, 195, 106, 155, 72, 139, 254, 102, 210, 58, 2, 193, 14, 22, 205, 62, 251, 47, 85, 33, 234, 211, 206, 137, 126, 242, 252, 65, 173, 222, 243, 162, 55, 98, 214, 15, 133, 66, 11, 18, 99, 79, 116, 6, 145, 164, 181, 125, 255, 53, 255, 62, 128, 101, 223, 11], "slow L6 5");
    }
    #[test]
    fn test_slow_l9_5() {
        let input: Vec<u8> = vec![231, 238, 231, 97, 94, 243, 95, 48, 228, 155, 72, 46, 21, 202, 231, 80, 7, 32, 30, 18, 97, 123, 15, 237, 167, 225, 100, 119, 150, 255, 2, 43, 234, 142, 208, 42, 130, 161, 117, 147, 15, 35, 55, 205, 55, 148, 197, 34, 8, 0, 109, 107, 26, 240, 192, 203, 214, 37, 101, 138, 172, 44, 159, 170, 7, 209, 60, 68, 126, 51, 5, 30, 238, 249, 90, 96, 229, 97, 67, 214, 196, 59, 202, 215, 108, 0, 138, 155, 10, 107, 95, 201, 51, 21, 74, 109, 226, 132, 4, 168, 151, 197, 37, 38, 46, 106, 124, 7, 188, 190, 232, 65, 247, 69, 197, 93, 78, 159, 116, 127, 97, 81, 100, 198, 247, 40, 215, 24, 53, 55, 19, 130, 122, 200, 131, 215, 251, 150, 89, 35, 64, 116, 245, 37, 143, 108, 104, 8, 35, 137, 210, 228, 127, 30, 23, 90, 144, 188, 67, 47, 185, 70, 230, 169, 71, 17, 9, 243, 183, 159, 17, 10, 38, 246, 34, 159, 163, 69, 37, 38, 231, 188, 22, 66, 174, 180, 43, 242, 39, 213, 15, 255, 7, 195, 194, 6, 36, 41, 46, 59, 131, 213, 169, 198, 234, 225, 236, 42, 15, 158, 44, 246, 11, 117, 57, 254, 248, 130, 5, 188, 154, 73, 103, 86, 175, 226, 255, 123, 167, 207, 128, 101, 220, 102, 109, 196, 112, 162, 107, 69, 68, 254, 179, 20, 32, 141, 86, 57, 230, 241, 140, 109, 211, 195, 252, 161, 231, 164, 38, 16, 142, 21, 143, 181, 158, 9, 69, 207, 232, 97, 12, 136, 121, 72, 24, 59, 228, 55, 188, 39, 101, 102, 243, 131, 91, 5, 241, 18, 91, 115, 139, 177, 81, 201, 114, 44, 210, 198, 66, 230, 232, 100, 3, 192, 175, 237, 167, 104, 50, 63, 109, 124, 199, 44, 158, 164, 134, 8, 178, 42, 19, 225, 175, 215, 140, 249, 14, 111, 32, 219, 17, 88, 171, 71, 240, 76, 225, 252, 44, 113, 224, 148, 84, 131, 159, 195, 106, 155, 72, 139, 254, 102, 210, 58, 2, 193, 14, 22, 205, 62, 251, 47, 85, 33, 234, 211, 206, 137, 126, 242, 252, 65, 173, 222, 243, 162, 55, 98, 214, 15, 133, 66, 11, 18, 99, 79, 116, 6, 145, 164, 181, 125, 255, 53, 255, 62, 128, 101, 223, 11];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![1, 144, 1, 111, 254, 231, 238, 231, 97, 94, 243, 95, 48, 228, 155, 72, 46, 21, 202, 231, 80, 7, 32, 30, 18, 97, 123, 15, 237, 167, 225, 100, 119, 150, 255, 2, 43, 234, 142, 208, 42, 130, 161, 117, 147, 15, 35, 55, 205, 55, 148, 197, 34, 8, 0, 109, 107, 26, 240, 192, 203, 214, 37, 101, 138, 172, 44, 159, 170, 7, 209, 60, 68, 126, 51, 5, 30, 238, 249, 90, 96, 229, 97, 67, 214, 196, 59, 202, 215, 108, 0, 138, 155, 10, 107, 95, 201, 51, 21, 74, 109, 226, 132, 4, 168, 151, 197, 37, 38, 46, 106, 124, 7, 188, 190, 232, 65, 247, 69, 197, 93, 78, 159, 116, 127, 97, 81, 100, 198, 247, 40, 215, 24, 53, 55, 19, 130, 122, 200, 131, 215, 251, 150, 89, 35, 64, 116, 245, 37, 143, 108, 104, 8, 35, 137, 210, 228, 127, 30, 23, 90, 144, 188, 67, 47, 185, 70, 230, 169, 71, 17, 9, 243, 183, 159, 17, 10, 38, 246, 34, 159, 163, 69, 37, 38, 231, 188, 22, 66, 174, 180, 43, 242, 39, 213, 15, 255, 7, 195, 194, 6, 36, 41, 46, 59, 131, 213, 169, 198, 234, 225, 236, 42, 15, 158, 44, 246, 11, 117, 57, 254, 248, 130, 5, 188, 154, 73, 103, 86, 175, 226, 255, 123, 167, 207, 128, 101, 220, 102, 109, 196, 112, 162, 107, 69, 68, 254, 179, 20, 32, 141, 86, 57, 230, 241, 140, 109, 211, 195, 252, 161, 231, 164, 38, 16, 142, 21, 143, 181, 158, 9, 69, 207, 232, 97, 12, 136, 121, 72, 24, 59, 228, 55, 188, 39, 101, 102, 243, 131, 91, 5, 241, 18, 91, 115, 139, 177, 81, 201, 114, 44, 210, 198, 66, 230, 232, 100, 3, 192, 175, 237, 167, 104, 50, 63, 109, 124, 199, 44, 158, 164, 134, 8, 178, 42, 19, 225, 175, 215, 140, 249, 14, 111, 32, 219, 17, 88, 171, 71, 240, 76, 225, 252, 44, 113, 224, 148, 84, 131, 159, 195, 106, 155, 72, 139, 254, 102, 210, 58, 2, 193, 14, 22, 205, 62, 251, 47, 85, 33, 234, 211, 206, 137, 126, 242, 252, 65, 173, 222, 243, 162, 55, 98, 214, 15, 133, 66, 11, 18, 99, 79, 116, 6, 145, 164, 181, 125, 255, 53, 255, 62, 128, 101, 223, 11], "slow L9 5");
    }
    #[test]
    fn test_slow_l6_6() {
        let input: Vec<u8> = vec![3, 3, 1, 1, 1, 1, 1, 1, 2, 1, 2, 2, 1, 1, 1, 0, 1, 1, 1, 0, 2, 3, 0, 3, 3, 1, 1, 3, 0, 0, 1, 2, 2, 0, 2, 1, 0, 3, 0, 0, 0, 3, 1, 1, 1, 0, 1, 1, 1, 2, 0, 0, 1, 3, 0, 0, 2, 3, 3, 3, 2, 3, 1, 2, 0, 0, 1, 1, 3, 3, 2, 2, 3, 1, 1, 0, 0, 2, 0, 3, 1, 2, 2, 2, 0, 1, 3, 1, 2, 2, 3, 1, 3, 1, 1, 0, 2, 2, 3, 0, 0, 2, 0, 1, 2, 2, 2, 1, 3, 1, 0, 3, 3, 1, 0, 3, 0, 0, 0, 1, 2, 3, 3, 0, 1, 3, 0, 0, 2, 2, 2, 2, 3, 0, 3, 0, 0, 3, 1, 3, 3, 1, 3, 0, 3, 3, 3, 2, 3, 2, 2, 2, 3, 2, 2, 2, 0, 0, 1, 0, 1, 3, 3, 0, 2, 3, 0, 2, 0, 1, 3, 3, 2, 1, 0, 0, 3, 1, 1, 0, 0, 3, 3, 0, 1, 0, 2, 1, 0, 2, 3, 1, 3, 3, 2, 3, 2, 1, 2, 1, 1, 3, 0, 2, 2, 2, 2, 1, 2, 1, 1, 1, 1, 0, 0, 0, 2, 2, 3, 0, 0, 0, 1, 2, 0, 0, 1, 1, 2, 3, 3, 2, 1, 2, 2, 3, 1, 0, 0, 3, 1, 3, 3, 2, 3, 1, 2, 1, 2, 2, 1, 3, 2, 0, 3, 2, 0, 0, 3, 3, 3, 2, 0, 0, 2, 1, 0, 2, 3, 2, 2, 1, 1, 2, 2, 2, 0, 2, 3, 2, 3, 2, 3, 2, 1, 3, 1, 0, 2, 2, 0, 2, 3, 3, 1, 2, 3, 1, 1, 1, 0, 3, 2, 0, 1, 0, 1, 2, 0, 3, 0, 2, 0, 2, 0, 2, 0, 2, 0, 0, 1, 0, 3, 1, 1, 3, 2, 3, 3, 2, 2, 2, 1, 3, 3, 0, 0, 3, 2, 0, 3, 0, 3, 0, 2, 0, 0, 3, 3, 1, 1, 1, 3, 1, 2, 1, 3, 3, 2, 2, 0, 3, 2, 0, 2, 1, 1, 0, 3, 0, 3, 0, 2, 0, 1, 1, 2, 1, 1, 3, 1, 3, 1, 2, 3, 1, 2, 3, 2, 3, 3, 2, 0, 3, 1, 3, 0, 1, 1, 3, 2, 0, 1, 0, 3, 2, 3, 1, 3, 1, 3, 1, 2, 1, 2, 1, 2, 0, 1, 1, 0, 1, 1, 1, 0, 2, 2, 0, 3, 3, 0, 2, 0, 1, 3, 1, 0, 3, 1, 0, 3, 3, 1, 2, 2, 2, 3, 0, 2, 3, 0, 2, 0, 1, 0, 3, 3, 0, 3, 0, 3, 3, 1, 2, 0, 3, 0, 1, 1, 2, 3, 2, 2, 3, 0, 2, 1, 1, 3, 0, 2, 2, 2, 3, 2, 3, 3, 0, 0, 1, 0, 1, 1, 1, 1, 3, 0, 3, 0, 0];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![45, 145, 9, 18, 128, 48, 12, 2, 9, 252, 255, 207, 178, 84, 29, 167, 205, 5, 4, 147, 219, 227, 179, 123, 136, 207, 81, 154, 142, 212, 164, 124, 234, 77, 249, 171, 110, 182, 177, 147, 56, 139, 174, 183, 94, 175, 201, 118, 185, 35, 199, 145, 35, 215, 147, 60, 233, 198, 224, 14, 237, 58, 255, 112, 76, 71, 192, 111, 13, 226, 194, 146, 3, 71, 101, 108, 95, 27, 192, 76, 149, 104, 60, 204, 162, 11, 14, 218, 171, 190, 163, 64, 113, 163, 227, 241, 234, 233, 51, 163, 8, 122, 44, 200, 102, 219, 84, 174, 53, 70, 61, 52, 44, 128, 215, 217, 139, 224, 69, 29, 216, 250, 109, 60, 48, 209, 243, 222, 198, 56, 5, 3, 136, 236, 65, 153, 134, 121, 136, 19, 243, 135, 188, 129, 88, 237, 166, 248, 134, 235, 77, 163, 12, 43, 97, 200, 188, 155, 202, 163, 247, 253, 20, 179, 246, 188, 213, 51, 114, 206, 61, 111, 40, 237, 167, 65, 206, 194, 43, 253, 166, 128, 63, 43, 145, 131, 213, 31], "slow L6 6");
    }
    #[test]
    fn test_slow_l9_6() {
        let input: Vec<u8> = vec![3, 3, 1, 1, 1, 1, 1, 1, 2, 1, 2, 2, 1, 1, 1, 0, 1, 1, 1, 0, 2, 3, 0, 3, 3, 1, 1, 3, 0, 0, 1, 2, 2, 0, 2, 1, 0, 3, 0, 0, 0, 3, 1, 1, 1, 0, 1, 1, 1, 2, 0, 0, 1, 3, 0, 0, 2, 3, 3, 3, 2, 3, 1, 2, 0, 0, 1, 1, 3, 3, 2, 2, 3, 1, 1, 0, 0, 2, 0, 3, 1, 2, 2, 2, 0, 1, 3, 1, 2, 2, 3, 1, 3, 1, 1, 0, 2, 2, 3, 0, 0, 2, 0, 1, 2, 2, 2, 1, 3, 1, 0, 3, 3, 1, 0, 3, 0, 0, 0, 1, 2, 3, 3, 0, 1, 3, 0, 0, 2, 2, 2, 2, 3, 0, 3, 0, 0, 3, 1, 3, 3, 1, 3, 0, 3, 3, 3, 2, 3, 2, 2, 2, 3, 2, 2, 2, 0, 0, 1, 0, 1, 3, 3, 0, 2, 3, 0, 2, 0, 1, 3, 3, 2, 1, 0, 0, 3, 1, 1, 0, 0, 3, 3, 0, 1, 0, 2, 1, 0, 2, 3, 1, 3, 3, 2, 3, 2, 1, 2, 1, 1, 3, 0, 2, 2, 2, 2, 1, 2, 1, 1, 1, 1, 0, 0, 0, 2, 2, 3, 0, 0, 0, 1, 2, 0, 0, 1, 1, 2, 3, 3, 2, 1, 2, 2, 3, 1, 0, 0, 3, 1, 3, 3, 2, 3, 1, 2, 1, 2, 2, 1, 3, 2, 0, 3, 2, 0, 0, 3, 3, 3, 2, 0, 0, 2, 1, 0, 2, 3, 2, 2, 1, 1, 2, 2, 2, 0, 2, 3, 2, 3, 2, 3, 2, 1, 3, 1, 0, 2, 2, 0, 2, 3, 3, 1, 2, 3, 1, 1, 1, 0, 3, 2, 0, 1, 0, 1, 2, 0, 3, 0, 2, 0, 2, 0, 2, 0, 2, 0, 0, 1, 0, 3, 1, 1, 3, 2, 3, 3, 2, 2, 2, 1, 3, 3, 0, 0, 3, 2, 0, 3, 0, 3, 0, 2, 0, 0, 3, 3, 1, 1, 1, 3, 1, 2, 1, 3, 3, 2, 2, 0, 3, 2, 0, 2, 1, 1, 0, 3, 0, 3, 0, 2, 0, 1, 1, 2, 1, 1, 3, 1, 3, 1, 2, 3, 1, 2, 3, 2, 3, 3, 2, 0, 3, 1, 3, 0, 1, 1, 3, 2, 0, 1, 0, 3, 2, 3, 1, 3, 1, 3, 1, 2, 1, 2, 1, 2, 0, 1, 1, 0, 1, 1, 1, 0, 2, 2, 0, 3, 3, 0, 2, 0, 1, 3, 1, 0, 3, 1, 0, 3, 3, 1, 2, 2, 2, 3, 0, 2, 3, 0, 2, 0, 1, 0, 3, 3, 0, 3, 0, 3, 3, 1, 2, 0, 3, 0, 1, 1, 2, 3, 2, 2, 3, 0, 2, 1, 1, 3, 0, 2, 2, 2, 3, 2, 3, 3, 0, 0, 1, 0, 1, 1, 1, 1, 3, 0, 3, 0, 0];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![45, 145, 9, 18, 128, 48, 12, 2, 9, 252, 255, 207, 178, 84, 29, 167, 205, 5, 4, 147, 219, 227, 179, 123, 136, 207, 81, 154, 142, 212, 164, 124, 234, 77, 249, 171, 110, 182, 177, 147, 56, 139, 174, 183, 94, 175, 201, 118, 185, 35, 199, 145, 35, 215, 147, 60, 233, 198, 224, 14, 237, 58, 255, 112, 76, 71, 192, 111, 13, 226, 194, 146, 3, 71, 101, 108, 95, 27, 192, 76, 149, 104, 60, 204, 162, 11, 14, 218, 171, 190, 163, 64, 113, 163, 227, 241, 234, 233, 51, 163, 8, 122, 44, 200, 102, 219, 84, 174, 53, 70, 61, 52, 44, 128, 215, 217, 139, 224, 69, 29, 216, 250, 109, 60, 48, 209, 243, 222, 198, 56, 5, 3, 136, 236, 65, 153, 134, 121, 136, 19, 243, 135, 188, 129, 88, 237, 166, 248, 134, 235, 77, 163, 12, 43, 97, 200, 188, 155, 202, 163, 247, 253, 20, 179, 246, 188, 213, 51, 114, 206, 61, 111, 40, 237, 167, 65, 206, 194, 43, 253, 166, 128, 63, 43, 145, 131, 213, 31], "slow L9 6");
    }
    #[test]
    fn test_slow_l6_7() {
        let input: Vec<u8> = vec![97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![75, 76, 74, 78, 28, 73, 8, 0], "slow L6 7");
    }
    #[test]
    fn test_slow_l9_7() {
        let input: Vec<u8> = vec![97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99, 97, 98, 99];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 9, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 3000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret");
        assert_eq!(strm.next_out, vec![75, 76, 74, 78, 28, 73, 8, 0], "slow L9 7");
    }

    #[test]
    fn test_fast_l1_0() {
        let input: Vec<u8> = vec![];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 0");
        assert_eq!(strm.next_out, vec![3, 0], "fast L1 0");
    }
    #[test]
    fn test_fast_l1_1() {
        let input: Vec<u8> = vec![97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 1");
        assert_eq!(strm.next_out, vec![75, 4, 0], "fast L1 1");
    }
    #[test]
    fn test_fast_l1_2() {
        let input: Vec<u8> = vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100, 32, 104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 2");
        assert_eq!(strm.next_out, vec![203, 72, 205, 201, 201, 87, 40, 207, 47, 202, 73, 81, 200, 64, 176, 1], "fast L1 2");
    }
    #[test]
    fn test_fast_l1_3() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 3");
        assert_eq!(strm.next_out, vec![75, 76, 196, 4, 0], "fast L1 3");
    }
    #[test]
    fn test_fast_l1_4() {
        let input: Vec<u8> = vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 4");
        assert_eq!(strm.next_out, vec![11, 201, 72, 85, 40, 44, 205, 76, 206, 86, 72, 42, 202, 47, 207, 83, 72, 203, 175, 80, 200, 42, 205, 45, 40, 86, 200, 47, 75, 45, 82, 40, 1, 74, 231, 36, 86, 85, 42, 164, 228, 167, 235, 41, 132, 12, 14, 197, 0], "fast L1 4");
    }
    #[test]
    fn test_fast_l1_5() {
        let input: Vec<u8> = vec![165, 77, 202, 24, 37, 48, 187, 29, 109, 19, 44, 222, 214, 35, 123, 46, 217, 30, 63, 114, 31, 203, 25, 113, 23, 68, 148, 214, 73, 60, 157, 92, 52, 96, 190, 49, 32, 30, 105, 254, 218, 160, 238, 232, 185, 153, 127, 92, 124, 41, 153, 253, 175, 229, 147, 37, 60, 214, 84, 175, 77, 250, 215, 20, 39, 160, 174, 179, 254, 233, 35, 47, 138, 242, 33, 31, 158, 228, 145, 197, 177, 11, 236, 181, 86, 59, 252, 30, 111, 147, 66, 126, 203, 200, 254, 41, 85, 229, 205, 142, 70, 220, 142, 212, 183, 194, 118, 77, 42, 90, 77, 118, 119, 6, 248, 93, 134, 144, 2, 74, 214, 189, 163, 64, 27, 233, 200, 203, 204, 201, 53, 246, 205, 31, 97, 34, 106, 225, 83, 56, 174, 26, 52, 0, 77, 51, 186, 13, 36, 106, 192, 76, 129, 177, 186, 242, 62, 59, 249, 238, 245, 247, 159, 43, 73, 52, 175, 135, 245, 82, 11, 105, 185, 75, 13, 152, 46, 133, 187, 85, 182, 114, 168, 114, 99, 122, 205, 116, 102, 252, 182, 14, 14, 143, 241, 132, 99, 176, 228, 178, 186, 41, 112, 52, 116, 240, 100, 172, 104, 247, 0, 245, 176, 43, 61, 198, 102, 244, 91, 222, 170, 44, 202, 237, 205, 43, 81, 87, 65, 14, 77, 238, 74, 242, 179, 79, 67, 10, 7, 52, 71, 222, 99, 108, 14, 128, 108, 149, 123, 166, 132, 214, 67, 31, 181, 234, 215, 66, 77, 9, 225, 93, 2, 76, 88, 72, 242, 61, 31, 166, 247, 54, 29, 127, 97, 141, 21, 50, 231, 14, 32, 226, 166, 102, 141, 231, 244, 126, 132, 103, 229, 70, 213, 62, 200, 226, 161, 37, 123, 219];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 5");
        assert_eq!(strm.next_out, vec![1, 44, 1, 211, 254, 165, 77, 202, 24, 37, 48, 187, 29, 109, 19, 44, 222, 214, 35, 123, 46, 217, 30, 63, 114, 31, 203, 25, 113, 23, 68, 148, 214, 73, 60, 157, 92, 52, 96, 190, 49, 32, 30, 105, 254, 218, 160, 238, 232, 185, 153, 127, 92, 124, 41, 153, 253, 175, 229, 147, 37, 60, 214, 84, 175, 77, 250, 215, 20, 39, 160, 174, 179, 254, 233, 35, 47, 138, 242, 33, 31, 158, 228, 145, 197, 177, 11, 236, 181, 86, 59, 252, 30, 111, 147, 66, 126, 203, 200, 254, 41, 85, 229, 205, 142, 70, 220, 142, 212, 183, 194, 118, 77, 42, 90, 77, 118, 119, 6, 248, 93, 134, 144, 2, 74, 214, 189, 163, 64, 27, 233, 200, 203, 204, 201, 53, 246, 205, 31, 97, 34, 106, 225, 83, 56, 174, 26, 52, 0, 77, 51, 186, 13, 36, 106, 192, 76, 129, 177, 186, 242, 62, 59, 249, 238, 245, 247, 159, 43, 73, 52, 175, 135, 245, 82, 11, 105, 185, 75, 13, 152, 46, 133, 187, 85, 182, 114, 168, 114, 99, 122, 205, 116, 102, 252, 182, 14, 14, 143, 241, 132, 99, 176, 228, 178, 186, 41, 112, 52, 116, 240, 100, 172, 104, 247, 0, 245, 176, 43, 61, 198, 102, 244, 91, 222, 170, 44, 202, 237, 205, 43, 81, 87, 65, 14, 77, 238, 74, 242, 179, 79, 67, 10, 7, 52, 71, 222, 99, 108, 14, 128, 108, 149, 123, 166, 132, 214, 67, 31, 181, 234, 215, 66, 77, 9, 225, 93, 2, 76, 88, 72, 242, 61, 31, 166, 247, 54, 29, 127, 97, 141, 21, 50, 231, 14, 32, 226, 166, 102, 141, 231, 244, 126, 132, 103, 229, 70, 213, 62, 200, 226, 161, 37, 123, 219], "fast L1 5");
    }
    #[test]
    fn test_fast_l1_6() {
        let input: Vec<u8> = vec![0, 1, 2, 0, 1, 2, 1, 2, 1, 3, 1, 0, 3, 3, 1, 1, 1, 3, 4, 3, 2, 3, 1, 2, 2, 0, 2, 0, 2, 4, 3, 3, 0, 3, 2, 4, 4, 2, 4, 0, 0, 1, 0, 0, 2, 2, 0, 1, 2, 1, 3, 2, 3, 1, 4, 4, 4, 3, 2, 0, 2, 0, 1, 3, 0, 2, 0, 0, 2, 0, 4, 1, 0, 2, 0, 3, 0, 2, 4, 3, 2, 4, 1, 0, 4, 1, 0, 1, 2, 0, 1, 1, 2, 2, 4, 1, 2, 3, 4, 1, 2, 2, 0, 2, 0, 0, 0, 4, 4, 1, 4, 3, 1, 3, 0, 3, 3, 4, 3, 4, 2, 1, 1, 2, 1, 1, 3, 2, 0, 1, 0, 0, 2, 3, 1, 0, 0, 3, 4, 2, 4, 1, 2, 0, 3, 1, 1, 2, 3, 0, 2, 2, 2, 4, 2, 1, 0, 2, 1, 2, 1, 0, 2, 3, 0, 3, 2, 4, 1, 1, 4, 0, 0, 2, 0, 1, 3, 4, 0, 3, 0, 2, 2, 1, 0, 4, 4, 1, 4, 3, 2, 3, 1, 2, 4, 1, 0, 4, 3, 4, 1, 4, 4, 4, 0, 4, 1, 0, 0, 0, 1, 2, 0, 3, 3, 4, 0, 0, 4, 1, 3, 2, 0, 3, 0, 4, 4, 0, 4, 0, 3, 2, 0, 2, 1, 1, 1, 3, 3, 3, 0, 3, 2, 0, 4, 1, 0, 4, 1, 2, 2, 2, 4, 4, 1, 0, 3, 0, 3, 2, 0, 1, 3, 2, 4, 2, 3, 3, 3, 0, 4, 1, 2, 0, 3, 0, 2, 3, 0, 4, 3, 2, 3, 1, 1, 0, 4, 0, 1, 4, 2, 2, 1, 4, 4, 2, 0, 2, 1, 3, 3, 3, 0, 1, 0, 3, 3, 3, 2, 1, 3, 2, 3, 2, 0, 2, 0, 2, 2, 3, 0, 1, 0, 2, 2, 2, 0, 3, 3, 4, 0, 2, 3, 2, 0, 2, 0, 0, 2, 1, 1, 2, 3, 4, 2, 1, 2, 3, 0, 3, 4, 4, 1, 0, 0, 3, 3, 4, 1, 2, 3, 0, 4, 1, 1, 3, 3, 2, 2, 2, 2, 2, 3, 1, 2, 3, 4, 3, 0, 1, 1, 0, 1, 4, 3, 4, 1, 3, 2, 3, 3, 1, 4, 1, 1, 0, 1, 2, 4, 0];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 1, 8, -15, 8, 0);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 6");
        assert_eq!(strm.next_out, vec![29, 208, 11, 22, 0, 33, 8, 2, 64, 127, 247, 63, 115, 67, 91, 219, 43, 69, 65, 170, 167, 122, 172, 237, 218, 237, 238, 189, 157, 237, 153, 178, 110, 183, 118, 238, 230, 170, 186, 74, 48, 64, 233, 59, 40, 136, 94, 135, 125, 237, 112, 23, 117, 181, 211, 85, 147, 235, 89, 127, 160, 85, 119, 125, 171, 98, 81, 220, 72, 35, 3, 83, 143, 187, 132, 32, 139, 132, 209, 72, 233, 232, 9, 35, 27, 13, 221, 52, 132, 240, 194, 35, 252, 187, 69, 105, 8, 145, 144, 20, 98, 66, 53, 129, 242, 208, 125, 225, 74, 9, 5, 153, 237, 207, 19, 88, 68, 25, 204, 204, 201, 65, 222, 36, 249, 21, 132, 241, 155, 0, 86, 125, 200, 56, 160, 62, 128, 152, 180, 223, 131, 204, 52, 144, 4, 154, 47, 140, 19, 22, 34, 51, 1, 245, 209, 29, 134, 228, 242, 48, 130, 210, 124, 68, 179, 128, 65, 186, 203, 49, 148, 163, 121, 241, 249, 1], "fast L1 6");
    }

    #[test]
    fn test_big_huff_0() {
        let input: Vec<u8> = vec![57, 12, 140, 125, 114, 71, 52, 44, 216, 16, 15, 47, 111, 119, 13, 101, 214, 112, 229, 142, 3, 81, 216, 174, 142, 79, 110, 172, 52, 47, 194, 49, 183, 176, 135, 22, 235, 63, 193, 40, 150, 185, 98, 35, 23, 116, 148, 40, 119, 51, 194, 142, 232, 186, 83, 189, 181, 107, 136, 36, 87, 125, 83, 236, 194, 138, 112, 166, 28, 117, 16, 161, 205, 137, 33, 108, 161, 108, 255, 202, 234, 73, 135, 71, 126, 134, 219, 204, 185, 112, 70, 252, 46, 24, 56, 78, 81, 216, 32, 197, 195, 239, 128, 5, 58, 136, 174, 57, 150, 222, 80, 232, 1, 134, 91, 54, 152, 101, 78, 191, 82, 0, 165, 250, 9, 57, 185, 157, 122, 29, 123, 40, 43, 248, 35, 64, 65, 243, 84, 135, 216, 108, 102, 159, 204, 191, 224, 231, 61, 126, 115, 32, 173, 10, 117, 112, 3, 36, 30, 117, 34, 16, 169, 36, 121, 142, 248, 109, 67, 242, 124, 242, 208, 97, 48, 49, 220, 181, 216, 210, 239, 27, 50, 31, 206, 173, 55, 127, 98, 97, 229, 71, 216, 93, 142, 236, 127, 38, 226, 50, 25, 7, 47, 121, 85, 208, 248, 246, 109, 205, 30, 84, 194, 1, 199, 135, 232, 146, 216, 249, 79, 97, 151, 111, 29, 31, 160, 29, 25, 244, 80, 29, 41, 95, 35, 34, 120, 206, 61, 126, 20, 41, 214, 161, 133, 104, 160, 122, 135, 202, 67, 153, 234, 161, 37, 4, 234, 51, 37, 109, 135, 67, 178, 35, 125, 189, 145, 80, 224, 154, 4, 153, 53, 68, 135, 59, 54, 79, 139, 144, 107, 175, 104, 135, 250, 128, 26, 47, 216, 141, 22, 1, 170, 66, 134, 82, 226, 218, 4, 57, 38, 76, 18, 189, 75, 220, 65, 21, 157, 186, 20, 183, 107, 127, 52, 181, 208, 79, 121, 83, 90, 211, 12, 91, 170, 210, 127];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 0");
        assert_eq!(strm.next_out, vec![1, 71, 1, 184, 254, 57, 12, 140, 125, 114, 71, 52, 44, 216, 16, 15, 47, 111, 119, 13, 101, 214, 112, 229, 142, 3, 81, 216, 174, 142, 79, 110, 172, 52, 47, 194, 49, 183, 176, 135, 22, 235, 63, 193, 40, 150, 185, 98, 35, 23, 116, 148, 40, 119, 51, 194, 142, 232, 186, 83, 189, 181, 107, 136, 36, 87, 125, 83, 236, 194, 138, 112, 166, 28, 117, 16, 161, 205, 137, 33, 108, 161, 108, 255, 202, 234, 73, 135, 71, 126, 134, 219, 204, 185, 112, 70, 252, 46, 24, 56, 78, 81, 216, 32, 197, 195, 239, 128, 5, 58, 136, 174, 57, 150, 222, 80, 232, 1, 134, 91, 54, 152, 101, 78, 191, 82, 0, 165, 250, 9, 57, 185, 157, 122, 29, 123, 40, 43, 248, 35, 64, 65, 243, 84, 135, 216, 108, 102, 159, 204, 191, 224, 231, 61, 126, 115, 32, 173, 10, 117, 112, 3, 36, 30, 117, 34, 16, 169, 36, 121, 142, 248, 109, 67, 242, 124, 242, 208, 97, 48, 49, 220, 181, 216, 210, 239, 27, 50, 31, 206, 173, 55, 127, 98, 97, 229, 71, 216, 93, 142, 236, 127, 38, 226, 50, 25, 7, 47, 121, 85, 208, 248, 246, 109, 205, 30, 84, 194, 1, 199, 135, 232, 146, 216, 249, 79, 97, 151, 111, 29, 31, 160, 29, 25, 244, 80, 29, 41, 95, 35, 34, 120, 206, 61, 126, 20, 41, 214, 161, 133, 104, 160, 122, 135, 202, 67, 153, 234, 161, 37, 4, 234, 51, 37, 109, 135, 67, 178, 35, 125, 189, 145, 80, 224, 154, 4, 153, 53, 68, 135, 59, 54, 79, 139, 144, 107, 175, 104, 135, 250, 128, 26, 47, 216, 141, 22, 1, 170, 66, 134, 82, 226, 218, 4, 57, 38, 76, 18, 189, 75, 220, 65, 21, 157, 186, 20, 183, 107, 127, 52, 181, 208, 79, 121, 83, 90, 211, 12, 91, 170, 210, 127], "big huff 0");
    }
    #[test]
    fn test_big_huff_1() {
        let input: Vec<u8> = vec![1, 0, 3, 0, 3, 1, 1, 3, 2, 2, 1, 1, 0, 1, 3, 2, 2, 0, 2, 2, 3, 2, 0, 0, 2, 1, 2, 0, 0, 3, 2, 2, 3, 0, 3, 1, 2, 0, 3, 0, 1, 2, 3, 0, 2, 2, 0, 2, 2, 3, 2, 3, 2, 1, 1, 3, 3, 1, 2, 3, 0, 2, 2, 1, 3, 2, 3, 3, 3, 1, 3, 1, 0, 2, 2, 0, 1, 2, 1, 1, 1, 0, 0, 1, 3, 0, 3, 3, 1, 3, 3, 3, 1, 1, 0, 0, 3, 1, 1, 3, 0, 1, 0, 3, 1, 3, 2, 3, 3, 3, 1, 3, 3, 2, 1, 2, 3, 1, 2, 3, 0, 2, 1, 2, 2, 2, 0, 1, 1, 1, 3, 1, 1, 0, 3, 3, 2];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 1");
        assert_eq!(strm.next_out, vec![5, 193, 1, 1, 0, 0, 0, 130, 160, 212, 255, 159, 3, 214, 130, 20, 70, 58, 205, 77, 220, 210, 22, 174, 97, 211, 105, 38, 20, 54, 37, 43, 98, 58, 4, 54, 90, 81, 193, 22, 52, 22, 89, 81, 98, 216, 68, 29, 16, 172, 60], "big huff 1");
    }
    #[test]
    fn test_big_huff_2() {
        let input: Vec<u8> = vec![112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 2");
        assert_eq!(strm.next_out, vec![5, 193, 193, 9, 0, 0, 8, 196, 176, 85, 110, 181, 130, 126, 69, 164, 251, 99, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 15], "big huff 2");
    }
    #[test]
    fn test_big_huff_3() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 3");
        assert_eq!(strm.next_out, vec![5, 193, 129, 0, 0, 0, 0, 0, 144, 86, 255, 19, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4], "big huff 3");
    }
    #[test]
    fn test_big_huff_4() {
        let input: Vec<u8> = vec![31, 105, 215, 199, 10, 194, 244, 3, 180, 152, 199, 214, 112, 249, 112, 139, 223, 248, 14, 199, 172, 207, 84, 239, 65, 13, 201, 13, 42, 219, 69, 236, 93, 25, 133, 194, 167, 108, 232, 167, 172, 194, 142, 215, 129, 41, 240, 9, 26, 179, 114, 35, 20, 15, 126, 102, 10, 78, 122, 64, 242, 58, 111, 238, 131, 188, 85, 58, 83, 159, 55, 13, 159, 192, 203, 101, 38, 124, 52, 154, 61, 21, 177, 219, 189, 35, 174, 6, 215, 250, 54, 221, 185, 235, 78, 222, 90, 138, 247, 238, 223, 137, 165, 125, 44, 142, 230, 124, 237, 194, 172, 14, 253, 166, 93, 249, 108, 181, 132, 174, 143, 141, 5, 97, 43, 123, 208, 250, 123, 243, 251, 229, 8, 47, 150, 113, 207, 124, 156, 188, 242, 176, 217, 169, 180, 232, 138, 156, 128, 118, 61, 98, 161, 61, 94, 98, 110, 247, 141, 144, 51, 99, 151, 116, 184, 91, 154, 7, 64, 140, 23, 27, 149, 64, 251, 52, 6, 145, 240, 245, 225, 174, 94, 26, 129, 244, 58, 33, 205, 251, 37, 27, 77, 76, 155, 43, 127, 60, 213, 115, 194, 230, 226, 152, 219, 156, 30, 50, 106, 108, 135, 41];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 4");
        assert_eq!(strm.next_out, vec![1, 212, 0, 43, 255, 31, 105, 215, 199, 10, 194, 244, 3, 180, 152, 199, 214, 112, 249, 112, 139, 223, 248, 14, 199, 172, 207, 84, 239, 65, 13, 201, 13, 42, 219, 69, 236, 93, 25, 133, 194, 167, 108, 232, 167, 172, 194, 142, 215, 129, 41, 240, 9, 26, 179, 114, 35, 20, 15, 126, 102, 10, 78, 122, 64, 242, 58, 111, 238, 131, 188, 85, 58, 83, 159, 55, 13, 159, 192, 203, 101, 38, 124, 52, 154, 61, 21, 177, 219, 189, 35, 174, 6, 215, 250, 54, 221, 185, 235, 78, 222, 90, 138, 247, 238, 223, 137, 165, 125, 44, 142, 230, 124, 237, 194, 172, 14, 253, 166, 93, 249, 108, 181, 132, 174, 143, 141, 5, 97, 43, 123, 208, 250, 123, 243, 251, 229, 8, 47, 150, 113, 207, 124, 156, 188, 242, 176, 217, 169, 180, 232, 138, 156, 128, 118, 61, 98, 161, 61, 94, 98, 110, 247, 141, 144, 51, 99, 151, 116, 184, 91, 154, 7, 64, 140, 23, 27, 149, 64, 251, 52, 6, 145, 240, 245, 225, 174, 94, 26, 129, 244, 58, 33, 205, 251, 37, 27, 77, 76, 155, 43, 127, 60, 213, 115, 194, 230, 226, 152, 219, 156, 30, 50, 106, 108, 135, 41], "big huff 4");
    }
    #[test]
    fn test_big_huff_5() {
        let input: Vec<u8> = vec![1, 1, 0, 1, 0, 3, 3, 3, 2, 0, 1, 2, 2, 3, 0, 1, 2, 1, 3, 0, 1, 1, 2, 1, 0, 0, 1, 2, 2, 3, 0, 3, 2, 3, 2, 3, 3, 0, 0, 3, 2, 2, 0, 0, 1, 0, 2, 0, 1, 3, 3, 2, 1, 3, 3, 0, 3, 2, 3, 2, 2, 0, 1, 2, 3, 3, 2, 3, 0, 3, 0, 2, 2, 2, 0, 3, 0, 3, 3, 0, 1];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 5");
        assert_eq!(strm.next_out, vec![5, 193, 1, 1, 0, 0, 0, 130, 32, 211, 255, 159, 131, 141, 81, 201, 52, 230, 98, 115, 48, 141, 204, 130, 20, 134, 172, 92, 145, 41, 179, 140, 80, 137, 98, 7], "big huff 5");
    }
    #[test]
    fn test_big_huff_6() {
        let input: Vec<u8> = vec![112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 6");
        assert_eq!(strm.next_out, vec![5, 193, 193, 9, 0, 0, 8, 196, 176, 85, 110, 181, 130, 126, 69, 164, 251, 99, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 60], "big huff 6");
    }
    #[test]
    fn test_big_huff_7() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 7");
        assert_eq!(strm.next_out, vec![5, 193, 129, 0, 0, 0, 0, 0, 144, 86, 255, 19, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32], "big huff 7");
    }
    #[test]
    fn test_big_huff_8() {
        let input: Vec<u8> = vec![255, 226, 26, 104, 136, 67, 147, 224, 248, 62, 14, 122, 81, 159, 7, 208, 47, 115, 58, 236, 60, 78, 255, 149, 139, 212, 247, 241, 124, 233, 74, 196, 97, 69, 35, 141, 212, 174, 136, 1, 144, 152, 250, 76, 228, 247, 176, 170, 193, 233, 164, 96, 122, 196, 119, 210, 22, 162, 242, 195, 197, 77, 253, 18, 64, 169, 51, 225, 51, 233, 7, 73, 209, 79, 38, 240, 135, 173, 203, 41, 168, 194, 162, 249, 18, 35, 120, 147, 116, 46, 222, 50, 51, 227, 85, 153, 14, 23, 166, 28, 150, 183, 191, 220, 74, 125, 210, 92, 87, 89, 40, 195, 123, 254, 73, 118, 236, 130, 235, 130, 4, 238, 147, 80, 37, 226, 176, 153, 217, 128, 233, 154, 101, 196, 247, 54, 121, 195, 183, 151, 151, 11, 202, 140, 4, 25, 254, 146, 117, 180, 112, 97, 128, 70, 49, 20, 158, 225, 17, 186, 67, 46, 151, 167, 212, 89, 102, 67, 187, 139, 84, 131, 246, 151, 173, 58, 239, 38, 72, 115, 203, 187, 46, 202, 7, 135, 63, 232, 188, 134, 195, 190, 55, 119, 241, 12, 167, 113, 32, 237, 154, 209, 59, 71, 23, 19, 155, 252, 59, 49, 120, 69, 198, 232, 189, 214, 79, 212, 50, 250, 208, 143, 16, 189, 111, 227, 227, 120, 185, 50, 188, 183, 31, 203, 141, 97, 62, 232, 46, 108, 10, 25, 170, 124, 64, 105, 35, 106, 110, 119, 168, 75, 1, 141, 74, 66, 128, 89, 56, 13, 67, 7, 183, 121, 165, 8, 89, 135, 26, 64, 215, 58, 32, 243, 229, 185, 55, 231, 113, 22, 154, 234, 15, 31, 245, 205, 218, 55, 251, 227, 37, 41, 164, 75, 33, 64, 140, 166, 195, 150, 232, 220, 50, 58, 110, 220, 231, 116, 211, 173, 232, 204, 212, 48, 160, 218, 160, 130];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 8");
        assert_eq!(strm.next_out, vec![1, 62, 1, 193, 254, 255, 226, 26, 104, 136, 67, 147, 224, 248, 62, 14, 122, 81, 159, 7, 208, 47, 115, 58, 236, 60, 78, 255, 149, 139, 212, 247, 241, 124, 233, 74, 196, 97, 69, 35, 141, 212, 174, 136, 1, 144, 152, 250, 76, 228, 247, 176, 170, 193, 233, 164, 96, 122, 196, 119, 210, 22, 162, 242, 195, 197, 77, 253, 18, 64, 169, 51, 225, 51, 233, 7, 73, 209, 79, 38, 240, 135, 173, 203, 41, 168, 194, 162, 249, 18, 35, 120, 147, 116, 46, 222, 50, 51, 227, 85, 153, 14, 23, 166, 28, 150, 183, 191, 220, 74, 125, 210, 92, 87, 89, 40, 195, 123, 254, 73, 118, 236, 130, 235, 130, 4, 238, 147, 80, 37, 226, 176, 153, 217, 128, 233, 154, 101, 196, 247, 54, 121, 195, 183, 151, 151, 11, 202, 140, 4, 25, 254, 146, 117, 180, 112, 97, 128, 70, 49, 20, 158, 225, 17, 186, 67, 46, 151, 167, 212, 89, 102, 67, 187, 139, 84, 131, 246, 151, 173, 58, 239, 38, 72, 115, 203, 187, 46, 202, 7, 135, 63, 232, 188, 134, 195, 190, 55, 119, 241, 12, 167, 113, 32, 237, 154, 209, 59, 71, 23, 19, 155, 252, 59, 49, 120, 69, 198, 232, 189, 214, 79, 212, 50, 250, 208, 143, 16, 189, 111, 227, 227, 120, 185, 50, 188, 183, 31, 203, 141, 97, 62, 232, 46, 108, 10, 25, 170, 124, 64, 105, 35, 106, 110, 119, 168, 75, 1, 141, 74, 66, 128, 89, 56, 13, 67, 7, 183, 121, 165, 8, 89, 135, 26, 64, 215, 58, 32, 243, 229, 185, 55, 231, 113, 22, 154, 234, 15, 31, 245, 205, 218, 55, 251, 227, 37, 41, 164, 75, 33, 64, 140, 166, 195, 150, 232, 220, 50, 58, 110, 220, 231, 116, 211, 173, 232, 204, 212, 48, 160, 218, 160, 130], "big huff 8");
    }
    #[test]
    fn test_big_huff_9() {
        let input: Vec<u8> = vec![1, 3, 0, 0, 0, 0, 3, 0, 2, 1, 0, 2, 0, 3, 2, 3, 0, 2, 2, 2, 0, 1, 1, 3, 1, 0, 2, 2, 0, 2, 1, 3, 0, 2, 0, 1, 2, 2, 2, 2, 0, 1, 1, 3, 0, 1, 0, 0, 1, 3, 3, 3, 2, 1, 2, 2, 2, 0, 0, 1, 1, 0, 0, 2, 3, 3, 3, 3, 3, 2, 1, 0, 2, 3, 0, 2, 3, 2, 0, 1, 3, 0, 0, 1, 2, 1, 1, 2, 2, 2, 0, 0, 3, 3, 1, 1, 3, 1, 2, 0, 3, 0, 3, 0, 3, 0, 2, 3, 3, 3, 2, 0, 3, 0, 2, 1, 3, 2, 0, 3, 0, 1, 3, 3, 0, 3, 2, 2, 1, 2, 1, 0, 0, 1, 2, 2, 1, 1, 0, 1, 2, 1, 1, 1, 0, 1, 3, 3, 3, 2, 2, 1, 3, 0, 3, 3, 2, 2, 0, 2, 0, 2, 3, 3, 0, 0, 2, 2, 0, 0, 3, 3, 0, 3, 1, 2, 3, 1, 0, 3, 0, 2, 0, 1, 0, 1, 3, 3, 1, 2, 2, 2];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 9");
        assert_eq!(strm.next_out, vec![5, 193, 1, 1, 0, 0, 0, 130, 32, 211, 255, 159, 131, 5, 16, 14, 201, 80, 217, 26, 138, 11, 153, 42, 91, 12, 86, 57, 21, 54, 176, 42, 135, 97, 178, 96, 110, 42, 212, 214, 36, 34, 172, 36, 92, 18, 43, 210, 57, 152, 110, 204, 109, 172, 210, 69, 41, 98, 129, 66, 209, 108, 132, 140, 213, 212, 3], "big huff 9");
    }
    #[test]
    fn test_big_huff_10() {
        let input: Vec<u8> = vec![112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 10");
        assert_eq!(strm.next_out, vec![5, 193, 193, 9, 0, 0, 8, 196, 176, 85, 110, 181, 130, 126, 69, 164, 251, 99, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 60], "big huff 10");
    }
    #[test]
    fn test_big_huff_11() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 11");
        assert_eq!(strm.next_out, vec![5, 193, 129, 0, 0, 0, 0, 0, 144, 86, 255, 19, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32], "big huff 11");
    }
    #[test]
    fn test_big_huff_12() {
        let input: Vec<u8> = vec![173, 26, 171, 33, 168, 48, 197, 145, 129, 76, 170, 41, 72, 179, 158, 200, 66, 43, 158, 192, 168, 65, 47, 216, 185, 9, 185, 158, 92, 109, 174, 248, 98, 115, 70, 79, 39, 151, 51, 19, 172, 67, 192, 78, 83, 92, 84, 224, 22, 210, 186, 121, 227, 145, 229, 119, 122, 158, 240, 99, 188, 225, 236, 144, 195, 214, 82, 102, 70, 128, 26, 246, 190, 52, 63, 145, 42, 82, 139, 230, 75, 223, 46, 113, 230, 178, 13, 212, 27, 202, 191, 120, 197, 41, 191, 114, 14, 163, 50, 171, 74, 70, 19, 146, 241, 71, 240, 229, 2, 40, 9, 131, 110, 76, 216, 56, 147, 121, 154, 62, 24, 122, 214, 234, 32, 56, 255, 8, 123, 73, 149, 219, 0, 180, 123, 213, 95, 43, 184, 34, 10, 199, 240, 22, 198, 191, 129, 8, 182, 34, 176, 123, 53, 170, 68, 22, 180, 173, 89, 237, 245, 93, 69, 32, 234, 18, 150, 103, 22, 102, 21, 161, 158, 203, 242, 129, 18, 97, 146, 182, 24, 169, 139, 63, 188, 223, 204, 225, 197, 173, 95, 254, 254, 188, 136, 42, 217, 40, 220, 92, 150, 164, 52, 40, 167, 151, 156, 228, 218, 85, 227, 179, 228, 21, 180, 222, 140, 29, 38, 207, 186, 81, 15, 73, 224, 17, 64, 34, 120, 187, 185, 196, 16, 78, 230, 189, 190, 227, 39, 70, 187, 203, 160, 142, 127, 58, 13, 95, 255, 198, 60, 134, 133, 228, 109, 146, 251, 102, 62, 69, 37, 231, 88, 227, 44, 163, 177, 33, 148, 153, 80, 89, 185, 114, 62, 102, 71, 121, 252, 13, 184, 188, 239, 66, 44, 33, 158, 203, 245, 210, 209, 37, 64, 162, 37, 230, 238, 176, 65, 93, 66, 221, 28, 63, 78, 155, 84, 82, 165, 115, 177, 145, 40, 128, 100, 140, 64, 155, 47, 86, 78, 87, 172, 21, 14, 41, 23, 135, 107, 213, 15, 254, 148, 154, 247, 125, 207, 152, 232, 37, 30, 80, 225, 212, 247, 237, 104, 174, 73, 160, 163, 176, 204, 66, 189, 54, 163, 123, 238, 62, 136, 230, 126, 72, 49, 25, 148, 196, 214, 127, 81, 167, 160, 97, 81, 255, 239, 255, 157, 254, 11, 46, 201, 234, 123, 110, 180, 24, 25, 144, 253, 240, 146, 4, 55, 220];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 12");
        assert_eq!(strm.next_out, vec![1, 140, 1, 115, 254, 173, 26, 171, 33, 168, 48, 197, 145, 129, 76, 170, 41, 72, 179, 158, 200, 66, 43, 158, 192, 168, 65, 47, 216, 185, 9, 185, 158, 92, 109, 174, 248, 98, 115, 70, 79, 39, 151, 51, 19, 172, 67, 192, 78, 83, 92, 84, 224, 22, 210, 186, 121, 227, 145, 229, 119, 122, 158, 240, 99, 188, 225, 236, 144, 195, 214, 82, 102, 70, 128, 26, 246, 190, 52, 63, 145, 42, 82, 139, 230, 75, 223, 46, 113, 230, 178, 13, 212, 27, 202, 191, 120, 197, 41, 191, 114, 14, 163, 50, 171, 74, 70, 19, 146, 241, 71, 240, 229, 2, 40, 9, 131, 110, 76, 216, 56, 147, 121, 154, 62, 24, 122, 214, 234, 32, 56, 255, 8, 123, 73, 149, 219, 0, 180, 123, 213, 95, 43, 184, 34, 10, 199, 240, 22, 198, 191, 129, 8, 182, 34, 176, 123, 53, 170, 68, 22, 180, 173, 89, 237, 245, 93, 69, 32, 234, 18, 150, 103, 22, 102, 21, 161, 158, 203, 242, 129, 18, 97, 146, 182, 24, 169, 139, 63, 188, 223, 204, 225, 197, 173, 95, 254, 254, 188, 136, 42, 217, 40, 220, 92, 150, 164, 52, 40, 167, 151, 156, 228, 218, 85, 227, 179, 228, 21, 180, 222, 140, 29, 38, 207, 186, 81, 15, 73, 224, 17, 64, 34, 120, 187, 185, 196, 16, 78, 230, 189, 190, 227, 39, 70, 187, 203, 160, 142, 127, 58, 13, 95, 255, 198, 60, 134, 133, 228, 109, 146, 251, 102, 62, 69, 37, 231, 88, 227, 44, 163, 177, 33, 148, 153, 80, 89, 185, 114, 62, 102, 71, 121, 252, 13, 184, 188, 239, 66, 44, 33, 158, 203, 245, 210, 209, 37, 64, 162, 37, 230, 238, 176, 65, 93, 66, 221, 28, 63, 78, 155, 84, 82, 165, 115, 177, 145, 40, 128, 100, 140, 64, 155, 47, 86, 78, 87, 172, 21, 14, 41, 23, 135, 107, 213, 15, 254, 148, 154, 247, 125, 207, 152, 232, 37, 30, 80, 225, 212, 247, 237, 104, 174, 73, 160, 163, 176, 204, 66, 189, 54, 163, 123, 238, 62, 136, 230, 126, 72, 49, 25, 148, 196, 214, 127, 81, 167, 160, 97, 81, 255, 239, 255, 157, 254, 11, 46, 201, 234, 123, 110, 180, 24, 25, 144, 253, 240, 146, 4, 55, 220], "big huff 12");
    }
    #[test]
    fn test_big_huff_13() {
        let input: Vec<u8> = vec![2, 2, 3, 2, 0, 3, 0, 1, 2, 2, 0, 3, 3, 2, 0, 1, 0, 3, 2, 2, 2, 1, 1, 3, 0, 0, 0, 1, 2, 3, 3, 1, 1, 2, 2, 1, 3, 2, 2, 3, 2, 3, 0, 2, 2, 0, 3, 2, 0, 3, 2, 1, 0, 3, 1, 3, 1, 1, 0, 0, 1, 0, 3, 2, 3, 1, 3, 1, 3];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 13");
        assert_eq!(strm.next_out, vec![5, 193, 1, 1, 0, 0, 0, 130, 32, 211, 255, 159, 3, 77, 98, 74, 201, 72, 221, 2, 102, 109, 186, 52, 67, 73, 114, 180, 54, 24, 217, 90, 7], "big huff 13");
    }
    #[test]
    fn test_big_huff_14() {
        let input: Vec<u8> = vec![112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 14");
        assert_eq!(strm.next_out, vec![5, 193, 193, 9, 0, 0, 8, 196, 176, 85, 110, 181, 130, 126, 69, 164, 251, 99, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 162, 125, 147, 66, 178, 104, 223, 164, 144, 60], "big huff 14");
    }
    #[test]
    fn test_big_huff_15() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 15");
        assert_eq!(strm.next_out, vec![5, 193, 129, 0, 0, 0, 0, 0, 144, 86, 255, 19, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 32], "big huff 15");
    }
    #[test]
    fn test_big_huff_16() {
        let input: Vec<u8> = vec![31, 70, 106, 166, 244, 192, 160, 88, 235, 175, 181, 135, 247, 98, 126, 142, 152, 115, 152, 147, 106, 250, 162, 245, 178, 140, 147, 62, 194, 202, 176, 74, 148, 21, 147, 40, 177, 226, 131, 245, 109, 103, 138, 139, 70, 55, 122, 124, 25, 115, 119, 26, 51, 211, 169, 241, 51, 70, 2, 80, 208, 243, 244, 102, 147, 164, 146, 30, 45, 118, 19, 89, 213, 90, 18, 203, 253, 95, 148, 19, 4, 152, 54, 171, 145, 232, 252, 68, 239, 139, 98, 57, 169, 83, 234, 131, 95, 7, 172, 151, 98, 89, 207, 218, 167, 44, 205, 48, 94, 71, 244, 165, 127, 3, 133, 196, 120, 228, 136, 168, 154, 5, 133, 184, 120, 31, 60, 238, 157, 81, 207, 159, 60, 151, 188, 113, 112, 68, 244, 78, 232, 191, 212, 241, 111, 126, 41, 228, 185, 39, 57, 31, 103, 76, 84, 167, 226, 59, 105, 250, 46, 228, 28, 232, 67, 212, 233, 29, 236, 157, 11, 202, 130, 1, 111, 37, 23, 216, 176, 32, 30, 35, 241, 16, 146, 209, 92, 69, 215, 191, 195, 229, 193, 192, 41, 68, 178, 60, 91, 201, 65, 114, 1, 11, 152, 237, 217, 194, 117, 126, 235, 177, 79, 141, 96, 57, 16, 214, 8, 123, 105, 34, 51, 17, 228, 24, 125, 22, 205, 224, 119, 111, 28, 71, 148, 119, 163, 164, 121, 154, 73, 113, 211, 153, 140, 31, 89, 218, 253, 24, 176, 195, 163, 213, 209, 76, 153, 192, 94, 242, 123, 115, 153, 73, 237, 29, 211, 213, 68, 198, 124, 130, 104, 169, 40, 230, 189, 47, 97, 26, 137, 193, 20, 37, 96, 111, 245, 106, 170, 155, 7, 108, 97, 60, 245, 124, 104, 203, 122, 164, 144, 194, 238, 183, 157, 133, 184, 254, 238, 50, 240, 163, 104, 189, 160, 211, 23, 113, 74, 8, 133, 213, 151, 78, 100, 168, 117, 194, 125, 255, 172, 131, 250, 251, 235, 86, 180, 86, 71, 250, 94, 30, 17, 38, 24, 3, 211, 70, 118, 34, 77, 4, 111, 233, 191, 30, 247, 249, 8, 3, 210, 6, 8, 140, 146, 8, 220, 91, 54, 49, 76, 123, 98, 129, 181, 136, 203, 40, 191, 207, 235, 124, 115, 153, 41, 16, 47, 207, 194, 193, 243, 28, 4, 87, 42, 255, 222, 169, 48, 21, 117, 108, 243, 138, 23, 38, 143, 16, 91, 161, 8, 106, 73, 203, 39, 153, 83, 123, 199, 169, 196, 71, 40, 177, 27, 50, 223, 118, 38, 174, 203, 167, 15, 139, 230, 251, 116, 182, 192, 221, 95, 194, 43, 151, 126, 37];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 16");
        assert_eq!(strm.next_out, vec![1, 190, 1, 65, 254, 31, 70, 106, 166, 244, 192, 160, 88, 235, 175, 181, 135, 247, 98, 126, 142, 152, 115, 152, 147, 106, 250, 162, 245, 178, 140, 147, 62, 194, 202, 176, 74, 148, 21, 147, 40, 177, 226, 131, 245, 109, 103, 138, 139, 70, 55, 122, 124, 25, 115, 119, 26, 51, 211, 169, 241, 51, 70, 2, 80, 208, 243, 244, 102, 147, 164, 146, 30, 45, 118, 19, 89, 213, 90, 18, 203, 253, 95, 148, 19, 4, 152, 54, 171, 145, 232, 252, 68, 239, 139, 98, 57, 169, 83, 234, 131, 95, 7, 172, 151, 98, 89, 207, 218, 167, 44, 205, 48, 94, 71, 244, 165, 127, 3, 133, 196, 120, 228, 136, 168, 154, 5, 133, 184, 120, 31, 60, 238, 157, 81, 207, 159, 60, 151, 188, 113, 112, 68, 244, 78, 232, 191, 212, 241, 111, 126, 41, 228, 185, 39, 57, 31, 103, 76, 84, 167, 226, 59, 105, 250, 46, 228, 28, 232, 67, 212, 233, 29, 236, 157, 11, 202, 130, 1, 111, 37, 23, 216, 176, 32, 30, 35, 241, 16, 146, 209, 92, 69, 215, 191, 195, 229, 193, 192, 41, 68, 178, 60, 91, 201, 65, 114, 1, 11, 152, 237, 217, 194, 117, 126, 235, 177, 79, 141, 96, 57, 16, 214, 8, 123, 105, 34, 51, 17, 228, 24, 125, 22, 205, 224, 119, 111, 28, 71, 148, 119, 163, 164, 121, 154, 73, 113, 211, 153, 140, 31, 89, 218, 253, 24, 176, 195, 163, 213, 209, 76, 153, 192, 94, 242, 123, 115, 153, 73, 237, 29, 211, 213, 68, 198, 124, 130, 104, 169, 40, 230, 189, 47, 97, 26, 137, 193, 20, 37, 96, 111, 245, 106, 170, 155, 7, 108, 97, 60, 245, 124, 104, 203, 122, 164, 144, 194, 238, 183, 157, 133, 184, 254, 238, 50, 240, 163, 104, 189, 160, 211, 23, 113, 74, 8, 133, 213, 151, 78, 100, 168, 117, 194, 125, 255, 172, 131, 250, 251, 235, 86, 180, 86, 71, 250, 94, 30, 17, 38, 24, 3, 211, 70, 118, 34, 77, 4, 111, 233, 191, 30, 247, 249, 8, 3, 210, 6, 8, 140, 146, 8, 220, 91, 54, 49, 76, 123, 98, 129, 181, 136, 203, 40, 191, 207, 235, 124, 115, 153, 41, 16, 47, 207, 194, 193, 243, 28, 4, 87, 42, 255, 222, 169, 48, 21, 117, 108, 243, 138, 23, 38, 143, 16, 91, 161, 8, 106, 73, 203, 39, 153, 83, 123, 199, 169, 196, 71, 40, 177, 27, 50, 223, 118, 38, 174, 203, 167, 15, 139, 230, 251, 116, 182, 192, 221, 95, 194, 43, 151, 126, 37], "big huff 16");
    }
    #[test]
    fn test_big_huff_17() {
        let input: Vec<u8> = vec![2, 1, 3, 1, 3, 2, 2, 0, 0, 0, 2, 3, 2, 2, 0, 1, 0, 1, 3, 3, 3, 0, 0, 0, 2, 0, 2, 3, 0, 2, 3, 3, 0, 1, 1, 3, 1, 1, 2, 2, 2, 3, 1];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 17");
        assert_eq!(strm.next_out, vec![5, 193, 1, 1, 0, 0, 0, 130, 32, 211, 255, 159, 3, 215, 82, 192, 148, 177, 10, 16, 195, 98, 107, 83, 219, 1], "big huff 17");
    }
    #[test]
    fn test_big_huff_18() {
        let input: Vec<u8> = vec![112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32, 112, 97, 116, 116, 101, 114, 110, 32, 100, 97, 116, 97, 32];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 18");
        assert_eq!(strm.next_out, vec![5, 193, 193, 9, 0, 0, 8, 196, 176, 85, 110, 181, 130, 126, 69, 164, 251, 99, 178, 104, 223, 164, 144, 44, 218, 55, 41, 36, 139, 246, 77, 10, 201, 3], "big huff 18");
    }
    #[test]
    fn test_big_huff_19() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 2000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "ret 19");
        assert_eq!(strm.next_out, vec![5, 193, 129, 0, 0, 0, 0, 0, 144, 86, 255, 19, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2], "big huff 19");
    }

    #[test]
    fn test_dbg_steps() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.status = 42;
        assert_eq!(super::deflate_state_check(&strm), false, "sc42");
        let r = super::deflate_reset_keep(&mut strm);
        assert_eq!(r, 0, "rk ret");
        assert_eq!(strm.state.status, 42, "status after rk");
        assert_eq!(strm.state.wrap, 0, "wrap after rk default0");
    }


    #[test]
    fn test_dbg_init() {
        let mut strm = zlib_types::DeflateStream::default();
        let ir = super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        assert_eq!(ir, 0, "init ret");
        assert_eq!(strm.state.status, 42, "status after init");
        assert_eq!(super::deflate_state_check(&strm), false, "statecheck");
        assert_eq!(strm.state.wrap, 0, "wrap raw");
        assert_eq!(strm.state.w_size, 32768, "wsize");
    }


    #[test]
    fn test_e2e_huff_0() {
        let input: Vec<u8> = vec![];
        let mut strm = zlib_types::DeflateStream::default();
        let ir = super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        assert_eq!(ir, 0, "init 0");
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "deflate ret 0");
        assert_eq!(strm.next_out, vec![3, 0], "e2e huff 0");
    }
    #[test]
    fn test_e2e_huff_1() {
        let input: Vec<u8> = vec![97];
        let mut strm = zlib_types::DeflateStream::default();
        let ir = super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        assert_eq!(ir, 0, "init 1");
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "deflate ret 1");
        assert_eq!(strm.next_out, vec![75, 4, 0], "e2e huff 1");
    }
    #[test]
    fn test_e2e_huff_2() {
        let input: Vec<u8> = vec![104, 101, 108, 108, 111, 32, 119, 111, 114, 108, 100];
        let mut strm = zlib_types::DeflateStream::default();
        let ir = super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        assert_eq!(ir, 0, "init 2");
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "deflate ret 2");
        assert_eq!(strm.next_out, vec![203, 72, 205, 201, 201, 87, 40, 207, 47, 202, 73, 1, 0], "e2e huff 2");
    }
    #[test]
    fn test_e2e_huff_3() {
        let input: Vec<u8> = vec![97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97, 97];
        let mut strm = zlib_types::DeflateStream::default();
        let ir = super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        assert_eq!(ir, 0, "init 3");
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "deflate ret 3");
        assert_eq!(strm.next_out, vec![5, 193, 129, 0, 0, 0, 0, 0, 144, 86, 255, 19, 0, 0, 8], "e2e huff 3");
    }
    #[test]
    fn test_e2e_huff_4() {
        let input: Vec<u8> = vec![68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68, 68];
        let mut strm = zlib_types::DeflateStream::default();
        let ir = super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        assert_eq!(ir, 0, "init 4");
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "deflate ret 4");
        assert_eq!(strm.next_out, vec![5, 193, 129, 0, 0, 0, 0, 0, 144, 57, 255, 77, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8], "e2e huff 4");
    }
    #[test]
    fn test_e2e_huff_5() {
        let input: Vec<u8> = vec![84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32, 84, 104, 101, 32, 113, 117, 105, 99, 107, 32, 98, 114, 111, 119, 110, 32, 102, 111, 120, 32, 106, 117, 109, 112, 115, 32, 111, 118, 101, 114, 32, 116, 104, 101, 32, 108, 97, 122, 121, 32, 100, 111, 103, 46, 32];
        let mut strm = zlib_types::DeflateStream::default();
        let ir = super::deflate_init2(&mut strm, 6, 8, -15, 8, 2);
        assert_eq!(ir, 0, "init 5");
        strm.next_in = input.clone(); strm.avail_in = input.len(); strm.next_out = vec![]; strm.avail_out = 1000000;
        let r = super::deflate(&mut strm, 4);
        assert_eq!(r, 1, "deflate ret 5");
        assert_eq!(strm.next_out, vec![5, 193, 9, 1, 128, 32, 16, 0, 193, 42, 155, 128, 52, 22, 16, 61, 64, 124, 14, 249, 68, 211, 59, 51, 5, 225, 110, 219, 178, 99, 179, 62, 23, 78, 7, 177, 157, 169, 160, 93, 50, 53, 8, 199, 252, 189, 172, 234, 13, 83, 16, 238, 182, 45, 59, 54, 235, 115, 225, 116, 16, 219, 153, 10, 218, 37, 83, 131, 112, 204, 223, 203, 170, 222, 48, 5, 225, 110, 219, 178, 99, 179, 62, 23, 78, 7, 177, 157, 169, 160, 93, 50, 53, 8, 199, 252, 189, 172, 234, 13, 83, 16, 238, 182, 45, 59, 54, 235, 115, 225, 116, 16, 219, 153, 10, 218, 37, 83, 131, 112, 204, 223, 203, 170, 222, 48, 5, 225, 110, 219, 178, 99, 179, 62, 23, 78, 7, 177, 157, 169, 160, 93, 50, 53, 8, 199, 252, 189, 172, 234, 13, 63], "e2e huff 5");
    }

    #[test]
    fn test_lm_0() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![4, 0, 3, 1, 0, 1, 0, 2, 3, 1, 3, 4, 0, 4, 1, 0, 1, 3, 2, 1, 3, 1, 0, 1, 4, 4, 3, 1, 1, 0, 0, 1, 1, 1, 1, 2, 2, 1, 4, 1, 1, 1, 3, 2, 0, 2, 3, 1, 1, 2, 0, 2, 2, 4, 4, 0, 4, 2, 0, 2, 2, 2, 3, 2, 1, 3, 3, 1, 0, 2, 0, 2, 3, 0, 4, 3, 2, 3, 4, 0, 3, 0, 1, 4, 1, 0, 1, 3, 2, 4, 2, 4, 2, 3, 0, 4, 2, 2, 0, 3, 0, 1, 2, 4, 4, 2, 1, 2, 2, 4, 0, 2, 2, 2, 1, 0, 1, 2, 3, 1, 0, 0, 4, 4, 3, 0, 1, 4, 2, 2, 3, 3, 1, 0, 0, 3, 2, 1, 1, 4, 1, 3, 0, 1, 3, 2, 1, 0, 3, 2, 1, 3, 4, 1, 4, 3, 3, 2, 3, 2, 2, 3, 3, 1, 0, 3, 4, 1, 3, 2, 1, 0, 3, 2, 4, 4, 4, 2, 0, 2, 4, 0, 2, 2, 4, 2, 3, 2, 2, 2, 1, 4, 0, 3, 4, 2, 2, 2, 3, 2, 4, 2, 2, 2, 2, 3, 2, 1, 3, 2, 2, 4, 1, 4, 1, 1, 2, 3, 2, 0, 3, 1, 4, 4, 4, 3, 2, 4, 4, 2, 0, 1, 1, 4, 3, 4, 1, 1, 1, 0, 3, 1, 1, 0, 1, 0, 2, 1, 3, 1, 4, 0, 3, 3, 2, 3, 4, 0, 4, 1, 1, 2, 0, 2, 3, 2, 3, 0, 4, 2, 0, 4, 4, 2, 0, 2, 4, 4, 2, 4, 2, 2, 1, 3, 3, 4, 4, 2, 3, 1, 1, 4, 3, 4, 3, 1, 1, 4, 0, 2, 0, 3, 0, 2, 4, 4, 4, 1, 2, 4, 3, 3, 3, 1, 3, 2, 3, 3, 3, 1, 4, 4, 2, 2, 3, 2, 3, 0, 2, 2, 3, 2, 1, 3, 0, 0, 4, 3, 1, 2, 0, 1, 3, 0, 3, 4, 4, 2, 1, 3, 0, 1, 3, 2, 1, 2, 2, 3, 4, 3, 4, 4, 0, 0, 1, 2, 2, 4, 2, 4, 2, 4, 0, 3, 2, 2, 4, 1, 0, 0, 2, 4, 3, 0, 4, 1, 0, 3, 3, 4, 4, 3, 3, 3, 3, 1, 2, 3, 0, 2, 0, 3, 4, 2, 3, 2, 1, 1, 3, 4, 3, 2, 4, 1, 3, 4, 4, 0, 0, 1, 2, 0, 0, 0, 2, 3, 0, 3, 3, 0, 0, 0, 1, 4, 0, 1, 2, 3, 1, 1, 4, 1, 3, 1, 0, 4, 1, 0, 4, 0, 3, 0, 2, 0, 4, 4, 0, 3, 4, 1, 0, 3, 0, 2, 4, 3, 3, 2, 2, 0, 1, 2, 1, 4, 4, 2, 4, 4, 4, 1, 2, 0, 4, 1, 2, 2, 4, 1, 1, 2, 3, 3, 1, 1, 0, 2, 0, 4, 0, 0, 0, 4, 4, 3, 1, 3, 3, 3, 2, 0, 4, 0, 4, 3, 0, 1, 3, 1, 0, 0, 3, 1, 1, 4, 3, 2, 1, 2, 2, 4, 2, 3, 3, 1, 2, 2, 3, 2, 4, 0, 4, 4, 1, 1, 3, 0, 0, 0, 0, 1, 1, 1, 0, 3, 3, 2, 0, 3, 3, 2, 4, 3, 2, 3, 3, 0, 1, 1, 1, 0, 2, 3, 3, 1, 4, 2, 0, 2, 1, 2, 1, 0, 3, 0, 2, 2, 2, 0, 0, 3, 3, 1, 0, 2, 2, 3, 1, 1, 0, 1, 0, 4, 1, 0, 4, 3, 2, 2, 1, 3, 2, 2, 0, 3, 1, 1, 1, 1, 0, 4, 3, 2, 0, 3, 0, 3, 3, 1, 0, 0, 4, 4, 4, 2, 0, 0, 1, 3, 0, 3, 0, 1, 0, 3, 3, 0, 0, 2, 3, 3, 2, 0, 0, 1, 1, 4, 3, 1, 4, 1, 0, 2, 0, 0, 4, 1, 4, 0, 1, 4, 0, 3, 4, 2, 3, 3, 4, 3, 4, 1, 0, 2, 3, 1, 4, 0, 1, 2, 3, 0, 2, 3, 2, 1, 1, 4, 0, 3, 1, 0, 3, 4, 1, 2, 0, 3, 1, 0, 1, 2, 2, 0]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 177, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 319usize; s.lookahead = 133usize; s.prev_length = 4u32; s.good_match = 16u32; s.nice_match = 200i32; s.max_chain_length = 1u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 266usize);
        assert_eq!(r, 4u32, "lm ret 0");
        assert_eq!(s.match_start, 0usize, "lm match_start 0");
    }
    #[test]
    fn test_lm_1() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![1, 1, 1, 0, 2, 1, 1, 1, 1, 2, 1, 2, 0, 1, 0, 2, 1, 1, 1, 1, 0, 2, 2, 0, 1, 1, 2, 0, 1, 0, 0, 2, 1, 1, 2, 1, 0, 1, 1, 2, 1, 0, 2, 0, 1, 2, 0, 0, 1, 1, 0, 1, 0, 0, 0, 2, 2, 1, 2, 0, 1, 0, 2, 0, 2, 2, 2, 0, 2, 2, 2, 2, 2, 2, 1, 0, 0, 2, 2, 2, 2, 0, 0, 0, 0, 1, 2, 2, 2, 2, 0, 2, 0, 0, 2, 0, 1, 2, 0, 2, 2, 1, 0, 1, 1, 2, 1, 0, 2, 2, 2, 0, 2, 2, 1, 2, 1, 0, 1, 0, 2, 1, 1, 1, 2, 0, 2, 1, 1, 0, 2, 2, 0, 2, 0, 0, 0, 2, 2, 2, 0, 0, 1, 1, 1, 0, 2, 0, 1, 1, 2, 1, 0, 0, 0, 2, 0, 1, 0, 1, 0, 0, 0, 2, 0, 0, 1, 2, 0, 2, 1, 1, 0, 1, 2, 1, 2, 1, 1, 0, 0, 2, 2, 2, 2, 1, 1, 1, 1, 0, 2, 2, 0, 2, 0, 2, 0, 2, 0, 1, 2, 1, 1, 1, 1, 0, 1, 0, 1, 0, 0, 0, 2, 2, 2, 1, 2, 0, 0, 2, 0, 2, 1, 1, 0, 2, 1, 2, 2, 1, 0, 1, 1, 2, 0, 0, 2, 1, 2, 2, 1, 2, 0, 1, 2, 1, 1, 2, 2, 0, 2, 0, 2, 0, 0, 1, 1, 2, 0, 0, 1, 0, 2, 0, 0, 1, 2, 2, 0, 2, 2, 1, 0, 2, 1, 2, 2, 1, 0, 1, 0, 1, 0, 2, 2, 1, 1, 1, 2, 2, 1, 0, 2, 2, 1, 0, 1, 2, 1, 0, 0, 2, 0, 1, 2, 0, 1, 1, 1, 1, 1, 0, 1, 2, 1, 0, 2, 0, 0, 2, 0, 2, 0, 1, 0, 1, 1, 0, 1, 0, 2, 1, 1, 2, 2, 2, 2, 2, 1, 0, 2, 1, 2, 0, 1, 0, 1, 1, 0, 0, 2, 0, 2, 1, 0, 0, 1, 2, 0, 0, 2, 1, 2, 0, 1, 1, 2, 1, 0, 0, 2, 1, 2, 2, 0, 1, 1, 2, 0, 2, 0, 0, 1, 0, 0, 2, 2, 0, 1, 0, 1, 1, 0, 0, 2, 2, 1, 2, 1, 0, 1, 1, 0, 2, 0, 0, 1, 2, 2, 2, 0, 0, 1, 1, 2, 1, 0, 2, 1, 1, 0, 1, 1, 1, 1, 2, 0, 2, 1, 1, 1, 0, 1, 1, 2, 2, 0, 0, 2, 2, 0, 0, 2, 0, 2, 0, 2, 0, 1, 0, 2, 2, 0, 1, 1, 2, 2, 1, 0, 1, 2, 0, 0, 1, 1, 1, 0, 1, 0, 2, 2, 2, 2, 1, 0, 2, 0, 2, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0, 0, 0, 2, 0, 0, 0, 1, 1, 2, 1, 0, 1, 2, 0, 0, 0, 1, 1, 1, 2, 0, 1, 2, 0, 1, 1, 1, 2, 0, 1, 1, 1, 2, 2, 2, 1, 2, 1, 2, 0, 1, 2, 2, 1, 2, 0, 1, 1, 0, 1, 1, 2, 0, 2, 1, 0, 1, 1, 0, 0, 1, 0, 1, 1, 2, 1, 2, 1, 1, 2, 0, 0, 2, 0, 2, 0, 2, 1, 1, 1, 0, 2, 0, 0, 1, 1, 1, 2, 2, 1, 0, 2, 0, 2, 0, 2, 2, 2, 0, 2, 0, 2, 0, 2, 1, 0, 2, 0, 2, 2, 1, 2, 1, 2, 1, 2, 0, 1, 2, 2, 2, 2, 1, 2, 1, 2, 2, 1, 0, 0, 0, 1, 1, 1, 2, 0, 2, 1, 1, 0, 2, 0, 2, 1, 1, 0, 2, 1, 1, 1, 2, 0, 2, 0, 2, 1, 0, 2, 1, 2, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 2, 1, 2, 2, 2, 0, 0, 1, 0, 2, 2, 1]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 80, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 81, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 113, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 314usize; s.lookahead = 96usize; s.prev_length = 6u32; s.good_match = 28u32; s.nice_match = 31i32; s.max_chain_length = 15u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 139usize);
        assert_eq!(r, 6u32, "lm ret 1");
        assert_eq!(s.match_start, 0usize, "lm match_start 1");
    }
    #[test]
    fn test_lm_2() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![1, 1, 0, 0, 2, 0, 0, 2, 0, 0, 1, 2, 2, 2, 2, 0, 2, 2, 0, 1, 0, 2, 2, 2, 2, 0, 2, 1, 1, 0, 0, 0, 2, 1, 1, 1, 1, 1, 2, 1, 2, 0, 1, 1, 2, 0, 1, 0, 0, 0, 1, 0, 2, 1, 1, 1, 2, 1, 2, 0, 2, 0, 2, 2, 0, 2, 0, 1, 2, 0, 0, 1, 0, 2, 1, 2, 0, 2, 1, 1, 0, 0, 2, 1, 1, 2, 1, 1, 2, 0, 2, 1, 0, 1, 0, 1, 2, 1, 1, 0, 2, 0, 0, 2, 0, 0, 1, 0, 2, 1, 2, 1, 0, 1, 2, 2, 0, 1, 1, 1, 0, 0, 1, 2, 0, 2, 0, 1, 1, 1, 2, 0, 0, 2, 2, 2, 0, 1, 0, 2, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 2, 2, 1, 0, 0, 1, 0, 2, 0, 0, 2, 2, 0, 0, 2, 1, 0, 1, 0, 2, 2, 2, 1, 1, 0, 2, 2, 2, 2, 0, 2, 2, 2, 0, 1, 0, 0, 1, 2, 2, 0, 0, 2, 2, 0, 1, 1, 2, 2, 0, 0, 0, 0, 2, 1, 1, 2, 2, 1, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 2, 1, 2, 2, 1, 0, 2, 2, 2, 2, 1, 1, 1, 0, 2, 0, 2, 2, 0, 1, 0, 1, 0, 2, 1, 0, 1, 2, 1, 1, 0, 0, 1, 0, 1, 2, 2, 1, 2, 2, 0, 2, 1, 0, 2, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 0, 1, 2, 2, 0, 0, 2, 1, 2, 2, 0, 1, 0, 2, 1, 0, 1, 1, 0, 1, 1, 2, 2, 1, 2, 0, 1, 1, 1, 0, 0, 1, 0, 2, 0, 0, 1, 1, 0, 2, 2, 1, 2, 1, 0, 0, 0, 1, 2, 2, 1, 0, 2, 2, 1, 1, 1, 1, 0, 1, 1, 0, 2, 2, 1, 0, 2, 0, 2, 1, 2, 2, 2, 1, 1, 0, 1, 0, 0, 2, 2, 2, 2, 2, 1, 0, 0, 2, 0, 2, 1, 0, 1, 0, 1, 2, 2, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 2, 2, 1, 1, 2, 2, 0, 2, 0, 0, 0, 1, 1, 2, 1, 2, 1, 0, 0, 2, 2, 1, 0, 1, 2, 0, 0, 2, 0, 0, 0, 0, 1, 2, 1, 2, 2, 1, 2, 2, 0, 0, 2, 2, 0, 2, 0, 0, 1, 0, 0, 0, 0, 2, 1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 2, 0, 1, 0, 0, 2, 2, 1, 1, 1, 2, 2, 0, 0, 1, 2, 0, 1, 1, 0, 1, 0, 2, 0, 0, 0, 2, 2, 0, 2, 2, 2, 1, 1, 0, 2, 2, 0, 1, 2, 1, 1, 1, 0, 2, 0, 2, 2, 2, 1, 1, 2, 0, 1, 2, 0, 2, 2, 1, 1, 2, 0, 0, 2, 0, 0, 2, 1, 2, 0, 2, 0, 0, 0, 2, 0, 1, 1, 0, 2, 0, 0, 2, 2, 1, 0, 2, 0, 2, 0, 2, 2, 2, 2, 0, 1, 1, 2, 2, 0, 2, 2, 1, 1, 0, 0, 0, 0, 2, 0, 0, 1, 1, 2, 0, 0, 1, 2, 0, 2, 0, 1, 2, 0, 1, 1, 0, 0, 0, 0, 1, 0, 0, 2, 2, 0, 1, 0, 0, 1, 2, 1]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 41, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 85, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 286usize; s.lookahead = 49usize; s.prev_length = 4u32; s.good_match = 4u32; s.nice_match = 180i32; s.max_chain_length = 42u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 150usize);
        assert_eq!(r, 4u32, "lm ret 2");
        assert_eq!(s.match_start, 0usize, "lm match_start 2");
    }
    #[test]
    fn test_lm_3() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![2, 1, 1, 1, 2, 2, 1, 2, 2, 0, 2, 1, 0, 1, 0, 0, 0, 1, 0, 0, 2, 2, 0, 2, 2, 2, 2, 2, 2, 2, 0, 1, 0, 1, 1, 1, 0, 2, 2, 0, 2, 0, 2, 1, 0, 1, 2, 1, 1, 0, 1, 1, 1, 1, 2, 0, 1, 0, 0, 2, 2, 0, 2, 2, 0, 1, 2, 1, 2, 2, 0, 2, 0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 1, 0, 2, 1, 0, 1, 2, 2, 0, 0, 2, 1, 2, 0, 1, 2, 2, 0, 1, 1, 2, 1, 0, 1, 1, 2, 1, 0, 0, 0, 2, 0, 2, 1, 2, 0, 2, 2, 1, 1, 1, 0, 1, 2, 0, 2, 0, 2, 1, 2, 0, 0, 2, 1, 1, 0, 1, 1, 2, 1, 1, 2, 2, 1, 2, 2, 1, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 2, 1, 2, 2, 1, 0, 1, 2, 0, 0, 1, 0, 0, 2, 1, 1, 1, 1, 0, 2, 2, 2, 2, 2, 0, 0, 2, 2, 2, 1, 0, 0, 2, 1, 0, 1, 0, 1, 1, 0, 2, 2, 1, 2, 0, 2, 2, 2, 1, 2, 2, 0, 1, 2, 2, 0, 1, 1, 1, 1, 2, 0, 1, 0, 1, 1, 1, 2, 0, 1, 1, 0, 0, 2, 0, 0, 2, 1, 1, 2, 1, 2, 2, 0, 1, 0, 0, 0, 0, 1, 2, 0, 1, 0, 1, 0, 1, 1, 0, 0, 2, 2, 0, 1, 1, 2, 1, 0, 0, 1, 1, 2, 1, 1, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 2, 2, 2, 1, 2, 1, 1, 0, 0, 1, 1, 1, 2, 0, 0, 1, 1, 1, 0, 0, 0, 1, 2, 1, 2, 1, 0, 0, 0, 1, 1, 0, 2, 0, 2, 2, 1, 1, 0, 1, 0, 0, 1, 0, 2, 1, 1, 1, 2, 0, 2, 1, 1, 2, 0, 0, 0, 1, 2, 2, 1, 0, 1, 2, 2, 2, 1, 0, 1, 0, 0, 1, 1, 2, 2, 1, 2, 2, 2, 1, 0, 0, 2, 1, 1, 0, 1, 1, 0, 0, 0, 1, 2, 2, 2, 0, 1, 1, 1, 2, 0, 2, 1, 1, 2, 0, 1, 2, 2, 0, 2, 1, 2, 0, 1, 0, 2, 0, 1, 1, 2, 1, 2, 1, 0, 2, 2, 1, 0, 2, 1, 1, 0, 1, 0, 1, 2, 2, 2, 0, 0, 0, 1, 0, 1, 0, 2, 1, 0, 2, 0, 2, 1, 0, 0, 1, 2, 1, 1, 1, 2, 1, 0, 2, 0, 0, 2, 2, 1, 0, 2, 0, 2, 2, 2, 0, 2, 0, 2, 0, 1, 1, 1, 1, 0, 1, 2, 0, 1, 2, 2, 2, 0, 1, 0, 1, 2, 1, 1, 0, 2, 2, 2, 2, 1, 0, 2, 0, 1, 1, 0, 2, 0, 0, 0, 0, 0, 2, 2, 1, 1, 0, 0, 2, 2, 0, 1, 2, 2, 1, 2, 2, 0, 2, 1, 0, 0, 2, 1, 1, 1, 0, 0, 1, 1, 0, 0, 2, 1, 0, 2, 2, 1, 0, 2, 0, 0, 1, 2, 0, 0, 0, 1, 1, 2, 1, 0, 0, 2, 0, 0, 1, 1, 0, 1, 0, 2, 0, 1, 1, 2, 0, 1, 2, 0, 1, 2, 0, 1, 0, 1, 0, 0, 2, 2, 2, 2, 0, 2, 0, 1, 1, 1, 1, 0, 1, 2, 1, 2, 2, 0, 1, 1, 2, 2, 2, 1, 1, 0, 2, 2, 0, 1, 2, 2, 0, 0, 2, 2, 1, 0, 1, 2, 1, 1, 0, 1, 1, 0, 0, 2, 1, 1, 1, 2, 2, 0, 1, 2, 2, 1, 2, 2, 2, 1, 2, 0, 2, 2, 0, 0, 0, 2, 0, 1, 1, 0, 1, 2, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 2, 0, 1, 1, 1, 1, 1, 0, 1, 0, 0, 2, 2, 0, 1, 1, 2, 0, 2, 2, 0, 2, 0, 0, 1, 2, 2, 1, 0, 1, 0, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 2, 2, 2, 2, 2, 1, 2, 2, 0, 2, 1, 1, 1, 0, 1, 1, 0, 2, 1, 2, 2, 1, 1, 2, 1, 0, 1, 0, 2, 1, 2, 0, 2, 1, 2, 2, 1, 0, 0, 1, 1, 0, 0, 1, 0, 1, 0]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 65, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 74, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 310usize; s.lookahead = 186usize; s.prev_length = 6u32; s.good_match = 18u32; s.nice_match = 116i32; s.max_chain_length = 49u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 221usize);
        assert_eq!(r, 6u32, "lm ret 3");
        assert_eq!(s.match_start, 0usize, "lm match_start 3");
    }
    #[test]
    fn test_lm_4() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![3, 3, 0, 3, 5, 1, 4, 1, 4, 4, 2, 3, 4, 2, 3, 0, 3, 4, 4, 0, 3, 2, 0, 0, 1, 0, 3, 4, 3, 2, 5, 3, 4, 2, 1, 4, 5, 1, 0, 5, 3, 3, 1, 1, 3, 0, 3, 4, 0, 4, 1, 2, 1, 2, 0, 4, 0, 1, 1, 2, 2, 3, 1, 3, 0, 1, 4, 2, 4, 1, 4, 5, 0, 1, 2, 2, 0, 5, 0, 1, 0, 1, 2, 2, 1, 0, 1, 0, 2, 1, 3, 1, 0, 3, 2, 5, 5, 3, 2, 2, 5, 1, 1, 3, 3, 3, 5, 0, 3, 0, 5, 2, 5, 5, 2, 4, 2, 2, 3, 0, 2, 4, 2, 0, 1, 5, 5, 3, 2, 3, 5, 5, 4, 3, 5, 2, 1, 0, 3, 1, 2, 2, 3, 5, 3, 5, 4, 2, 1, 3, 0, 3, 3, 0, 2, 4, 4, 5, 1, 0, 5, 4, 2, 4, 2, 0, 5, 4, 4, 1, 1, 4, 5, 0, 2, 3, 2, 5, 4, 4, 5, 1, 2, 2, 3, 0, 2, 3, 4, 5, 0, 2, 3, 5, 1, 1, 4, 1, 0, 3, 4, 5, 4, 0, 3, 3, 4, 2, 4, 4, 0, 3, 0, 0, 1, 3, 4, 5, 1, 3, 2, 4, 5, 2, 1, 3, 0, 2, 1, 5, 3, 1, 4, 3, 5, 1, 1, 3, 0, 0, 5, 5, 4, 0, 5, 0, 3, 4, 2, 3, 3, 1, 0, 5, 3, 4, 0, 2, 1, 3, 3, 1, 0, 2, 2, 0, 5, 3, 1, 2, 4, 5, 1, 1, 4, 5, 3, 5, 3, 2, 0, 1, 0, 5, 5, 0, 0, 0, 3, 5, 2, 4, 3, 0, 2, 5, 4, 2, 5, 0, 2, 4, 2, 2, 2, 5, 4, 3, 1, 5, 4, 5, 0, 3, 2, 1, 3, 5, 3, 3, 0, 5, 5, 4, 5, 2, 5, 5, 3, 3, 0, 1, 3, 3, 4, 2, 4, 3, 3, 5, 1, 0, 2, 0, 4, 5, 2, 3, 2, 4, 3, 1, 0, 1, 4, 4, 1, 4, 4, 1, 1, 4, 2, 5, 0, 1, 2, 1, 5, 2, 4, 3, 1, 2, 3, 2, 2, 3, 3, 0, 2, 1, 4, 5, 4, 0, 0, 0, 5, 4, 5, 1, 2, 1, 4, 3, 2, 1, 1, 5, 3, 4, 0, 5, 4, 1, 1, 2, 2, 2, 3, 4, 1, 0, 1, 4, 5, 4, 1, 5, 2, 4, 5, 3, 3, 1, 4, 1, 0, 5, 0, 3, 0, 0, 3, 1, 5, 0, 4, 2, 3, 2, 0, 2, 4, 3, 2, 1, 4, 0, 5, 2, 2, 3, 1, 0, 1, 1, 3, 2, 2, 0, 1, 4, 4, 4, 0, 1, 3, 4, 5, 1, 4, 0, 5, 5, 1, 4, 5, 3, 1, 4, 2, 5, 3, 4, 1, 4, 0, 0, 4, 0, 3, 5, 1, 4, 4, 1, 0, 5, 1, 5, 2, 5, 4, 1, 5, 5, 3, 5, 1, 1, 4, 5, 2, 4, 5, 0, 4, 5, 5, 4, 0, 1, 2, 1, 5, 1, 5, 4, 4, 3, 5, 2, 4, 1, 4, 3, 0, 5, 3, 1, 4, 3, 1, 2, 0, 0, 1, 0, 5, 2, 3, 2, 1, 3, 5, 5, 5, 0, 3, 4, 2, 0, 0, 0, 3, 0, 2, 0, 2, 5, 3, 4, 1, 5, 3, 3, 1, 3, 1, 1, 3, 3, 5, 4, 5, 5, 2, 3, 4, 4, 2, 0, 1, 1, 5, 2, 0, 1, 2, 3, 1, 1, 3, 1, 3, 4, 1, 4, 5, 2, 4, 0, 4, 4, 5, 4, 1, 2, 5, 5, 1, 5, 5, 2, 3, 1, 1, 4, 2, 1, 2, 4, 5, 1, 0, 2, 1, 0, 2, 2, 4, 3, 0, 4, 0, 1]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 78, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 319usize; s.lookahead = 69usize; s.prev_length = 5u32; s.good_match = 32u32; s.nice_match = 73i32; s.max_chain_length = 64u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 239usize);
        assert_eq!(r, 5u32, "lm ret 4");
        assert_eq!(s.match_start, 0usize, "lm match_start 4");
    }
    #[test]
    fn test_lm_5() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![3, 0, 0, 3, 0, 0, 1, 3, 0, 0, 2, 1, 2, 0, 0, 2, 2, 1, 0, 1, 3, 0, 3, 1, 0, 1, 0, 1, 3, 0, 2, 3, 3, 3, 1, 0, 2, 2, 2, 3, 3, 3, 3, 0, 0, 0, 2, 3, 3, 0, 1, 2, 1, 2, 2, 1, 3, 1, 0, 0, 3, 0, 2, 0, 0, 2, 2, 3, 3, 1, 2, 1, 0, 3, 2, 2, 1, 2, 0, 1, 2, 2, 0, 2, 1, 2, 2, 1, 2, 3, 2, 3, 1, 3, 3, 3, 3, 0, 0, 3, 1, 2, 2, 3, 3, 0, 3, 1, 3, 2, 0, 0, 0, 3, 2, 0, 3, 1, 0, 0, 3, 3, 1, 3, 3, 0, 3, 1, 3, 0, 2, 2, 2, 1, 0, 0, 1, 3, 3, 1, 2, 3, 0, 0, 2, 3, 3, 2, 1, 3, 1, 1, 0, 3, 2, 0, 1, 3, 2, 0, 3, 2, 3, 2, 1, 0, 3, 1, 1, 2, 1, 2, 3, 2, 1, 0, 1, 2, 2, 2, 3, 2, 3, 2, 2, 3, 0, 3, 2, 0, 3, 1, 2, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 2, 3, 1, 1, 2, 2, 0, 3, 1, 1, 2, 3, 3, 0, 1, 3, 1, 0, 2, 2, 2, 3, 1, 0, 0, 1, 0, 1, 0, 3, 0, 3, 3, 2, 2, 1, 3, 3, 0, 3, 2, 1, 3, 2, 0, 1, 3, 1, 0, 2, 2, 2, 2, 0, 0, 2, 1, 3, 2, 1, 0, 1, 2, 0, 2, 2, 3, 1, 3, 1, 0, 0, 3, 1, 3, 2, 3, 3, 2, 3, 3, 1, 2, 2, 1, 3, 0, 3, 2, 3, 0, 2, 1, 3, 3, 1, 0, 1, 1, 3, 1, 1, 3, 2, 1, 3, 1, 3, 2, 3, 3, 3, 3, 3, 0, 0, 0, 0, 0, 3, 1, 1, 0, 2, 3, 1, 2, 2, 2, 2, 1, 2, 0, 2, 3, 3, 0, 2, 1, 0, 2, 3, 3, 0, 2, 0, 0, 2, 1, 1, 0, 2, 1, 2, 0, 0, 3, 1, 2, 1, 3, 1, 1, 1, 1, 2, 0, 1, 2, 3, 0, 0, 0, 3, 0, 0, 2, 1, 3, 1, 0, 2, 2, 1, 0, 1, 1, 0, 0, 1, 0, 0, 2, 1, 0, 0, 0, 2, 1, 3, 0, 1, 1, 2, 3, 3, 2, 3, 3, 3, 0, 1, 0, 3, 2, 2, 0, 1, 3, 0, 3, 2, 1, 1, 0, 3, 2, 3, 1, 1, 3, 2, 1, 0, 2, 1, 2, 0, 3, 2, 0, 2, 1, 0, 0, 3, 0, 3, 0, 3, 1, 3, 2, 2, 0, 2, 1, 0, 1, 0, 2, 3, 3, 1, 1, 1, 2, 2, 0, 2, 1, 0, 3, 2, 3, 0, 1, 1, 1, 1, 3, 2, 3, 2, 0, 2, 3, 3, 2, 1, 2, 2, 1, 3, 2, 1, 1, 1, 3, 2, 0, 2, 3, 0, 2, 2, 0, 0, 0, 0, 2, 3, 2, 2, 1, 2, 1, 3, 1, 3, 3, 2, 2, 1, 1, 0, 1, 3, 0, 0, 2, 2, 3, 0, 2, 1, 1, 2, 2, 0, 0, 0, 3, 2, 2, 1, 2, 0, 1, 0, 1, 3, 2, 0, 1, 3, 2, 2, 2, 0, 3, 3, 0, 3, 3, 1, 2, 3, 2, 3, 2, 3, 2, 3, 1, 1, 2, 1, 1, 2, 3, 3, 3, 2, 3, 1, 2, 1, 2, 2, 0, 1, 2, 1, 0, 3, 2, 2, 2, 2, 1, 0, 0, 3, 2, 0, 3, 1, 2, 2, 3, 1, 2, 1, 2, 3, 1, 3, 2, 3, 0, 2, 3, 2, 0, 0, 0, 3, 3, 0, 0, 1, 2, 0, 0, 1, 1, 2, 1, 3, 1, 1, 1, 3, 2, 1, 1, 3, 2, 2, 0, 1, 2, 0, 2, 0, 0, 2, 3, 3, 3, 2, 1, 3, 1, 1, 2, 0, 2, 0, 1, 0, 3, 1, 2, 0, 1, 0, 2, 2, 2, 0, 0, 1, 1, 0, 3, 0, 2, 2, 3, 2, 1, 1, 2, 0, 3, 1, 0, 0, 1, 3, 2, 2, 0, 2, 0, 2, 1, 0, 1, 0, 1, 0, 3, 1, 3, 2, 1, 0, 1, 0, 3, 1, 2, 0, 0, 2, 1, 2, 2, 3, 1, 1, 2, 2, 1, 1, 3, 2, 3, 3, 1, 3, 3, 3, 2, 1, 3, 0, 2, 2, 2, 3, 0, 3, 0, 0, 2, 2, 0, 0, 0, 1, 2, 3, 1, 2, 0, 2, 0, 2, 3, 3, 1, 0, 1, 3, 1, 0, 2, 0, 2, 3, 3, 1, 3, 2, 0, 3, 2, 3, 0, 0, 2, 0, 1, 2]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 43, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 66, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 91, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 117, 0, 0, 0, 0, 0, 0, 140, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 147, 0, 0, 0, 0, 0, 0, 0, 0, 0, 182, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 286usize; s.lookahead = 255usize; s.prev_length = 2u32; s.good_match = 16u32; s.nice_match = 106i32; s.max_chain_length = 39u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 192usize);
        assert_eq!(r, 3u32, "lm ret 5");
        assert_eq!(s.match_start, 147usize, "lm match_start 5");
    }
    #[test]
    fn test_lm_6() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![0, 2, 1, 0, 0, 0, 0, 1, 2, 0, 1, 2, 2, 0, 2, 0, 1, 0, 0, 0, 0, 2, 2, 0, 1, 2, 2, 1, 2, 0, 1, 1, 2, 2, 2, 2, 1, 0, 1, 2, 1, 1, 0, 2, 0, 1, 1, 0, 0, 2, 0, 2, 0, 0, 2, 1, 0, 2, 0, 1, 1, 2, 1, 0, 1, 0, 0, 2, 1, 0, 1, 0, 2, 2, 0, 0, 2, 0, 1, 1, 2, 2, 0, 2, 1, 0, 0, 1, 1, 1, 2, 0, 0, 0, 0, 0, 2, 1, 0, 0, 2, 1, 0, 0, 0, 2, 1, 2, 2, 0, 0, 1, 1, 1, 0, 2, 1, 1, 1, 1, 0, 0, 2, 1, 2, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 2, 0, 0, 2, 0, 2, 2, 2, 0, 1, 0, 2, 2, 2, 2, 1, 1, 2, 0, 2, 2, 2, 0, 0, 1, 2, 1, 2, 0, 1, 1, 2, 1, 0, 2, 2, 1, 0, 1, 1, 0, 1, 1, 2, 2, 1, 0, 0, 0, 2, 1, 1, 0, 0, 2, 1, 2, 1, 1, 1, 2, 2, 2, 1, 1, 2, 1, 1, 1, 1, 0, 0, 1, 2, 1, 0, 0, 0, 1, 2, 2, 0, 0, 1, 0, 2, 0, 1, 1, 1, 1, 1, 0, 2, 2, 1, 1, 2, 2, 0, 0, 2, 2, 1, 0, 2, 1, 1, 2, 1, 2, 0, 0, 1, 0, 1, 2, 0, 2, 1, 1, 0, 0, 2, 0, 2, 0, 2, 0, 0, 2, 1, 0, 0, 0, 0, 1, 2, 2, 0, 2, 2, 2, 1, 2, 1, 0, 2, 0, 0, 0, 0, 2, 2, 1, 1, 1, 2, 1, 2, 1, 0, 2, 0, 0, 1, 2, 0, 2, 1, 2, 2, 2, 1, 0, 0, 1, 2, 2, 1, 2, 0, 2, 2, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 2, 1, 2, 2, 2, 1, 2, 0, 1, 0, 1, 1, 0, 2, 1, 0, 2, 0, 1, 2, 1, 0, 2, 1, 0, 2, 1, 1, 2, 2, 2, 0, 1, 1, 2, 2, 2, 2, 1, 0, 0, 0, 2, 2, 2, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0, 2, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 1, 2, 0, 2, 1, 1, 0, 0, 1, 1, 0, 1, 2, 0, 2, 1, 0, 1, 2, 0, 2, 1, 0, 0, 0, 1, 0, 1, 2, 0, 0, 0, 1, 2, 0, 0, 1, 2, 0, 0, 1, 0, 0, 1, 1, 0, 0, 2, 1, 1, 2, 1, 0, 2, 1, 2, 1, 0, 1, 2, 0, 1, 1, 0, 1, 2, 0, 0, 0, 2, 1, 2, 1, 0, 0, 0, 1, 2, 0, 0, 1, 0, 0, 2, 1, 1, 0, 2, 2, 1, 0, 2, 1, 1, 1, 0, 2, 1, 0, 2, 1, 1, 2, 2, 0, 2, 1, 0, 1, 2, 2, 0, 2, 1, 1, 2, 0, 1, 0, 2, 1, 0, 2, 2, 2, 1, 0, 2, 2, 2, 0, 1, 2, 1, 1, 0, 0, 0, 2, 0, 0, 2, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 2, 2, 0, 1, 0, 2, 1, 1, 0, 0, 0, 0, 2, 2, 2, 0, 1, 2, 1, 0, 2, 1, 1, 2, 2, 1, 2, 0, 1, 2, 0, 1, 2, 0, 0, 2, 2, 0, 0, 1, 2, 2, 2, 2, 0, 2, 1, 0, 1, 1, 2, 0, 2, 2, 1, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 0, 2, 0, 2, 0, 0, 1, 1, 1, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 2, 1, 1, 0, 2, 0, 2, 2, 1, 0, 1, 2, 2, 1, 1, 0]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 298usize; s.lookahead = 101usize; s.prev_length = 3u32; s.good_match = 26u32; s.nice_match = 206i32; s.max_chain_length = 32u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 286usize);
        assert_eq!(r, 3u32, "lm ret 6");
        assert_eq!(s.match_start, 0usize, "lm match_start 6");
    }
    #[test]
    fn test_lm_7() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![1, 0, 0, 2, 2, 1, 1, 1, 2, 1, 0, 1, 1, 2, 2, 0, 2, 1, 1, 1, 0, 0, 1, 1, 0, 1, 2, 2, 1, 0, 0, 2, 2, 0, 0, 1, 1, 0, 1, 1, 1, 0, 1, 2, 1, 0, 1, 2, 2, 0, 0, 0, 2, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1, 0, 0, 2, 0, 2, 0, 1, 0, 2, 2, 0, 0, 0, 0, 0, 1, 1, 1, 0, 2, 1, 1, 2, 2, 2, 0, 2, 2, 1, 2, 1, 1, 0, 0, 1, 2, 0, 2, 2, 1, 2, 2, 2, 1, 0, 2, 2, 1, 1, 0, 0, 2, 1, 2, 2, 2, 2, 2, 1, 1, 1, 1, 0, 0, 1, 2, 2, 2, 1, 1, 1, 2, 0, 2, 2, 1, 1, 2, 0, 1, 2, 1, 1, 2, 2, 2, 0, 1, 0, 2, 2, 1, 2, 2, 1, 0, 0, 2, 1, 1, 1, 0, 0, 2, 0, 2, 0, 2, 1, 0, 0, 2, 2, 1, 0, 1, 1, 0, 2, 2, 0, 0, 0, 0, 0, 0, 2, 1, 0, 2, 1, 2, 2, 0, 2, 0, 1, 0, 2, 0, 1, 2, 0, 1, 0, 1, 2, 2, 2, 2, 0, 2, 1, 2, 0, 1, 2, 1, 2, 1, 1, 0, 2, 2, 0, 0, 2, 0, 1, 0, 1, 2, 2, 2, 0, 0, 0, 2, 2, 1, 2, 1, 2, 2, 0, 1, 0, 0, 2, 2, 1, 0, 0, 2, 0, 1, 1, 1, 1, 1, 1, 2, 1, 0, 1, 2, 0, 1, 0, 0, 2, 1, 1, 2, 2, 2, 2, 0, 1, 1, 1, 0, 2, 2, 2, 1, 1, 1, 2, 1, 2, 1, 0, 1, 0, 1, 1, 1, 2, 0, 1, 0, 1, 1, 2, 1, 0, 1, 1, 0, 1, 1, 0, 1, 2, 1, 2, 0, 0, 0, 1, 1, 0, 2, 0, 0, 2, 0, 1, 1, 2, 0, 0, 2, 0, 2, 1, 0, 0, 2, 2, 2, 0, 1, 1, 1, 2, 1, 2, 0, 0, 1, 1, 1, 2, 0, 2, 1, 1, 1, 2, 1, 2, 0, 1, 1, 0, 1, 0, 1, 2, 0, 1, 1, 0, 2, 1, 1, 1, 1, 1, 2, 0, 0, 1, 1, 1, 0, 2, 0, 0, 1, 2, 2, 1, 0, 1, 1, 1, 1, 1, 2, 1, 0, 2, 1, 0, 1, 1, 2, 0, 1, 1, 0, 0, 0, 1, 2, 1, 1, 1, 2, 1, 2, 1, 2, 2, 0, 2, 1, 2, 2, 0, 2, 1, 1, 0, 1, 2, 1, 1, 2, 0, 1, 0, 0, 2, 0, 1, 0, 2, 1, 2, 2, 0, 2, 1, 0, 2, 1, 0, 0, 1, 2, 1, 1, 0, 0, 1, 1, 1, 0, 2, 0, 1, 2, 1, 2, 2, 2, 2, 0, 0, 2, 2, 1, 0, 2, 1, 0, 2, 1, 2, 0, 0, 2, 2, 1, 1, 2, 0, 0, 0, 1, 1, 0, 2, 0, 2, 1, 0, 2, 1, 0, 2, 1, 2, 1, 2, 0, 1, 1, 0, 2, 2, 1, 2, 2, 2, 0, 0, 1, 0, 1, 1, 1, 0, 0, 0, 2, 0, 1, 2, 0, 2, 0, 0, 2, 0, 2, 0, 1, 0, 2, 1, 0, 1, 2, 0, 1, 1, 2, 0, 2, 0, 2, 0, 1, 1, 1, 1, 1, 2, 0, 1, 0, 0, 2, 0, 1, 1, 2, 1, 2, 1, 2, 0, 2, 2, 0, 2, 2, 0, 0, 0, 1, 0, 2, 1, 2, 0, 2, 1, 2, 0, 1, 0, 2, 0, 1, 0, 1]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 67, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 71, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 122, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 143, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 175, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 211, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 305usize; s.lookahead = 50usize; s.prev_length = 5u32; s.good_match = 5u32; s.nice_match = 181i32; s.max_chain_length = 41u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 252usize);
        assert_eq!(r, 5u32, "lm ret 7");
        assert_eq!(s.match_start, 0usize, "lm match_start 7");
    }
    #[test]
    fn test_lm_8() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![3, 1, 0, 0, 2, 0, 2, 3, 0, 2, 3, 1, 2, 3, 3, 0, 3, 1, 0, 1, 0, 0, 1, 2, 1, 1, 0, 1, 0, 3, 3, 2, 0, 3, 3, 3, 0, 2, 0, 0, 0, 2, 0, 1, 0, 0, 2, 3, 1, 2, 2, 0, 3, 0, 3, 0, 2, 3, 1, 0, 0, 1, 3, 3, 2, 1, 3, 0, 3, 2, 1, 3, 0, 3, 0, 3, 0, 2, 3, 0, 3, 3, 1, 0, 1, 0, 0, 2, 2, 1, 0, 3, 3, 2, 1, 3, 1, 1, 0, 2, 0, 2, 2, 1, 3, 0, 3, 1, 2, 0, 3, 3, 0, 3, 0, 2, 3, 0, 3, 0, 0, 2, 3, 1, 2, 1, 1, 2, 0, 0, 2, 0, 2, 3, 0, 1, 1, 3, 0, 2, 3, 3, 3, 2, 2, 3, 2, 1, 3, 0, 2, 0, 0, 0, 2, 2, 1, 2, 1, 3, 0, 0, 2, 1, 3, 2, 0, 3, 2, 2, 2, 2, 0, 0, 3, 1, 1, 3, 3, 1, 2, 1, 1, 3, 1, 1, 2, 3, 2, 0, 1, 2, 1, 3, 0, 2, 0, 3, 2, 1, 0, 0, 1, 3, 0, 3, 0, 0, 3, 1, 0, 1, 0, 0, 0, 3, 0, 0, 3, 1, 1, 0, 3, 2, 1, 1, 1, 2, 0, 3, 1, 0, 3, 2, 2, 1, 0, 2, 2, 0, 1, 1, 1, 1, 2, 0, 0, 1, 3, 1, 3, 3, 2, 0, 1, 0, 1, 0, 2, 1, 1, 3, 2, 2, 0, 1, 2, 1, 3, 1, 3, 3, 0, 1, 2, 2, 0, 0, 3, 0, 3, 1, 2, 3, 3, 2, 0, 2, 2, 0, 0, 3, 3, 0, 0, 1, 1, 2, 0, 2, 1, 1, 0, 3, 2, 1, 2, 2, 3, 0, 0, 2, 0, 1, 0, 3, 2, 2, 0, 0, 1, 0, 0, 2, 0, 1, 2, 1, 0, 2, 0, 2, 0, 1, 1, 3, 1, 1, 3, 3, 0, 0, 0, 3, 2, 2, 1, 2, 0, 1, 1, 3, 1, 0, 0, 0, 0, 1, 1, 2, 1, 2, 0, 0, 1, 2, 3, 0, 2, 3, 1, 1, 3, 0, 2, 2, 3, 2, 3, 2, 2, 3, 3, 3, 3, 2, 3, 0, 3, 2, 2, 0, 3, 1, 1, 0, 0, 3, 1, 2, 1, 1, 2, 3, 2, 0, 0, 1, 3, 2, 0, 3, 3, 0, 0, 0, 0, 1, 0, 0, 1, 1, 3, 2, 2, 1, 0, 0, 3, 1, 0, 3, 0, 0, 3, 0, 2, 2, 3, 0, 0, 3, 1, 1, 2, 1, 3, 1, 1, 0, 0, 1, 1, 3, 3, 2, 3, 1, 3, 3, 2, 2, 1, 0, 1, 2, 0, 2, 2, 0, 1, 3, 3, 2, 3, 1, 1, 1, 3, 2, 1, 1, 0, 3, 2, 2, 3, 2, 3, 3, 2, 0, 3, 3, 0, 1, 3, 2, 1, 0, 3, 1, 3, 2, 0, 2, 0, 0, 3, 3, 2, 1, 1, 0, 3, 0, 0, 1, 2, 3, 0, 2, 2, 1, 2, 0, 1, 0, 3, 1, 3, 0, 0, 0, 1, 0, 0, 1, 0, 2, 1, 1, 0, 2, 0, 2, 2, 3, 0, 3, 0, 0, 1, 1, 3, 3, 3, 2, 1, 2, 2, 1, 2, 3, 1, 3, 3, 3, 1, 2, 0, 2, 1, 3, 2, 2, 0, 1, 1, 2, 0, 1, 0, 2, 1, 0, 0, 3, 0, 0, 2, 3, 3, 1, 0, 1, 2, 2, 3, 0, 3, 2, 3, 3, 3, 1, 0, 2, 2, 0, 3, 2, 2, 0, 1, 2, 3, 3, 0, 3, 0, 0, 2, 3, 1, 2, 2, 2, 2, 2, 0, 3, 3, 2, 0, 0]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 72, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 118, 0, 0, 135, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 138, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 295usize; s.lookahead = 81usize; s.prev_length = 3u32; s.good_match = 20u32; s.nice_match = 53i32; s.max_chain_length = 43u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 265usize);
        assert_eq!(r, 3u32, "lm ret 8");
        assert_eq!(s.match_start, 0usize, "lm match_start 8");
    }
    #[test]
    fn test_lm_9() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![4, 2, 4, 2, 1, 3, 0, 3, 3, 2, 3, 2, 1, 0, 4, 0, 1, 1, 0, 0, 0, 1, 3, 0, 4, 0, 2, 0, 1, 0, 0, 4, 4, 1, 2, 3, 1, 0, 1, 1, 2, 3, 1, 1, 2, 1, 2, 1, 2, 4, 4, 1, 2, 2, 0, 0, 3, 1, 3, 3, 1, 2, 3, 2, 4, 3, 4, 3, 0, 3, 3, 1, 2, 4, 1, 1, 1, 4, 4, 0, 2, 3, 1, 2, 0, 2, 4, 4, 1, 2, 1, 2, 4, 2, 1, 0, 0, 0, 3, 4, 2, 2, 0, 1, 0, 1, 2, 0, 1, 3, 3, 4, 2, 1, 0, 3, 1, 3, 2, 4, 2, 3, 0, 3, 1, 1, 3, 2, 2, 4, 1, 1, 0, 2, 4, 1, 4, 3, 1, 3, 0, 1, 3, 0, 2, 1, 1, 3, 4, 0, 1, 2, 4, 0, 3, 2, 2, 4, 3, 3, 0, 4, 1, 3, 3, 3, 1, 0, 4, 0, 3, 0, 4, 2, 1, 3, 0, 1, 3, 4, 1, 2, 2, 0, 0, 2, 0, 3, 0, 1, 1, 1, 2, 0, 2, 4, 3, 2, 2, 1, 0, 2, 0, 3, 3, 2, 1, 1, 2, 2, 4, 3, 4, 0, 3, 1, 1, 0, 2, 4, 3, 1, 0, 0, 2, 0, 2, 0, 1, 2, 1, 1, 3, 0, 1, 1, 0, 1, 4, 1, 0, 3, 1, 0, 2, 0, 3, 0, 1, 1, 0, 2, 1, 4, 0, 1, 3, 0, 3, 1, 1, 4, 0, 1, 0, 1, 0, 4, 1, 3, 4, 1, 0, 3, 2, 4, 4, 0, 2, 3, 2, 3, 3, 4, 4, 4, 2, 1, 0, 1, 2, 3, 2, 3, 2, 3, 3, 3, 3, 2, 1, 4, 4, 1, 0, 2, 0, 1, 1, 3, 1, 4, 2, 4, 4, 4, 4, 3, 3, 2, 1, 0, 2, 3, 2, 3, 2, 1, 4, 4, 4, 4, 3, 4, 0, 4, 4, 0, 3, 3, 4, 2, 2, 2, 2, 4, 1, 0, 1, 4, 3, 4, 0, 1, 3, 2, 0, 0, 0, 1, 1, 3, 1, 3, 0, 2, 3, 4, 0, 2, 0, 3, 1, 0, 0, 2, 3, 1, 0, 3, 0, 2, 1, 0, 4, 2, 3, 0, 0, 0, 0, 2, 3, 0, 4, 2, 0, 0, 1, 4, 4, 4, 1, 0, 3, 1, 0, 3, 3, 4, 3, 1, 3, 4, 3, 4, 4, 3, 2, 4, 1, 2, 3, 1, 2, 4, 3, 4, 4, 2, 0, 4, 0, 3, 1, 2, 0, 3, 1, 1, 4, 2, 4, 0, 3, 1, 2, 4, 1, 3, 4, 2, 1, 0, 2, 4, 1, 0, 2, 2, 1, 0, 4, 1, 0, 4, 0, 4, 1, 2, 3, 3, 4, 0, 2, 1, 4, 1, 3, 3, 2, 1, 2, 0, 2, 1, 4, 1, 4, 0, 3, 3, 0, 3, 2, 2, 2, 4, 2, 2, 4, 0, 0, 1, 0, 1, 0, 1, 3, 2, 0, 3, 3, 0, 1, 2, 4, 4, 1, 4, 2, 1, 3, 3, 3, 1, 2, 4, 4, 3, 0, 3, 1, 2, 3, 4, 4, 0, 2, 2, 0, 0, 1, 2, 1, 4, 0, 2, 3, 3, 3, 4, 3, 0, 2, 1, 2, 1, 1, 2, 2, 3, 4, 4, 2, 1, 0, 2, 0, 3, 4, 0, 1, 3, 1, 2]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 62, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 82, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 126, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 239, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 263, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 284, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 309usize; s.lookahead = 7usize; s.prev_length = 6u32; s.good_match = 31u32; s.nice_match = 84i32; s.max_chain_length = 56u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 297usize);
        assert_eq!(r, 6u32, "lm ret 9");
        assert_eq!(s.match_start, 0usize, "lm match_start 9");
    }
    #[test]
    fn test_lm_10() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![1, 1, 3, 2, 3, 3, 3, 3, 2, 2, 0, 0, 1, 0, 2, 3, 0, 1, 0, 2, 1, 2, 3, 0, 3, 2, 0, 1, 2, 0, 3, 2, 3, 3, 1, 2, 3, 2, 1, 3, 0, 3, 2, 2, 0, 3, 2, 0, 2, 1, 0, 2, 1, 0, 2, 0, 3, 3, 1, 1, 0, 0, 2, 1, 2, 0, 2, 2, 2, 1, 2, 0, 3, 0, 3, 2, 1, 0, 2, 2, 2, 2, 2, 3, 2, 1, 0, 2, 0, 3, 1, 2, 3, 3, 3, 3, 1, 0, 0, 3, 2, 1, 0, 2, 3, 3, 1, 3, 2, 0, 2, 1, 3, 1, 2, 1, 0, 2, 2, 0, 3, 1, 3, 1, 3, 2, 2, 3, 2, 2, 0, 1, 3, 0, 1, 2, 2, 1, 0, 3, 1, 3, 2, 2, 0, 3, 1, 1, 3, 2, 2, 3, 3, 0, 0, 0, 2, 0, 3, 3, 3, 0, 0, 0, 1, 1, 0, 1, 3, 3, 1, 0, 0, 0, 0, 3, 2, 0, 0, 2, 0, 1, 1, 1, 0, 1, 2, 2, 3, 2, 1, 0, 0, 2, 0, 0, 0, 1, 0, 3, 3, 1, 3, 1, 3, 1, 0, 1, 2, 2, 0, 1, 3, 1, 1, 2, 0, 0, 3, 0, 2, 1, 1, 1, 2, 2, 3, 3, 0, 1, 0, 2, 0, 1, 0, 0, 0, 0, 0, 1, 3, 2, 3, 3, 3, 2, 1, 2, 0, 2, 1, 0, 0, 2, 2, 1, 0, 0, 3, 2, 2, 0, 1, 1, 2, 2, 2, 2, 0, 1, 2, 0, 1, 2, 0, 1, 0, 2, 3, 2, 1, 1, 0, 1, 3, 2, 0, 3, 0, 0, 1, 1, 3, 0, 2, 3, 3, 1, 2, 3, 1, 0, 0, 0, 1, 2, 3, 0, 1, 0, 3, 1, 1, 0, 3, 0, 3, 3, 2, 3, 0, 3, 2, 3, 2, 2, 2, 3, 0, 3, 0, 2, 3, 1, 1, 2, 0, 1, 2, 0, 0, 3, 2, 1, 3, 2, 2, 2, 3, 3, 2, 3, 2, 0, 1, 0, 1, 2, 1, 3, 3, 0, 1, 1, 0, 0, 0, 2, 3, 2, 2, 1, 2, 0, 2, 3, 3, 0, 0, 1, 1, 2, 3, 1, 1, 0, 2, 0, 3, 2, 2, 2, 2, 3, 2, 0, 2, 0, 3, 1, 3, 3, 2, 3, 3, 3, 1, 2, 1, 3, 3, 2, 1, 0, 3, 3, 2, 1, 0, 2, 2, 1, 3, 3, 0, 1, 0, 3, 1, 2, 0, 0, 0, 0, 0, 1, 1, 3, 2, 3, 0, 1, 2, 0, 1, 3, 2, 0, 0, 0, 2, 3, 0, 1, 2, 0, 2, 1, 3, 3, 0, 2, 2, 3, 1, 1, 3, 1, 2, 3, 2, 0, 1, 0, 1, 2, 2, 1, 2, 0, 3, 0, 0, 3, 2, 3, 2, 0, 3, 2, 3, 3, 0, 1, 2, 1, 2, 3, 0, 3, 2, 3, 0, 1, 2, 3, 0, 2, 3, 1, 2, 1, 1, 2, 3, 2, 3, 0, 3, 1, 3, 0, 0, 1, 3, 2, 0, 3, 0, 0, 2, 1, 2, 0, 2, 2, 0, 0, 1, 0, 2, 1, 2, 0, 1, 0, 0, 3, 1, 2, 3, 1, 1, 0, 2, 0, 2, 1, 0, 0, 2, 3, 0, 1, 0, 1, 1, 1, 3, 1, 3, 1, 2, 1, 1, 3, 2, 0, 0, 3, 1, 3, 3, 3, 3, 1, 1, 3, 0, 2, 1, 3, 1, 2, 2, 2, 1, 1, 0, 2, 0, 2, 3, 0, 3, 0, 3, 2, 3, 2, 1, 1, 0, 0, 1, 2, 2, 0, 0, 1, 0, 3, 3, 2, 0, 3, 0, 0, 3, 2, 2, 1, 3, 0, 0, 3, 2, 2, 2, 0, 1, 1, 2, 1, 0, 2, 3, 1, 3, 2, 2, 0, 0, 3, 2, 0, 0, 1, 2, 0, 1, 0, 1, 1, 2, 2, 0, 3, 3, 0, 1, 0, 1, 3, 2, 3, 1, 0, 2, 1, 0, 0, 1, 2, 3, 0, 3, 0, 2, 1, 3, 3, 1, 3, 1, 2, 2, 0, 2, 0, 1, 1, 2, 0, 0, 3, 3, 2, 0, 3, 0, 0, 3, 2, 0, 2, 2, 2, 0, 3, 2, 2, 3, 1, 2, 0, 1, 0, 1, 0, 0, 3, 1, 1, 3, 2, 2, 1, 2, 2, 3, 2, 1, 0, 1, 2, 0, 1, 0, 2, 0, 1, 2, 0, 3, 3, 1, 1, 3, 0, 1, 2]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 62, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 82, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 110, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 155, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 231, 0, 0, 0, 245, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 281usize; s.lookahead = 221usize; s.prev_length = 6u32; s.good_match = 25u32; s.nice_match = 94i32; s.max_chain_length = 10u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 249usize);
        assert_eq!(r, 6u32, "lm ret 10");
        assert_eq!(s.match_start, 0usize, "lm match_start 10");
    }
    #[test]
    fn test_lm_11() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![1, 0, 4, 2, 2, 0, 4, 4, 2, 5, 2, 1, 4, 1, 1, 2, 5, 5, 5, 2, 1, 0, 4, 1, 0, 1, 2, 2, 1, 4, 3, 5, 0, 5, 4, 1, 2, 1, 4, 3, 5, 0, 4, 2, 4, 5, 0, 4, 2, 1, 0, 1, 5, 1, 1, 5, 4, 4, 3, 1, 5, 5, 4, 3, 5, 4, 2, 1, 2, 3, 5, 4, 2, 4, 1, 0, 3, 2, 3, 0, 2, 1, 0, 2, 5, 5, 2, 5, 0, 0, 2, 5, 0, 1, 2, 0, 3, 1, 3, 0, 2, 3, 4, 3, 5, 2, 5, 4, 0, 2, 2, 1, 0, 3, 0, 1, 0, 3, 4, 1, 1, 5, 2, 0, 0, 1, 1, 1, 4, 2, 0, 1, 4, 2, 5, 3, 4, 3, 1, 2, 5, 5, 2, 2, 1, 4, 5, 2, 2, 0, 3, 0, 5, 4, 3, 5, 0, 0, 3, 2, 0, 2, 4, 5, 3, 5, 4, 1, 2, 4, 4, 1, 1, 2, 0, 2, 0, 3, 5, 5, 3, 0, 0, 4, 5, 1, 5, 3, 4, 3, 0, 1, 2, 3, 0, 5, 0, 5, 1, 5, 0, 0, 2, 4, 4, 5, 2, 4, 5, 5, 2, 1, 0, 5, 0, 0, 2, 4, 1, 3, 3, 4, 5, 1, 1, 1, 4, 2, 3, 5, 5, 4, 2, 2, 5, 1, 2, 3, 5, 3, 4, 2, 5, 4, 2, 4, 0, 2, 3, 2, 2, 2, 4, 2, 2, 0, 5, 5, 5, 4, 3, 5, 0, 4, 3, 3, 2, 5, 5, 3, 5, 2, 1, 5, 0, 1, 4, 3, 5, 1, 5, 3, 0, 5, 3, 2, 2, 1, 3, 4, 4, 4, 0, 5, 0, 0, 0, 4, 4, 4, 2, 4, 4, 4, 1, 5, 5, 1, 5, 5, 5, 5, 2, 1, 5, 4, 0, 5, 4, 3, 1, 2, 1, 4, 5, 5, 3, 5, 1, 5, 1, 4, 5, 0, 4, 5, 2, 0, 4, 0, 4, 5, 1, 5, 0, 4, 4, 0, 1, 4, 4, 2, 2, 0, 0, 2, 2, 4, 4, 2, 4, 4, 1, 4, 4, 3, 4, 0, 2, 2, 0, 0, 1, 5, 4, 2, 5, 1, 2, 4, 0, 3, 5, 5, 2, 2, 5, 5, 4, 5, 1, 4, 1, 3, 2, 2, 3, 3, 4, 2, 1, 0, 2, 2, 5, 0, 4, 4, 2, 3, 4, 3, 4, 0, 2, 5, 4, 3, 0, 2, 0, 4, 4, 3, 0, 4, 3, 5, 5, 5, 5, 4, 3, 3, 1, 0, 4, 3, 5, 2, 5, 5, 1, 0, 0, 4, 5, 1, 5, 1, 3, 4, 1, 1, 5, 1, 2, 5, 2, 5, 2, 1, 5, 0, 5, 4, 3, 0, 0, 3, 0, 4, 5, 4, 5, 5, 0, 0, 0, 5, 1, 3, 2, 4, 3, 4, 3, 2, 4, 2, 2, 1, 5, 3, 1, 3, 5, 1, 5, 0, 3, 4, 3, 5, 2, 1, 5, 2, 0, 0, 4, 4, 0, 4, 0, 2, 4, 1, 4, 0, 3, 5, 3, 2, 5, 5, 2, 3, 4, 4, 0, 4, 4, 1, 5, 1, 1, 1, 5, 1, 4, 4, 3, 1, 2, 2, 4, 0, 4, 2, 3, 5, 4, 0, 2, 0, 3, 5, 0, 1, 5, 4, 5, 3, 2, 3, 0, 1, 4, 0, 1, 1, 4, 4, 0, 2, 4, 5, 1, 0, 4, 5, 3, 4, 4, 5, 2, 2, 3, 4, 5, 3, 4, 4, 0, 0, 4, 2, 2, 3, 5, 5, 5, 1, 5, 2, 2, 5, 3, 3, 5, 4, 1, 0, 1, 0, 5, 4, 4, 4, 2, 5, 4, 4, 2, 2, 3, 0, 3, 4, 0, 2, 2]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 123, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 202, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 320usize; s.lookahead = 53usize; s.prev_length = 5u32; s.good_match = 4u32; s.nice_match = 230i32; s.max_chain_length = 36u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 271usize);
        assert_eq!(r, 5u32, "lm ret 11");
        assert_eq!(s.match_start, 0usize, "lm match_start 11");
    }
    #[test]
    fn test_lm_12() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![4, 0, 4, 4, 0, 3, 3, 1, 1, 0, 0, 2, 0, 2, 1, 1, 0, 0, 2, 1, 2, 0, 4, 1, 2, 2, 1, 0, 3, 1, 3, 2, 4, 0, 1, 1, 3, 4, 1, 1, 4, 4, 1, 4, 4, 4, 1, 3, 3, 4, 1, 1, 2, 4, 2, 1, 3, 4, 1, 4, 4, 1, 1, 3, 3, 4, 3, 0, 3, 2, 2, 0, 2, 2, 4, 0, 0, 2, 4, 3, 4, 0, 0, 3, 2, 1, 3, 2, 0, 2, 4, 1, 3, 1, 3, 1, 2, 3, 3, 3, 0, 1, 3, 1, 1, 2, 0, 2, 3, 2, 0, 3, 4, 2, 2, 3, 1, 0, 0, 4, 4, 1, 4, 2, 2, 0, 4, 4, 2, 4, 2, 3, 2, 3, 2, 4, 3, 1, 2, 1, 0, 3, 2, 3, 3, 4, 2, 2, 3, 0, 4, 2, 2, 0, 4, 3, 0, 3, 3, 1, 0, 0, 2, 4, 2, 4, 3, 0, 4, 1, 3, 1, 2, 3, 2, 3, 3, 2, 4, 0, 2, 0, 4, 4, 0, 4, 3, 0, 4, 0, 4, 1, 4, 1, 4, 1, 4, 2, 1, 2, 1, 0, 4, 4, 3, 0, 0, 2, 1, 0, 0, 3, 4, 4, 0, 3, 4, 4, 1, 0, 2, 3, 2, 3, 4, 0, 3, 2, 0, 2, 4, 3, 4, 0, 0, 1, 1, 3, 0, 2, 2, 3, 3, 2, 1, 2, 2, 2, 3, 3, 0, 0, 0, 0, 2, 4, 0, 0, 4, 1, 0, 2, 3, 0, 3, 2, 0, 3, 4, 0, 3, 4, 3, 3, 4, 2, 4, 4, 2, 1, 0, 0, 3, 2, 3, 4, 1, 0, 0, 3, 3, 0, 0, 2, 2, 2, 4, 4, 1, 4, 1, 3, 4, 2, 3, 3, 0, 4, 3, 1, 0, 2, 2, 2, 1, 2, 3, 2, 4, 3, 1, 2, 3, 0, 2, 0, 2, 2, 4, 4, 1, 0, 3, 0, 3, 3, 1, 3, 0, 3, 2, 2, 1, 4, 1, 2, 2, 0, 1, 1, 1, 2, 2, 0, 3, 4, 1, 4, 3, 4, 4, 3, 1, 2, 2, 3, 0, 4, 0, 1, 0, 1, 3, 1, 3, 4, 3, 0, 2, 0, 1, 3, 2, 4, 4, 1, 0, 2, 2, 2, 2, 0, 4, 0, 2, 1, 1, 1, 0, 3, 0, 2, 3, 0, 3, 4, 4, 2, 1, 4, 1, 3, 3, 0, 0, 0, 4, 3, 2, 2, 3, 2, 0, 4, 0, 1, 4, 2, 4, 3, 3, 1, 0, 1, 4, 4, 3, 0, 1, 3, 0, 1, 4, 0, 1, 3, 2, 0, 2, 2, 1, 2, 0, 1, 1, 2, 4, 0, 4, 3, 0, 2, 4, 2, 1, 3, 3, 0, 0, 3, 0, 2, 2, 4, 2, 3, 4, 0, 0, 1, 4, 0, 0, 0, 0, 4, 4, 1, 4, 3, 1, 0, 2, 1, 3, 0, 4, 1, 4, 1, 0, 4, 0, 4, 3, 3, 2, 1, 4, 1, 1, 2, 1, 1, 1, 4, 3, 4, 3, 3, 0, 4, 2, 4, 1, 4, 4, 3, 1, 1, 4, 0, 4, 4, 4, 3, 4, 4, 0, 1, 0, 1, 3, 2, 3, 3, 2, 0, 3, 1, 4, 0, 3, 1, 2, 2, 2, 2, 0, 4, 1, 1, 1, 0]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 92, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 111, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 184, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 203, 0, 0, 0, 0, 0, 218, 0, 224, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 226, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 300usize; s.lookahead = 4usize; s.prev_length = 5u32; s.good_match = 5u32; s.nice_match = 132i32; s.max_chain_length = 7u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 291usize);
        assert_eq!(r, 4u32, "lm ret 12");
        assert_eq!(s.match_start, 0usize, "lm match_start 12");
    }
    #[test]
    fn test_lm_13() {
        let mut s = zlib_types::DeflateState::default();
        s.w_size = 512usize; s.w_mask = 511usize;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![1, 0, 0, 1, 1, 2, 0, 2, 2, 2, 0, 0, 1, 1, 0, 0, 1, 0, 1, 2, 2, 1, 0, 1, 2, 2, 1, 0, 1, 2, 0, 1, 2, 0, 1, 0, 2, 0, 1, 0, 1, 2, 1, 0, 2, 0, 0, 1, 0, 2, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 0, 2, 0, 1, 1, 2, 2, 1, 0, 0, 1, 2, 2, 2, 1, 0, 2, 1, 0, 1, 1, 1, 0, 1, 2, 1, 0, 1, 0, 0, 1, 1, 1, 0, 2, 0, 1, 0, 1, 1, 1, 2, 0, 0, 0, 2, 1, 2, 1, 1, 0, 0, 1, 0, 0, 2, 0, 2, 1, 1, 0, 0, 0, 0, 2, 1, 2, 0, 2, 1, 1, 0, 1, 1, 2, 2, 0, 0, 2, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 0, 1, 2, 1, 1, 0, 2, 1, 0, 1, 0, 0, 0, 2, 2, 1, 2, 0, 2, 2, 0, 2, 2, 0, 0, 2, 1, 1, 2, 1, 0, 1, 1, 1, 2, 2, 0, 1, 0, 0, 0, 2, 1, 0, 1, 0, 2, 2, 1, 0, 1, 1, 0, 2, 2, 1, 2, 2, 1, 0, 1, 2, 2, 2, 1, 1, 2, 0, 1, 1, 2, 2, 0, 0, 2, 2, 1, 2, 2, 0, 2, 0, 1, 1, 0, 0, 2, 1, 0, 2, 0, 1, 0, 1, 2, 1, 2, 2, 1, 0, 1, 1, 0, 1, 2, 1, 2, 1, 0, 1, 0, 0, 1, 2, 1, 0, 0, 0, 1, 2, 2, 2, 2, 2, 0, 0, 1, 0, 2, 1, 0, 0, 2, 0, 1, 2, 1, 0, 0, 1, 0, 1, 1, 1, 0, 2, 0, 1, 2, 1, 0, 1, 0, 1, 0, 2, 2, 0, 0, 1, 0, 2, 0, 1, 2, 1, 2, 1, 0, 0, 0, 1, 2, 0, 2, 0, 1, 1, 2, 1, 1, 2, 1, 2, 2, 1, 2, 1, 0, 0, 2, 1, 0, 1, 1, 2, 1, 0, 1, 1, 0, 1, 2, 0, 1, 2, 1, 1, 1, 2, 0, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 2, 0, 0, 1, 0, 0, 2, 1, 0, 0, 2, 2, 2, 2, 0, 2, 1, 2, 2, 2, 0, 2, 2, 1, 1, 0, 2, 0, 2, 2, 2, 2, 1, 2, 2, 0, 2, 2, 0, 1, 1, 2, 2, 2, 1, 1, 2, 0, 2, 2, 2, 1, 2, 1, 0, 1, 0, 1, 1, 0, 0, 1, 0, 2, 1, 2, 2, 1, 1, 2, 1, 2, 2, 0, 2, 2, 1, 1, 0, 0, 1, 1, 0, 2, 2, 2, 2, 0, 2, 0, 1, 2, 0, 2, 2, 0, 1, 1, 1, 1, 2, 1, 2, 1, 2, 0, 2, 0, 1, 0, 1, 2, 1, 2, 2, 0, 2, 0, 1, 1, 0, 1, 2, 1, 2, 0, 2, 2, 1, 1, 2, 0, 2, 2, 1, 0, 0, 0, 0, 1, 2, 0, 1, 0, 2, 1, 0, 1, 0, 2, 1, 2, 0, 2, 1, 0, 0, 1, 2, 2, 0, 2, 1, 0, 0, 1, 1, 1, 0, 2, 1, 0, 2, 1, 2, 2, 0, 0, 0, 1, 2, 1, 0, 2, 2, 0, 0, 2, 0, 1, 1, 1, 2, 1, 1, 0, 0, 0, 2, 1, 2, 1, 2, 1, 1, 0, 2, 0, 1, 1, 2, 0, 2, 0]; window[..wd.len()].copy_from_slice(&wd); } s.window = window;
        let mut prev = vec![0u16; 512]; { let pv: Vec<u16> = vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 125, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 161, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 202, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]; prev[..pv.len()].copy_from_slice(&pv); } s.prev = prev;
        s.strstart = 310usize; s.lookahead = 21usize; s.prev_length = 4u32; s.good_match = 24u32; s.nice_match = 152i32; s.max_chain_length = 15u32; s.match_start = 0usize;
        let r = super::longest_match(&mut s, 246usize);
        assert_eq!(r, 4u32, "lm ret 13");
        assert_eq!(s.match_start, 0usize, "lm match_start 13");
    }


    #[test]
    fn test_fw_0() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![66, 189, 242, 33, 6, 240, 132, 119, 98, 240, 243, 203, 77, 118, 77, 199, 7, 32, 81, 21, 154, 15, 137, 242, 198, 218, 202, 227, 68, 187, 49, 18, 69, 253, 111, 132, 223, 154, 215, 197, 179, 208]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 30usize; strm.state.lookahead = 4usize; strm.state.insert = 4u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![118, 172, 14, 143, 83, 167, 53, 108, 136, 145, 63, 32, 246, 247, 45, 176, 34, 210, 77, 10, 150, 218, 212, 60, 22, 23, 193, 169, 142, 120, 18, 158, 3, 39, 55, 16, 101, 208, 149, 134, 79, 21, 173, 160, 184, 70, 193, 192, 235, 197, 52, 138, 220, 121, 154, 223, 132, 155, 173, 5, 212, 161, 10, 192, 68, 30, 170, 238, 180, 180, 142, 250, 11, 31, 10, 189, 128, 233, 152, 163, 90, 186, 94, 160, 189, 135, 153, 193, 53, 13, 67, 158, 113, 137, 122, 167, 95, 222, 49, 52, 164, 170, 114, 224, 86, 40, 172, 111, 230, 138, 115, 61, 17, 97, 161, 93, 142, 174, 43, 176, 66, 215, 149, 138, 237, 177, 213, 148, 214, 209, 18, 211, 79, 102, 2, 244, 222, 113, 16, 233, 147, 174, 116, 34, 146, 61, 125, 23, 17, 101, 220, 25, 6, 246, 61, 87, 153, 122, 10, 211, 27, 58, 174, 64, 129, 244, 31, 180, 113, 101, 62, 61, 87, 122, 140, 65, 3, 249, 204, 25, 138, 127, 137, 216, 26, 242, 165, 0, 28, 64, 23, 63, 25, 35, 247, 16, 44, 250, 161, 80, 161, 36, 179, 197, 199, 155, 184, 135, 97, 168, 219, 63, 65, 1, 194, 40, 91, 21, 191, 235, 194, 22, 220, 27, 190, 254, 161, 215, 214, 235, 9, 125, 111, 138, 36, 217, 114, 218, 66, 14, 166, 191, 134, 62, 237, 63, 192, 55, 163, 52, 2, 242, 73, 120, 199, 22, 47, 50, 192, 91, 12, 174, 62, 13, 58, 246, 145, 153, 45, 18, 122, 54, 51, 31, 166, 92, 39, 123, 92, 127, 232, 201, 129, 188, 203, 179, 214, 42, 192, 120, 211, 82, 212, 247, 79, 205, 76, 83, 49]; strm.avail_in = 299usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 30usize, "fw strstart 0");
        assert_eq!(strm.state.lookahead, 303usize, "fw lookahead 0");
        assert_eq!(strm.state.insert, 0u32, "fw insert 0");
        assert_eq!(strm.state.ins_h, 90u32, "fw ins_h 0");
        assert_eq!(strm.state.high_water, 591u64, "fw high_water 0");
        assert_eq!(&strm.state.window[..333], &vec![66, 189, 242, 33, 6, 240, 132, 119, 98, 240, 243, 203, 77, 118, 77, 199, 7, 32, 81, 21, 154, 15, 137, 242, 198, 218, 202, 227, 68, 187, 49, 18, 69, 253, 118, 172, 14, 143, 83, 167, 53, 108, 136, 145, 63, 32, 246, 247, 45, 176, 34, 210, 77, 10, 150, 218, 212, 60, 22, 23, 193, 169, 142, 120, 18, 158, 3, 39, 55, 16, 101, 208, 149, 134, 79, 21, 173, 160, 184, 70, 193, 192, 235, 197, 52, 138, 220, 121, 154, 223, 132, 155, 173, 5, 212, 161, 10, 192, 68, 30, 170, 238, 180, 180, 142, 250, 11, 31, 10, 189, 128, 233, 152, 163, 90, 186, 94, 160, 189, 135, 153, 193, 53, 13, 67, 158, 113, 137, 122, 167, 95, 222, 49, 52, 164, 170, 114, 224, 86, 40, 172, 111, 230, 138, 115, 61, 17, 97, 161, 93, 142, 174, 43, 176, 66, 215, 149, 138, 237, 177, 213, 148, 214, 209, 18, 211, 79, 102, 2, 244, 222, 113, 16, 233, 147, 174, 116, 34, 146, 61, 125, 23, 17, 101, 220, 25, 6, 246, 61, 87, 153, 122, 10, 211, 27, 58, 174, 64, 129, 244, 31, 180, 113, 101, 62, 61, 87, 122, 140, 65, 3, 249, 204, 25, 138, 127, 137, 216, 26, 242, 165, 0, 28, 64, 23, 63, 25, 35, 247, 16, 44, 250, 161, 80, 161, 36, 179, 197, 199, 155, 184, 135, 97, 168, 219, 63, 65, 1, 194, 40, 91, 21, 191, 235, 194, 22, 220, 27, 190, 254, 161, 215, 214, 235, 9, 125, 111, 138, 36, 217, 114, 218, 66, 14, 166, 191, 134, 62, 237, 63, 192, 55, 163, 52, 2, 242, 73, 120, 199, 22, 47, 50, 192, 91, 12, 174, 62, 13, 58, 246, 145, 153, 45, 18, 122, 54, 51, 31, 166, 92, 39, 123, 92, 127, 232, 201, 129, 188, 203, 179, 214, 42, 192, 120, 211, 82, 212, 247, 79, 205, 76, 83, 49][..], "fw window 0");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 29, 27, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 26, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 28, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 0");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 0");
    }
    #[test]
    fn test_fw_1() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![58, 163, 61, 158, 93, 110, 179, 61, 226, 233, 142, 228, 87, 160, 142, 1, 22, 65, 116, 224, 79, 215, 120, 137, 130, 223, 0, 103, 81, 29, 111, 170, 21, 10, 9, 54, 202, 253, 202, 74, 87, 89, 220, 236, 237, 194, 52, 116, 95, 28, 224, 255, 64, 241, 79, 96, 156, 10, 147, 157, 152, 163, 90, 191, 56, 101, 88, 177, 211, 116, 164, 46, 62, 247, 108, 65, 153, 147, 71, 28, 246, 44, 152, 245, 43, 204, 19, 96, 92, 214]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 78usize; strm.state.lookahead = 4usize; strm.state.insert = 6u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![67, 227, 74, 150, 129, 236, 216, 99, 91, 125, 146, 80, 101, 197, 154, 61, 137, 79, 197, 87, 244, 51, 126, 8, 175, 79, 97, 16, 66, 95, 211, 126, 41, 233, 107, 211, 78, 7, 86, 126, 59, 195, 55, 202, 145, 167, 190, 138, 182, 97, 45, 93, 149, 250, 105, 122, 227, 34, 105, 224, 14, 27, 193, 233, 209, 21, 253, 134, 245, 207, 231, 97, 7, 193, 49, 8, 41, 181, 204, 246, 22, 135, 217, 22, 48, 78, 255, 108, 125, 29, 185, 105, 54, 110, 105, 164, 2, 65, 110, 128, 27, 223, 202, 222, 31, 177, 110, 4, 132, 58, 65, 54, 124, 61, 168, 98, 119, 137, 203, 205, 254, 109, 194, 211, 158, 120, 158, 220, 150, 255, 222, 25, 94, 235, 75, 118, 87, 5, 168, 137, 206, 188, 168, 94, 187, 229, 149, 33, 47, 76, 160, 108, 156, 10, 110, 127, 63, 39, 87, 14, 223, 211, 105, 13, 169, 195, 72, 180, 212, 244, 234, 104, 141, 138, 15, 102, 145, 253, 254, 47, 248, 179, 174, 75, 189, 16, 209, 97, 224, 80, 97, 222, 100, 109, 27, 98, 33, 162, 83, 239, 64, 54, 144, 41, 189, 207, 142, 199, 36, 237, 187, 111, 74, 165, 39, 155, 66, 241, 96, 12, 73, 14, 108, 124, 249, 58, 207, 89, 230, 30, 52, 161, 84, 90, 118, 25, 226, 171, 236, 104, 56, 110, 52, 22, 116, 54, 200, 5, 224, 9, 167]; strm.avail_in = 251usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 78usize, "fw strstart 1");
        assert_eq!(strm.state.lookahead, 255usize, "fw lookahead 1");
        assert_eq!(strm.state.insert, 0u32, "fw insert 1");
        assert_eq!(strm.state.ins_h, 228u32, "fw ins_h 1");
        assert_eq!(strm.state.high_water, 591u64, "fw high_water 1");
        assert_eq!(&strm.state.window[..333], &vec![58, 163, 61, 158, 93, 110, 179, 61, 226, 233, 142, 228, 87, 160, 142, 1, 22, 65, 116, 224, 79, 215, 120, 137, 130, 223, 0, 103, 81, 29, 111, 170, 21, 10, 9, 54, 202, 253, 202, 74, 87, 89, 220, 236, 237, 194, 52, 116, 95, 28, 224, 255, 64, 241, 79, 96, 156, 10, 147, 157, 152, 163, 90, 191, 56, 101, 88, 177, 211, 116, 164, 46, 62, 247, 108, 65, 153, 147, 71, 28, 246, 44, 67, 227, 74, 150, 129, 236, 216, 99, 91, 125, 146, 80, 101, 197, 154, 61, 137, 79, 197, 87, 244, 51, 126, 8, 175, 79, 97, 16, 66, 95, 211, 126, 41, 233, 107, 211, 78, 7, 86, 126, 59, 195, 55, 202, 145, 167, 190, 138, 182, 97, 45, 93, 149, 250, 105, 122, 227, 34, 105, 224, 14, 27, 193, 233, 209, 21, 253, 134, 245, 207, 231, 97, 7, 193, 49, 8, 41, 181, 204, 246, 22, 135, 217, 22, 48, 78, 255, 108, 125, 29, 185, 105, 54, 110, 105, 164, 2, 65, 110, 128, 27, 223, 202, 222, 31, 177, 110, 4, 132, 58, 65, 54, 124, 61, 168, 98, 119, 137, 203, 205, 254, 109, 194, 211, 158, 120, 158, 220, 150, 255, 222, 25, 94, 235, 75, 118, 87, 5, 168, 137, 206, 188, 168, 94, 187, 229, 149, 33, 47, 76, 160, 108, 156, 10, 110, 127, 63, 39, 87, 14, 223, 211, 105, 13, 169, 195, 72, 180, 212, 244, 234, 104, 141, 138, 15, 102, 145, 253, 254, 47, 248, 179, 174, 75, 189, 16, 209, 97, 224, 80, 97, 222, 100, 109, 27, 98, 33, 162, 83, 239, 64, 54, 144, 41, 189, 207, 142, 199, 36, 237, 187, 111, 74, 165, 39, 155, 66, 241, 96, 12, 73, 14, 108, 124, 249, 58, 207, 89, 230, 30, 52, 161, 84, 90, 118, 25, 226, 171, 236, 104, 56, 110, 52, 22, 116, 54, 200, 5, 224, 9, 167][..], "fw window 1");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 75, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 72, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 74, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 76, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 73, 0, 0, 77, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 1");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 1");
    }
    #[test]
    fn test_fw_2() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![225, 12, 164, 240, 140, 57, 135, 95, 30, 162, 227, 23, 136, 141, 130, 204, 95, 165, 3, 251, 19, 91, 26, 104, 22, 224, 221, 234, 159, 223, 176, 205, 7, 73, 199, 150, 220, 112, 156, 115, 131, 22, 195, 202, 117, 44, 115, 209, 232, 209, 154, 10, 93, 241, 108, 172, 129, 32, 214, 122, 18, 21, 5, 12, 185, 103]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 54usize; strm.state.lookahead = 4usize; strm.state.insert = 0u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![35, 118, 49, 118, 167, 112, 127, 235, 43, 215, 35, 216, 95, 82, 203, 144, 10, 160, 71, 14, 240, 253, 6, 50, 190, 41, 132, 27, 225, 191, 105, 229, 207, 58, 167, 38, 60, 112, 116, 128, 14, 178, 124, 176, 57, 194, 242, 99, 99, 243, 202, 178, 149, 2, 56, 84, 119, 124, 213, 204, 252, 114, 23, 164, 40, 109, 162, 25, 207, 46, 54, 246, 25, 80, 128, 71, 38, 133, 72, 243, 114, 243, 12, 58, 118, 109, 132, 87, 51, 39, 73, 65, 216, 64, 15, 239, 190, 72, 232, 122, 180, 248, 242, 26, 76, 24, 170, 130, 83, 32, 147, 57, 92, 29, 2, 156, 58, 179, 144, 53, 52, 197, 223, 124, 123, 135, 40, 243, 15, 136, 27, 45, 72, 53, 163, 8, 70, 70, 208, 253, 113, 18, 43, 136, 37, 158, 222, 98, 159, 88, 191, 103, 239, 30, 215, 54, 36, 80, 128, 139, 92, 41, 14, 49, 77, 214, 211, 81, 223, 105, 134, 82, 125, 209, 160, 207, 213, 168, 255, 46, 160, 5, 4, 162, 222, 1, 152, 22, 253, 140, 191, 98, 82, 234, 138, 24, 138, 24, 129, 251, 154, 96]; strm.avail_in = 202usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 54usize, "fw strstart 2");
        assert_eq!(strm.state.lookahead, 206usize, "fw lookahead 2");
        assert_eq!(strm.state.insert, 0u32, "fw insert 2");
        assert_eq!(strm.state.ins_h, 204u32, "fw ins_h 2");
        assert_eq!(strm.state.high_water, 518u64, "fw high_water 2");
        assert_eq!(&strm.state.window[..260], &vec![225, 12, 164, 240, 140, 57, 135, 95, 30, 162, 227, 23, 136, 141, 130, 204, 95, 165, 3, 251, 19, 91, 26, 104, 22, 224, 221, 234, 159, 223, 176, 205, 7, 73, 199, 150, 220, 112, 156, 115, 131, 22, 195, 202, 117, 44, 115, 209, 232, 209, 154, 10, 93, 241, 108, 172, 129, 32, 35, 118, 49, 118, 167, 112, 127, 235, 43, 215, 35, 216, 95, 82, 203, 144, 10, 160, 71, 14, 240, 253, 6, 50, 190, 41, 132, 27, 225, 191, 105, 229, 207, 58, 167, 38, 60, 112, 116, 128, 14, 178, 124, 176, 57, 194, 242, 99, 99, 243, 202, 178, 149, 2, 56, 84, 119, 124, 213, 204, 252, 114, 23, 164, 40, 109, 162, 25, 207, 46, 54, 246, 25, 80, 128, 71, 38, 133, 72, 243, 114, 243, 12, 58, 118, 109, 132, 87, 51, 39, 73, 65, 216, 64, 15, 239, 190, 72, 232, 122, 180, 248, 242, 26, 76, 24, 170, 130, 83, 32, 147, 57, 92, 29, 2, 156, 58, 179, 144, 53, 52, 197, 223, 124, 123, 135, 40, 243, 15, 136, 27, 45, 72, 53, 163, 8, 70, 70, 208, 253, 113, 18, 43, 136, 37, 158, 222, 98, 159, 88, 191, 103, 239, 30, 215, 54, 36, 80, 128, 139, 92, 41, 14, 49, 77, 214, 211, 81, 223, 105, 134, 82, 125, 209, 160, 207, 213, 168, 255, 46, 160, 5, 4, 162, 222, 1, 152, 22, 253, 140, 191, 98, 82, 234, 138, 24, 138, 24, 129, 251, 154, 96][..], "fw window 2");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 2");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 2");
    }
    #[test]
    fn test_fw_3() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![246, 243, 9, 193, 55, 12, 133, 177, 254, 76, 237, 216, 143, 237, 68, 19, 49, 247, 18, 30, 4, 193, 137, 147, 198, 252, 63, 163, 148, 111, 86, 147, 148, 209, 128]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 26usize; strm.state.lookahead = 1usize; strm.state.insert = 5u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![111, 234, 188, 196, 158, 2, 85, 213, 176, 46, 44, 97, 138, 143, 8, 79, 232, 134, 248, 101, 20, 134, 38, 140, 209, 115, 165, 234, 63, 145, 246, 147, 244, 252, 233, 206, 168, 245, 236, 67, 166, 195, 74, 249, 86, 253, 138, 111, 114, 144, 12, 115, 207, 138, 233, 128, 224, 207, 61, 96, 103, 120, 5, 187, 241, 58, 90, 69, 68, 59, 249, 112, 210, 124, 179, 249, 37, 169, 98, 248, 76, 50, 42, 71, 174, 153, 162, 220, 127, 166, 83, 158, 158, 12, 23, 15, 100, 226, 146, 81, 9, 59, 255, 31, 90, 197, 83, 8, 129, 149, 116, 78, 167, 251, 29, 123, 112, 3, 56, 81, 197, 166, 171, 65, 13, 199, 95, 205, 211, 250, 0]; strm.avail_in = 131usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 26usize, "fw strstart 3");
        assert_eq!(strm.state.lookahead, 132usize, "fw lookahead 3");
        assert_eq!(strm.state.insert, 0u32, "fw insert 3");
        assert_eq!(strm.state.ins_h, 151u32, "fw ins_h 3");
        assert_eq!(strm.state.high_water, 416u64, "fw high_water 3");
        assert_eq!(&strm.state.window[..158], &vec![246, 243, 9, 193, 55, 12, 133, 177, 254, 76, 237, 216, 143, 237, 68, 19, 49, 247, 18, 30, 4, 193, 137, 147, 198, 252, 63, 111, 234, 188, 196, 158, 2, 85, 213, 176, 46, 44, 97, 138, 143, 8, 79, 232, 134, 248, 101, 20, 134, 38, 140, 209, 115, 165, 234, 63, 145, 246, 147, 244, 252, 233, 206, 168, 245, 236, 67, 166, 195, 74, 249, 86, 253, 138, 111, 114, 144, 12, 115, 207, 138, 233, 128, 224, 207, 61, 96, 103, 120, 5, 187, 241, 58, 90, 69, 68, 59, 249, 112, 210, 124, 179, 249, 37, 169, 98, 248, 76, 50, 42, 71, 174, 153, 162, 220, 127, 166, 83, 158, 158, 12, 23, 15, 100, 226, 146, 81, 9, 59, 255, 31, 90, 197, 83, 8, 129, 149, 116, 78, 167, 251, 29, 123, 112, 3, 56, 81, 197, 166, 171, 65, 13, 199, 95, 205, 211, 250, 0][..], "fw window 3");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 23, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 22, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 25, 0, 0, 0, 21, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 3");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 3");
    }
    #[test]
    fn test_fw_4() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![135, 60, 85, 213, 115, 13, 74, 172, 146, 95, 202, 54, 19, 168, 252, 98, 94, 195, 64, 224, 142, 241, 52, 81, 53, 173, 192, 21, 186, 158, 165, 56, 195, 157, 211, 227, 132, 191, 115, 231, 185, 63, 70, 47, 163, 155, 43, 120, 55, 242, 121, 156, 74, 201, 160, 73, 243, 146, 69, 86, 175, 64, 11, 196, 154, 73, 201, 159, 71, 184, 21, 51, 52, 187, 237, 49, 41, 159, 126]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 71usize; strm.state.lookahead = 0usize; strm.state.insert = 2u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![70, 82, 154, 34, 238, 11, 210, 239, 145, 228, 237, 218, 126, 123, 20, 68, 231, 63, 95, 207, 117, 68, 178, 230, 77, 152, 9, 253, 180, 137, 102, 110, 225, 58, 88, 204, 13, 138, 97, 151, 132, 236, 61, 59, 111, 253, 1, 23, 136, 251, 112, 168, 183, 72, 187, 227, 30, 131, 138, 132, 195, 227, 125, 186, 1, 79, 133, 202, 208, 48, 134, 222, 234, 187, 49, 179, 234, 142, 166, 95, 240, 11, 68, 16, 95, 255, 70, 18, 44, 198, 24, 209, 120, 93, 141, 211, 194, 39, 210, 67, 128, 65, 0, 72, 64, 66, 55, 86, 140, 24, 56, 164, 157, 82, 199, 217, 233, 153, 233, 71, 169, 58, 6, 6, 233, 106, 110, 103, 191, 62, 172, 122, 145, 58, 15, 145, 213, 182, 77, 216, 100, 53, 138, 95, 174, 120, 44, 36, 130, 166, 251, 189, 170, 71, 43, 34, 145, 133, 159, 4, 20, 40, 101, 8, 183, 248, 121, 228, 165, 235, 11, 46, 96, 248, 248, 93, 7, 195, 97, 78, 221, 152, 116, 204, 205, 212, 115, 214, 14, 57, 1, 191, 108, 51, 84, 241, 31, 188, 137, 122, 128, 128, 60, 130, 188, 168, 121, 245, 249, 254, 61, 97, 201, 41, 143, 254, 58, 39, 106, 53, 13, 73, 154, 16, 169, 108, 155, 247, 26, 164, 185, 69, 150, 146, 236, 214, 202, 198]; strm.avail_in = 238usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 71usize, "fw strstart 4");
        assert_eq!(strm.state.lookahead, 238usize, "fw lookahead 4");
        assert_eq!(strm.state.insert, 0u32, "fw insert 4");
        assert_eq!(strm.state.ins_h, 34u32, "fw ins_h 4");
        assert_eq!(strm.state.high_water, 567u64, "fw high_water 4");
        assert_eq!(&strm.state.window[..309], &vec![135, 60, 85, 213, 115, 13, 74, 172, 146, 95, 202, 54, 19, 168, 252, 98, 94, 195, 64, 224, 142, 241, 52, 81, 53, 173, 192, 21, 186, 158, 165, 56, 195, 157, 211, 227, 132, 191, 115, 231, 185, 63, 70, 47, 163, 155, 43, 120, 55, 242, 121, 156, 74, 201, 160, 73, 243, 146, 69, 86, 175, 64, 11, 196, 154, 73, 201, 159, 71, 184, 21, 70, 82, 154, 34, 238, 11, 210, 239, 145, 228, 237, 218, 126, 123, 20, 68, 231, 63, 95, 207, 117, 68, 178, 230, 77, 152, 9, 253, 180, 137, 102, 110, 225, 58, 88, 204, 13, 138, 97, 151, 132, 236, 61, 59, 111, 253, 1, 23, 136, 251, 112, 168, 183, 72, 187, 227, 30, 131, 138, 132, 195, 227, 125, 186, 1, 79, 133, 202, 208, 48, 134, 222, 234, 187, 49, 179, 234, 142, 166, 95, 240, 11, 68, 16, 95, 255, 70, 18, 44, 198, 24, 209, 120, 93, 141, 211, 194, 39, 210, 67, 128, 65, 0, 72, 64, 66, 55, 86, 140, 24, 56, 164, 157, 82, 199, 217, 233, 153, 233, 71, 169, 58, 6, 6, 233, 106, 110, 103, 191, 62, 172, 122, 145, 58, 15, 145, 213, 182, 77, 216, 100, 53, 138, 95, 174, 120, 44, 36, 130, 166, 251, 189, 170, 71, 43, 34, 145, 133, 159, 4, 20, 40, 101, 8, 183, 248, 121, 228, 165, 235, 11, 46, 96, 248, 248, 93, 7, 195, 97, 78, 221, 152, 116, 204, 205, 212, 115, 214, 14, 57, 1, 191, 108, 51, 84, 241, 31, 188, 137, 122, 128, 128, 60, 130, 188, 168, 121, 245, 249, 254, 61, 97, 201, 41, 143, 254, 58, 39, 106, 53, 13, 73, 154, 16, 169, 108, 155, 247, 26, 164, 185, 69, 150, 146, 236, 214, 202, 198][..], "fw window 4");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 70, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 69, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 4");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 4");
    }
    #[test]
    fn test_fw_5() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![159, 96, 8, 48, 38, 74, 26, 115, 161, 227, 177, 83, 210, 71, 48, 36, 250, 220, 94, 101, 188, 53, 90, 254, 248, 149, 157, 119, 165, 228, 16, 31, 0, 191, 15, 132, 41, 4, 21]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 30usize; strm.state.lookahead = 1usize; strm.state.insert = 3u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![9, 219, 97, 103, 242, 254, 62, 59, 7, 5, 236, 109, 69, 30, 250, 119, 12, 23, 11, 178, 125, 89, 19, 156, 146, 204, 238, 234, 121, 121, 103, 232, 86, 83, 151, 158, 201, 144, 0, 48, 227, 220, 117, 238, 252, 151, 87, 252, 165, 60, 39, 62, 226, 59, 3, 179, 167, 5, 144, 239, 190, 168, 102, 105, 227, 137, 141, 82, 192, 91, 112, 50, 235, 225, 22, 242, 170, 112, 82, 138, 78, 204, 186, 154, 93, 9, 160, 226, 247, 220, 96, 251, 123, 92, 24, 137, 171, 94, 201, 45, 195, 91, 208, 195, 69, 239, 49, 99, 3, 104, 200, 114, 185, 178, 182, 39, 7, 217, 7, 177, 196, 208, 81, 168, 13, 6, 157, 41, 13, 80, 177, 237, 177, 103, 61, 26, 57, 239, 235, 161, 52, 43, 27, 246, 227, 30, 32, 163, 175, 187, 50, 216, 135, 131, 46, 6, 162, 251, 208, 242, 11, 136, 0, 130, 106, 42, 122, 150, 105, 175, 93, 39, 2, 134, 132, 37, 84, 213, 166, 125, 22, 118, 12, 220, 172, 239, 80, 223, 110, 172, 81, 84, 116, 166, 249, 46, 116, 213, 152, 103, 181, 49, 38, 152, 17, 241, 15, 241, 237, 183, 35, 243, 54, 245, 74, 31, 210, 65, 31, 159, 128, 186, 57, 142, 255, 31, 36, 196, 84, 152, 33, 125, 66, 115, 207, 15, 176, 195, 141, 143, 189, 179, 155, 108, 178, 95, 247, 234, 146, 180, 158, 36, 202, 33]; strm.avail_in = 254usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 30usize, "fw strstart 5");
        assert_eq!(strm.state.lookahead, 255usize, "fw lookahead 5");
        assert_eq!(strm.state.insert, 0u32, "fw insert 5");
        assert_eq!(strm.state.ins_h, 137u32, "fw ins_h 5");
        assert_eq!(strm.state.high_water, 543u64, "fw high_water 5");
        assert_eq!(&strm.state.window[..285], &vec![159, 96, 8, 48, 38, 74, 26, 115, 161, 227, 177, 83, 210, 71, 48, 36, 250, 220, 94, 101, 188, 53, 90, 254, 248, 149, 157, 119, 165, 228, 16, 9, 219, 97, 103, 242, 254, 62, 59, 7, 5, 236, 109, 69, 30, 250, 119, 12, 23, 11, 178, 125, 89, 19, 156, 146, 204, 238, 234, 121, 121, 103, 232, 86, 83, 151, 158, 201, 144, 0, 48, 227, 220, 117, 238, 252, 151, 87, 252, 165, 60, 39, 62, 226, 59, 3, 179, 167, 5, 144, 239, 190, 168, 102, 105, 227, 137, 141, 82, 192, 91, 112, 50, 235, 225, 22, 242, 170, 112, 82, 138, 78, 204, 186, 154, 93, 9, 160, 226, 247, 220, 96, 251, 123, 92, 24, 137, 171, 94, 201, 45, 195, 91, 208, 195, 69, 239, 49, 99, 3, 104, 200, 114, 185, 178, 182, 39, 7, 217, 7, 177, 196, 208, 81, 168, 13, 6, 157, 41, 13, 80, 177, 237, 177, 103, 61, 26, 57, 239, 235, 161, 52, 43, 27, 246, 227, 30, 32, 163, 175, 187, 50, 216, 135, 131, 46, 6, 162, 251, 208, 242, 11, 136, 0, 130, 106, 42, 122, 150, 105, 175, 93, 39, 2, 134, 132, 37, 84, 213, 166, 125, 22, 118, 12, 220, 172, 239, 80, 223, 110, 172, 81, 84, 116, 166, 249, 46, 116, 213, 152, 103, 181, 49, 38, 152, 17, 241, 15, 241, 237, 183, 35, 243, 54, 245, 74, 31, 210, 65, 31, 159, 128, 186, 57, 142, 255, 31, 36, 196, 84, 152, 33, 125, 66, 115, 207, 15, 176, 195, 141, 143, 189, 179, 155, 108, 178, 95, 247, 234, 146, 180, 158, 36, 202, 33][..], "fw window 5");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 28, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 29, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 5");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 5");
    }
    #[test]
    fn test_fw_6() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![175, 10, 115, 249, 198, 89, 11, 207, 210, 54, 224, 144, 23, 153, 137, 92, 28, 81, 33, 176, 30, 182, 99, 110, 30, 71, 249, 200, 167, 164, 250, 233, 77, 160, 86, 37, 127, 247, 210, 113, 163, 13, 242, 161, 102, 115, 78, 88, 141, 1, 145, 58, 228, 111, 244, 33, 150, 162, 222, 152, 128, 213, 41, 214, 80, 82, 150, 12, 220, 80, 62, 209, 39, 37, 19, 35, 58, 37, 72, 173, 222, 170, 240, 197]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 76usize; strm.state.lookahead = 0usize; strm.state.insert = 0u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![26, 128, 159, 78, 241, 156, 122, 131, 213, 252, 33, 220, 206, 215, 153, 55, 47, 17, 131, 85, 1, 156, 232, 85, 200, 162, 101, 143, 239, 124, 251, 40, 78, 242, 48, 250, 172, 101, 163, 95, 69, 194, 91, 97, 253, 119, 179, 182, 33, 141, 152, 113, 146, 179, 55, 4, 47, 17, 199, 2, 78, 28, 104, 136, 210, 139, 56, 153, 120, 234, 230, 106, 38, 67, 247, 133, 97, 10, 182, 136, 69, 160, 114, 8, 180, 53, 100, 214, 5, 49, 56, 238, 176, 236, 97, 209, 22, 119, 58, 230, 254, 22, 149, 54, 99, 153, 0, 164, 62, 222, 60, 167, 61, 217, 127, 25, 121, 97, 66, 153, 225, 78, 164, 19, 156, 252, 3, 195, 180, 53, 220, 108, 106, 73, 154, 0, 150, 154, 178, 66, 137, 84, 244, 240, 51, 115, 42, 206, 36, 229, 218, 166, 210, 253, 211, 19, 208, 150, 59, 246, 229, 182, 21, 74, 138, 182, 175, 169, 171, 89, 248, 201, 4, 27, 134, 167, 125, 53, 64, 168, 236, 201, 52, 39, 167, 183, 239, 112, 172, 116, 119, 125, 44, 72, 94, 127, 123, 21, 15, 209, 156, 36, 165, 19, 182, 129, 182, 11, 52, 135, 184, 54, 1, 148, 26, 54, 242, 75, 6, 208, 93, 61, 42, 62, 250, 124, 57, 4, 28, 195, 151, 173, 200, 5, 45, 37]; strm.avail_in = 236usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 76usize, "fw strstart 6");
        assert_eq!(strm.state.lookahead, 236usize, "fw lookahead 6");
        assert_eq!(strm.state.insert, 0u32, "fw insert 6");
        assert_eq!(strm.state.ins_h, 80u32, "fw ins_h 6");
        assert_eq!(strm.state.high_water, 570u64, "fw high_water 6");
        assert_eq!(&strm.state.window[..312], &vec![175, 10, 115, 249, 198, 89, 11, 207, 210, 54, 224, 144, 23, 153, 137, 92, 28, 81, 33, 176, 30, 182, 99, 110, 30, 71, 249, 200, 167, 164, 250, 233, 77, 160, 86, 37, 127, 247, 210, 113, 163, 13, 242, 161, 102, 115, 78, 88, 141, 1, 145, 58, 228, 111, 244, 33, 150, 162, 222, 152, 128, 213, 41, 214, 80, 82, 150, 12, 220, 80, 62, 209, 39, 37, 19, 35, 26, 128, 159, 78, 241, 156, 122, 131, 213, 252, 33, 220, 206, 215, 153, 55, 47, 17, 131, 85, 1, 156, 232, 85, 200, 162, 101, 143, 239, 124, 251, 40, 78, 242, 48, 250, 172, 101, 163, 95, 69, 194, 91, 97, 253, 119, 179, 182, 33, 141, 152, 113, 146, 179, 55, 4, 47, 17, 199, 2, 78, 28, 104, 136, 210, 139, 56, 153, 120, 234, 230, 106, 38, 67, 247, 133, 97, 10, 182, 136, 69, 160, 114, 8, 180, 53, 100, 214, 5, 49, 56, 238, 176, 236, 97, 209, 22, 119, 58, 230, 254, 22, 149, 54, 99, 153, 0, 164, 62, 222, 60, 167, 61, 217, 127, 25, 121, 97, 66, 153, 225, 78, 164, 19, 156, 252, 3, 195, 180, 53, 220, 108, 106, 73, 154, 0, 150, 154, 178, 66, 137, 84, 244, 240, 51, 115, 42, 206, 36, 229, 218, 166, 210, 253, 211, 19, 208, 150, 59, 246, 229, 182, 21, 74, 138, 182, 175, 169, 171, 89, 248, 201, 4, 27, 134, 167, 125, 53, 64, 168, 236, 201, 52, 39, 167, 183, 239, 112, 172, 116, 119, 125, 44, 72, 94, 127, 123, 21, 15, 209, 156, 36, 165, 19, 182, 129, 182, 11, 52, 135, 184, 54, 1, 148, 26, 54, 242, 75, 6, 208, 93, 61, 42, 62, 250, 124, 57, 4, 28, 195, 151, 173, 200, 5, 45, 37][..], "fw window 6");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 6");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 6");
    }
    #[test]
    fn test_fw_7() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![239, 130, 192, 108, 55, 173, 46, 9, 103, 169, 118, 203, 150, 25, 35, 166, 229, 157, 191, 68, 249, 59, 97, 189, 83, 191, 187, 171, 227, 93, 41, 3, 74, 239, 254, 93, 244, 230, 201, 90, 231, 140, 141, 31, 242, 177, 136, 173, 183, 28, 55, 178, 132, 237, 93, 168, 214, 23, 185, 137, 11, 18, 15, 15, 12, 89, 201, 37, 243, 120, 123]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 59usize; strm.state.lookahead = 4usize; strm.state.insert = 4u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![198, 146, 243, 236, 89, 252, 1, 2, 74, 41, 245, 57, 173, 174, 212, 75, 148, 189, 5, 204, 244, 98, 26, 17, 0, 170, 185, 180, 150, 197, 2, 28, 250, 217, 253, 93, 119, 178, 11, 139, 40, 45, 27, 184, 248, 31, 175, 110, 111, 91, 198, 22, 140, 178, 173, 1, 125, 135, 87, 53, 254, 251, 209, 227, 25, 189, 72, 162, 238, 47, 192, 133, 103, 21, 212, 189, 248, 171, 186, 185, 178, 87, 183, 37, 202, 66, 7, 246, 62, 253, 74, 210, 77, 116, 47, 122, 17, 97, 8, 116, 156, 250, 212, 121, 35, 142, 26, 180, 96, 212, 47, 21, 64, 17, 171, 122, 28, 10, 42, 169, 254, 128, 166, 22, 172, 161, 171, 94, 174, 8, 176, 150, 244, 122, 14, 70, 185, 113]; strm.avail_in = 138usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 59usize, "fw strstart 7");
        assert_eq!(strm.state.lookahead, 142usize, "fw lookahead 7");
        assert_eq!(strm.state.insert, 0u32, "fw insert 7");
        assert_eq!(strm.state.ins_h, 3u32, "fw ins_h 7");
        assert_eq!(strm.state.high_water, 459u64, "fw high_water 7");
        assert_eq!(&strm.state.window[..201], &vec![239, 130, 192, 108, 55, 173, 46, 9, 103, 169, 118, 203, 150, 25, 35, 166, 229, 157, 191, 68, 249, 59, 97, 189, 83, 191, 187, 171, 227, 93, 41, 3, 74, 239, 254, 93, 244, 230, 201, 90, 231, 140, 141, 31, 242, 177, 136, 173, 183, 28, 55, 178, 132, 237, 93, 168, 214, 23, 185, 137, 11, 18, 15, 198, 146, 243, 236, 89, 252, 1, 2, 74, 41, 245, 57, 173, 174, 212, 75, 148, 189, 5, 204, 244, 98, 26, 17, 0, 170, 185, 180, 150, 197, 2, 28, 250, 217, 253, 93, 119, 178, 11, 139, 40, 45, 27, 184, 248, 31, 175, 110, 111, 91, 198, 22, 140, 178, 173, 1, 125, 135, 87, 53, 254, 251, 209, 227, 25, 189, 72, 162, 238, 47, 192, 133, 103, 21, 212, 189, 248, 171, 186, 185, 178, 87, 183, 37, 202, 66, 7, 246, 62, 253, 74, 210, 77, 116, 47, 122, 17, 97, 8, 116, 156, 250, 212, 121, 35, 142, 26, 180, 96, 212, 47, 21, 64, 17, 171, 122, 28, 10, 42, 169, 254, 128, 166, 22, 172, 161, 171, 94, 174, 8, 176, 150, 244, 122, 14, 70, 185, 113][..], "fw window 7");
        assert_eq!(strm.state.head, vec![0, 0, 0, 58, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 57, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 55, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 7");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 56, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 7");
    }
    #[test]
    fn test_fw_8() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![58, 215, 26, 64, 29, 91, 86, 93, 170, 11, 135, 184, 41, 250, 16, 226, 143, 166, 27, 20, 199, 200, 25, 21, 133, 241, 159, 101, 91]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 19usize; strm.state.lookahead = 2usize; strm.state.insert = 6u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![92, 73, 251, 108, 119, 64, 238, 45, 247, 249, 78, 36, 47, 4, 22, 146, 119, 212, 48, 33, 96, 74, 200, 152, 8, 16, 48, 115, 84, 0, 217, 193, 7, 208, 179, 148, 250, 97, 18, 119, 156, 50, 189, 192, 153, 238, 206, 137, 77, 85, 111, 10, 162, 83, 107, 191, 252, 202, 174, 190, 218, 99, 111, 193, 53, 199, 185, 207, 88, 46, 193, 111, 103, 212, 158, 36, 181, 65, 68, 23, 244, 61, 205, 61, 141, 164, 112, 213, 207, 184, 204, 18, 34]; strm.avail_in = 93usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 19usize, "fw strstart 8");
        assert_eq!(strm.state.lookahead, 95usize, "fw lookahead 8");
        assert_eq!(strm.state.insert, 0u32, "fw insert 8");
        assert_eq!(strm.state.ins_h, 167u32, "fw ins_h 8");
        assert_eq!(strm.state.high_water, 372u64, "fw high_water 8");
        assert_eq!(&strm.state.window[..114], &vec![58, 215, 26, 64, 29, 91, 86, 93, 170, 11, 135, 184, 41, 250, 16, 226, 143, 166, 27, 20, 199, 92, 73, 251, 108, 119, 64, 238, 45, 247, 249, 78, 36, 47, 4, 22, 146, 119, 212, 48, 33, 96, 74, 200, 152, 8, 16, 48, 115, 84, 0, 217, 193, 7, 208, 179, 148, 250, 97, 18, 119, 156, 50, 189, 192, 153, 238, 206, 137, 77, 85, 111, 10, 162, 83, 107, 191, 252, 202, 174, 190, 218, 99, 111, 193, 53, 199, 185, 207, 88, 46, 193, 111, 103, 212, 158, 36, 181, 65, 68, 23, 244, 61, 205, 61, 141, 164, 112, 213, 207, 184, 204, 18, 34][..], "fw window 8");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 17, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 14, 0, 0, 0, 0, 0, 0, 0, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 0, 0, 0, 0, 0, 0, 0, 0, 16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 8");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 8");
    }
    #[test]
    fn test_fw_9() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![241, 45, 170, 215, 148, 185, 69, 211, 208, 20, 217, 51, 46, 96, 236, 231, 32, 208, 78, 29, 142, 232, 58, 73, 231, 240, 219, 5, 90, 82, 107, 195, 127, 83, 186, 3, 45, 150, 219, 120, 82, 117, 121]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 32usize; strm.state.lookahead = 3usize; strm.state.insert = 4u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![162, 237, 125, 3, 4, 31, 227, 180, 69, 20, 72, 105, 244, 16, 179, 169, 147, 30, 50, 52, 235, 33, 57, 24, 1, 54, 157, 135, 175, 145, 127, 224, 156, 243, 141, 157, 141, 237, 36, 37, 206, 171, 152, 152, 102, 65, 104, 102, 9, 46, 226, 216, 24, 24, 102, 79, 70, 125, 130, 84, 41, 168, 194, 147, 225, 43, 45, 11, 250, 68, 179, 137, 20, 68, 25, 232, 218, 86, 125, 214, 206, 120, 42, 201, 249, 39, 144, 9, 143, 50, 187, 136, 167, 19, 41, 255, 195, 233, 169, 245, 217, 246, 128, 48, 245, 221, 158, 176, 9, 229, 251, 193, 91, 189, 24, 147, 130, 17, 106, 243, 53, 157, 165, 16, 212, 183, 181, 138, 179, 15, 223, 45, 131, 48, 136, 219, 84, 157, 90, 180, 172, 103, 222, 187, 64, 44, 227, 157, 1, 115, 118, 57, 87, 87, 146, 63, 84, 208, 200, 49, 224, 151, 72, 253, 122, 203, 191, 166, 96, 125, 237, 103, 208, 48, 169, 190, 181, 46, 148, 68, 109, 178, 240, 207, 94, 235, 234, 131, 193, 187, 16, 31, 137, 93, 184, 45, 6, 0, 98, 105, 103, 88, 229, 252, 219, 19, 91, 118, 76, 78, 117, 137, 231, 68, 95, 82, 55, 27, 44, 159, 235, 21, 105, 240, 7, 200, 109, 227, 160, 46, 173, 199, 195, 237, 84, 7, 42, 16, 196, 14, 232, 183, 192, 244, 78, 165, 126, 204, 18, 249, 57, 198, 211, 212, 249, 95, 214, 17, 155, 193, 232, 96, 66, 105, 0, 255, 189, 255, 17, 65, 83, 215, 32, 12, 32, 152, 113, 155, 133, 164, 186, 7, 184, 126, 183, 164, 53, 165, 117, 126, 67, 116, 73, 123, 197, 16, 79]; strm.avail_in = 297usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 32usize, "fw strstart 9");
        assert_eq!(strm.state.lookahead, 300usize, "fw lookahead 9");
        assert_eq!(strm.state.insert, 0u32, "fw insert 9");
        assert_eq!(strm.state.ins_h, 107u32, "fw ins_h 9");
        assert_eq!(strm.state.high_water, 590u64, "fw high_water 9");
        assert_eq!(&strm.state.window[..332], &vec![241, 45, 170, 215, 148, 185, 69, 211, 208, 20, 217, 51, 46, 96, 236, 231, 32, 208, 78, 29, 142, 232, 58, 73, 231, 240, 219, 5, 90, 82, 107, 195, 127, 83, 186, 162, 237, 125, 3, 4, 31, 227, 180, 69, 20, 72, 105, 244, 16, 179, 169, 147, 30, 50, 52, 235, 33, 57, 24, 1, 54, 157, 135, 175, 145, 127, 224, 156, 243, 141, 157, 141, 237, 36, 37, 206, 171, 152, 152, 102, 65, 104, 102, 9, 46, 226, 216, 24, 24, 102, 79, 70, 125, 130, 84, 41, 168, 194, 147, 225, 43, 45, 11, 250, 68, 179, 137, 20, 68, 25, 232, 218, 86, 125, 214, 206, 120, 42, 201, 249, 39, 144, 9, 143, 50, 187, 136, 167, 19, 41, 255, 195, 233, 169, 245, 217, 246, 128, 48, 245, 221, 158, 176, 9, 229, 251, 193, 91, 189, 24, 147, 130, 17, 106, 243, 53, 157, 165, 16, 212, 183, 181, 138, 179, 15, 223, 45, 131, 48, 136, 219, 84, 157, 90, 180, 172, 103, 222, 187, 64, 44, 227, 157, 1, 115, 118, 57, 87, 87, 146, 63, 84, 208, 200, 49, 224, 151, 72, 253, 122, 203, 191, 166, 96, 125, 237, 103, 208, 48, 169, 190, 181, 46, 148, 68, 109, 178, 240, 207, 94, 235, 234, 131, 193, 187, 16, 31, 137, 93, 184, 45, 6, 0, 98, 105, 103, 88, 229, 252, 219, 19, 91, 118, 76, 78, 117, 137, 231, 68, 95, 82, 55, 27, 44, 159, 235, 21, 105, 240, 7, 200, 109, 227, 160, 46, 173, 199, 195, 237, 84, 7, 42, 16, 196, 14, 232, 183, 192, 244, 78, 165, 126, 204, 18, 249, 57, 198, 211, 212, 249, 95, 214, 17, 155, 193, 232, 96, 66, 105, 0, 255, 189, 255, 17, 65, 83, 215, 32, 12, 32, 152, 113, 155, 133, 164, 186, 7, 184, 126, 183, 164, 53, 165, 117, 126, 67, 116, 73, 123, 197, 16, 79][..], "fw window 9");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 29, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 28, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 9");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 9");
    }
    #[test]
    fn test_fw_10() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![245, 206, 32, 134, 225, 187, 45, 115, 20, 115, 95, 15, 98, 39, 56, 228, 19, 168, 206, 49, 42, 29, 229, 39, 177, 104, 180, 237, 189, 64, 29, 20, 43, 77, 208, 24, 193, 81, 249, 85, 171, 99, 75, 129, 106, 121, 168, 33, 202, 203, 210, 221, 28, 83, 116, 204, 70, 233, 200]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 49usize; strm.state.lookahead = 2usize; strm.state.insert = 2u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![32, 46, 13, 76, 80, 56, 56, 136, 219, 207, 100, 145, 12, 87, 69, 60, 107, 156, 175, 91, 225, 217, 143, 169, 112, 96, 237, 248, 176, 26, 110, 112, 49, 209, 71, 219, 189, 48, 26, 250, 242, 219, 10, 177, 193, 135, 85, 242, 182, 156, 180, 60, 154, 11, 229, 45, 146, 37, 160, 228, 25, 214, 58, 199, 62, 131, 224, 63, 239, 98, 199, 66, 150, 177, 231, 167, 27, 179, 73, 240, 116, 19, 121, 215, 127, 164, 6, 133, 174, 252, 178, 160, 251, 162, 219, 61, 134, 230, 220, 136, 62, 122, 148, 32, 106, 101, 56, 3, 66, 20, 198, 252, 232, 223, 115, 153, 160, 175, 60, 80, 232, 105, 14, 67, 84, 117, 203, 40, 87, 196, 206, 167, 66, 233, 16, 1, 238, 71, 118, 196, 14, 143, 238, 20, 180, 78, 229, 140, 233, 22, 10, 116, 162, 210, 59, 112, 110, 13, 247, 112, 50, 212, 66, 17, 0, 144, 23, 124, 214, 177, 154, 79, 14, 68, 209, 160, 30, 9, 110, 193, 200, 239, 211, 175, 246, 140, 127, 88, 98, 75, 249, 227, 176, 240, 124, 120, 254, 125, 156, 24, 11, 32, 188, 140, 50, 133, 206, 145, 23, 37, 56, 30, 201, 229, 204, 35, 155, 77, 110, 119, 217, 4, 250, 178, 144, 68, 234, 185, 131, 30, 26, 174, 163, 31, 56, 189, 141, 100, 13, 178, 176, 178, 184, 218, 217, 118, 58, 237, 87, 98, 133, 215, 203, 126, 206, 101, 38, 125, 107, 185, 241, 49, 1, 133]; strm.avail_in = 264usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 49usize, "fw strstart 10");
        assert_eq!(strm.state.lookahead, 266usize, "fw lookahead 10");
        assert_eq!(strm.state.insert, 0u32, "fw insert 10");
        assert_eq!(strm.state.ins_h, 10u32, "fw ins_h 10");
        assert_eq!(strm.state.high_water, 573u64, "fw high_water 10");
        assert_eq!(&strm.state.window[..315], &vec![245, 206, 32, 134, 225, 187, 45, 115, 20, 115, 95, 15, 98, 39, 56, 228, 19, 168, 206, 49, 42, 29, 229, 39, 177, 104, 180, 237, 189, 64, 29, 20, 43, 77, 208, 24, 193, 81, 249, 85, 171, 99, 75, 129, 106, 121, 168, 33, 202, 203, 210, 32, 46, 13, 76, 80, 56, 56, 136, 219, 207, 100, 145, 12, 87, 69, 60, 107, 156, 175, 91, 225, 217, 143, 169, 112, 96, 237, 248, 176, 26, 110, 112, 49, 209, 71, 219, 189, 48, 26, 250, 242, 219, 10, 177, 193, 135, 85, 242, 182, 156, 180, 60, 154, 11, 229, 45, 146, 37, 160, 228, 25, 214, 58, 199, 62, 131, 224, 63, 239, 98, 199, 66, 150, 177, 231, 167, 27, 179, 73, 240, 116, 19, 121, 215, 127, 164, 6, 133, 174, 252, 178, 160, 251, 162, 219, 61, 134, 230, 220, 136, 62, 122, 148, 32, 106, 101, 56, 3, 66, 20, 198, 252, 232, 223, 115, 153, 160, 175, 60, 80, 232, 105, 14, 67, 84, 117, 203, 40, 87, 196, 206, 167, 66, 233, 16, 1, 238, 71, 118, 196, 14, 143, 238, 20, 180, 78, 229, 140, 233, 22, 10, 116, 162, 210, 59, 112, 110, 13, 247, 112, 50, 212, 66, 17, 0, 144, 23, 124, 214, 177, 154, 79, 14, 68, 209, 160, 30, 9, 110, 193, 200, 239, 211, 175, 246, 140, 127, 88, 98, 75, 249, 227, 176, 240, 124, 120, 254, 125, 156, 24, 11, 32, 188, 140, 50, 133, 206, 145, 23, 37, 56, 30, 201, 229, 204, 35, 155, 77, 110, 119, 217, 4, 250, 178, 144, 68, 234, 185, 131, 30, 26, 174, 163, 31, 56, 189, 141, 100, 13, 178, 176, 178, 184, 218, 217, 118, 58, 237, 87, 98, 133, 215, 203, 126, 206, 101, 38, 125, 107, 185, 241, 49, 1, 133][..], "fw window 10");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 47, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 10");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 10");
    }
    #[test]
    fn test_fw_11() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.state.w_size = 512usize; strm.state.w_mask = 511usize; strm.state.window_size = 1024u32;
        strm.state.hash_size = 256u32; strm.state.hash_mask = 255u32; strm.state.hash_shift = 3u32; strm.state.hash_bits = 8u32;
        strm.state.wrap = 0i32;
        let mut window = vec![0u8; 1024]; { let wd: Vec<u8> = vec![156, 127, 156, 148, 171, 247, 243, 188, 217, 168, 66, 12, 127, 46, 173, 205, 194, 86, 192, 213, 226, 160, 66, 245, 146, 45, 168, 67, 6, 96, 246, 250, 185, 114, 194, 32, 223, 213, 86, 154, 120, 224, 83, 213, 96, 131, 150, 254, 171, 22, 116, 229, 121, 19, 11, 6, 120, 178, 175, 127, 119, 19, 173, 243, 96, 197, 167]; window[..wd.len()].copy_from_slice(&wd); } strm.state.window = window;
        strm.state.head = vec![0u16; 256]; strm.state.prev = vec![0u16; 512];
        strm.state.strstart = 55usize; strm.state.lookahead = 4usize; strm.state.insert = 0u32; strm.state.ins_h = 0u32; strm.state.block_start = 0i64; strm.state.high_water = 0u64; strm.state.match_start = 0usize;
        strm.next_in = vec![4, 86, 101, 69, 199, 55, 205, 19, 6, 143, 216, 22, 43, 79, 175, 156, 216, 178, 250, 33, 180, 106, 155, 111, 3, 46, 189, 4, 16, 5, 66, 20, 123, 38, 186, 163, 3, 56, 192, 139, 52, 68, 47, 247, 200, 252, 78, 20, 124, 102, 149, 145, 144, 245, 185, 154, 136, 227, 110, 104, 21, 21, 92, 4, 68, 248, 38, 49, 56, 37, 76, 188, 106, 121, 2, 22, 205, 204, 136, 132, 148, 19, 194, 123, 177, 139, 131, 148, 238, 136, 72, 185, 118, 7, 243, 98, 136, 218, 43, 240, 135, 89, 132, 57, 218, 30, 16, 22, 63, 240, 154, 31, 121, 248, 69, 122, 96, 6, 67, 199, 4, 53, 8, 233, 113, 118, 124, 223, 36, 156, 70, 205, 68, 24, 30, 145, 51, 72, 186, 110, 119, 214, 70, 47, 81, 194, 142, 223, 177, 63, 228, 52, 233, 216, 24, 49, 116, 236, 133, 167, 179, 242, 63, 249, 99, 223, 150, 188, 250, 211, 15, 101, 57, 250, 175, 33, 201, 136, 72, 64, 194, 217, 89, 99, 161, 175, 99, 211, 15, 11, 22, 229, 6, 179, 15, 143, 0, 204, 107, 114, 176, 115, 144, 12, 125, 178, 53, 72, 251, 45, 81]; strm.avail_in = 211usize; strm.total_in = 0; strm.adler = 0;
        super::fill_window(&mut strm);
        assert_eq!(strm.state.strstart, 55usize, "fw strstart 11");
        assert_eq!(strm.state.lookahead, 215usize, "fw lookahead 11");
        assert_eq!(strm.state.insert, 0u32, "fw insert 11");
        assert_eq!(strm.state.ins_h, 72u32, "fw ins_h 11");
        assert_eq!(strm.state.high_water, 528u64, "fw high_water 11");
        assert_eq!(&strm.state.window[..270], &vec![156, 127, 156, 148, 171, 247, 243, 188, 217, 168, 66, 12, 127, 46, 173, 205, 194, 86, 192, 213, 226, 160, 66, 245, 146, 45, 168, 67, 6, 96, 246, 250, 185, 114, 194, 32, 223, 213, 86, 154, 120, 224, 83, 213, 96, 131, 150, 254, 171, 22, 116, 229, 121, 19, 11, 6, 120, 178, 175, 4, 86, 101, 69, 199, 55, 205, 19, 6, 143, 216, 22, 43, 79, 175, 156, 216, 178, 250, 33, 180, 106, 155, 111, 3, 46, 189, 4, 16, 5, 66, 20, 123, 38, 186, 163, 3, 56, 192, 139, 52, 68, 47, 247, 200, 252, 78, 20, 124, 102, 149, 145, 144, 245, 185, 154, 136, 227, 110, 104, 21, 21, 92, 4, 68, 248, 38, 49, 56, 37, 76, 188, 106, 121, 2, 22, 205, 204, 136, 132, 148, 19, 194, 123, 177, 139, 131, 148, 238, 136, 72, 185, 118, 7, 243, 98, 136, 218, 43, 240, 135, 89, 132, 57, 218, 30, 16, 22, 63, 240, 154, 31, 121, 248, 69, 122, 96, 6, 67, 199, 4, 53, 8, 233, 113, 118, 124, 223, 36, 156, 70, 205, 68, 24, 30, 145, 51, 72, 186, 110, 119, 214, 70, 47, 81, 194, 142, 223, 177, 63, 228, 52, 233, 216, 24, 49, 116, 236, 133, 167, 179, 242, 63, 249, 99, 223, 150, 188, 250, 211, 15, 101, 57, 250, 175, 33, 201, 136, 72, 64, 194, 217, 89, 99, 161, 175, 99, 211, 15, 11, 22, 229, 6, 179, 15, 143, 0, 204, 107, 114, 176, 115, 144, 12, 125, 178, 53, 72, 251, 45, 81][..], "fw window 11");
        assert_eq!(strm.state.head, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw head 11");
        assert_eq!(strm.state.prev, vec![0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "fw prev 11");
    }


    #[test]
    fn test_rb_0() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![24, 37, 48, 187, 29, 109, 19, 44, 222, 214, 35, 123, 46, 217, 30, 63, 114, 31, 203, 25, 113, 23, 68, 148, 214, 73, 60, 157, 92, 52, 96, 190, 49, 32, 30, 105, 254, 218, 160, 238, 232, 185, 153, 127, 92, 124, 41, 153, 253, 175, 229, 147, 37, 60, 214, 84, 175, 77, 250, 215, 20, 39, 160, 174, 179, 254, 233, 35, 47, 138, 242, 33, 31, 158, 228, 145, 197, 177, 11, 236, 181, 86]; strm.avail_in = 82usize; strm.total_in = 0; strm.adler = 1u32; strm.state.wrap = 1i32;
        let mut buf = vec![0u8; 38];
        let ret = super::read_buf(&mut strm, &mut buf, 38usize);
        assert_eq!(ret, 38usize, "rb ret 0");
        assert_eq!(&buf[..ret], &vec![24, 37, 48, 187, 29, 109, 19, 44, 222, 214, 35, 123, 46, 217, 30, 63, 114, 31, 203, 25, 113, 23, 68, 148, 214, 73, 60, 157, 92, 52, 96, 190, 49, 32, 30, 105, 254, 218][..], "rb out 0");
        assert_eq!(strm.avail_in, 44usize, "rb avail 0");
        assert_eq!(strm.total_in, 38u64, "rb total 0");
        assert_eq!(strm.adler, 164040403u32, "rb adler 0");
        assert_eq!(strm.next_in, vec![160, 238, 232, 185, 153, 127, 92, 124, 41, 153, 253, 175, 229, 147, 37, 60, 214, 84, 175, 77, 250, 215, 20, 39, 160, 174, 179, 254, 233, 35, 47, 138, 242, 33, 31, 158, 228, 145, 197, 177, 11, 236, 181, 86], "rb next_in 0");
    }
    #[test]
    fn test_rb_1() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![78, 135, 117, 247, 239, 170, 21, 47, 94, 78, 199, 23, 122, 4, 211, 85, 66, 156, 76, 24, 55, 154, 76, 10, 112, 150, 123, 140, 33, 113, 65, 131, 104, 100, 62, 163, 252, 187, 192, 44, 49, 17, 12, 46, 41, 89, 199, 161, 199, 198, 86, 172, 171, 235, 39, 196, 12, 225, 130, 68, 57, 115, 213, 45, 220, 23, 246, 8, 218, 55, 16, 105, 34, 95, 191, 215, 252, 71]; strm.avail_in = 78usize; strm.total_in = 0; strm.adler = 0u32; strm.state.wrap = 2i32;
        let mut buf = vec![0u8; 72];
        let ret = super::read_buf(&mut strm, &mut buf, 72usize);
        assert_eq!(ret, 72usize, "rb ret 1");
        assert_eq!(&buf[..ret], &vec![78, 135, 117, 247, 239, 170, 21, 47, 94, 78, 199, 23, 122, 4, 211, 85, 66, 156, 76, 24, 55, 154, 76, 10, 112, 150, 123, 140, 33, 113, 65, 131, 104, 100, 62, 163, 252, 187, 192, 44, 49, 17, 12, 46, 41, 89, 199, 161, 199, 198, 86, 172, 171, 235, 39, 196, 12, 225, 130, 68, 57, 115, 213, 45, 220, 23, 246, 8, 218, 55, 16, 105][..], "rb out 1");
        assert_eq!(strm.avail_in, 6usize, "rb avail 1");
        assert_eq!(strm.total_in, 72u64, "rb total 1");
        assert_eq!(strm.adler, 3690913200u32, "rb adler 1");
        assert_eq!(strm.next_in, vec![34, 95, 191, 215, 252, 71], "rb next_in 1");
    }
    #[test]
    fn test_rb_2() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![140, 9, 244, 178, 122, 223, 15]; strm.avail_in = 7usize; strm.total_in = 0; strm.adler = 0u32; strm.state.wrap = 2i32;
        let mut buf = vec![0u8; 167];
        let ret = super::read_buf(&mut strm, &mut buf, 167usize);
        assert_eq!(ret, 7usize, "rb ret 2");
        assert_eq!(&buf[..ret], &vec![140, 9, 244, 178, 122, 223, 15][..], "rb out 2");
        assert_eq!(strm.avail_in, 0usize, "rb avail 2");
        assert_eq!(strm.total_in, 7u64, "rb total 2");
        assert_eq!(strm.adler, 811816827u32, "rb adler 2");
        assert_eq!(strm.next_in, vec![], "rb next_in 2");
    }
    #[test]
    fn test_rb_3() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![208, 219, 6, 167, 17, 249, 188, 148, 102, 87, 5, 255, 49, 96, 197, 63, 0, 83, 136, 111, 248, 81, 163, 231, 140, 106, 81, 120, 239, 25, 135, 238, 137, 82, 155, 12, 54, 253, 41, 125, 2, 217, 190, 160, 252]; strm.avail_in = 45usize; strm.total_in = 0; strm.adler = 0u32; strm.state.wrap = 2i32;
        let mut buf = vec![0u8; 161];
        let ret = super::read_buf(&mut strm, &mut buf, 161usize);
        assert_eq!(ret, 45usize, "rb ret 3");
        assert_eq!(&buf[..ret], &vec![208, 219, 6, 167, 17, 249, 188, 148, 102, 87, 5, 255, 49, 96, 197, 63, 0, 83, 136, 111, 248, 81, 163, 231, 140, 106, 81, 120, 239, 25, 135, 238, 137, 82, 155, 12, 54, 253, 41, 125, 2, 217, 190, 160, 252][..], "rb out 3");
        assert_eq!(strm.avail_in, 0usize, "rb avail 3");
        assert_eq!(strm.total_in, 45u64, "rb total 3");
        assert_eq!(strm.adler, 758210408u32, "rb adler 3");
        assert_eq!(strm.next_in, vec![], "rb next_in 3");
    }
    #[test]
    fn test_rb_4() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![20, 168, 52, 146, 223, 173, 147, 242, 20, 68, 28, 224, 186, 69, 76, 67, 20, 137, 168, 203, 161, 36, 50, 250, 164, 188, 188, 166, 11, 26, 6, 63, 159, 214, 6, 58, 22, 183, 185, 213, 45, 20, 40, 231, 191, 179, 83, 173, 62, 202, 192, 224, 9, 7, 114, 52, 149, 5, 237, 93, 94, 92, 44, 136, 216, 201, 170, 112, 208, 127, 120, 217, 93, 106, 68, 9, 191, 77, 37, 126, 18, 244, 49, 211, 21, 32, 38, 216, 219, 180, 106, 232, 128, 144, 42, 187, 46, 18, 17, 116, 197, 105, 175, 92, 204, 232, 157, 187, 99, 123, 151, 107, 138, 124, 172, 155, 110, 118, 78, 20, 4, 198, 240, 177, 81, 239, 58, 0, 177, 180, 225, 1, 148, 32, 145, 146, 172, 18, 207, 241, 103, 167, 133, 99, 35, 114, 245, 169, 172, 179, 120, 202, 47, 47, 128, 178, 239, 51, 201, 184, 162, 162, 141, 93, 140, 246, 234, 172, 118, 66, 43, 131, 38, 104, 88, 107, 131, 104]; strm.avail_in = 178usize; strm.total_in = 0; strm.adler = 1u32; strm.state.wrap = 1i32;
        let mut buf = vec![0u8; 163];
        let ret = super::read_buf(&mut strm, &mut buf, 163usize);
        assert_eq!(ret, 163usize, "rb ret 4");
        assert_eq!(&buf[..ret], &vec![20, 168, 52, 146, 223, 173, 147, 242, 20, 68, 28, 224, 186, 69, 76, 67, 20, 137, 168, 203, 161, 36, 50, 250, 164, 188, 188, 166, 11, 26, 6, 63, 159, 214, 6, 58, 22, 183, 185, 213, 45, 20, 40, 231, 191, 179, 83, 173, 62, 202, 192, 224, 9, 7, 114, 52, 149, 5, 237, 93, 94, 92, 44, 136, 216, 201, 170, 112, 208, 127, 120, 217, 93, 106, 68, 9, 191, 77, 37, 126, 18, 244, 49, 211, 21, 32, 38, 216, 219, 180, 106, 232, 128, 144, 42, 187, 46, 18, 17, 116, 197, 105, 175, 92, 204, 232, 157, 187, 99, 123, 151, 107, 138, 124, 172, 155, 110, 118, 78, 20, 4, 198, 240, 177, 81, 239, 58, 0, 177, 180, 225, 1, 148, 32, 145, 146, 172, 18, 207, 241, 103, 167, 133, 99, 35, 114, 245, 169, 172, 179, 120, 202, 47, 47, 128, 178, 239, 51, 201, 184, 162, 162, 141][..], "rb out 4");
        assert_eq!(strm.avail_in, 15usize, "rb avail 4");
        assert_eq!(strm.total_in, 163u64, "rb total 4");
        assert_eq!(strm.adler, 3393212450u32, "rb adler 4");
        assert_eq!(strm.next_in, vec![93, 140, 246, 234, 172, 118, 66, 43, 131, 38, 104, 88, 107, 131, 104], "rb next_in 4");
    }
    #[test]
    fn test_rb_5() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![188, 140, 92, 174, 86, 203, 11, 121, 100, 182, 69, 125, 117, 70, 241, 32, 239, 229, 210, 103, 78, 47, 197, 95, 170, 170, 233, 40, 232, 233, 222, 176, 13, 156, 112, 10, 60, 12, 229, 146, 76, 97, 162, 249, 63, 79, 16, 169, 16, 210, 170, 133, 16, 148, 96, 144, 114, 65, 211, 8, 207, 112, 133, 217, 242, 64, 253, 142, 178, 107, 79, 124, 8, 136, 74, 175, 133, 244, 102, 207, 25, 123, 166, 30, 98, 208, 211, 12, 169, 156, 211, 201, 242, 140, 248, 89, 184, 254, 216, 147, 96, 86, 70, 0, 60, 172, 240, 7, 191, 104, 80, 214, 58, 127, 138, 141, 153, 150, 70, 68, 35, 165]; strm.avail_in = 122usize; strm.total_in = 0; strm.adler = 2139554606u32; strm.state.wrap = 0i32;
        let mut buf = vec![0u8; 91];
        let ret = super::read_buf(&mut strm, &mut buf, 91usize);
        assert_eq!(ret, 91usize, "rb ret 5");
        assert_eq!(&buf[..ret], &vec![188, 140, 92, 174, 86, 203, 11, 121, 100, 182, 69, 125, 117, 70, 241, 32, 239, 229, 210, 103, 78, 47, 197, 95, 170, 170, 233, 40, 232, 233, 222, 176, 13, 156, 112, 10, 60, 12, 229, 146, 76, 97, 162, 249, 63, 79, 16, 169, 16, 210, 170, 133, 16, 148, 96, 144, 114, 65, 211, 8, 207, 112, 133, 217, 242, 64, 253, 142, 178, 107, 79, 124, 8, 136, 74, 175, 133, 244, 102, 207, 25, 123, 166, 30, 98, 208, 211, 12, 169, 156, 211][..], "rb out 5");
        assert_eq!(strm.avail_in, 31usize, "rb avail 5");
        assert_eq!(strm.total_in, 91u64, "rb total 5");
        assert_eq!(strm.adler, 2139554606u32, "rb adler 5");
        assert_eq!(strm.next_in, vec![201, 242, 140, 248, 89, 184, 254, 216, 147, 96, 86, 70, 0, 60, 172, 240, 7, 191, 104, 80, 214, 58, 127, 138, 141, 153, 150, 70, 68, 35, 165], "rb next_in 5");
    }
    #[test]
    fn test_rb_6() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![37, 87, 182, 124, 121, 123, 61, 11, 41, 56, 71, 99, 228, 240, 102, 46, 3, 255, 96, 139, 28, 195, 183, 246, 43, 40, 188, 111, 22, 195, 163, 164, 160, 248, 202, 121, 147, 225, 162, 189, 232, 44, 138, 189, 164, 100, 122, 70, 171, 241, 93, 38, 250, 136, 217, 211, 43, 205, 233, 118, 154, 29, 101, 33, 6, 55, 14, 47, 120, 205, 135, 175, 91, 125, 5, 191, 245, 116, 169, 55, 34, 21, 107, 152, 178, 194, 81, 188, 112, 186, 90, 87, 117, 84, 65, 37, 18, 35, 129, 97, 132, 254, 24, 29, 37, 104, 247, 54, 25, 205, 218, 55, 42, 140, 244, 216, 108, 45, 111, 235, 54, 136, 145, 207, 240, 43, 239, 147, 96, 110, 219, 90, 156, 177, 133, 6, 169, 65, 206, 122]; strm.avail_in = 140usize; strm.total_in = 0; strm.adler = 2423003282u32; strm.state.wrap = 0i32;
        let mut buf = vec![0u8; 218];
        let ret = super::read_buf(&mut strm, &mut buf, 218usize);
        assert_eq!(ret, 140usize, "rb ret 6");
        assert_eq!(&buf[..ret], &vec![37, 87, 182, 124, 121, 123, 61, 11, 41, 56, 71, 99, 228, 240, 102, 46, 3, 255, 96, 139, 28, 195, 183, 246, 43, 40, 188, 111, 22, 195, 163, 164, 160, 248, 202, 121, 147, 225, 162, 189, 232, 44, 138, 189, 164, 100, 122, 70, 171, 241, 93, 38, 250, 136, 217, 211, 43, 205, 233, 118, 154, 29, 101, 33, 6, 55, 14, 47, 120, 205, 135, 175, 91, 125, 5, 191, 245, 116, 169, 55, 34, 21, 107, 152, 178, 194, 81, 188, 112, 186, 90, 87, 117, 84, 65, 37, 18, 35, 129, 97, 132, 254, 24, 29, 37, 104, 247, 54, 25, 205, 218, 55, 42, 140, 244, 216, 108, 45, 111, 235, 54, 136, 145, 207, 240, 43, 239, 147, 96, 110, 219, 90, 156, 177, 133, 6, 169, 65, 206, 122][..], "rb out 6");
        assert_eq!(strm.avail_in, 0usize, "rb avail 6");
        assert_eq!(strm.total_in, 140u64, "rb total 6");
        assert_eq!(strm.adler, 2423003282u32, "rb adler 6");
        assert_eq!(strm.next_in, vec![], "rb next_in 6");
    }
    #[test]
    fn test_rb_7() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![207, 232, 74, 225, 218]; strm.avail_in = 5usize; strm.total_in = 0; strm.adler = 0u32; strm.state.wrap = 2i32;
        let mut buf = vec![0u8; 74];
        let ret = super::read_buf(&mut strm, &mut buf, 74usize);
        assert_eq!(ret, 5usize, "rb ret 7");
        assert_eq!(&buf[..ret], &vec![207, 232, 74, 225, 218][..], "rb out 7");
        assert_eq!(strm.avail_in, 0usize, "rb avail 7");
        assert_eq!(strm.total_in, 5u64, "rb total 7");
        assert_eq!(strm.adler, 3804369073u32, "rb adler 7");
        assert_eq!(strm.next_in, vec![], "rb next_in 7");
    }
    #[test]
    fn test_rb_8() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![0, 219, 80, 111, 102, 218, 127, 181, 46, 150, 202, 36, 39, 76, 192, 33, 85, 89, 238, 177, 93, 39, 69, 130, 189, 187, 147, 21, 221, 97, 45, 241, 79, 22, 250, 146, 242, 206, 216, 60, 0, 28, 105, 155, 38, 131, 82, 200, 242, 116, 35, 133, 121, 14, 60, 201, 128, 106, 79, 191, 229, 39, 234, 154, 173, 85, 216, 7, 118, 51, 148, 254, 240, 150]; strm.avail_in = 74usize; strm.total_in = 0; strm.adler = 3377496303u32; strm.state.wrap = 0i32;
        let mut buf = vec![0u8; 198];
        let ret = super::read_buf(&mut strm, &mut buf, 198usize);
        assert_eq!(ret, 74usize, "rb ret 8");
        assert_eq!(&buf[..ret], &vec![0, 219, 80, 111, 102, 218, 127, 181, 46, 150, 202, 36, 39, 76, 192, 33, 85, 89, 238, 177, 93, 39, 69, 130, 189, 187, 147, 21, 221, 97, 45, 241, 79, 22, 250, 146, 242, 206, 216, 60, 0, 28, 105, 155, 38, 131, 82, 200, 242, 116, 35, 133, 121, 14, 60, 201, 128, 106, 79, 191, 229, 39, 234, 154, 173, 85, 216, 7, 118, 51, 148, 254, 240, 150][..], "rb out 8");
        assert_eq!(strm.avail_in, 0usize, "rb avail 8");
        assert_eq!(strm.total_in, 74u64, "rb total 8");
        assert_eq!(strm.adler, 3377496303u32, "rb adler 8");
        assert_eq!(strm.next_in, vec![], "rb next_in 8");
    }
    #[test]
    fn test_rb_9() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![166, 20, 48, 234, 125, 57, 138, 47, 108, 192, 219, 171, 205, 189, 70, 170, 174, 65, 65, 207, 194, 99, 24, 189, 2, 117, 96, 194, 7, 184, 233, 244, 92, 182, 235, 192, 190, 96, 25, 244, 30, 156, 126, 50, 49, 209, 104, 41, 63, 112, 15, 74, 160, 60, 122, 41, 188, 62, 180, 139, 7, 194, 161, 190, 6, 140, 14, 136, 188, 10, 249, 3, 117, 153, 76, 219, 18, 234, 59, 53, 119, 11, 121, 130, 33, 176, 103, 77, 114, 85, 179, 89, 2, 58, 250, 85, 236, 77, 211, 116, 208, 252, 41, 211, 80, 174, 44, 89, 142, 95, 4, 55, 119, 14, 189, 0, 245, 194, 10, 166, 255, 143, 206, 213, 224, 172, 139, 34, 130, 199, 55, 100, 131, 185, 70, 26, 58, 212, 12, 171, 89, 193, 174, 142, 203, 222]; strm.avail_in = 146usize; strm.total_in = 0; strm.adler = 1u32; strm.state.wrap = 1i32;
        let mut buf = vec![0u8; 40];
        let ret = super::read_buf(&mut strm, &mut buf, 40usize);
        assert_eq!(ret, 40usize, "rb ret 9");
        assert_eq!(&buf[..ret], &vec![166, 20, 48, 234, 125, 57, 138, 47, 108, 192, 219, 171, 205, 189, 70, 170, 174, 65, 65, 207, 194, 99, 24, 189, 2, 117, 96, 194, 7, 184, 233, 244, 92, 182, 235, 192, 190, 96, 25, 244][..], "rb out 9");
        assert_eq!(strm.avail_in, 106usize, "rb avail 9");
        assert_eq!(strm.total_in, 40u64, "rb total 9");
        assert_eq!(strm.adler, 2744128902u32, "rb adler 9");
        assert_eq!(strm.next_in, vec![30, 156, 126, 50, 49, 209, 104, 41, 63, 112, 15, 74, 160, 60, 122, 41, 188, 62, 180, 139, 7, 194, 161, 190, 6, 140, 14, 136, 188, 10, 249, 3, 117, 153, 76, 219, 18, 234, 59, 53, 119, 11, 121, 130, 33, 176, 103, 77, 114, 85, 179, 89, 2, 58, 250, 85, 236, 77, 211, 116, 208, 252, 41, 211, 80, 174, 44, 89, 142, 95, 4, 55, 119, 14, 189, 0, 245, 194, 10, 166, 255, 143, 206, 213, 224, 172, 139, 34, 130, 199, 55, 100, 131, 185, 70, 26, 58, 212, 12, 171, 89, 193, 174, 142, 203, 222], "rb next_in 9");
    }
    #[test]
    fn test_rb_10() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![235, 220, 70, 143, 161, 29, 212, 200, 253, 181, 35, 51, 136, 100, 117, 72, 151, 194, 6, 106, 206, 254, 167, 108, 105, 172, 90, 118, 149, 20, 178, 70, 21, 202, 223, 101, 185, 226, 100, 76, 57, 25, 89, 84, 212, 105, 116, 116, 219, 12, 127, 138, 24, 124, 170, 122, 80, 175, 27, 0, 206, 103, 10, 91, 104, 145, 187, 119, 218, 64, 32, 63, 51, 243, 133, 12, 193, 87, 157, 183, 167, 4, 224, 144, 39, 110, 247, 233, 145, 235, 91, 94, 127, 252, 103, 165, 102, 99, 110, 59, 228, 237, 134, 158, 177, 211, 197, 215, 254, 82, 94, 160, 127, 162, 89, 47, 206, 92, 27, 135, 34, 105, 136, 136, 43, 29, 226, 102, 232, 248, 71, 185, 26, 148, 108, 94, 25, 184, 101, 79, 108, 60, 9, 63, 21, 215, 239, 210, 230, 57, 24, 206, 128, 155, 52, 102, 124, 141, 132, 146, 70, 213, 44, 207, 55, 207, 88, 162, 9, 220, 14, 253, 215, 66, 35, 82, 139, 187, 5, 53, 77, 207, 27, 148, 79, 185]; strm.avail_in = 186usize; strm.total_in = 0; strm.adler = 958115059u32; strm.state.wrap = 0i32;
        let mut buf = vec![0u8; 113];
        let ret = super::read_buf(&mut strm, &mut buf, 113usize);
        assert_eq!(ret, 113usize, "rb ret 10");
        assert_eq!(&buf[..ret], &vec![235, 220, 70, 143, 161, 29, 212, 200, 253, 181, 35, 51, 136, 100, 117, 72, 151, 194, 6, 106, 206, 254, 167, 108, 105, 172, 90, 118, 149, 20, 178, 70, 21, 202, 223, 101, 185, 226, 100, 76, 57, 25, 89, 84, 212, 105, 116, 116, 219, 12, 127, 138, 24, 124, 170, 122, 80, 175, 27, 0, 206, 103, 10, 91, 104, 145, 187, 119, 218, 64, 32, 63, 51, 243, 133, 12, 193, 87, 157, 183, 167, 4, 224, 144, 39, 110, 247, 233, 145, 235, 91, 94, 127, 252, 103, 165, 102, 99, 110, 59, 228, 237, 134, 158, 177, 211, 197, 215, 254, 82, 94, 160, 127][..], "rb out 10");
        assert_eq!(strm.avail_in, 73usize, "rb avail 10");
        assert_eq!(strm.total_in, 113u64, "rb total 10");
        assert_eq!(strm.adler, 958115059u32, "rb adler 10");
        assert_eq!(strm.next_in, vec![162, 89, 47, 206, 92, 27, 135, 34, 105, 136, 136, 43, 29, 226, 102, 232, 248, 71, 185, 26, 148, 108, 94, 25, 184, 101, 79, 108, 60, 9, 63, 21, 215, 239, 210, 230, 57, 24, 206, 128, 155, 52, 102, 124, 141, 132, 146, 70, 213, 44, 207, 55, 207, 88, 162, 9, 220, 14, 253, 215, 66, 35, 82, 139, 187, 5, 53, 77, 207, 27, 148, 79, 185], "rb next_in 10");
    }
    #[test]
    fn test_rb_11() {
        let mut strm = zlib_types::DeflateStream::default();
        strm.next_in = vec![249, 204, 216, 177, 77, 248]; strm.avail_in = 6usize; strm.total_in = 0; strm.adler = 0u32; strm.state.wrap = 2i32;
        let mut buf = vec![0u8; 12];
        let ret = super::read_buf(&mut strm, &mut buf, 12usize);
        assert_eq!(ret, 6usize, "rb ret 11");
        assert_eq!(&buf[..ret], &vec![249, 204, 216, 177, 77, 248][..], "rb out 11");
        assert_eq!(strm.avail_in, 0usize, "rb avail 11");
        assert_eq!(strm.total_in, 6u64, "rb total 11");
        assert_eq!(strm.adler, 2121769631u32, "rb adler 11");
        assert_eq!(strm.next_in, vec![], "rb next_in 11");
    }

    #[test]
    fn test_slide_hash_state_0() {
        let mut state = zlib_types::DeflateState::default();
        state.w_size = 16usize;
        state.head = vec![37749u16, 24376u16, 38993u16, 44384u16, 31721u16, 12495u16, 45574u16, 53338u16, 56083u16, 35864u16, 13424u16, 56924u16, 28952u16, 52256u16, 11010u16, 11039u16];
        state.prev = vec![34085u16, 41036u16, 30426u16, 39252u16, 63176u16, 11574u16, 47562u16, 43014u16, 38276u16, 28315u16, 19713u16, 41990u16, 53962u16, 20059u16, 35824u16, 36630u16];
        super::slide_hash(&mut state);
        assert_eq!(state.w_size, 16usize, "c_shim_fuzz_0 field w_size");
        assert_eq!(state.head, vec![37733u16, 24360u16, 38977u16, 44368u16, 31705u16, 12479u16, 45558u16, 53322u16, 56067u16, 35848u16, 13408u16, 56908u16, 28936u16, 52240u16, 10994u16, 11023u16], "c_shim_fuzz_0 field head");
        assert_eq!(state.prev, vec![34069u16, 41020u16, 30410u16, 39236u16, 63160u16, 11558u16, 47546u16, 42998u16, 38260u16, 28299u16, 19697u16, 41974u16, 53946u16, 20043u16, 35808u16, 36614u16], "c_shim_fuzz_0 field prev");
    }

    #[test]
    fn test_slide_hash_state_1() {
        let mut state = zlib_types::DeflateState::default();
        state.w_size = 16usize;
        state.head = vec![2423u16, 64954u16, 32146u16, 14649u16, 13829u16, 60269u16, 53415u16, 43487u16, 3831u16, 7007u16, 9253u16, 18485u16, 33420u16, 54128u16, 58785u16, 38720u16];
        state.prev = vec![14799u16, 21450u16, 41527u16, 50492u16, 8266u16, 51718u16, 11753u16, 2148u16, 62038u16, 39968u16, 57078u16, 56185u16, 34200u16, 21527u16, 15698u16, 48370u16];
        super::slide_hash(&mut state);
        assert_eq!(state.w_size, 16usize, "c_shim_fuzz_1 field w_size");
        assert_eq!(state.head, vec![2407u16, 64938u16, 32130u16, 14633u16, 13813u16, 60253u16, 53399u16, 43471u16, 3815u16, 6991u16, 9237u16, 18469u16, 33404u16, 54112u16, 58769u16, 38704u16], "c_shim_fuzz_1 field head");
        assert_eq!(state.prev, vec![14783u16, 21434u16, 41511u16, 50476u16, 8250u16, 51702u16, 11737u16, 2132u16, 62022u16, 39952u16, 57062u16, 56169u16, 34184u16, 21511u16, 15682u16, 48354u16], "c_shim_fuzz_1 field prev");
    }

    #[test]
    fn test_slide_hash_state_2() {
        let mut state = zlib_types::DeflateState::default();
        state.w_size = 16usize;
        state.head = vec![49975u16, 12391u16, 18861u16, 39316u16, 52496u16, 56036u16, 24998u16, 47681u16, 59979u16, 23304u16, 12344u16, 6830u16, 36912u16, 6614u16, 870u16, 11505u16];
        state.prev = vec![3667u16, 7033u16, 26704u16, 10656u16, 20218u16, 65510u16, 63101u16, 2871u16, 6656u16, 5357u16, 21365u16, 65318u16, 14642u16, 16774u16, 47397u16, 8076u16];
        super::slide_hash(&mut state);
        assert_eq!(state.w_size, 16usize, "c_shim_fuzz_2 field w_size");
        assert_eq!(state.head, vec![49959u16, 12375u16, 18845u16, 39300u16, 52480u16, 56020u16, 24982u16, 47665u16, 59963u16, 23288u16, 12328u16, 6814u16, 36896u16, 6598u16, 854u16, 11489u16], "c_shim_fuzz_2 field head");
        assert_eq!(state.prev, vec![3651u16, 7017u16, 26688u16, 10640u16, 20202u16, 65494u16, 63085u16, 2855u16, 6640u16, 5341u16, 21349u16, 65302u16, 14626u16, 16758u16, 47381u16, 8060u16], "c_shim_fuzz_2 field prev");
    }

    #[test]
    fn test_slide_hash_state_3() {
        let mut state = zlib_types::DeflateState::default();
        state.w_size = 16usize;
        state.head = vec![40565u16, 11474u16, 34067u16, 63771u16, 61843u16, 5917u16, 12134u16, 51896u16, 38403u16, 41918u16, 37662u16, 49128u16, 30249u16, 53653u16, 34379u16, 11100u16];
        state.prev = vec![52676u16, 47059u16, 42689u16, 22585u16, 26548u16, 61561u16, 12625u16, 58652u16, 51580u16, 21067u16, 50524u16, 26924u16, 29241u16, 59796u16, 64582u16, 444u16];
        super::slide_hash(&mut state);
        assert_eq!(state.w_size, 16usize, "c_shim_fuzz_3 field w_size");
        assert_eq!(state.head, vec![40549u16, 11458u16, 34051u16, 63755u16, 61827u16, 5901u16, 12118u16, 51880u16, 38387u16, 41902u16, 37646u16, 49112u16, 30233u16, 53637u16, 34363u16, 11084u16], "c_shim_fuzz_3 field head");
        assert_eq!(state.prev, vec![52660u16, 47043u16, 42673u16, 22569u16, 26532u16, 61545u16, 12609u16, 58636u16, 51564u16, 21051u16, 50508u16, 26908u16, 29225u16, 59780u16, 64566u16, 428u16], "c_shim_fuzz_3 field prev");
    }

    #[test]
    fn test_slide_hash_state_4() {
        let mut state = zlib_types::DeflateState::default();
        state.w_size = 16usize;
        state.head = vec![4770u16, 36746u16, 63315u16, 47488u16, 52344u16, 25666u16, 30184u16, 26199u16, 22369u16, 49505u16, 58032u16, 8887u16, 36113u16, 57878u16, 47590u16, 58784u16];
        state.prev = vec![43756u16, 61043u16, 11029u16, 62389u16, 51933u16, 64696u16, 43891u16, 30175u16, 13887u16, 24952u16, 30816u16, 17039u16, 19011u16, 63207u16, 33629u16, 50514u16];
        super::slide_hash(&mut state);
        assert_eq!(state.w_size, 16usize, "c_shim_fuzz_4 field w_size");
        assert_eq!(state.head, vec![4754u16, 36730u16, 63299u16, 47472u16, 52328u16, 25650u16, 30168u16, 26183u16, 22353u16, 49489u16, 58016u16, 8871u16, 36097u16, 57862u16, 47574u16, 58768u16], "c_shim_fuzz_4 field head");
        assert_eq!(state.prev, vec![43740u16, 61027u16, 11013u16, 62373u16, 51917u16, 64680u16, 43875u16, 30159u16, 13871u16, 24936u16, 30800u16, 17023u16, 18995u16, 63191u16, 33613u16, 50498u16], "c_shim_fuzz_4 field prev");
    }

    #[test]
    fn test_slide_hash_state_5() {
        let mut state = zlib_types::DeflateState::default();
        state.w_size = 16usize;
        state.head = vec![15334u16, 45135u16, 27958u16, 12000u16, 43139u16, 7576u16, 39355u16, 2106u16, 15196u16, 59069u16, 62670u16, 43044u16, 20609u16, 57292u16, 19512u16, 29468u16];
        state.prev = vec![31753u16, 62994u16, 40626u16, 35281u16, 53494u16, 54453u16, 6505u16, 9259u16, 13579u16, 22777u16, 17881u16, 35375u16, 13563u16, 32685u16, 21938u16, 28190u16];
        super::slide_hash(&mut state);
        assert_eq!(state.w_size, 16usize, "c_shim_fuzz_5 field w_size");
        assert_eq!(state.head, vec![15318u16, 45119u16, 27942u16, 11984u16, 43123u16, 7560u16, 39339u16, 2090u16, 15180u16, 59053u16, 62654u16, 43028u16, 20593u16, 57276u16, 19496u16, 29452u16], "c_shim_fuzz_5 field head");
        assert_eq!(state.prev, vec![31737u16, 62978u16, 40610u16, 35265u16, 53478u16, 54437u16, 6489u16, 9243u16, 13563u16, 22761u16, 17865u16, 35359u16, 13547u16, 32669u16, 21922u16, 28174u16], "c_shim_fuzz_5 field prev");
    }

    #[test]
    fn test_slide_hash_state_6() {
        let mut state = zlib_types::DeflateState::default();
        state.w_size = 16usize;
        state.head = vec![10648u16, 20230u16, 27041u16, 36263u16, 48984u16, 61721u16, 59087u16, 47445u16, 42262u16, 55021u16, 28168u16, 18446u16, 59994u16, 40183u16, 32875u16, 20192u16];
        state.prev = vec![61635u16, 53928u16, 58114u16, 51003u16, 47335u16, 55901u16, 14834u16, 15431u16, 23545u16, 21860u16, 39839u16, 23u16, 64413u16, 38048u16, 29831u16, 55567u16];
        super::slide_hash(&mut state);
        assert_eq!(state.w_size, 16usize, "c_shim_fuzz_6 field w_size");
        assert_eq!(state.head, vec![10632u16, 20214u16, 27025u16, 36247u16, 48968u16, 61705u16, 59071u16, 47429u16, 42246u16, 55005u16, 28152u16, 18430u16, 59978u16, 40167u16, 32859u16, 20176u16], "c_shim_fuzz_6 field head");
        assert_eq!(state.prev, vec![61619u16, 53912u16, 58098u16, 50987u16, 47319u16, 55885u16, 14818u16, 15415u16, 23529u16, 21844u16, 39823u16, 7u16, 64397u16, 38032u16, 29815u16, 55551u16], "c_shim_fuzz_6 field prev");
    }

    #[test]
    fn test_slide_hash_state_7() {
        let mut state = zlib_types::DeflateState::default();
        state.w_size = 16usize;
        state.head = vec![39463u16, 2499u16, 54614u16, 37447u16, 42193u16, 6748u16, 10887u16, 8482u16, 34434u16, 47792u16, 40724u16, 37565u16, 14733u16, 27537u16, 19399u16, 7489u16];
        state.prev = vec![53863u16, 63220u16, 60846u16, 28668u16, 21617u16, 4651u16, 60652u16, 961u16, 62839u16, 16190u16, 29324u16, 56651u16, 60112u16, 43431u16, 41596u16, 27006u16];
        super::slide_hash(&mut state);
        assert_eq!(state.w_size, 16usize, "c_shim_fuzz_7 field w_size");
        assert_eq!(state.head, vec![39447u16, 2483u16, 54598u16, 37431u16, 42177u16, 6732u16, 10871u16, 8466u16, 34418u16, 47776u16, 40708u16, 37549u16, 14717u16, 27521u16, 19383u16, 7473u16], "c_shim_fuzz_7 field head");
        assert_eq!(state.prev, vec![53847u16, 63204u16, 60830u16, 28652u16, 21601u16, 4635u16, 60636u16, 945u16, 62823u16, 16174u16, 29308u16, 56635u16, 60096u16, 43415u16, 41580u16, 26990u16], "c_shim_fuzz_7 field prev");
    }

    #[test]
    fn test_zlib_compile_flags_spec_0() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_0");
    }

    #[test]
    fn test_zlib_compile_flags_spec_1() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_1");
    }

    #[test]
    fn test_zlib_compile_flags_spec_2() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_1");
    }

    #[test]
    fn test_zlib_compile_flags_spec_3() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_1");
    }

    #[test]
    fn test_zlib_compile_flags_spec_4() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_2");
    }

    #[test]
    fn test_zlib_compile_flags_spec_5() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_3");
    }

    #[test]
    fn test_zlib_compile_flags_spec_6() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_16");
    }

    #[test]
    fn test_zlib_compile_flags_spec_7() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_16");
    }

    #[test]
    fn test_zlib_compile_flags_spec_8() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_43");
    }

    #[test]
    fn test_zlib_compile_flags_spec_9() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_256");
    }

    #[test]
    fn test_zlib_compile_flags_spec_10() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_1");
    }

    #[test]
    fn test_zlib_compile_flags_spec_11() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_4");
    }

    #[test]
    fn test_zlib_compile_flags_spec_12() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_7");
    }

    #[test]
    fn test_zlib_compile_flags_spec_13() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_15");
    }

    #[test]
    fn test_zlib_compile_flags_spec_14() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_31");
    }

    #[test]
    fn test_zlib_compile_flags_spec_15() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_63");
    }

    #[test]
    fn test_zlib_compile_flags_spec_16() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_127");
    }

    #[test]
    fn test_zlib_compile_flags_spec_17() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_255");
    }

    #[test]
    fn test_zlib_compile_flags_spec_18() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_511");
    }

    #[test]
    fn test_zlib_compile_flags_spec_19() {
        let got = super::zlib_compile_flags();
        assert_eq!(got, 169u32, "fuzz_input_len_1023");
    }

    #[test]
    fn test_zmemcpy_xform_0() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 0];
        let src = &[0x93];
        let n = 0usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[], "fuzz_byte_xform_0_n0");
    }

    #[test]
    fn test_zmemcpy_xform_1() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 1];
        let src = &[0x98];
        let n = 1usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0x98], "fuzz_byte_xform_1_n1");
    }

    #[test]
    fn test_zmemcpy_xform_2() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 7];
        let src = &[0x7b, 0x30, 0xb2, 0xd0, 0xdb, 0x8c, 0x34];
        let n = 7usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0x7b, 0x30, 0xb2, 0xd0, 0xdb, 0x8c, 0x34], "fuzz_byte_xform_2_n7");
    }

    #[test]
    fn test_zmemcpy_xform_3() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 16];
        let src = &[0x76, 0x99, 0xf6, 0x2d, 0xb9, 0xa8, 0x95, 0x6e, 0x4d, 0xa4, 0xd2, 0x4e, 0x8b, 0x8f, 0x09, 0xfd];
        let n = 16usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0x76, 0x99, 0xf6, 0x2d, 0xb9, 0xa8, 0x95, 0x6e, 0x4d, 0xa4, 0xd2, 0x4e, 0x8b, 0x8f, 0x09, 0xfd], "fuzz_byte_xform_3_n16");
    }

    #[test]
    fn test_zmemcpy_xform_4() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 31];
        let src = &[0xa2, 0xc5, 0x20, 0xca, 0x2d, 0x08, 0xf2, 0x9c, 0xde, 0xdb, 0x85, 0x54, 0x3d, 0xbc, 0xc3, 0x30, 0x49, 0x99, 0xcd, 0xda, 0x61, 0xba, 0xea, 0x5b, 0x30, 0x1a, 0x90, 0x19, 0x03, 0x2c, 0x0e];
        let n = 31usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0xa2, 0xc5, 0x20, 0xca, 0x2d, 0x08, 0xf2, 0x9c, 0xde, 0xdb, 0x85, 0x54, 0x3d, 0xbc, 0xc3, 0x30, 0x49, 0x99, 0xcd, 0xda, 0x61, 0xba, 0xea, 0x5b, 0x30, 0x1a, 0x90, 0x19, 0x03, 0x2c, 0x0e], "fuzz_byte_xform_4_n31");
    }

    #[test]
    fn test_zmemcpy_xform_5() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 12];
        let src = &[0xb7, 0xa6, 0x58, 0x67, 0xf0, 0x31, 0xe5, 0xc9, 0x52, 0xc5, 0x69, 0x72];
        let n = 12usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0xb7, 0xa6, 0x58, 0x67, 0xf0, 0x31, 0xe5, 0xc9, 0x52, 0xc5, 0x69, 0x72], "fuzz_byte_xform_5_n12");
    }

    #[test]
    fn test_zmemcpy_xform_6() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 14];
        let src = &[0xfc, 0x01, 0x12, 0x8f, 0xf7, 0xb9, 0xcc, 0x64, 0x75, 0x66, 0x57, 0xc1, 0xe2, 0x22];
        let n = 14usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0xfc, 0x01, 0x12, 0x8f, 0xf7, 0xb9, 0xcc, 0x64, 0x75, 0x66, 0x57, 0xc1, 0xe2, 0x22], "fuzz_byte_xform_6_n14");
    }

    #[test]
    fn test_zmemcpy_xform_7() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 18];
        let src = &[0x8d, 0xe2, 0xb9, 0xe5, 0xaa, 0xee, 0x2b, 0xf3, 0xca, 0xfc, 0xab, 0x75, 0x36, 0x61, 0x78, 0x42, 0x4a, 0xf6];
        let n = 18usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0x8d, 0xe2, 0xb9, 0xe5, 0xaa, 0xee, 0x2b, 0xf3, 0xca, 0xfc, 0xab, 0x75, 0x36, 0x61, 0x78, 0x42, 0x4a, 0xf6], "fuzz_byte_xform_7_n18");
    }

    #[test]
    fn test_zmemcpy_xform_8() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 16];
        let src = &[0xc5, 0x3b, 0xb0, 0x6d, 0x2e, 0xa8, 0x1d, 0x99, 0x08, 0x3b, 0xe6, 0xf4, 0xa8, 0x50, 0xdf, 0x4c];
        let n = 16usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0xc5, 0x3b, 0xb0, 0x6d, 0x2e, 0xa8, 0x1d, 0x99, 0x08, 0x3b, 0xe6, 0xf4, 0xa8, 0x50, 0xdf, 0x4c], "fuzz_byte_xform_8_n16");
    }

    #[test]
    fn test_zmemcpy_xform_9() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 23];
        let src = &[0xa5, 0xd6, 0x6e, 0x48, 0xea, 0x9c, 0x80, 0x4e, 0xf0, 0xd2, 0xe3, 0xc7, 0xb8, 0xda, 0x39, 0x3c, 0x5b, 0x55, 0x9b, 0x00, 0xfb, 0x94, 0x74];
        let n = 23usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0xa5, 0xd6, 0x6e, 0x48, 0xea, 0x9c, 0x80, 0x4e, 0xf0, 0xd2, 0xe3, 0xc7, 0xb8, 0xda, 0x39, 0x3c, 0x5b, 0x55, 0x9b, 0x00, 0xfb, 0x94, 0x74], "fuzz_byte_xform_9_n23");
    }

    #[test]
    fn test_zmemcpy_xform_10() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 20];
        let src = &[0x69, 0x02, 0x35, 0x82, 0x09, 0x5c, 0x7e, 0xbf, 0xb7, 0xd3, 0x64, 0x20, 0xb4, 0x7f, 0x1e, 0xd1, 0x86, 0x6b, 0x69, 0x34];
        let n = 20usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0x69, 0x02, 0x35, 0x82, 0x09, 0x5c, 0x7e, 0xbf, 0xb7, 0xd3, 0x64, 0x20, 0xb4, 0x7f, 0x1e, 0xd1, 0x86, 0x6b, 0x69, 0x34], "fuzz_byte_xform_10_n20");
    }

    #[test]
    fn test_zmemcpy_xform_11() {
        let mut dst: alloc::vec::Vec<u8> = alloc::vec![0u8; 5];
        let src = &[0x00, 0x16, 0x51, 0x5b, 0xf2];
        let n = 5usize;
        super::zmemcpy(&mut dst, src, n);
        assert_eq!(&dst[..n], &[0x00, 0x16, 0x51, 0x5b, 0xf2], "fuzz_byte_xform_11_n5");
    }

    #[test]
    fn test_zmemcmp_xform_0() {
        let s1 = &[0x93];
        let s2 = &[0x5f];
        let n = 0usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, 0i32, "fuzz_byte_xform_0_n0");
    }

    #[test]
    fn test_zmemcmp_xform_1() {
        let s1 = &[0x98];
        let s2 = &[0xad];
        let n = 1usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, (-21i32), "fuzz_byte_xform_1_n1");
    }

    #[test]
    fn test_zmemcmp_xform_2() {
        let s1 = &[0x7b, 0x30, 0xb2, 0xd0, 0xdb, 0x8c, 0x34];
        let s2 = &[0xde, 0x71, 0xcc, 0x2b, 0x2b, 0x85, 0xa0];
        let n = 7usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, (-99i32), "fuzz_byte_xform_2_n7");
    }

    #[test]
    fn test_zmemcmp_xform_3() {
        let s1 = &[0x76, 0x99, 0xf6, 0x2d, 0xb9, 0xa8, 0x95, 0x6e, 0x4d, 0xa4, 0xd2, 0x4e, 0x8b, 0x8f, 0x09, 0xfd];
        let s2 = &[0x7d, 0x39, 0x36, 0xeb, 0xd0, 0xa9, 0x0e, 0x1b, 0x24, 0x48, 0x82, 0xd3, 0xe5, 0x97, 0x39, 0x53];
        let n = 16usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, (-7i32), "fuzz_byte_xform_3_n16");
    }

    #[test]
    fn test_zmemcmp_xform_4() {
        let s1 = &[0xa2, 0xc5, 0x20, 0xca, 0x2d, 0x08, 0xf2, 0x9c, 0xde, 0xdb, 0x85, 0x54, 0x3d, 0xbc, 0xc3, 0x30, 0x49, 0x99, 0xcd, 0xda, 0x61, 0xba, 0xea, 0x5b, 0x30, 0x1a, 0x90, 0x19, 0x03, 0x2c, 0x0e];
        let s2 = &[0x1b, 0x68, 0x29, 0x4e, 0xff, 0xf6, 0x0b, 0x1a, 0x14, 0x53, 0xff, 0x39, 0x41, 0xb9, 0x1f, 0x9e, 0x2c, 0x85, 0xf9, 0xf1, 0x17, 0x2f, 0xca, 0x96, 0xa3, 0x93, 0xbf, 0x76, 0xd1, 0x86, 0x2b];
        let n = 31usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, 135i32, "fuzz_byte_xform_4_n31");
    }

    #[test]
    fn test_zmemcmp_xform_5() {
        let s1 = &[0xb7, 0xa6, 0x58, 0x67, 0xf0, 0x31, 0xe5, 0xc9, 0x52, 0xc5, 0x69, 0x72];
        let s2 = &[0xb7, 0xa6, 0x58, 0x67, 0xf0, 0x31, 0xe5, 0xc9, 0x52, 0xc5, 0x69, 0x72];
        let n = 12usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, 0i32, "fuzz_byte_xform_5_n12");
    }

    #[test]
    fn test_zmemcmp_xform_6() {
        let s1 = &[0xfc, 0x01, 0x12, 0x8f, 0xf7, 0xb9, 0xcc, 0x64, 0x75, 0x66, 0x57, 0xc1, 0xe2, 0x22];
        let s2 = &[0xfc, 0x01, 0x12, 0x8f, 0xf7, 0xb9, 0xcc, 0x64, 0x75, 0x66, 0x57, 0xc1, 0xe2, 0x22];
        let n = 14usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, 0i32, "fuzz_byte_xform_6_n14");
    }

    #[test]
    fn test_zmemcmp_xform_7() {
        let s1 = &[0x8d, 0xe2, 0xb9, 0xe5, 0xaa, 0xee, 0x2b, 0xf3, 0xca, 0xfc, 0xab, 0x75, 0x36, 0x61, 0x78, 0x42, 0x4a, 0xf6];
        let s2 = &[0x8d, 0xe2, 0xb9, 0xe5, 0xaa, 0xee, 0x2b, 0xf3, 0xca, 0xfc, 0xab, 0x75, 0x36, 0x61, 0x78, 0x42, 0x4a, 0xf6];
        let n = 18usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, 0i32, "fuzz_byte_xform_7_n18");
    }

    #[test]
    fn test_zmemcmp_xform_8() {
        let s1 = &[0xc5, 0x3b, 0xb0, 0x6d, 0x2e, 0xa8, 0x1d, 0x99, 0x08, 0x3b, 0xe6, 0xf4, 0xa8, 0x50, 0xdf, 0x4c];
        let s2 = &[0x89, 0xd0, 0xd4, 0x19, 0x24, 0x35, 0x58, 0x45, 0x8a, 0x34, 0x7f, 0x55, 0x6e, 0x29, 0x4f, 0x69];
        let n = 16usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, 60i32, "fuzz_byte_xform_8_n16");
    }

    #[test]
    fn test_zmemcmp_xform_9() {
        let s1 = &[0xa5, 0xd6, 0x6e, 0x48, 0xea, 0x9c, 0x80, 0x4e, 0xf0, 0xd2, 0xe3, 0xc7, 0xb8, 0xda, 0x39, 0x3c, 0x5b, 0x55, 0x9b, 0x00, 0xfb, 0x94, 0x74];
        let s2 = &[0x92, 0xa4, 0x1a, 0x2a, 0x21, 0x86, 0xba, 0x9f, 0x92, 0x39, 0x6b, 0x4b, 0x1d, 0xd2, 0xf6, 0xed, 0x6f, 0x54, 0x12, 0xec, 0x03, 0xf5, 0x3f];
        let n = 23usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, 19i32, "fuzz_byte_xform_9_n23");
    }

    #[test]
    fn test_zmemcmp_xform_10() {
        let s1 = &[0x69, 0x02, 0x35, 0x82, 0x09, 0x5c, 0x7e, 0xbf, 0xb7, 0xd3, 0x64, 0x20, 0xb4, 0x7f, 0x1e, 0xd1, 0x86, 0x6b, 0x69, 0x34];
        let s2 = &[0x8d, 0x4b, 0x56, 0xdb, 0x9b, 0xdc, 0xed, 0xa0, 0x8c, 0xf3, 0x42, 0x2c, 0x17, 0x34, 0x06, 0x48, 0xc6, 0x4a, 0x5f, 0x9e];
        let n = 20usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, (-36i32), "fuzz_byte_xform_10_n20");
    }

    #[test]
    fn test_zmemcmp_xform_11() {
        let s1 = &[0x00, 0x16, 0x51, 0x5b, 0xf2];
        let s2 = &[0xd0, 0x75, 0x34, 0x31, 0x96];
        let n = 5usize;
        let got = super::zmemcmp(s1, s2, n);
        assert_eq!(got, (-208i32), "fuzz_byte_xform_11_n5");
    }

    #[test]
    fn test_zmemzero_xform_0() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 0];
        let len = 0usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[], "fuzz_byte_xform_0_n0");
    }

    #[test]
    fn test_zmemzero_xform_1() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 1];
        let len = 1usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00], "fuzz_byte_xform_1_n1");
    }

    #[test]
    fn test_zmemzero_xform_2() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 7];
        let len = 7usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_2_n7");
    }

    #[test]
    fn test_zmemzero_xform_3() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 16];
        let len = 16usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_3_n16");
    }

    #[test]
    fn test_zmemzero_xform_4() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 31];
        let len = 31usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_4_n31");
    }

    #[test]
    fn test_zmemzero_xform_5() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 12];
        let len = 12usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_5_n12");
    }

    #[test]
    fn test_zmemzero_xform_6() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 14];
        let len = 14usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_6_n14");
    }

    #[test]
    fn test_zmemzero_xform_7() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 18];
        let len = 18usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_7_n18");
    }

    #[test]
    fn test_zmemzero_xform_8() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 16];
        let len = 16usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_8_n16");
    }

    #[test]
    fn test_zmemzero_xform_9() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 23];
        let len = 23usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_9_n23");
    }

    #[test]
    fn test_zmemzero_xform_10() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 20];
        let len = 20usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_10_n20");
    }

    #[test]
    fn test_zmemzero_xform_11() {
        let mut buffer: alloc::vec::Vec<u8> = alloc::vec![0xFFu8; 5];
        let len = 5usize;
        super::zmemzero(&mut buffer, len);
        assert_eq!(&buffer[..len], &[0x00, 0x00, 0x00, 0x00, 0x00], "fuzz_byte_xform_11_n5");
    }

}
