/// Braid
/// Generates lookup tables for CRC-32 combining operations, providing both
/// little-endian (ltl) and big-endian (big) representations for a specified number
/// of blocks.
///
/// Standards: IEEE 802.3, variant:ieee_reflected
///
/// Port of zlib crc32.c:braid — generate the little- and big-endian braid
/// tables for the given `n` (number of braids) and z_word_t size `w` (bytes
/// per word). Each slice must have room for `w` blocks of 256 elements.
///
/// ```c
/// for (k = 0; k < w; k++) {
///     p = (z_crc_t)x2nmodp((n * w + 3 - k) << 3, 0);
///     ltl[k][0] = 0;
///     big[w - 1 - k][0] = 0;
///     for (i = 1; i < 256; i++) {
///         ltl[k][i] = q = (z_crc_t)multmodp(i << 24, p);
///         big[w - 1 - k][i] = byte_swap(q);
///     }
/// }
/// ```
///
/// Signature note: the generated skeleton declared `big` as
/// `&mut [[u32; 256]]`, but the C writes z_word_t values into big[][] and
/// this crate's table model is W == 8 (64-bit z_word_t), whose big-table
/// entries (e.g. crc32.h crc_braid_big_table[0][1] == 0xf390f23600000000)
/// do not fit in u32 — `byte_swap(q)` promotes the 32-bit CRC entry to
/// 64 bits and moves it into the high bytes. The parameter type was
/// therefore changed to `&mut [[u64; 256]]`.
pub fn braid(ltl: &mut [[u32; 256]], big: &mut [[u64; 256]], n: usize, w: usize) {
    for k in 0..w {
        let p = x2nmodp(((n * w + 3 - k) << 3) as u64, 0);
        ltl[k][0] = 0;
        big[w - 1 - k][0] = 0;
        for i in 1..256u32 {
            let q = multmodp(i << 24, p);
            ltl[k][i as usize] = q;
            big[w - 1 - k][i as usize] = byte_swap(q as u64);
        }
    }
}
