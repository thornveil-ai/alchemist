/// Write Table
/// Formats and writes a CRC lookup table to an output stream in a specific
/// hexadecimal layout.
///
/// Port of zlib crc32.c:write_table (MAKECRCH block):
///
/// ```c
/// fprintf(out, "%s0x%08lx%s", n == 0 || n % 5 ? "" : "    ",
///         (unsigned long)(table[n]),
///         n == k - 1 ? "" : (n % 5 == 4 ? ",\n" : ", "));
/// ```
///
/// Five entries per line, comma-separated; continuation lines are indented
/// four spaces (the first line's indent is emitted by the caller in the C
/// generator, so this function starts a first line unindented). No separator
/// follows the final entry. The C writes to a FILE*; here bytes are appended
/// to `out`.
pub fn write_table(out: &mut Vec<u8>, table: &[u32], k: usize) {
    for n in 0..k {
        // C truthiness: `n == 0 || n % 5` selects "" — i.e. the four-space
        // indent appears only when n != 0 and n % 5 == 0 (start of a line).
        let prefix = if n == 0 || n % 5 != 0 { "" } else { "    " };
        let suffix = if n == k - 1 {
            ""
        } else if n % 5 == 4 {
            ",\n"
        } else {
            ", "
        };
        out.extend_from_slice(prefix.as_bytes());
        out.extend_from_slice(format!("0x{:08x}", table[n]).as_bytes());
        out.extend_from_slice(suffix.as_bytes());
    }
}
