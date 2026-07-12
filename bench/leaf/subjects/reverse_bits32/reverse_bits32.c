/* leaf-bench subject: reverse_bits32 (category: scalar) */
#include <stdint.h>
unsigned reverse_bits32(unsigned x) {
    unsigned r = 0;
    for (int i = 0; i < 32; i++) { r = (r << 1) | (x & 1u); x >>= 1; }
    return r;
}
