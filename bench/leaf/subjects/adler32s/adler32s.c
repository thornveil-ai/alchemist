/* leaf-bench subject: adler32s (category: checksum) */
#include <stdint.h>
unsigned adler32s(unsigned adler, const unsigned char *buf, int len) {
    unsigned s1 = adler & 0xffff, s2 = (adler >> 16) & 0xffff;
    for (int i = 0; i < len; i++) { s1 = (s1 + buf[i]) % 65521u; s2 = (s2 + s1) % 65521u; }
    return (s2 << 16) | s1;
}
