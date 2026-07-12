/* leaf-bench subject: djb2buf (category: checksum) */
#include <stdint.h>
unsigned djb2buf(const unsigned char *data, int len) {
    unsigned h = 5381u;
    for (int i = 0; i < len; i++) h = ((h << 5) + h) + data[i];
    return h;
}
