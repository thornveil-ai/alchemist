/* leaf-bench subject: popcount32 (category: scalar) */
#include <stdint.h>
int popcount32(unsigned x) { int c = 0; while (x) { c += (int)(x & 1u); x >>= 1; } return c; }
