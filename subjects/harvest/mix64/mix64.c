#include <stdint.h>
uint64_t mix_splitmix(uint64_t z){ z+=0x9E3779B97F4A7C15ull; z=(z^(z>>30))*0xBF58476D1CE4E5B9ull; z=(z^(z>>27))*0x94D049BB133111EBull; return z^(z>>31); }
uint64_t mix_murmur3_fmix64(uint64_t k){ k^=k>>33; k*=0xff51afd7ed558ccdull; k^=k>>33; k*=0xc4ceb9fe1a85ec53ull; k^=k>>33; return k; }
uint64_t mix_rrmxmx(uint64_t v){ v^=(v>>49)|(v<<15); v*=0xD6E8FEB86659FD93ull; v^=v>>32; v*=0xD6E8FEB86659FD93ull; v^=v>>32; return v; }
uint64_t mix_moremur(uint64_t x){ x^=x>>27; x*=0x3C79AC492BA7B653ull; x^=x>>33; x*=0x1C69B3F74AC4AE35ull; x^=x>>27; return x; }
uint64_t mix_nasam64(uint64_t x){ x^=(x>>25)|(x<<39); x^=(x>>47)|(x<<17); x*=0x9E6C63D0676A9A99ull; x^=x>>23; x^=x>>51; x*=0x9E6D62D06F6A9A9Bull; x^=x>>23; x^=x>>51; return x; }
uint64_t hash64_to_64(uint64_t x){ x=(~x)+(x<<21); x=x^(x>>24); x=x*265; x=x^(x>>14); x=x*21; x=x^(x>>28); x=x+(x<<31); return x; }
uint64_t rotl64v(uint64_t x, int r){ r&=63; return (x<<r)|(x>>((64-r)&63)); }
uint64_t mul_hi64(uint64_t a, uint64_t b){ return (uint64_t)(((unsigned __int128)a*b)>>64); }
