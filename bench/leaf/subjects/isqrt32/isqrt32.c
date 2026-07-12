/* leaf-bench subject: isqrt32 (category: scalar) */
#include <stdint.h>
unsigned isqrt32(unsigned x) {
    unsigned res = 0, bit = 1u << 30;
    while (bit > x) bit >>= 2;
    while (bit) { if (x >= res + bit) { x -= res + bit; res = (res >> 1) + bit; } else res >>= 1; bit >>= 2; }
    return res;
}
