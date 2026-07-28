#include <stdint.h>
/*
 * OpenZFS fletcher-4 checksum (scalar, little-endian words = ZFS 'native' on
 * little-endian hosts, which is x86_64/arm64). Four 64-bit accumulators over
 * the input read as 32-bit little-endian words, plain mod-2^64 wrapping (NO
 * modular reduction -- this is what distinguishes it from classic Fletcher).
 * The four accumulators are written to out as 32 little-endian bytes.
 * Reference: github.com/openzfs/zfs module/zcommon/zfs_fletcher.c
 * (fletcher_4_scalar_native). Reference algorithm license: CDDL-1.0.
 */
int fletcher4(const char *in, int inlen, char *out, int outcap)
{
    const uint8_t *buf = (const uint8_t *)in;
    uint64_t a = 0, b = 0, c = 0, d = 0;
    int nwords = inlen / 4;
    for (int i = 0; i < nwords; i++) {
        uint32_t w = (uint32_t)buf[i*4]
                   | ((uint32_t)buf[i*4+1] << 8)
                   | ((uint32_t)buf[i*4+2] << 16)
                   | ((uint32_t)buf[i*4+3] << 24);
        a += w;
        b += a;
        c += b;
        d += c;
    }
    if (outcap < 32) return -1;
    uint64_t acc[4]; acc[0] = a; acc[1] = b; acc[2] = c; acc[3] = d;
    for (int i = 0; i < 4; i++)
        for (int j = 0; j < 8; j++)
            out[i*8 + j] = (char)((acc[i] >> (8*j)) & 0xFF);
    return 32;
}
