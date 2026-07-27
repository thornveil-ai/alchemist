#include <stdint.h>
uint32_t mix_murmurish(uint32_t h){ h*=0xcc9e2d51u; h=(h<<15)|(h>>17); h*=0x1b873593u; return h; }
uint32_t mix_fasthash32(uint32_t h){ h^=h>>23; h*=0x2127599bf4325c37u; h^=h>>47; return h; }
uint32_t mix_belloch(uint32_t x){ x=((x>>16)^x)*0x45d9f3bu; x=((x>>16)^x)*0x45d9f3bu; x=(x>>16)^x; return x; }
uint32_t mix_pcg_output(uint32_t x){ x^=x>>16; x*=0x7feb352du; x^=x>>15; return x; }
uint32_t mix_wyhash32(uint32_t x){ uint64_t r=(uint64_t)x*0xa0761d65u; return (uint32_t)(r^(r>>32)); }
uint32_t mix_iqint1(uint32_t x){ x=(x<<13)^x; return x*(x*x*15731u+789221u)+1376312589u; }
uint32_t mix_hashint(uint32_t a){ a=(a+0x479ab41du)+(a<<8); a=(a^0xe4aa10ceu)^(a>>5); a=(a+0x9942f0a6u)-(a<<14); a=(a^0x5aedd67du)^(a>>3); a=(a+0x17bea992u)+(a<<7); return a; }
uint32_t mix_shifter(uint32_t x){ x+=x<<10; x^=x>>6; x+=x<<3; x^=x>>11; x+=x<<15; return x; }
uint32_t mix_bitrev_mult(uint32_t x){ x*=0x9E3779B1u; x^=x>>15; x*=0x85EBCA77u; return x^(x>>13); }
uint32_t mix_avaround(uint32_t x){ x=(x^61u)^(x>>16); x*=9u; x^=x>>4; x*=0x27d4eb2du; return x^(x>>15); }
