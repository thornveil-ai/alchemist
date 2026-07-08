#include "mathlib.h"
uint32_t ml_checksum(const unsigned char *data, int len) {
    uint32_t h = 5381u;
    int i;
    for (i = 0; i < len; i++) {
        h = ((h << 5) + h) + (uint32_t)data[i];
    }
    return h;
}
