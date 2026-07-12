/* leaf-bench subject: count_char (category: cstr_scalar) */
#include <stdint.h>
int count_char(const char *s, char c) {
    int n = 0;
    while (*s) { if (*s == c) n++; s++; }
    return n;
}
