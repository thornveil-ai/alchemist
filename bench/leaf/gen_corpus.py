#!/usr/bin/env python3
"""P0.11 — leaf-function benchmark corpus generator.

Emits a fixed corpus of small, self-contained, pure C leaf functions — one
subject directory per function under `bench/leaf/subjects/<name>/<name>.c`.

The corpus deliberately spans the shape spectrum so the benchmark honestly
measures BOTH what the converter now handles and what it still refuses:
  - checksums (seeded + unseeded)        -> classify_checksum
  - hashes over a byte buffer            -> classify_checksum
  - scalar bit/int functions (1-2 args)  -> classify_scalar
  - string transforms `char* f(char*)`   -> classify_cstr_out (P0.8a)
  - a few intentionally-uncovered shapes -> honest refusals (coverage gaps)

Run: `python bench/leaf/gen_corpus.py`  (regenerates the .c files).
The generated files ARE committed (the benchmark's fixed input); this generator
is the compact, reviewable source of truth.
"""

from __future__ import annotations

import sys
from pathlib import Path

# name -> (category, C source). Each function is self-contained and standalone-
# compilable with only <stdint.h>/<string.h>/<stdlib.h>.
CORPUS: dict[str, tuple[str, str]] = {
    # ---- checksums (seeded) ----
    "crc32b": ("checksum", r"""
unsigned crc32b(unsigned crc, const unsigned char *buf, int len) {
    crc = ~crc;
    for (int i = 0; i < len; i++) {
        crc ^= buf[i];
        for (int j = 0; j < 8; j++)
            crc = (crc >> 1) ^ (0xEDB88320u & (unsigned)(-(int)(crc & 1)));
    }
    return ~crc;
}
"""),
    "adler32s": ("checksum", r"""
unsigned adler32s(unsigned adler, const unsigned char *buf, int len) {
    unsigned s1 = adler & 0xffff, s2 = (adler >> 16) & 0xffff;
    for (int i = 0; i < len; i++) { s1 = (s1 + buf[i]) % 65521u; s2 = (s2 + s1) % 65521u; }
    return (s2 << 16) | s1;
}
"""),
    # ---- checksums / hashes (unseeded over a buffer) ----
    "fletcher16b": ("checksum", r"""
unsigned short fletcher16b(const unsigned char *data, int len) {
    unsigned short s1 = 0, s2 = 0;
    for (int i = 0; i < len; i++) { s1 = (s1 + data[i]) % 255; s2 = (s2 + s1) % 255; }
    return (unsigned short)((s2 << 8) | s1);
}
"""),
    "fnv1a": ("checksum", r"""
unsigned fnv1a(const unsigned char *data, int len) {
    unsigned h = 2166136261u;
    for (int i = 0; i < len; i++) { h ^= data[i]; h *= 16777619u; }
    return h;
}
"""),
    "djb2buf": ("checksum", r"""
unsigned djb2buf(const unsigned char *data, int len) {
    unsigned h = 5381u;
    for (int i = 0; i < len; i++) h = ((h << 5) + h) + data[i];
    return h;
}
"""),
    "sdbm": ("checksum", r"""
unsigned sdbm(const unsigned char *data, int len) {
    unsigned h = 0;
    for (int i = 0; i < len; i++) h = data[i] + (h << 6) + (h << 16) - h;
    return h;
}
"""),
    "jenkins_oaat": ("checksum", r"""
unsigned jenkins_oaat(const unsigned char *data, int len) {
    unsigned h = 0;
    for (int i = 0; i < len; i++) { h += data[i]; h += h << 10; h ^= h >> 6; }
    h += h << 3; h ^= h >> 11; h += h << 15;
    return h;
}
"""),
    "sum8": ("checksum", r"""
unsigned char sum8(const unsigned char *data, int len) {
    unsigned char s = 0;
    for (int i = 0; i < len; i++) s = (unsigned char)(s + data[i]);
    return s;
}
"""),
    # ---- scalar bit/int functions ----
    "popcount32": ("scalar", r"""
int popcount32(unsigned x) { int c = 0; while (x) { c += (int)(x & 1u); x >>= 1; } return c; }
"""),
    "clz32": ("scalar", r"""
int clz32(unsigned x) { if (!x) return 32; int n = 0; while (!(x & 0x80000000u)) { n++; x <<= 1; } return n; }
"""),
    "reverse_bits32": ("scalar", r"""
unsigned reverse_bits32(unsigned x) {
    unsigned r = 0;
    for (int i = 0; i < 32; i++) { r = (r << 1) | (x & 1u); x >>= 1; }
    return r;
}
"""),
    "parity32": ("scalar", r"""
int parity32(unsigned x) { int p = 0; while (x) { p ^= 1; x &= x - 1; } return p; }
"""),
    "next_pow2": ("scalar", r"""
unsigned next_pow2(unsigned x) {
    if (x == 0) return 1;
    x--; x |= x >> 1; x |= x >> 2; x |= x >> 4; x |= x >> 8; x |= x >> 16; x++;
    return x;
}
"""),
    "isqrt32": ("scalar", r"""
unsigned isqrt32(unsigned x) {
    unsigned res = 0, bit = 1u << 30;
    while (bit > x) bit >>= 2;
    while (bit) { if (x >= res + bit) { x -= res + bit; res = (res >> 1) + bit; } else res >>= 1; bit >>= 2; }
    return res;
}
"""),
    "rotl32": ("scalar", r"""
unsigned rotl32(unsigned x, int n) { n &= 31; return (x << n) | (x >> ((32 - n) & 31)); }
"""),
    "gcd32": ("scalar", r"""
unsigned gcd32(unsigned a, unsigned b) { while (b) { unsigned t = a % b; a = b; b = t; } return a; }
"""),
    "imin": ("scalar", r"""
int imin(int a, int b) { return a < b ? a : b; }
"""),
    "myabs": ("scalar", r"""
int myabs(int x) { return x < 0 ? -x : x; }
"""),
    # ---- string transforms: char* f(char*) (cstr_out shape, P0.8a) ----
    "to_upper": ("cstr", r"""
#include <stdlib.h>
#include <string.h>
char *to_upper(char *s) {
    size_t n = strlen(s);
    char *out = (char *)malloc(n + 1);
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        out[i] = (c >= 'a' && c <= 'z') ? (char)(c - 32) : c;
    }
    out[n] = 0;
    return out;
}
"""),
    "rot13": ("cstr", r"""
#include <stdlib.h>
#include <string.h>
char *rot13(char *s) {
    size_t n = strlen(s);
    char *out = (char *)malloc(n + 1);
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        if (c >= 'a' && c <= 'z') out[i] = (char)('a' + (c - 'a' + 13) % 26);
        else if (c >= 'A' && c <= 'Z') out[i] = (char)('A' + (c - 'A' + 13) % 26);
        else out[i] = c;
    }
    out[n] = 0;
    return out;
}
"""),
    "hex_encode": ("cstr", r"""
#include <stdlib.h>
#include <string.h>
char *hex_encode(char *s) {
    static const char *hx = "0123456789abcdef";
    size_t n = strlen(s);
    char *out = (char *)malloc(2 * n + 1);
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        out[2 * i] = hx[c >> 4];
        out[2 * i + 1] = hx[c & 0xf];
    }
    out[2 * n] = 0;
    return out;
}
"""),
    # ---- string + scalar -> scalar: cstr_scalar shape (P0.8) ----
    "count_char": ("cstr_scalar", r"""
int count_char(const char *s, char c) {
    int n = 0;
    while (*s) { if (*s == c) n++; s++; }
    return n;
}
"""),
    # ---- int-array reduction: iarray_reduce shape (P0.8) ----
    "sum_array": ("iarray_reduce", r"""
long sum_array(const int *a, int n) {
    long s = 0;
    for (int i = 0; i < n; i++) s += a[i];
    return s;
}
"""),
    "imax_array": ("iarray_reduce", r"""
int imax_array(const int *a, int n) {
    if (n <= 0) return 0;
    int m = a[0];
    for (int i = 1; i < n; i++) if (a[i] > m) m = a[i];
    return m;
}
"""),
    # ---- intentionally-uncovered shapes (honest refusals expected) ----
    # float scalar (the scalar shape is integer-only) and a void in-place int
    # array (the in-place shape is byte-only) — kept as the benchmark's honest
    # coverage-gap probes so the refusal rate stays a real measurement.
    "dsquare": ("uncovered", r"""
double dsquare(double x) { return x * x; }
"""),
    "negate_all": ("uncovered", r"""
void negate_all(int *a, int n) {
    for (int i = 0; i < n; i++) a[i] = -a[i];
}
"""),
}


def main() -> int:
    root = Path(__file__).resolve().parent / "subjects"
    root.mkdir(parents=True, exist_ok=True)
    for name, (cat, src) in CORPUS.items():
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        header = f"/* leaf-bench subject: {name} (category: {cat}) */\n#include <stdint.h>\n"
        (d / f"{name}.c").write_text(header + src.lstrip("\n"), encoding="utf-8")
    print(f"generated {len(CORPUS)} leaf subjects under {root}")
    # quick category tally
    from collections import Counter
    tally = Counter(cat for cat, _ in CORPUS.values())
    for k, v in sorted(tally.items()):
        print(f"  {k:10} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
