#include <stdint.h>
uint32_t mulberry32(uint32_t s){ uint32_t z=(s+0x6D2B79F5u); z=(z^(z>>15))*(z|1u); z^=z+(z^(z>>7))*(z|61u); return z^(z>>14); }
uint32_t sfc32_hash(uint32_t a){ uint32_t t=a+0x9E3779B9u; t^=t>>16; t*=0x21f0aaadu; t^=t>>15; t*=0x735a2d97u; t^=t>>15; return t; }
uint32_t pcg_xsh_rr(uint64_t s){ uint32_t xorshifted=(uint32_t)(((s>>18)^s)>>27); uint32_t rot=(uint32_t)(s>>59); return (xorshifted>>rot)|(xorshifted<<((-rot)&31)); }
uint32_t pcg_xsh_rs(uint64_t s){ return (uint32_t)(((s>>22)^s)>>((s>>61)+22)); }
uint32_t park_miller(uint32_t seed){ return (uint32_t)(((uint64_t)seed*48271u)%0x7fffffffu); }
uint64_t lehmer64(uint64_t s){ return (uint64_t)(((unsigned __int128)s*0xda942042e4dd58b5ull)>>64); }
uint32_t msws_step(uint64_t x){ x*=x; uint64_t w=0xb5ad4eceda1ce2a9ull; x+=w; return (uint32_t)((x>>32)|(x<<32)); }
uint32_t xshift_star32(uint32_t x){ x^=x>>16; x*=0x45d9f3bu; x^=x>>16; x*=0x45d9f3bu; x^=x>>16; return x; }
uint32_t squares_rng(uint64_t ctr, uint64_t key){ uint64_t x=ctr*key, y=x, z=y+key; x=x*x+y; x=(x>>32)|(x<<32); x=x*x+z; x=(x>>32)|(x<<32); return (uint32_t)((x*x+y)>>32); }
uint32_t romu_mix(uint32_t x){ x=0xD3833E80u*(x^(x>>15)); return x^(x>>14); }
