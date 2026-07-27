#include <stdint.h>
uint64_t mix_stafford13(uint64_t z){ z=(z^(z>>30))*0xBF58476D1CE4E5B9ull; z=(z^(z>>27))*0x94D049BB133111EBull; return z^(z>>31); }
uint64_t mix_degski64(uint64_t x){ x^=x>>32; x*=0xd6e8feb86659fd93ull; x^=x>>32; x*=0xd6e8feb86659fd93ull; x^=x>>32; return x; }
uint64_t mix_xnasam(uint64_t x, uint64_t c){ x^=c; x^=(x>>25)|(x<<39); x^=(x>>47)|(x<<17); x*=0x9E6C63D0676A9A99ull; x^=x>>23; x^=x>>51; return x; }
uint64_t mix_lea64(uint64_t z){ z=(z^(z>>32))*0xdaba0b6eb09322e3ull; z=(z^(z>>32))*0xdaba0b6eb09322e3ull; return z^(z>>32); }
uint64_t mix_pelican64(uint64_t x){ x^=x>>31; x*=0x7fb5d329728ea185ull; x^=x>>27; x*=0x81dadef4bc2dd44dull; x^=x>>33; return x; }
uint64_t hash_boost64(uint64_t seed, uint64_t v){ seed^=v+0x9e3779b97f4a7c15ull+(seed<<12)+(seed>>4); return seed; }
uint64_t splitmix_step(uint64_t x, uint64_t gamma){ uint64_t z=x+gamma; z=(z^(z>>30))*0xBF58476D1CE4E5B9ull; z=(z^(z>>27))*0x94D049BB133111EBull; return z^(z>>31); }
uint64_t rotl_mul64(uint64_t x){ x=((x<<23)|(x>>41)); x*=0xff51afd7ed558ccdull; return x^(x>>29); }
