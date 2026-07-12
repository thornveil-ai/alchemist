/* leaf-bench subject: clz32 (category: scalar) */
#include <stdint.h>
int clz32(unsigned x) { if (!x) return 32; int n = 0; while (!(x & 0x80000000u)) { n++; x <<= 1; } return n; }
