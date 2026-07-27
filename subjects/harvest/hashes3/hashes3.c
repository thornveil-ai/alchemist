#include <stdint.h>
uint32_t kr_hash(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++) h=h*31u+d[i]; return h; }
uint32_t kr_hash131(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++) h=h*131u+d[i]; return h; }
uint32_t jenkins_oaat(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++){ h+=d[i]; h+=h<<10; h^=h>>6; } h+=h<<3; h^=h>>11; h+=h<<15; return h; }
uint32_t murmur_oaat(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++){ h^=d[i]; h*=0x5bd1e995u; h^=h>>15; } return h; }
uint32_t sax_hash(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++) h^=(h<<5)+(h>>2)+d[i]; return h; }
uint32_t rolling_poly(const uint8_t* d, int n){ uint32_t h=0; const uint32_t B=257u; for(int i=0;i<n;i++) h=h*B+d[i]+1u; return h; }
uint32_t fletcher_like(const uint8_t* d, int n){ uint32_t a=0,b=0; for(int i=0;i<n;i++){ a+=d[i]; b+=a; } return (b<<16)|(a&0xFFFF); }
uint32_t xorshift_hash(const uint8_t* d, int n){ uint32_t h=(uint32_t)n*2654435761u; for(int i=0;i<n;i++){ h^=d[i]; h^=h<<13; h^=h>>17; h^=h<<5; } return h; }
uint32_t add_rotate_hash(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++){ h+=d[i]; h=(h<<7)|(h>>25); } return h; }
uint32_t bernstein_xor(const uint8_t* d, int n){ uint32_t h=5381; for(int i=0;i<n;i++) h=(h*33)^d[i]; return h; }
uint64_t fnv0_64(const uint8_t* d, int n){ uint64_t h=0; for(int i=0;i<n;i++){ h*=1099511628211ull; h^=d[i]; } return h; }
uint32_t crc_like_poly(const uint8_t* d, int n){ uint32_t h=0xFFFFFFFFu; for(int i=0;i<n;i++){ h^=(uint32_t)d[i]<<24; for(int b=0;b<8;b++) h=(h&0x80000000u)?((h<<1)^0x04C11DB7u):(h<<1); } return h; }
