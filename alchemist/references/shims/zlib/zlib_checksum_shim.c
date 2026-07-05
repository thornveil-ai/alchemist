/* Checksum shim exposing zlib's static-local CRC-32 helpers as testable
   DLL entry points. Companion to zlib_state_shim.c (deflate side) and
   zlib_inflate_shim.c (inflate side).

   Strategy: pull crc32.c into a single compile unit. Its `local` (static)
   helpers — crc_word, crc_word_big, multmodp, x2nmodp — are then in-scope
   for the shim's extern entry points. crc32.c includes zutil.h itself and,
   without DYNAMIC_CRC_TABLE, takes crc_table / crc_big_table / x2n_table
   statically from crc32.h, so no other zlib sources are needed.

   Configuration pin: on x86_64 gcc, crc32.c self-selects the braided
   W=8 / N=5 build (z_word_t is 64-bit). That is the configuration the
   Python pure references model, so shim_crc_w() / shim_crc_n() export
   the compiled values for the harness to assert. Do NOT define
   Z_TESTW / Z_TESTN here — the point is to pin the natural build.

   Each target function gets a shim_run_<fn>() entry with fixed-width
   argument/return types (stdint.h) so the ctypes bindings are exact:
     shim_run_crc_word(u64)      -> u32   (z_crc_t result)
     shim_run_crc_word_big(u64)  -> u64   (z_word_t result)
     shim_run_multmodp(u32, u32) -> u32   (uLong is 32-bit on win64)
     shim_run_x2nmodp(i64, u32)  -> u32   (z_off64_t n is signed)
*/

#include <stdint.h>

/* Slurp the crc32 source body so its `local` helpers become available
   in this CU. Resolves to subjects/zlib/crc32.c (shim builds run from
   subjects/zlib/shim/ with -I ../). */
#include "../crc32.c"

/* Pin the braided configuration at compile time. crc_word/crc_word_big
   only exist when W is defined and the generic (non-ARMCRC32) path is
   compiled; the Python references assume W == 8 / N == 5 exactly. */
#if !defined(W) || W != 8
#  error "checksum shim requires the braided W=8 configuration (x86_64 gcc default)"
#endif
#if N != 5
#  error "checksum shim requires N=5 (crc32.c default; do not define Z_TESTN)"
#endif
#ifdef ARMCRC32
#  error "ARMCRC32 build replaces crc_word/crc_word_big; not a valid shim target"
#endif

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

/* ---------- Configuration pins ---------- */

EXPORT int32_t shim_crc_w(void) { return (int32_t)W; }
EXPORT int32_t shim_crc_n(void) { return (int32_t)N; }

/* ---------- Pure function runners ---------- */

/* crc_word: iterate the CRC through the W bytes of a z_word_t,
   least-significant byte first. Returns the 32-bit z_crc_t residue. */
EXPORT uint32_t shim_run_crc_word(uint64_t data) {
    return (uint32_t)crc_word((z_word_t)data);
}

/* crc_word_big: big-endian braid variant; returns the full 64-bit
   z_word_t (the swapped CRC rides in the high 32 bits). */
EXPORT uint64_t shim_run_crc_word_big(uint64_t data) {
    return (uint64_t)crc_word_big((z_word_t)data);
}

/* multmodp: GF(2)[x] multiply modulo the reflected CRC polynomial.
   uLong is 32-bit on win64 mingw (LLP64), so the uint32_t casts are
   value-preserving. CAUTION: zlib requires a != 0 — the C loop never
   terminates for a == 0. Callers must not pass a == 0. */
EXPORT uint32_t shim_run_multmodp(uint32_t a, uint32_t b) {
    return (uint32_t)multmodp((uLong)a, (uLong)b);
}

/* x2nmodp: x^(n * 2^k) mod p(x). n is z_off64_t (signed 64-bit) in C
   and must be non-negative; k wraps as unsigned (only k & 31 is used). */
EXPORT uint32_t shim_run_x2nmodp(int64_t n, uint32_t k) {
    return (uint32_t)x2nmodp((z_off64_t)n, (unsigned)k);
}

EXPORT void shim_get_crc_big_table(uint64_t *out) {
    for (int i = 0; i < 256; i++) out[i] = (uint64_t)crc_big_table[i];
}
