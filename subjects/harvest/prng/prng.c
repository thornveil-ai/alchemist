#include <stdint.h>
uint32_t xorshift32(uint32_t x){ x^=x<<13; x^=x>>17; x^=x<<5; return x; }
uint64_t xorshift64(uint64_t x){ x^=x<<13; x^=x>>7; x^=x<<17; return x; }
uint32_t lcg_glibc(uint32_t s){ return (uint32_t)(1103515245u*s+12345u)&0x7fffffffu; }
uint32_t lcg_numerical_recipes(uint32_t s){ return 1664525u*s+1013904223u; }
uint64_t splitmix64(uint64_t x){ x+=0x9E3779B97F4A7C15ull; uint64_t z=x; z=(z^(z>>30))*0xBF58476D1CE4E5B9ull; z=(z^(z>>27))*0x94D049BB133111EBull; return z^(z>>31); }
uint32_t pcg32_step(uint64_t s){ uint64_t x=s; uint32_t c=(uint32_t)(x>>59); x^=x>>18; uint32_t r=(uint32_t)(x>>27); return (r>>c)|(r<<((32-c)&31)); }
uint32_t wang_hash(uint32_t k){ k=(k^61u)^(k>>16); k*=9u; k^=k>>4; k*=0x27d4eb2du; k^=k>>15; return k; }
uint32_t murmur3_fmix32(uint32_t h){ h^=h>>16; h*=0x85ebca6bu; h^=h>>13; h*=0xc2b2ae35u; h^=h>>16; return h; }
uint64_t murmur3_fmix64(uint64_t k){ k^=k>>33; k*=0xff51afd7ed558ccdull; k^=k>>33; k*=0xc4ceb9fe1a85ec53ull; k^=k>>33; return k; }
