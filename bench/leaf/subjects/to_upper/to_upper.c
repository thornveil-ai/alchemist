/* leaf-bench subject: to_upper (category: cstr) */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
char *to_upper(char *s) {
    size_t n = strlen(s);
    char *out = (char *)malloc(n + 1);
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        out[i] = (c >= 'a' && c <= 'z') ? (char)(c - 32) : c;
    }
    out[n] = 0;
    return out;
}
