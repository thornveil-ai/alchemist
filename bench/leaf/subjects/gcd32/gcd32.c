/* leaf-bench subject: gcd32 (category: scalar) */
#include <stdint.h>
unsigned gcd32(unsigned a, unsigned b) { while (b) { unsigned t = a % b; a = b; b = t; } return a; }
