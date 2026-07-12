/* leaf-bench subject: rotl32 (category: scalar) */
#include <stdint.h>
unsigned rotl32(unsigned x, int n) { n &= 31; return (x << n) | (x >> ((32 - n) & 31)); }
