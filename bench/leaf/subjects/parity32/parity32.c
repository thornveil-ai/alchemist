/* leaf-bench subject: parity32 (category: scalar) */
#include <stdint.h>
int parity32(unsigned x) { int p = 0; while (x) { p ^= 1; x &= x - 1; } return p; }
