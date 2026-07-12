/* leaf-bench subject: crc32b (category: checksum) */
#include <stdint.h>
unsigned crc32b(unsigned crc, const unsigned char *buf, int len) {
    crc = ~crc;
    for (int i = 0; i < len; i++) {
        crc ^= buf[i];
        for (int j = 0; j < 8; j++)
            crc = (crc >> 1) ^ (0xEDB88320u & (unsigned)(-(int)(crc & 1)));
    }
    return ~crc;
}
