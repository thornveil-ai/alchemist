/* leaf-bench subject: rot13 (category: cstr) */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
char *rot13(char *s) {
    size_t n = strlen(s);
    char *out = (char *)malloc(n + 1);
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        if (c >= 'a' && c <= 'z') out[i] = (char)('a' + (c - 'a' + 13) % 26);
        else if (c >= 'A' && c <= 'Z') out[i] = (char)('A' + (c - 'A' + 13) % 26);
        else out[i] = c;
    }
    out[n] = 0;
    return out;
}
