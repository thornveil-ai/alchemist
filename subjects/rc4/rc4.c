#include <stdint.h>

typedef struct {
    uint8_t s[256];
    int i;
    int j;
} rc4_state;

/* Key schedule: initialize the 256-byte permutation from the key. */
void rc4_init(rc4_state *st, const uint8_t *key, int keylen) {
    int i, j = 0;
    for (i = 0; i < 256; i++) st->s[i] = (uint8_t)i;
    for (i = 0; i < 256; i++) {
        j = (j + st->s[i] + key[i % keylen]) & 0xff;
        uint8_t t = st->s[i]; st->s[i] = st->s[j]; st->s[j] = t;
    }
    st->i = 0;
    st->j = 0;
}

/* PRGA: produce len keystream bytes, advancing the state. */
void rc4_keystream(rc4_state *st, uint8_t *out, int len) {
    int i = st->i, j = st->j, k;
    for (k = 0; k < len; k++) {
        i = (i + 1) & 0xff;
        j = (j + st->s[i]) & 0xff;
        uint8_t t = st->s[i]; st->s[i] = st->s[j]; st->s[j] = t;
        out[k] = st->s[(st->s[i] + st->s[j]) & 0xff];
    }
    st->i = i;
    st->j = j;
}
