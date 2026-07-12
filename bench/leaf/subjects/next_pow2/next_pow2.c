/* leaf-bench subject: next_pow2 (category: scalar) */
#include <stdint.h>
unsigned next_pow2(unsigned x) {
    if (x == 0) return 1;
    x--; x |= x >> 1; x |= x >> 2; x |= x >> 4; x |= x >> 8; x |= x >> 16; x++;
    return x;
}
