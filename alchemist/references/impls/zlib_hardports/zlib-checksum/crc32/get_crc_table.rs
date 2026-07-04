/// Get Crc Table
/// Provides access to the precomputed CRC-32 lookup table, ensuring the table is
/// initialized before access.
///
/// Standards: IEEE 802.3, variant:ieee_reflected
///
/// Port of zlib crc32.c:get_crc_table. In C, when DYNAMIC_CRC_TABLE is
/// defined this runs make_crc_table() under z_once() and then returns
/// `crc_table`; in this translation the byte-wise table is the const
/// `CRC32_TABLE`, so initialization is unconditional at compile time and
/// the function just exposes the table.
pub fn get_crc_table() -> &'static [u32] {
    &CRC32_TABLE
}
