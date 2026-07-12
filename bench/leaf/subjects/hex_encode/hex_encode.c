/* leaf-bench subject: hex_encode (category: cstr) */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
char *hex_encode(char *s) {
    static const char *hx = "0123456789abcdef";
    size_t n = strlen(s);
    char *out = (char *)malloc(2 * n + 1);
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)s[i];
        out[2 * i] = hx[c >> 4];
        out[2 * i + 1] = hx[c & 0xf];
    }
    out[2 * n] = 0;
    return out;
}
