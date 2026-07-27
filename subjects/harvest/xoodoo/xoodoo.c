#include <stdint.h>
#include <string.h>

static inline uint32_t le_load_word32(const uint8_t*p){uint32_t v;memcpy(&v,p,4);return v;}
static inline void le_store_word32(uint8_t*p,uint32_t v){memcpy(p,&v,4);}
static inline uint32_t be_load_word32(const uint8_t*p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static inline void be_store_word32(uint8_t*p,uint32_t v){p[0]=(uint8_t)(v>>24);p[1]=(uint8_t)(v>>16);p[2]=(uint8_t)(v>>8);p[3]=(uint8_t)v;}
typedef union
{

    uint32_t S[3][4];

    uint32_t W[3 * 4];

    uint8_t B[3 * 4 * sizeof(uint32_t)];

} xoodoo_state_t;
static void xoodoo_permute(xoodoo_state_t *state);
static void xoodoo_permute(xoodoo_state_t *state)
{
    static uint16_t const rc[12] = {
        0x0058, 0x0038, 0x03C0, 0x00D0, 0x0120, 0x0014,
        0x0060, 0x002C, 0x0380, 0x00F0, 0x01A0, 0x0012
    };
    uint8_t round;
    uint32_t x00, x01, x02, x03;
    uint32_t x10, x11, x12, x13;
    uint32_t x20, x21, x22, x23;
    uint32_t t1, t2;

    x00 = state->S[0][0];
    x01 = state->S[0][1];
    x02 = state->S[0][2];
    x03 = state->S[0][3];
    x10 = state->S[1][0];
    x11 = state->S[1][1];
    x12 = state->S[1][2];
    x13 = state->S[1][3];
    x20 = state->S[2][0];
    x21 = state->S[2][1];
    x22 = state->S[2][2];
    x23 = state->S[2][3];
    for (round = 0; round < 12; ++round) {

        t1 = x03 ^ x13 ^ x23;
        t2 = x00 ^ x10 ^ x20;
        t1 = (((uint32_t)(((t1))<<(5)))|((uint32_t)(((t1))>>((32-(5))&31)))) ^ (((uint32_t)(((t1))<<(14)))|((uint32_t)(((t1))>>((32-(14))&31))));
        t2 = (((uint32_t)(((t2))<<(5)))|((uint32_t)(((t2))>>((32-(5))&31)))) ^ (((uint32_t)(((t2))<<(14)))|((uint32_t)(((t2))>>((32-(14))&31))));
        x00 ^= t1;
        x10 ^= t1;
        x20 ^= t1;
        t1 = x01 ^ x11 ^ x21;
        t1 = (((uint32_t)(((t1))<<(5)))|((uint32_t)(((t1))>>((32-(5))&31)))) ^ (((uint32_t)(((t1))<<(14)))|((uint32_t)(((t1))>>((32-(14))&31))));
        x01 ^= t2;
        x11 ^= t2;
        x21 ^= t2;
        t2 = x02 ^ x12 ^ x22;
        t2 = (((uint32_t)(((t2))<<(5)))|((uint32_t)(((t2))>>((32-(5))&31)))) ^ (((uint32_t)(((t2))<<(14)))|((uint32_t)(((t2))>>((32-(14))&31))));
        x02 ^= t1;
        x12 ^= t1;
        x22 ^= t1;
        x03 ^= t2;
        x13 ^= t2;
        x23 ^= t2;

        t1 = x13;
        x13 = x12;
        x12 = x11;
        x11 = x10;
        x10 = t1;
        x20 = (((uint32_t)(((x20))<<(11)))|((uint32_t)(((x20))>>((32-(11))&31))));
        x21 = (((uint32_t)(((x21))<<(11)))|((uint32_t)(((x21))>>((32-(11))&31))));
        x22 = (((uint32_t)(((x22))<<(11)))|((uint32_t)(((x22))>>((32-(11))&31))));
        x23 = (((uint32_t)(((x23))<<(11)))|((uint32_t)(((x23))>>((32-(11))&31))));

        x00 ^= rc[round];

        x00 ^= (~x10) & x20;
        x10 ^= (~x20) & x00;
        x20 ^= (~x00) & x10;
        x01 ^= (~x11) & x21;
        x11 ^= (~x21) & x01;
        x21 ^= (~x01) & x11;
        x02 ^= (~x12) & x22;
        x12 ^= (~x22) & x02;
        x22 ^= (~x02) & x12;
        x03 ^= (~x13) & x23;
        x13 ^= (~x23) & x03;
        x23 ^= (~x03) & x13;

        x10 = (((uint32_t)(((x10))<<(1)))|((uint32_t)(((x10))>>((32-(1))&31))));
        x11 = (((uint32_t)(((x11))<<(1)))|((uint32_t)(((x11))>>((32-(1))&31))));
        x12 = (((uint32_t)(((x12))<<(1)))|((uint32_t)(((x12))>>((32-(1))&31))));
        x13 = (((uint32_t)(((x13))<<(1)))|((uint32_t)(((x13))>>((32-(1))&31))));
        t1 = (((uint32_t)(((x22))<<(8)))|((uint32_t)(((x22))>>((32-(8))&31))));
        t2 = (((uint32_t)(((x23))<<(8)))|((uint32_t)(((x23))>>((32-(8))&31))));
        x22 = (((uint32_t)(((x20))<<(8)))|((uint32_t)(((x20))>>((32-(8))&31))));
        x23 = (((uint32_t)(((x21))<<(8)))|((uint32_t)(((x21))>>((32-(8))&31))));
        x20 = t1;
        x21 = t2;
    }

    state->S[0][0] = x00;
    state->S[0][1] = x01;
    state->S[0][2] = x02;
    state->S[0][3] = x03;
    state->S[1][0] = x10;
    state->S[1][1] = x11;
    state->S[1][2] = x12;
    state->S[1][3] = x13;
    state->S[2][0] = x20;
    state->S[2][1] = x21;
    state->S[2][2] = x22;
    state->S[2][3] = x23;
}

int xoodoo_perm(const char *in, int inlen, char *out, int outcap){
    unsigned char buf[48]; memset(buf,0,sizeof(buf));
    int n = inlen<48?inlen:48; if(n>0) memcpy(buf,in,n);
    xoodoo_state_t st; memcpy(&st, buf, 48); xoodoo_permute(&st);
    if(outcap<48) return -1;
    memcpy(out, &st, 48); return 48;
}
