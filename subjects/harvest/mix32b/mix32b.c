#include <stdint.h>
uint32_t mix_h2_32(uint32_t x){ x*=0x9e3779b1u; x^=x>>15; x*=0x85ebca77u; x^=x>>13; return x; }
uint32_t mix_degski32(uint32_t x){ x^=x>>16; x*=0x45d9f3bu; x^=x>>16; x*=0x45d9f3bu; x^=x>>16; return x; }
uint32_t mix_skeeto2(uint32_t x){ x^=x>>16; x*=0x21f0aaadu; x^=x>>15; x*=0x735a2d97u; x^=x>>15; return x; }
uint32_t mix_skeeto3(uint32_t x){ x^=x>>17; x*=0xed5ad4bbu; x^=x>>11; x*=0xac4c1b51u; x^=x>>15; return x; }
uint32_t mix_xqo32(uint32_t x){ x^=x>>16; x*=0xa812d533u; x^=x>>15; x*=0xb278e4adu; x^=x>>17; return x; }
uint32_t hash_jenkins32(uint32_t a){ a=(a+0x7ed55d16u)+(a<<12); a=(a^0xc761c23cu)^(a>>19); a=(a+0x165667b1u)+(a<<5); a=(a+0xd3a2646cu)^(a<<9); a=(a+0xfd7046c5u)+(a<<3); a=(a^0xb55a4f09u)^(a>>16); return a; }
uint32_t hash_h32_finalize(uint32_t h){ h^=h>>15; h*=0x85EBCA77u; h^=h>>13; h*=0xC2B2AE3Du; h^=h>>16; return h; }
uint32_t hash_thomas_wang7(uint32_t key){ key+=~(key<<15); key^=(key>>10); key+=(key<<3); key^=(key>>6); key+=~(key<<11); key^=(key>>16); return key; }
uint32_t mul_shift_hash(uint32_t x, uint32_t m){ return (uint32_t)(((uint64_t)x*m)>>16); }
uint32_t xorrot_mix(uint32_t x){ x^=(x<<13)|(x>>19); x*=0x9e3779b1u; x^=(x<<7)|(x>>25); return x; }
uint32_t combine2_32(uint32_t a, uint32_t b){ uint32_t h=a*0x9e3779b1u; h^=b + 0x9e3779b9u + (h<<6) + (h>>2); return h; }
uint32_t fmix_variant(uint32_t h){ h^=h>>13; h*=0x5bd1e995u; h^=h>>15; return h; }
