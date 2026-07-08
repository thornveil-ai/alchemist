#include <stdint.h>
static uint8_t mix_byte(uint8_t acc, uint8_t b) { return (uint8_t)((acc ^ b) + 0x9e); }
uint32_t rollcksum(const unsigned char *data, int len) {
    uint32_t sum = 0;
    uint8_t acc = 0;
    int i;
    for (i = 0; i < len; i++) { acc = mix_byte(acc, data[i]); sum += acc; }
    return sum;
}
