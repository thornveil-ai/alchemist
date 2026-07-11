#include <stdlib.h>
#include "heapbuf.h"
unsigned char *make_buffer(unsigned long n, unsigned char fill) {
    unsigned char *p = (unsigned char*)malloc(n);
    for (unsigned long i = 0; i < n; i++) p[i] = (unsigned char)(fill + i);
    return p;
}
void free_buffer(unsigned char *p) { free(p); }
