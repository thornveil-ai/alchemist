#include <stdint.h>
uint32_t rng_gjrand32(uint32_t x){ x^=x<<10; x^=x>>15; x^=x<<4; return x+0x9E3779B9u; }
uint32_t rng_gorilla(uint32_t s){ s^=s<<7; s^=s>>1; s^=s<<9; return s; }
uint32_t rng_gpu_hash(uint32_t x){ x+=(x<<10); x^=(x>>6); x+=(x<<3); x^=(x>>11); x+=(x<<15); return x; }
uint32_t rng_hash_wo(uint32_t s){ s=(s^61u)^(s>>16); s*=9u; s=s^(s>>4); s*=0x27d4eb2du; s=s^(s>>15); return s; }
uint64_t rng_xorshift128p_step(uint64_t s0){ uint64_t x=s0; x^=x<<23; x^=x>>17; x^=x>>26; return x; }
uint32_t rng_lcg_knuth(uint32_t s){ return 1103515245u*s+12345u; }
uint32_t rng_lcg_glibc2(uint32_t s){ return (1103515245u*s+12345u)&0x7FFFFFFFu; }
uint64_t rng_pcg64_step(uint64_t s){ return s*6364136223846793005ull+1442695040888963407ull; }
uint32_t rng_add_rotate(uint32_t s){ s+=0x6D2B79F5u; s=(s<<13)|(s>>19); return s*5u+0xe6546b64u; }
uint32_t rng_tea_round(uint32_t v, uint32_t k){ return v+(((v<<4)+k)^(v+0x9e3779b9u)^((v>>5)+k)); }
