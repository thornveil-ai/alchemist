#include <stdint.h>
int popcount32(uint32_t x){ int c=0; while(x){ c+=(int)(x&1u); x>>=1; } return c; }
int popcount64(uint64_t x){ int c=0; while(x){ c+=(int)(x&1u); x>>=1; } return c; }
int parity32(uint32_t x){ int p=0; while(x){ p^=1; x&=x-1u; } return p; }
uint32_t reverse_bits32(uint32_t x){ uint32_t r=0; for(int i=0;i<32;i++){ r=(r<<1)|(x&1u); x>>=1; } return r; }
uint8_t reverse_bits8(uint8_t x){ uint8_t r=0; for(int i=0;i<8;i++){ r=(uint8_t)((r<<1)|(x&1u)); x>>=1; } return r; }
uint32_t next_pow2_u32(uint32_t x){ if(x==0) return 1u; x--; x|=x>>1; x|=x>>2; x|=x>>4; x|=x>>8; x|=x>>16; return x+1u; }
int ilog2_u32(uint32_t x){ int r=-1; while(x){ r++; x>>=1; } return r; }
uint32_t gcd_u32(uint32_t a, uint32_t b){ while(b){ uint32_t t=b; b=a%b; a=t; } return a; }
uint32_t rotl32(uint32_t x, uint32_t n){ n&=31u; return (x<<n)|(x>>((32u-n)&31u)); }
uint32_t rotr32(uint32_t x, uint32_t n){ n&=31u; return (x>>n)|(x<<((32u-n)&31u)); }
