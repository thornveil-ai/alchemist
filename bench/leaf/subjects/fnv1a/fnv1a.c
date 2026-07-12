/* leaf-bench subject: fnv1a (category: checksum) */
#include <stdint.h>
unsigned fnv1a(const unsigned char *data, int len) {
    unsigned h = 2166136261u;
    for (int i = 0; i < len; i++) { h ^= data[i]; h *= 16777619u; }
    return h;
}
