//! Trees
//!
//! Module containing 16 functions: bi_reverse, bi_flush, bi_windup, gen_codes,
//! send_bits, tr_static_init, init_block, _tr_init, pqdownheap, gen_bitlen,
//! build_tree, build_bl_tree, send_all_trees, _tr_align, compress_block,
//! detect_data_type

#![allow(unused_variables, unused_imports, dead_code)]
use crate::static_tables::*;

use zlib_types::*;

use crate::*;

/// Bi Reverse
/// Reverses the bit order of a given integer within a specific bit-length window.
pub fn bi_reverse(mut code: u32, len: u8) -> u32 { let mut res: u32 = 0; for _ in 0..len { res = (res << 1) | (code & 1); code >>= 1; } res }

/// Bi Flush
/// Flushes accumulated bits from a bit buffer to the output stream, ensuring the
/// buffer contains at most 7 bits after the operation.
///
/// Standards: RFC 1951
pub fn bi_flush(state: &mut DeflateState) {
    if state.bi_valid == 16 {
        state.pending.push((state.bi_buf & 0xff) as u8);
        state.pending.push((state.bi_buf >> 8) as u8);
        state.bi_buf = 0;
        state.bi_valid = 0;
    } else if state.bi_valid >= 8 {
        state.pending.push((state.bi_buf & 0xff) as u8);
        state.bi_buf >>= 8;
        state.bi_valid -= 8;
    }
}

/// Bi Windup
/// Flushes the remaining bits in the bit buffer to the output stream and resets
/// the buffer state to align with byte boundaries.
///
/// Standards: RFC 1951
pub fn bi_windup(state: &mut DeflateState) {
    if state.bi_valid > 8 {
        state.pending.push((state.bi_buf & 0xff) as u8);
        state.pending.push((state.bi_buf >> 8) as u8);
    } else if state.bi_valid > 0 {
        state.pending.push((state.bi_buf & 0xff) as u8);
    }
    state.bi_buf = 0;
    state.bi_valid = 0;
}

/// Gen Codes
/// Generates canonical Huffman codes for a set of symbols based on their
/// bit-length distribution.
///
/// Standards: DEFLATE (RFC 1951)
pub fn gen_codes(tree: &mut [TreeElement], max_code: usize, bl_count: &[u16]) {
    let max_bits = bl_count.len() - 1;
    let mut next_code = [0u16; 16];
    let mut code: u16 = 0;
    for bits in 1..=max_bits {
        code = (code + bl_count[bits - 1]) << 1;
        if bits < next_code.len() {
            next_code[bits] = code;
        }
    }
    for n in 0..=max_code {
        if n >= tree.len() {
            break;
        }
        let len = tree[n].len as usize;
        if len == 0 {
            continue;
        }
        let c = next_code[len];
        next_code[len] = c + 1;
        // Reflected (LSB-first) code per RFC 1951.
        let mut res: u16 = 0;
        let mut code_val = c;
        for _ in 0..len {
            res = (res << 1) | (code_val & 1);
            code_val >>= 1;
        }
        tree[n].code = res;
    }
}

/// Send Bits
/// Encodes a variable number of bits from a value into a bit buffer, flushing the
/// buffer to the output stream when it reaches capacity.
///
/// Standards: RFC 1951
pub fn send_bits(state: &mut DeflateState, value: u16, length: u8) {
    let len = length as u32;
    let val = value as u32;
    let valid = state.bi_valid as u32;
    if valid + len > 16 {
        state.bi_buf |= (val << valid) as u16;
        state.pending.push((state.bi_buf & 0xff) as u8);
        state.pending.push((state.bi_buf >> 8) as u8);
        state.bi_buf = (val >> (16 - valid)) as u16;
        state.bi_valid = ((valid + len) - 16) as i32;
    } else {
        state.bi_buf |= (val << valid) as u16;
        state.bi_valid = (valid + len) as i32;
    }
}

/// Tr Static Init
/// Initializes the constant lookup tables and static Huffman trees used for the
/// DEFLATE compression algorithm.
///
/// Standards: RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]
pub fn tr_static_init() {
    // Static Huffman tables are compile-time consts (see static_tables).
}

/// Init Block
/// Initializes the frequency counters for Huffman trees and resets block-related
/// tracking variables for a new compression block.
///
/// Standards: RFC 1951
pub fn init_block(s: &mut DeflateState) {
    for n in 0..286 { s.dyn_ltree[n].freq = 0; }
    for n in 0..30 { s.dyn_dtree[n].freq = 0; }
    for n in 0..19 { s.bl_tree[n].freq = 0; }
    s.dyn_ltree[256].freq = 1;
    s.opt_len = 0;
    s.static_len = 0;
    s.sym_next = 0;
    s.matches = 0;
}

///  Tr Init
/// Initializes the Huffman tree descriptors and bit buffer state for a new zlib
/// compression stream.
///
/// Standards: RFC 1951 (DEFLATE)
pub fn _tr_init(s: &mut DeflateState) {
    s.l_desc.stat_desc = zlib_types::StaticTreeDesc {
        static_tree: STATIC_LTREE.to_vec(), extra_bits: EXTRA_LBITS.to_vec(),
        extra_base: 257, elems: 286, max_length: 15,
    };
    s.d_desc.stat_desc = zlib_types::StaticTreeDesc {
        static_tree: STATIC_DTREE.to_vec(), extra_bits: EXTRA_DBITS.to_vec(),
        extra_base: 0, elems: 30, max_length: 15,
    };
    s.bl_desc.stat_desc = zlib_types::StaticTreeDesc {
        static_tree: Vec::new(), extra_bits: EXTRA_BLBITS.to_vec(),
        extra_base: 0, elems: 19, max_length: 7,
    };
    s.bi_buf = 0;
    s.bi_valid = 0;
    init_block(s);
}

pub fn pqdownheap(s: &mut DeflateState, tree: &[TreeElement], mut k: usize) {
    let v = s.heap[k];
    let mut j = k << 1;
    while j <= s.heap_len as usize {
        if j < s.heap_len as usize {
            let n = s.heap[j + 1] as usize;
            let m = s.heap[j] as usize;
            if tree[n].freq < tree[m].freq || (tree[n].freq == tree[m].freq && s.depth[n] <= s.depth[m]) {
                j += 1;
            }
        }
        let v_idx = v as usize;
        let j_idx = s.heap[j] as usize;
        if tree[v_idx].freq < tree[j_idx].freq || (tree[v_idx].freq == tree[j_idx].freq && s.depth[v_idx] <= s.depth[j_idx]) {
            break;
        }
        s.heap[k] = s.heap[j];
        k = j;
        j <<= 1;
    }
    s.heap[k] = v;
}

/// Gen Bitlen
/// Computes optimal Huffman bit lengths for symbols based on their frequencies,
/// handling bit-length overflow by redistributing leaf nodes to satisfy maximum
/// length constraints.
///
/// Standards: PKZIP Huffman Coding Specification
pub fn gen_bitlen(s: &mut DeflateState, desc: &mut TreeDesc) {
    if s.bl_count.len() < 16 {
        s.bl_count.resize(16, 0);
    }
    for bits in 0..16 {
        s.bl_count[bits] = 0;
    }

    let max_code = desc.max_code;
    let max_length = desc.stat_desc.max_length as i32;
    let base = desc.stat_desc.extra_base;
    let extra = &desc.stat_desc.extra_bits;
    let stree = &desc.stat_desc.static_tree;

    let root_idx = s.heap[s.heap_max as usize] as usize;
    desc.dyn_tree[root_idx].len = 0;

    let mut overflow = 0;

    for i in (s.heap_max + 1)..573 {
        let n = s.heap[i as usize] as usize;
        let dad = desc.dyn_tree[n].dad as usize;
        let mut bits = desc.dyn_tree[dad].len as i32 + 1;

        if bits > max_length {
            bits = max_length;
            overflow += 1;
        }

        desc.dyn_tree[n].len = bits as u16;

        if (n as i32) > max_code {
            continue;
        }

        s.bl_count[bits as usize] += 1;
        let mut xbits = 0;
        if (n as i32) >= base {
            xbits = extra[(n as i32 - base) as usize];
        }

        let f = desc.dyn_tree[n].freq as u64;
        s.opt_len = s.opt_len.wrapping_add(f.wrapping_mul((bits + xbits) as u64));

        if !stree.is_empty() {
            s.static_len = s.static_len.wrapping_add(f.wrapping_mul((stree[n].len as i32 + xbits) as u64));
        }
    }

    if overflow == 0 {
        return;
    }

    while overflow > 0 {
        let mut bits = max_length - 1;
        while bits >= 0 && s.bl_count[bits as usize] == 0 {
            bits -= 1;
        }
        s.bl_count[bits as usize] -= 1;
        s.bl_count[(bits + 1) as usize] += 2;
        s.bl_count[max_length as usize] -= 1;
        overflow -= 2;
    }

    let mut h = 572;
    for bits in (1..=max_length).rev() {
        let mut n = s.bl_count[bits as usize];
        while n != 0 {
            let m = s.heap[h] as i32;
            h -= 1;
            if m > max_code {
                continue;
            }
            let m_idx = m as usize;
            if desc.dyn_tree[m_idx].len as i32 != bits {
                s.opt_len = s.opt_len.wrapping_add(((bits - desc.dyn_tree[m_idx].len as i32) as u64).wrapping_mul(desc.dyn_tree[m_idx].freq as u64));
                desc.dyn_tree[m_idx].len = bits as u16;
            }
            n -= 1;
        }
    }
}

/// Build Tree
/// Constructs an optimal Huffman coding tree from symbol frequencies and generates
/// the corresponding bit lengths and codes.
///
/// Standards: PKZIP format specification
#[allow(clippy::unimplemented)]
pub fn build_tree(s: &mut DeflateState, desc: &mut TreeDesc) {
    if desc.dyn_tree.len() < 573 { desc.dyn_tree.resize(573, TreeElement::default()); }
    if s.heap.len() < 575 { s.heap.resize(575, 0); }
    if s.depth.len() < 573 { s.depth.resize(573, 0); }
    if s.bl_count.len() < 16 { s.bl_count.resize(16, 0); }

    let stree = &desc.stat_desc.static_tree;
    let elems = desc.stat_desc.elems as usize;
    let mut max_code = -1i32;
    
    s.heap_len = 0;
    s.heap_max = 573;

    for n in 0..elems {
        if desc.dyn_tree[n].freq != 0 {
            s.heap_len += 1;
            s.heap[s.heap_len as usize] = n as i32;
            max_code = n as i32;
            s.depth[n] = 0;
        } else {
            desc.dyn_tree[n].len = 0;
        }
    }

    while s.heap_len < 2 {
        s.heap_len += 1;
        let node = if max_code < 2 { max_code = max_code + 1; max_code } else { 0 };
        s.heap[s.heap_len as usize] = node;
        desc.dyn_tree[node as usize].freq = 1;
        s.depth[node as usize] = 0;
        s.opt_len = s.opt_len.wrapping_sub(1);
        if !stree.is_empty() {
            s.static_len = s.static_len.wrapping_sub(stree[node as usize].len as u64);
        }
    }

    desc.max_code = max_code;

    for n in (1..=(s.heap_len / 2)).rev() {
        pqdownheap(s, &desc.dyn_tree, n as usize);
    }

    let mut node = elems as i32;
    let smallest = 1usize;
    
    loop {
        if s.heap_len < 2 { break; }
        
        // pqremove(s, tree, n) where n is the current node index (which is 1 in the C loop logic)
        let n_val = s.heap[smallest];
        s.heap[smallest] = s.heap[s.heap_len as usize];
        s.heap_len -= 1;
        pqdownheap(s, &desc.dyn_tree, smallest);

        let m_val = s.heap[smallest];
        s.heap_max -= 1;
        s.heap[s.heap_max as usize] = n_val;
        s.heap_max -= 1;
        s.heap[s.heap_max as usize] = m_val;

        let n_idx = n_val as usize;
        let m_idx = m_val as usize;
        let node_idx = node as usize;

        desc.dyn_tree[node_idx].freq = desc.dyn_tree[n_idx].freq + desc.dyn_tree[m_idx].freq;
        s.depth[node_idx] = (if s.depth[n_idx] >= s.depth[m_idx] { s.depth[n_idx] } else { s.depth[m_idx] }).saturating_add(1);
        desc.dyn_tree[n_idx].dad = node as u16;
        desc.dyn_tree[m_idx].dad = node as u16;

        s.heap[smallest] = node;
        node += 1;
        pqdownheap(s, &desc.dyn_tree, smallest);
    }

    s.heap_max -= 1;
    s.heap[s.heap_max as usize] = s.heap[smallest];

    gen_bitlen(s, desc);
    let bl = s.bl_count.clone();
    gen_codes(&mut desc.dyn_tree, max_code as usize, &bl);
}

/// Build Bl Tree
/// Constructs the Huffman tree used to encode the bit lengths of the literal and
/// distance trees, and calculates the overhead for the bit-length tree metadata.
///
/// Standards: PKZIP format specification, RFC 1951
#[allow(clippy::unimplemented)]
fn scan_tree(bl_tree: &mut [TreeElement], tree: &mut [TreeElement], max_code: i32) {
    let mut n = 0;
    let mut prevlen: i32 = -1;
    let mut count: i32 = 0;
    let mut max_count: i32 = 7;
    let mut min_count: i32 = 4;
    let mut nextlen = tree[0].len as i32;
    if nextlen == 0 { max_count = 138; min_count = 3; }

    tree[(max_code + 1) as usize].len = 0xffff;

    while n <= max_code {
        let curlen = nextlen;
        nextlen = tree[(n + 1) as usize].len as i32;
        count += 1;

        if count < max_count && curlen == nextlen {
            n += 1;
            continue;
        } else if count < min_count {
            bl_tree[curlen as usize].freq = bl_tree[curlen as usize].freq.wrapping_add(count as u16);
        } else if curlen != 0 {
            if curlen != prevlen {
                bl_tree[curlen as usize].freq = bl_tree[curlen as usize].freq.wrapping_add(1);
            }
            bl_tree[REP_3_6 as usize].freq = bl_tree[REP_3_6 as usize].freq.wrapping_add(1);
        } else if count <= 10 {
            bl_tree[REPZ_3_10 as usize].freq = bl_tree[REPZ_3_10 as usize].freq.wrapping_add(1);
        } else {
            bl_tree[REPZ_11_138 as usize].freq = bl_tree[REPZ_11_138 as usize].freq.wrapping_add(1);
        }

        count = 0;
        prevlen = curlen;

        if nextlen == 0 {
            max_count = 138;
            min_count = 3;
        } else if curlen == nextlen {
            max_count = 6;
            min_count = 3;
        } else {
            max_count = 7;
            min_count = 4;
        }
        n += 1;
    }
}

pub fn build_bl_tree(s: &mut DeflateState) -> usize {
    let mut lt = std::mem::take(&mut s.dyn_ltree);
    scan_tree(&mut s.bl_tree, &mut lt, s.l_desc.max_code);
    s.dyn_ltree = lt;

    let mut dt = std::mem::take(&mut s.dyn_dtree);
    scan_tree(&mut s.bl_tree, &mut dt, s.d_desc.max_code);
    s.dyn_dtree = dt;

    let mut bl_desc = std::mem::take(&mut s.bl_desc);
    bl_desc.dyn_tree = std::mem::take(&mut s.bl_tree);
    build_tree(s, &mut bl_desc);
    s.bl_tree = std::mem::take(&mut bl_desc.dyn_tree);
    s.bl_desc = bl_desc;

    let mut max_blindex = 0;
    for i in (3..BL_CODES).rev() {
        if s.bl_tree[BL_ORDER[i]].len != 0 {
            max_blindex = i;
            break;
        }
    }

    s.opt_len = s.opt_len.wrapping_add(3 * (max_blindex as u64 + 1) + 5 + 5 + 4);
    max_blindex
}

/// Send All Trees
/// Serializes the Huffman tree definitions for a dynamic DEFLATE block, including
/// bit length codes, the literal tree, and the distance tree.
///
/// Standards: RFC 1951
#[allow(clippy::unimplemented)]
fn send_tree(s: &mut DeflateState, tree: &[TreeElement], max_code: i32) {
    let mut n = 0;
    let mut prevlen = -1;
    let mut count = 0;
    let mut max_count = 7;
    let mut min_count = 4;
    let mut nextlen = tree[0].len as i32;

    if nextlen == 0 {
        max_count = 138;
        min_count = 3;
    }

    while n <= max_code {
        let curlen = nextlen;
        nextlen = tree[(n as usize) + 1].len as i32;
        count += 1;

        if count < max_count && curlen == nextlen {
            n += 1;
            continue;
        } else if count < min_count {
            while count != 0 {
                let idx = curlen as usize;
                let c = s.bl_tree[idx].code;
                let ln = s.bl_tree[idx].len as u8;
                send_bits(s, c, ln);
                count -= 1;
            }
        } else if curlen != 0 {
            if curlen != prevlen {
                let idx = curlen as usize;
                let c = s.bl_tree[idx].code;
                let ln = s.bl_tree[idx].len as u8;
                send_bits(s, c, ln);
                count -= 1;
            }
            let idx = REP_3_6 as usize;
            let c = s.bl_tree[idx].code;
            let ln = s.bl_tree[idx].len as u8;
            send_bits(s, c, ln);
            send_bits(s, (count - 3) as u16, 2);
        } else if count <= 10 {
            let idx = REPZ_3_10 as usize;
            let c = s.bl_tree[idx].code;
            let ln = s.bl_tree[idx].len as u8;
            send_bits(s, c, ln);
            send_bits(s, (count - 3) as u16, 3);
        } else {
            let idx = REPZ_11_138 as usize;
            let c = s.bl_tree[idx].code;
            let ln = s.bl_tree[idx].len as u8;
            send_bits(s, c, ln);
            send_bits(s, (count - 11) as u16, 7);
        }

        count = 0;
        prevlen = curlen;
        if nextlen == 0 {
            max_count = 138;
            min_count = 3;
        } else if curlen == nextlen {
            max_count = 6;
            min_count = 3;
        } else {
            max_count = 7;
            min_count = 4;
        }
        n += 1;
    }
}

pub fn send_all_trees(s: &mut DeflateState, lcodes: usize, dcodes: usize, blcodes: usize) {
    send_bits(s, (lcodes - 257) as u16, 5);
    send_bits(s, (dcodes - 1) as u16, 5);
    send_bits(s, (blcodes - 4) as u16, 4);

    for rank in 0..blcodes {
        let len = s.bl_tree[BL_ORDER[rank]].len as u16;
        send_bits(s, len, 3);
    }

    let lt = s.dyn_ltree.clone();
    send_tree(s, &lt, (lcodes - 1) as i32);

    let dt = s.dyn_dtree.clone();
    send_tree(s, &dt, (dcodes - 1) as i32);
}

pub fn _tr_align(s: &mut DeflateState) {
    send_bits(s, (STATIC_TREES << 1) as u16, 3);
    send_bits(s, STATIC_LTREE[END_BLOCK].code, STATIC_LTREE[END_BLOCK].len as u8);
    bi_flush(s);
}

/// Compress Block
/// Encodes a sequence of literals and match pairs into a compressed bitstream
/// using provided Huffman trees.
///
/// Standards: RFC 1951 (DEFLATE)
#[allow(clippy::unimplemented)]
pub fn compress_block(s: &mut DeflateState, ltree: &[TreeElement], dtree: &[TreeElement]) {
    let mut sx = 0;
    let sym_next = s.sym_next as usize;
    if sym_next != 0 {
        loop {
            let mut dist = (s.sym_buf[sx] as u32) | ((s.sym_buf[sx + 1] as u32) << 8);
            sx += 2;
            let mut lc = s.sym_buf[sx] as usize;
            sx += 1;

            if dist == 0 {
                { let cc = ltree[lc].code; let ln = ltree[lc].len as u8; send_bits(s, cc, ln); }
            } else {
                let code = LENGTH_CODE[lc] as usize;
                { let cc = ltree[code + LITERALS + 1].code; let ln = ltree[code + LITERALS + 1].len as u8; send_bits(s, cc, ln); }
                let extra = EXTRA_LBITS[code];
                if extra != 0 {
                    lc = lc.wrapping_sub(BASE_LENGTH[code] as usize);
                    send_bits(s, lc as u16, extra as u8);
                }
                dist -= 1;
                let d_code = if dist < 256 {
                    DIST_CODE[dist as usize]
                } else {
                    DIST_CODE[256 + ((dist >> 7) as usize)]
                };
                { let cc = dtree[d_code as usize].code; let ln = dtree[d_code as usize].len as u8; send_bits(s, cc, ln); }
                let extra_d = EXTRA_DBITS[d_code as usize];
                if extra_d != 0 {
                    dist = dist.wrapping_sub(BASE_DIST[d_code as usize] as u32);
                    send_bits(s, dist as u16, extra_d as u8);
                }
            }
            if sx >= sym_next { break; }
        }
    }
    { let cc = ltree[END_BLOCK].code; let ln = ltree[END_BLOCK].len as u8; send_bits(s, cc, ln); }
}

/// Detect Data Type
/// Classifies a compressed data stream as either binary or text based on the
/// frequency of specific byte values in the dynamic Huffman tree.
pub fn detect_data_type(s: &DeflateState) -> i32 {
    // C: block_mask 0xf3ffc07f shifted right over bytes 0..=31; then
    // whitespace bytes 9/10/13; then bytes 32..LITERALS. Z_BINARY=0, Z_TEXT=1.
    let mut block_mask: u32 = 0xf3ffc07f;
    for n in 0..=31usize {
        if (block_mask & 1) != 0 && s.dyn_ltree[n].freq != 0 {
            return 0;
        }
        block_mask >>= 1;
    }
    if s.dyn_ltree[9].freq != 0 || s.dyn_ltree[10].freq != 0 || s.dyn_ltree[13].freq != 0 {
        return 1;
    }
    for n in 32..256usize {
        if s.dyn_ltree[n].freq != 0 {
            return 1;
        }
    }
    0
}

pub fn _tr_tally(s: &mut DeflateState, dist: u32, lc: u32) -> bool {
    s.sym_buf[s.sym_next as usize] = dist as u8;
    s.sym_next += 1;
    s.sym_buf[s.sym_next as usize] = (dist >> 8) as u8;
    s.sym_next += 1;
    s.sym_buf[s.sym_next as usize] = lc as u8;
    s.sym_next += 1;

    if dist == 0 {
        s.dyn_ltree[lc as usize].freq = s.dyn_ltree[lc as usize].freq.wrapping_add(1);
    } else {
        s.matches += 1;
        let dist = dist - 1;
        let lc_idx = (LENGTH_CODE[lc as usize] as usize) + LITERALS + 1;
        s.dyn_ltree[lc_idx].freq = s.dyn_ltree[lc_idx].freq.wrapping_add(1);
        
        let d_idx = if dist < 256 {
            DIST_CODE[dist as usize]
        } else {
            DIST_CODE[256 + (dist >> 7) as usize]
        };
        s.dyn_dtree[d_idx as usize].freq = s.dyn_dtree[d_idx as usize].freq.wrapping_add(1);
    }
    s.sym_next == s.sym_end
}

pub fn _tr_stored_block(s: &mut DeflateState, buf: &[u8], stored_len: u32, last: i32) {
    send_bits(s, last as u16, 3);
    bi_windup(s);
    let sl = stored_len as u16;
    s.pending.push((sl & 0xff) as u8);
    s.pending.push((sl >> 8) as u8);
    let nsl = !sl;
    s.pending.push((nsl & 0xff) as u8);
    s.pending.push((nsl >> 8) as u8);
    if stored_len > 0 {
        s.pending.extend_from_slice(&buf[..stored_len as usize]);
    }
}

pub fn _tr_flush_bits(s: &mut DeflateState) {
    bi_flush(s);
}

pub fn _tr_flush_block(strm: &mut DeflateStream, buf: Option<&[u8]>, stored_len: u32, last: i32) {
    let mut opt_lenb: u64;
    let mut static_lenb: u64;
    let mut max_blindex = 0;

    if strm.state.level > 0 {
        if strm.state.data_type == 2 {
            strm.state.data_type = detect_data_type(&strm.state);
        }
        strm.state.l_desc.dyn_tree = core::mem::take(&mut strm.state.dyn_ltree);
        let mut ld = core::mem::take(&mut strm.state.l_desc);
        build_tree(&mut strm.state, &mut ld);
        strm.state.dyn_ltree = core::mem::take(&mut ld.dyn_tree);
        strm.state.l_desc = ld;

        strm.state.d_desc.dyn_tree = core::mem::take(&mut strm.state.dyn_dtree);
        let mut dd = core::mem::take(&mut strm.state.d_desc);
        build_tree(&mut strm.state, &mut dd);
        strm.state.dyn_dtree = core::mem::take(&mut dd.dyn_tree);
        strm.state.d_desc = dd;

        max_blindex = build_bl_tree(&mut strm.state);
        opt_lenb = (strm.state.opt_len + 3 + 7) >> 3;
        static_lenb = (strm.state.static_len + 3 + 7) >> 3;
        if static_lenb <= opt_lenb || strm.state.strategy == 4 {
            opt_lenb = static_lenb;
        }
    } else {
        opt_lenb = stored_len as u64 + 5;
        static_lenb = stored_len as u64 + 5;
    }

    if (stored_len as u64 + 4) <= opt_lenb && buf.is_some() {
        _tr_stored_block(&mut strm.state, buf.unwrap(), stored_len, last);
    } else if static_lenb == opt_lenb {
        send_bits(&mut strm.state, ((1 << 1) + last) as u16, 3);
        compress_block(&mut strm.state, &crate::static_tables::STATIC_LTREE, &crate::static_tables::STATIC_DTREE);
    } else {
        send_bits(&mut strm.state, ((2 << 1) + last) as u16, 3);
        let lcodes = (strm.state.l_desc.max_code + 1) as usize;
        let dcodes = (strm.state.d_desc.max_code + 1) as usize;
        send_all_trees(&mut strm.state, lcodes, dcodes, max_blindex + 1);
        let lt = strm.state.dyn_ltree.clone();
        let dt = strm.state.dyn_dtree.clone();
        compress_block(&mut strm.state, &lt, &dt);
    }

    init_block(&mut strm.state);
    if last != 0 {
        bi_windup(&mut strm.state);
    }
}


