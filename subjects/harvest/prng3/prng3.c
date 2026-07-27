#include <stdint.h>
uint32_t weyl_step(uint32_t s){ return s+0x9E3779B9u; }
uint32_t jsf32_mix(uint32_t x){ uint32_t e=x-((x<<27)|(x>>5)); x=e^((x<<17)|(x>>15)); return x; }
uint32_t gjrand_mix(uint32_t x){ x^=x<<11; x^=x>>8; return x+0x9e3779b9u; }
uint32_t xorshift32_mul(uint32_t x){ x^=x<<13; x^=x>>17; x^=x<<5; return x*0x2545F491u; }
uint64_t xorshift64_mul(uint64_t x){ x^=x>>12; x^=x<<25; x^=x>>27; return x*0x2545F4914F6CDD1Dull; }
uint32_t lcg_msvc(uint32_t s){ return (214013u*s+2531011u)>>16 & 0x7fff; }
uint32_t lcg_borland(uint32_t s){ return 22695477u*s+1u; }
uint32_t lcg_minstd(uint32_t s){ return (uint32_t)(((uint64_t)s*16807u)%2147483647u); }
uint32_t middle_square(uint32_t s){ uint64_t sq=(uint64_t)s*s; return (uint32_t)((sq>>16)&0xFFFFFFFFu); }
uint64_t wyrand_step(uint64_t s){ s+=0xa0761d6478bd642full; uint64_t t=(unsigned __int128)s*(s^0xe7037ed1a0b428dbull)>>64; uint64_t u=(unsigned __int128)s*(s^0xe7037ed1a0b428dbull); return t^u; }
