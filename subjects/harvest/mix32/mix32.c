#include <stdint.h>
uint32_t mix_murmur3_fmix(uint32_t h){ h^=h>>16; h*=0x85ebca6bu; h^=h>>13; h*=0xc2b2ae35u; h^=h>>16; return h; }
uint32_t mix_xxh32_avalanche(uint32_t h){ h^=h>>15; h*=0x85EBCA77u; h^=h>>13; h*=0xC2B2AE3Du; h^=h>>16; return h; }
uint32_t mix_nasam32(uint32_t x){ x^=(x>>15)|(x<<17); x*=0xD168AAADu; x^=x>>15; x*=0xAF723597u; x^=x>>15; return x; }
uint32_t mix_lowbias32(uint32_t x){ x^=x>>16; x*=0x7feb352du; x^=x>>15; x*=0x846ca68bu; x^=x>>16; return x; }
uint32_t mix_triple32(uint32_t x){ x^=x>>17; x*=0xed5ad4bbu; x^=x>>11; x*=0xac4c1b51u; x^=x>>15; x*=0x31848babu; x^=x>>14; return x; }
uint32_t mix_prospector(uint32_t x){ x^=x>>15; x*=0x2c1b3c6du; x^=x>>12; x*=0x297a2d39u; x^=x>>15; return x; }
uint32_t hash_int_knuth(uint32_t x){ return x*2654435761u; }
uint32_t hash_int_wang32(uint32_t k){ k=(k^61u)^(k>>16); k=k+(k<<3); k=k^(k>>4); k=k*0x27d4eb2du; k=k^(k>>15); return k; }
uint32_t rotl32v(uint32_t x, int r){ r&=31; return (x<<r)|(x>>((32-r)&31)); }
uint32_t rotr32v(uint32_t x, int r){ r&=31; return (x>>r)|(x<<((32-r)&31)); }
uint32_t fold_xor(uint32_t x){ return (x>>16)^(x&0xFFFF); }
uint32_t hash_combine(uint32_t seed, uint32_t v){ seed^= v + 0x9e3779b9u + (seed<<6) + (seed>>2); return seed; }
