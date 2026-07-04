/// Tables produced by `make_crc_table` — the W=8/N=5 table model that the
/// crate's consts (and zlib's shipped crc32.h) were derived from.
///
/// Field names mirror the static arrays filled by zlib crc32.c
/// (DYNAMIC_CRC_TABLE branch): `crc_table[256]`, `crc_big_table[256]`
/// (64-bit z_word_t), `x2n_table[32]`, `crc_braid_table[W][256]`, and
/// `crc_braid_big_table[W][256]`.
pub struct CrcTables {
    /// Byte-wise CRC table (crc32.h `crc_table[]`).
    pub crc_table: [u32; 256],
    /// Big-endian word table for 64-bit z_word_t (crc32.h `crc_big_table[]`, W == 8 branch).
    pub crc_big_table: [u64; 256],
    /// x^2^n mod p(x) powers table (crc32.h `x2n_table[]`).
    pub x2n_table: [u32; 32],
    /// Braid tables for N == 5, W == 8 (crc32.h `crc_braid_table[][256]`).
    pub crc_braid_table: [[u32; 256]; 8],
    /// Big-endian braid tables for N == 5, W == 8 (crc32.h `crc_braid_big_table[][256]`).
    pub crc_braid_big_table: [[u64; 256]; 8],
}

/// Make Crc Table
/// Initializes precomputed lookup tables used for accelerated CRC-32 calculations,
/// including byte-wise CRC tables, modular exponentiation tables (x^2^n mod p), and
/// braiding tables for combining checksums.
///
/// Standards: IEEE 802.3, variant:ieee_reflected
///
/// Port of zlib crc32.c:make_crc_table (DYNAMIC_CRC_TABLE branch). In the C
/// source this fills `static` tables under z_once(); in this translation the
/// tables are consts, so the return type was changed from `()` to
/// [`CrcTables`]: the function performs the table computation the consts were
/// derived from and returns the result, letting callers/tests verify the
/// consts against the generator.
///
/// Model note: the module-level `W: i32 = 4` const above was extracted from a
/// `#else` branch of the C; the tables this crate's consts were lifted from
/// are the W == 8 / N == 5 configuration of crc32.h (64-bit z_word_t, five
/// braids), so explicit local constants are used here instead of relying on
/// the module-level `W`/`N`.
pub fn make_crc_table() -> CrcTables {
    /// z_word_t is 64 bits in the table model reproduced here (crc32.h W == 8 branch).
    const CRC_W: usize = 8;
    /// Number of braids (crc32.h N == 5 branch).
    const CRC_N: usize = 5;

    // initialize the CRC of bytes tables:
    //   p = i; 8x { p = p & 1 ? (p >> 1) ^ POLY : p >> 1; }
    //   crc_table[i] = p; crc_big_table[i] = byte_swap(p);
    let mut crc_table = [0u32; 256];
    let mut crc_big_table = [0u64; 256];
    for i in 0..256u32 {
        let mut p = i;
        for _ in 0..8 {
            p = if p & 1 != 0 { (p >> 1) ^ POLY } else { p >> 1 };
        }
        crc_table[i as usize] = p;
        crc_big_table[i as usize] = byte_swap(p as u64);
    }

    // initialize the x^2^n mod p(x) table:
    //   x2n_table[0] = 1 << 30 (x^1); x2n_table[n] = multmodp(prev, prev)
    let mut x2n_table = [0u32; 32];
    let mut p: u32 = 1u32 << 30;
    x2n_table[0] = p;
    for n in 1..32 {
        p = multmodp(p, p);
        x2n_table[n] = p;
    }

    // initialize the braiding tables -- needs x^2^n mod p(x), which the
    // ported braid() obtains via x2nmodp (self-contained in this module)
    let mut crc_braid_table = [[0u32; 256]; CRC_W];
    let mut crc_braid_big_table = [[0u64; 256]; CRC_W];
    braid(&mut crc_braid_table, &mut crc_braid_big_table, CRC_N, CRC_W);

    CrcTables {
        crc_table,
        crc_big_table,
        x2n_table,
        crc_braid_table,
        crc_braid_big_table,
    }
}
