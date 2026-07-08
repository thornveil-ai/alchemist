#include <stdint.h>
uint32_t byte_sum(const unsigned char *data, int len) {
    uint32_t s = 0;
    int i;
    for (i = 0; i < len; i++) {
        s += data[i];
    }
    return s;
}
uint32_t weighted_sum(const unsigned char *data, int len) {
    uint32_t base = byte_sum(data, len);
    uint32_t doubled = base * 2u;
    uint32_t total = doubled + (uint32_t)len;
    return total;
}
