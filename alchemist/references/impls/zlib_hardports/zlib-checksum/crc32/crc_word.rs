pub fn crc_word(mut data: u64) -> u32 {
    for _ in 0..8 {
        data = (data >> 8) ^ (CRC32_TABLE[(data & 0xff) as usize] as u64);
    }
    data as u32
}
