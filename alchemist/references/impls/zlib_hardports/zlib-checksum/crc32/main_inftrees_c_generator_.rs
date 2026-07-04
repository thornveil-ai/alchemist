/// Main (Inftrees.C Generator)
/// Generates a C header file containing static lookup tables for decoding fixed
/// Huffman codes used in zlib decompression.
///
/// Port of zlib inftrees.c:main (MAKEFIXED) plus the pieces it drives:
/// buildtables() (BUILDFIXED) and inflate_table(). It computes the fixed
/// Huffman decode tables — lenfix[512] (literal/length code: 144 symbols of
/// length 8, 112 of 9, 24 of 7, 8 of 8, built over a 512-entry root table
/// with bits = 9) and distfix[32] (32 distance symbols of length 5, bits = 5)
/// — and formats them exactly as makefixed() prints inffixed.h.
///
/// Signature note: the C main() writes the header to stdout; the return type
/// was changed from `()` to `String` because this translation has no process
/// stdout contract — the generated header text is returned so callers/tests
/// can compare it against the shipped inffixed.h.
pub fn main_inftrees_c_generator_() -> String {
    /// zlib inftrees.h `code` table entry: operation, bits, value.
    #[derive(Clone, Copy, Default)]
    struct Code {
        op: u8,
        bits: u8,
        val: u16,
    }

    /// inftrees.h codetype CODES.
    const CODES: u32 = 0;
    /// inftrees.h codetype LENS.
    const LENS: u32 = 1;
    /// inftrees.h codetype DISTS.
    const DISTS: u32 = 2;
    /// inftrees.c MAXBITS — maximum bits in a code.
    const MAXBITS: usize = 15;
    /// inftrees.h ENOUGH_LENS (without PKZIP_BUG_WORKAROUND).
    const ENOUGH_LENS: u32 = 852;
    /// inftrees.h ENOUGH_DISTS (without PKZIP_BUG_WORKAROUND).
    const ENOUGH_DISTS: u32 = 592;

    /// Port of inftrees.c:inflate_table. Builds decoding tables for the
    /// canonical Huffman code described by lens[0..codes-1] into
    /// `tbl[*table..]`; `table` is an offset into `tbl` standing in for the
    /// C's `code **table` and is advanced past the entries used. Returns 0
    /// on success, -1 for an invalid code, +1 if ENOUGH is exceeded.
    fn inflate_table(
        typ: u32,
        lens: &[u16],
        codes: usize,
        tbl: &mut [Code],
        table: &mut usize,
        bits: &mut u32,
        work: &mut [u16],
    ) -> i32 {
        /// Length codes 257..285 base (inftrees.c lbase).
        static LBASE: [u16; 31] = [
            3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99,
            115, 131, 163, 195, 227, 258, 0, 0,
        ];
        /// Length codes 257..285 extra (inftrees.c lext).
        static LEXT: [u16; 31] = [
            16, 16, 16, 16, 16, 16, 16, 16, 17, 17, 17, 17, 18, 18, 18, 18, 19, 19, 19, 19, 20,
            20, 20, 20, 21, 21, 21, 21, 16, 68, 193,
        ];
        /// Distance codes 0..29 base (inftrees.c dbase).
        static DBASE: [u16; 32] = [
            1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025,
            1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577, 0, 0,
        ];
        /// Distance codes 0..29 extra (inftrees.c dext).
        static DEXT: [u16; 32] = [
            16, 16, 16, 16, 17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 23, 24, 24, 25,
            25, 26, 26, 27, 27, 28, 28, 29, 29, 64, 64,
        ];

        let mut count = [0u16; MAXBITS + 1]; /* number of codes of each length */
        let mut offs = [0u16; MAXBITS + 1]; /* offsets in table for each length */

        /* accumulate lengths for codes (assumes lens[] all in 0..MAXBITS) */
        for sym in 0..codes {
            count[lens[sym] as usize] += 1;
        }

        /* bound code lengths, force root to be within code lengths */
        let mut root = *bits as usize;
        let mut max = MAXBITS;
        while max >= 1 {
            if count[max] != 0 {
                break;
            }
            max -= 1;
        }
        if root > max {
            root = max;
        }
        if max == 0 {
            /* no symbols to code at all: make a table to force an error */
            let here = Code {
                op: 64, /* invalid code marker */
                bits: 1,
                val: 0,
            };
            tbl[*table] = here;
            *table += 1;
            tbl[*table] = here;
            *table += 1;
            *bits = 1;
            return 0; /* no symbols, but wait for decoding to report error */
        }
        let mut min = 1;
        while min < max {
            if count[min] != 0 {
                break;
            }
            min += 1;
        }
        if root < min {
            root = min;
        }

        /* check for an over-subscribed or incomplete set of lengths */
        let mut left: i32 = 1;
        for len in 1..=MAXBITS {
            left <<= 1;
            left -= count[len] as i32;
            if left < 0 {
                return -1; /* over-subscribed */
            }
        }
        if left > 0 && (typ == CODES || max != 1) {
            return -1; /* incomplete set */
        }

        /* generate offsets into symbol table for each length for sorting */
        offs[1] = 0;
        for len in 1..MAXBITS {
            offs[len + 1] = offs[len] + count[len];
        }

        /* sort symbols by length, by symbol order within each length */
        for sym in 0..codes {
            if lens[sym] != 0 {
                work[offs[lens[sym] as usize] as usize] = sym as u16;
                offs[lens[sym] as usize] += 1;
            }
        }

        /* set up for code type */
        let (base, extra, match_): (&[u16], &[u16], usize) = match typ {
            CODES => (&[], &[], 20),
            LENS => (&LBASE, &LEXT, 257),
            _ => (&DBASE, &DEXT, 0), /* DISTS */
        };

        /* initialize state for loop */
        let mut huff: usize = 0; /* starting code */
        let mut sym: usize = 0; /* starting code symbol */
        let mut len = min; /* starting code length */
        let mut next = *table; /* current table to fill in (offset in tbl) */
        let mut curr = root; /* current table index bits */
        let mut drop_: usize = 0; /* current bits to drop from code for index */
        let mut low = usize::MAX; /* trigger new sub-table when len > root */
        let mut used: u32 = 1u32 << root; /* use root table entries */
        let mask = (1usize << root) - 1; /* mask for comparing low */

        /* check available table space */
        if (typ == LENS && used > ENOUGH_LENS) || (typ == DISTS && used > ENOUGH_DISTS) {
            return 1;
        }

        /* process all codes and make table entries */
        loop {
            /* create table entry */
            let w = work[sym] as usize;
            let here_bits = (len - drop_) as u8;
            let here = if w + 1 < match_ {
                Code {
                    op: 0,
                    bits: here_bits,
                    val: work[sym],
                }
            } else if w >= match_ {
                Code {
                    op: extra[w - match_] as u8,
                    bits: here_bits,
                    val: base[w - match_],
                }
            } else {
                Code {
                    op: 32 + 64, /* end of block */
                    bits: here_bits,
                    val: 0,
                }
            };

            /* replicate for those indices with low len bits equal to huff */
            let incr = 1usize << (len - drop_);
            let mut fill = 1usize << curr;
            min = fill; /* save offset to next table (C reuses `min`) */
            loop {
                fill -= incr;
                tbl[next + (huff >> drop_) + fill] = here;
                if fill == 0 {
                    break;
                }
            }

            /* backwards increment the len-bit code huff */
            let mut incr = 1usize << (len - 1);
            while huff & incr != 0 {
                incr >>= 1;
            }
            if incr != 0 {
                huff &= incr - 1;
                huff += incr;
            } else {
                huff = 0;
            }

            /* go to next symbol, update count, len */
            sym += 1;
            count[len] -= 1;
            if count[len] == 0 {
                if len == max {
                    break;
                }
                len = lens[work[sym] as usize] as usize;
            }

            /* create new sub-table if needed */
            if len > root && (huff & mask) != low {
                /* if first time, transition to sub-tables */
                if drop_ == 0 {
                    drop_ = root;
                }

                /* increment past last table */
                next += min; /* here min is 1 << curr */

                /* determine length of next table */
                curr = len - drop_;
                let mut left: i32 = 1 << curr;
                while curr + drop_ < max {
                    left -= count[curr + drop_] as i32;
                    if left <= 0 {
                        break;
                    }
                    curr += 1;
                    left <<= 1;
                }

                /* check for enough space */
                used += 1u32 << curr;
                if (typ == LENS && used > ENOUGH_LENS) || (typ == DISTS && used > ENOUGH_DISTS) {
                    return 1;
                }

                /* point entry in root table to sub-table */
                low = huff & mask;
                tbl[*table + low] = Code {
                    op: curr as u8,
                    bits: root as u8,
                    val: (next - *table) as u16,
                };
            }
        }

        /* fill in remaining table entry if code is incomplete (guaranteed to
        have at most one remaining entry, since if the code is incomplete, the
        maximum code length that was allowed to get this far is one bit) */
        if huff != 0 {
            tbl[next + huff] = Code {
                op: 64, /* invalid code marker */
                bits: (len - drop_) as u8,
                val: 0,
            };
        }

        /* set return parameters */
        *table += used as usize;
        *bits = root as u32;
        0
    }

    /* buildtables (inftrees.c, BUILDFIXED): build the fixed tables into
    fixed[544], lenfix at offset 0 and distfix immediately after */
    let mut lens = [0u16; 288];
    let mut work = [0u16; 288];
    let mut fixed = [Code::default(); 544];

    /* literal/length table */
    let mut sym = 0;
    while sym < 144 {
        lens[sym] = 8;
        sym += 1;
    }
    while sym < 256 {
        lens[sym] = 9;
        sym += 1;
    }
    while sym < 280 {
        lens[sym] = 7;
        sym += 1;
    }
    while sym < 288 {
        lens[sym] = 8;
        sym += 1;
    }
    let mut next: usize = 0;
    let lenfix = next;
    let mut bits: u32 = 9;
    inflate_table(LENS, &lens, 288, &mut fixed, &mut next, &mut bits, &mut work);

    /* distance table */
    sym = 0;
    while sym < 32 {
        lens[sym] = 5;
        sym += 1;
    }
    let distfix = next;
    bits = 5;
    inflate_table(DISTS, &lens, 32, &mut fixed, &mut next, &mut bits, &mut work);

    /* makefixed main(): print the tables in inffixed.h format */
    let mut out = String::new();
    out.push_str("/* inffixed.h -- table for decoding fixed codes\n");
    out.push_str(" * Generated automatically by makefixed().\n");
    out.push_str(" */\n");
    out.push('\n');
    out.push_str("/* WARNING: this file should *not* be used by applications.\n");
    out.push_str("   It is part of the implementation of this library and is\n");
    out.push_str("   subject to change. Applications should only use zlib.h.\n");
    out.push_str(" */\n");
    out.push('\n');

    let mut size: usize = 1 << 9;
    out.push_str(&format!("static const code lenfix[{}] = {{", size));
    let mut low: usize = 0;
    loop {
        if low % 7 == 0 {
            out.push_str("\n    ");
        }
        let e = fixed[lenfix + low];
        /* C: (low & 127) == 99 ? 64 : state.lencode[low].op — forces the
        invalid-code marker on the reserved length symbols so the output
        matches the shipped inffixed.h (see zlib ChangeLog for 1.2.1) */
        let op = if (low & 127) == 99 { 64 } else { e.op };
        out.push_str(&format!("{{{},{},{}}}", op, e.bits, e.val));
        low += 1;
        if low == size {
            break;
        }
        out.push(',');
    }
    out.push_str("\n};\n");

    size = 1 << 5;
    out.push_str(&format!("\nstatic const code distfix[{}] = {{", size));
    low = 0;
    loop {
        if low % 6 == 0 {
            out.push_str("\n    ");
        }
        let e = fixed[distfix + low];
        out.push_str(&format!("{{{},{},{}}}", e.op, e.bits, e.val));
        low += 1;
        if low == size {
            break;
        }
        out.push(',');
    }
    out.push_str("\n};\n");
    out
}
