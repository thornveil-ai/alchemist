#include <stdint.h>

typedef struct
{

    uint32_t s[4];

} tiny_jambu_state_t;
typedef uint32_t tiny_jambu_key_word_t;
static void tiny_jambu_permutation_128
    (tiny_jambu_state_t *state, const tiny_jambu_key_word_t *key,
     unsigned rounds);
static void tiny_jambu_permutation_192
    (tiny_jambu_state_t *state, const tiny_jambu_key_word_t *key,
     unsigned rounds);
static void tiny_jambu_permutation_256
    (tiny_jambu_state_t *state, const tiny_jambu_key_word_t *key,
     unsigned rounds);
static void tiny_jambu_permutation_128
    (tiny_jambu_state_t *state, const tiny_jambu_key_word_t *key,
     unsigned rounds)
{
    uint32_t t1, t2, t3, t4;

    uint32_t s0 = state->s[0];
    uint32_t s1 = state->s[1];
    uint32_t s2 = state->s[2];
    uint32_t s3 = state->s[3];

    for (; rounds > 0; --rounds) {

        do { t1 = (s1 >> 15) | (s2 << 17); t2 = (s2 >> 6) | (s3 << 26); t3 = (s2 >> 21) | (s3 << 11); t4 = (s2 >> 27) | (s3 << 5); s0 ^= t1 ^ (t2 & t3) ^ t4 ^ key[0]; } while (0);
        do { t1 = (s2 >> 15) | (s3 << 17); t2 = (s3 >> 6) | (s0 << 26); t3 = (s3 >> 21) | (s0 << 11); t4 = (s3 >> 27) | (s0 << 5); s1 ^= t1 ^ (t2 & t3) ^ t4 ^ key[1]; } while (0);
        do { t1 = (s3 >> 15) | (s0 << 17); t2 = (s0 >> 6) | (s1 << 26); t3 = (s0 >> 21) | (s1 << 11); t4 = (s0 >> 27) | (s1 << 5); s2 ^= t1 ^ (t2 & t3) ^ t4 ^ key[2]; } while (0);
        do { t1 = (s0 >> 15) | (s1 << 17); t2 = (s1 >> 6) | (s2 << 26); t3 = (s1 >> 21) | (s2 << 11); t4 = (s1 >> 27) | (s2 << 5); s3 ^= t1 ^ (t2 & t3) ^ t4 ^ key[3]; } while (0);

        if ((--rounds) == 0)
            break;

        do { t1 = (s1 >> 15) | (s2 << 17); t2 = (s2 >> 6) | (s3 << 26); t3 = (s2 >> 21) | (s3 << 11); t4 = (s2 >> 27) | (s3 << 5); s0 ^= t1 ^ (t2 & t3) ^ t4 ^ key[0]; } while (0);
        do { t1 = (s2 >> 15) | (s3 << 17); t2 = (s3 >> 6) | (s0 << 26); t3 = (s3 >> 21) | (s0 << 11); t4 = (s3 >> 27) | (s0 << 5); s1 ^= t1 ^ (t2 & t3) ^ t4 ^ key[1]; } while (0);
        do { t1 = (s3 >> 15) | (s0 << 17); t2 = (s0 >> 6) | (s1 << 26); t3 = (s0 >> 21) | (s1 << 11); t4 = (s0 >> 27) | (s1 << 5); s2 ^= t1 ^ (t2 & t3) ^ t4 ^ key[2]; } while (0);
        do { t1 = (s0 >> 15) | (s1 << 17); t2 = (s1 >> 6) | (s2 << 26); t3 = (s1 >> 21) | (s2 << 11); t4 = (s1 >> 27) | (s2 << 5); s3 ^= t1 ^ (t2 & t3) ^ t4 ^ key[3]; } while (0);
    }

    state->s[0] = s0;
    state->s[1] = s1;
    state->s[2] = s2;
    state->s[3] = s3;
}

static void tiny_jambu_permutation_192
    (tiny_jambu_state_t *state, const tiny_jambu_key_word_t *key,
     unsigned rounds)
{
    uint32_t t1, t2, t3, t4;

    uint32_t s0 = state->s[0];
    uint32_t s1 = state->s[1];
    uint32_t s2 = state->s[2];
    uint32_t s3 = state->s[3];

    for (; rounds > 0; --rounds) {

        do { t1 = (s1 >> 15) | (s2 << 17); t2 = (s2 >> 6) | (s3 << 26); t3 = (s2 >> 21) | (s3 << 11); t4 = (s2 >> 27) | (s3 << 5); s0 ^= t1 ^ (t2 & t3) ^ t4 ^ key[0]; } while (0);
        do { t1 = (s2 >> 15) | (s3 << 17); t2 = (s3 >> 6) | (s0 << 26); t3 = (s3 >> 21) | (s0 << 11); t4 = (s3 >> 27) | (s0 << 5); s1 ^= t1 ^ (t2 & t3) ^ t4 ^ key[1]; } while (0);
        do { t1 = (s3 >> 15) | (s0 << 17); t2 = (s0 >> 6) | (s1 << 26); t3 = (s0 >> 21) | (s1 << 11); t4 = (s0 >> 27) | (s1 << 5); s2 ^= t1 ^ (t2 & t3) ^ t4 ^ key[2]; } while (0);
        do { t1 = (s0 >> 15) | (s1 << 17); t2 = (s1 >> 6) | (s2 << 26); t3 = (s1 >> 21) | (s2 << 11); t4 = (s1 >> 27) | (s2 << 5); s3 ^= t1 ^ (t2 & t3) ^ t4 ^ key[3]; } while (0);

        if ((--rounds) == 0)
            break;

        do { t1 = (s1 >> 15) | (s2 << 17); t2 = (s2 >> 6) | (s3 << 26); t3 = (s2 >> 21) | (s3 << 11); t4 = (s2 >> 27) | (s3 << 5); s0 ^= t1 ^ (t2 & t3) ^ t4 ^ key[4]; } while (0);
        do { t1 = (s2 >> 15) | (s3 << 17); t2 = (s3 >> 6) | (s0 << 26); t3 = (s3 >> 21) | (s0 << 11); t4 = (s3 >> 27) | (s0 << 5); s1 ^= t1 ^ (t2 & t3) ^ t4 ^ key[5]; } while (0);
        do { t1 = (s3 >> 15) | (s0 << 17); t2 = (s0 >> 6) | (s1 << 26); t3 = (s0 >> 21) | (s1 << 11); t4 = (s0 >> 27) | (s1 << 5); s2 ^= t1 ^ (t2 & t3) ^ t4 ^ key[0]; } while (0);
        do { t1 = (s0 >> 15) | (s1 << 17); t2 = (s1 >> 6) | (s2 << 26); t3 = (s1 >> 21) | (s2 << 11); t4 = (s1 >> 27) | (s2 << 5); s3 ^= t1 ^ (t2 & t3) ^ t4 ^ key[1]; } while (0);

        if ((--rounds) == 0)
            break;

        do { t1 = (s1 >> 15) | (s2 << 17); t2 = (s2 >> 6) | (s3 << 26); t3 = (s2 >> 21) | (s3 << 11); t4 = (s2 >> 27) | (s3 << 5); s0 ^= t1 ^ (t2 & t3) ^ t4 ^ key[2]; } while (0);
        do { t1 = (s2 >> 15) | (s3 << 17); t2 = (s3 >> 6) | (s0 << 26); t3 = (s3 >> 21) | (s0 << 11); t4 = (s3 >> 27) | (s0 << 5); s1 ^= t1 ^ (t2 & t3) ^ t4 ^ key[3]; } while (0);
        do { t1 = (s3 >> 15) | (s0 << 17); t2 = (s0 >> 6) | (s1 << 26); t3 = (s0 >> 21) | (s1 << 11); t4 = (s0 >> 27) | (s1 << 5); s2 ^= t1 ^ (t2 & t3) ^ t4 ^ key[4]; } while (0);
        do { t1 = (s0 >> 15) | (s1 << 17); t2 = (s1 >> 6) | (s2 << 26); t3 = (s1 >> 21) | (s2 << 11); t4 = (s1 >> 27) | (s2 << 5); s3 ^= t1 ^ (t2 & t3) ^ t4 ^ key[5]; } while (0);
    }

    state->s[0] = s0;
    state->s[1] = s1;
    state->s[2] = s2;
    state->s[3] = s3;
}

static void tiny_jambu_permutation_256
    (tiny_jambu_state_t *state, const tiny_jambu_key_word_t *key,
     unsigned rounds)
{
    uint32_t t1, t2, t3, t4;

    uint32_t s0 = state->s[0];
    uint32_t s1 = state->s[1];
    uint32_t s2 = state->s[2];
    uint32_t s3 = state->s[3];

    for (; rounds > 0; --rounds) {

        do { t1 = (s1 >> 15) | (s2 << 17); t2 = (s2 >> 6) | (s3 << 26); t3 = (s2 >> 21) | (s3 << 11); t4 = (s2 >> 27) | (s3 << 5); s0 ^= t1 ^ (t2 & t3) ^ t4 ^ key[0]; } while (0);
        do { t1 = (s2 >> 15) | (s3 << 17); t2 = (s3 >> 6) | (s0 << 26); t3 = (s3 >> 21) | (s0 << 11); t4 = (s3 >> 27) | (s0 << 5); s1 ^= t1 ^ (t2 & t3) ^ t4 ^ key[1]; } while (0);
        do { t1 = (s3 >> 15) | (s0 << 17); t2 = (s0 >> 6) | (s1 << 26); t3 = (s0 >> 21) | (s1 << 11); t4 = (s0 >> 27) | (s1 << 5); s2 ^= t1 ^ (t2 & t3) ^ t4 ^ key[2]; } while (0);
        do { t1 = (s0 >> 15) | (s1 << 17); t2 = (s1 >> 6) | (s2 << 26); t3 = (s1 >> 21) | (s2 << 11); t4 = (s1 >> 27) | (s2 << 5); s3 ^= t1 ^ (t2 & t3) ^ t4 ^ key[3]; } while (0);

        if ((--rounds) == 0)
            break;

        do { t1 = (s1 >> 15) | (s2 << 17); t2 = (s2 >> 6) | (s3 << 26); t3 = (s2 >> 21) | (s3 << 11); t4 = (s2 >> 27) | (s3 << 5); s0 ^= t1 ^ (t2 & t3) ^ t4 ^ key[4]; } while (0);
        do { t1 = (s2 >> 15) | (s3 << 17); t2 = (s3 >> 6) | (s0 << 26); t3 = (s3 >> 21) | (s0 << 11); t4 = (s3 >> 27) | (s0 << 5); s1 ^= t1 ^ (t2 & t3) ^ t4 ^ key[5]; } while (0);
        do { t1 = (s3 >> 15) | (s0 << 17); t2 = (s0 >> 6) | (s1 << 26); t3 = (s0 >> 21) | (s1 << 11); t4 = (s0 >> 27) | (s1 << 5); s2 ^= t1 ^ (t2 & t3) ^ t4 ^ key[6]; } while (0);
        do { t1 = (s0 >> 15) | (s1 << 17); t2 = (s1 >> 6) | (s2 << 26); t3 = (s1 >> 21) | (s2 << 11); t4 = (s1 >> 27) | (s2 << 5); s3 ^= t1 ^ (t2 & t3) ^ t4 ^ key[7]; } while (0);
    }

    state->s[0] = s0;
    state->s[1] = s1;
    state->s[2] = s2;
    state->s[3] = s3;
}
#include <string.h>

/* Reshaped as buf_transform: input = state(16 LE) || key(K LE); output =
 * permuted state (16 LE). Rounds fixed at P1024 (the TinyJAMBU encryption
 * permutation). Input is zero-padded/truncated so every length maps
 * deterministically. K = 16 (128), 24 (192), 32 (256). */
int tinyjambu128_p1024(const char *in, int inlen, char *out, int outcap)
{
    unsigned char buf[32]; memset(buf, 0, sizeof(buf));
    int n = inlen < 32 ? inlen : 32; if (n > 0) memcpy(buf, in, n);
    tiny_jambu_state_t st; tiny_jambu_key_word_t key[4];
    memcpy(st.s, buf, 16); memcpy(key, buf + 16, 16);
    tiny_jambu_permutation_128(&st, key, 8);
    if (outcap < 16) return -1;
    memcpy(out, st.s, 16); return 16;
}

int tinyjambu192_p1024(const char *in, int inlen, char *out, int outcap)
{
    unsigned char buf[40]; memset(buf, 0, sizeof(buf));
    int n = inlen < 40 ? inlen : 40; if (n > 0) memcpy(buf, in, n);
    tiny_jambu_state_t st; tiny_jambu_key_word_t key[6];
    memcpy(st.s, buf, 16); memcpy(key, buf + 16, 24);
    tiny_jambu_permutation_192(&st, key, 8);
    if (outcap < 16) return -1;
    memcpy(out, st.s, 16); return 16;
}

int tinyjambu256_p1024(const char *in, int inlen, char *out, int outcap)
{
    unsigned char buf[48]; memset(buf, 0, sizeof(buf));
    int n = inlen < 48 ? inlen : 48; if (n > 0) memcpy(buf, in, n);
    tiny_jambu_state_t st; tiny_jambu_key_word_t key[8];
    memcpy(st.s, buf, 16); memcpy(key, buf + 16, 32);
    tiny_jambu_permutation_256(&st, key, 8);
    if (outcap < 16) return -1;
    memcpy(out, st.s, 16); return 16;
}
