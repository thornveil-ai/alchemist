#include <stdio.h>
#include <string.h>
#include "jsmn.h"
/* Reference: parse argv[1] JSON, print "ret" then one line per token:
   type start end size */
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    jsmn_parser p; jsmn_init(&p);
    jsmntok_t toks[256];
    int r = jsmn_parse(&p, argv[1], strlen(argv[1]), toks, 256);
    printf("%d\n", r);
    for (int i = 0; i < r; i++)
        printf("%d %d %d %d\n", toks[i].type, toks[i].start, toks[i].end, toks[i].size);
    return 0;
}
