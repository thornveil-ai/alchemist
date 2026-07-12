/* leaf-bench subject: sum8 (category: checksum) */
#include <stdint.h>
unsigned char sum8(const unsigned char *data, int len) {
    unsigned char s = 0;
    for (int i = 0; i < len; i++) s = (unsigned char)(s + data[i]);
    return s;
}
