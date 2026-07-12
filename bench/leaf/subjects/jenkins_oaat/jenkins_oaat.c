/* leaf-bench subject: jenkins_oaat (category: checksum) */
#include <stdint.h>
unsigned jenkins_oaat(const unsigned char *data, int len) {
    unsigned h = 0;
    for (int i = 0; i < len; i++) { h += data[i]; h += h << 10; h ^= h >> 6; }
    h += h << 3; h ^= h >> 11; h += h << 15;
    return h;
}
