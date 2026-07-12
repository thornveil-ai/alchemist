/* leaf-bench subject: sdbm (category: checksum) */
#include <stdint.h>
unsigned sdbm(const unsigned char *data, int len) {
    unsigned h = 0;
    for (int i = 0; i < len; i++) h = data[i] + (h << 6) + (h << 16) - h;
    return h;
}
