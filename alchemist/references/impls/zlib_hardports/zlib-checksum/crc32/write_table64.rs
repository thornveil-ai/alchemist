/// Write Table64
/// Formats and writes a 64-bit lookup table to an output stream as a
/// comma-separated list of hexadecimal values, organized into rows of three
/// elements each.
///
/// Port of zlib crc32.c:write_table64 (MAKECRCH block):
///
/// ```c
/// fprintf(out, "%s0x%016llx%s", n == 0 || n % 3 ? "" : "    ",
///         (unsigned long long)(table[n]),
///         n == k - 1 ? "" : (n % 3 == 2 ? ",\n" : ", "));
/// ```
///
/// Three entries per line, comma-separated; continuation lines are indented
/// four spaces (the first line's indent is emitted by the caller in the C
/// generator). No separator follows the final entry. Writing into a
/// `Vec<u8>` cannot fail, so this always returns `Ok(())`; the `io::Result`
/// shape mirrors the FILE* stream semantics of the C original.
pub fn write_table64(out: &mut Vec<u8>, table: &[u64], k: usize) -> std::io::Result<()> {
    use std::io::Write;
    for n in 0..k {
        // C truthiness: `n == 0 || n % 3` selects "" — i.e. the four-space
        // indent appears only when n != 0 and n % 3 == 0 (start of a line).
        let prefix = if n == 0 || n % 3 != 0 { "" } else { "    " };
        let suffix = if n == k - 1 {
            ""
        } else if n % 3 == 2 {
            ",\n"
        } else {
            ", "
        };
        write!(out, "{}0x{:016x}{}", prefix, table[n], suffix)?;
    }
    Ok(())
}
