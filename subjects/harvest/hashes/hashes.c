#include <stdint.h>
uint32_t fnv1a_32(const uint8_t* d, int n){ uint32_t h=2166136261u; for(int i=0;i<n;i++){ h^=d[i]; h*=16777619u; } return h; }
uint32_t fnv1_32(const uint8_t* d, int n){ uint32_t h=2166136261u; for(int i=0;i<n;i++){ h*=16777619u; h^=d[i]; } return h; }
uint32_t djb2(const uint8_t* d, int n){ uint32_t h=5381u; for(int i=0;i<n;i++) h=((h<<5)+h)+d[i]; return h; }
uint32_t djb2a(const uint8_t* d, int n){ uint32_t h=5381u; for(int i=0;i<n;i++) h=((h<<5)+h)^d[i]; return h; }
uint32_t sdbm(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++) h=d[i]+(h<<6)+(h<<16)-h; return h; }
uint32_t jenkins_oaat(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++){ h+=d[i]; h+=h<<10; h^=h>>6; } h+=h<<3; h^=h>>11; h+=h<<15; return h; }
uint32_t elf_hash(const uint8_t* d, int n){ uint32_t h=0,g; for(int i=0;i<n;i++){ h=(h<<4)+d[i]; g=h&0xf0000000u; if(g) h^=g>>24; h&=~g; } return h; }
uint32_t dek_hash(const uint8_t* d, int n){ uint32_t h=(uint32_t)n; for(int i=0;i<n;i++) h=((h<<5)^(h>>27))^d[i]; return h; }
uint32_t bkdr_hash(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++) h=h*131u+d[i]; return h; }
uint32_t ap_hash(const uint8_t* d, int n){ uint32_t h=0xAAAAAAAAu; for(int i=0;i<n;i++) h ^= (i&1)?(~((h<<11)+(d[i]^(h>>5)))):((h<<7)^(d[i]*(h>>3))); return h; }
uint64_t fnv1a_64(const uint8_t* d, int n){ uint64_t h=1469598103934665603ull; for(int i=0;i<n;i++){ h^=d[i]; h*=1099511628211ull; } return h; }
