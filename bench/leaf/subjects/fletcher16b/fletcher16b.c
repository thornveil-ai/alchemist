/* leaf-bench subject: fletcher16b (category: checksum) */
#include <stdint.h>
unsigned short fletcher16b(const unsigned char *data, int len) {
    unsigned short s1 = 0, s2 = 0;
    for (int i = 0; i < len; i++) { s1 = (s1 + data[i]) % 255; s2 = (s2 + s1) % 255; }
    return (unsigned short)((s2 << 8) | s1);
}
