#include <stdint.h>
uint32_t murmur2_32(const uint8_t* d, int n){ uint32_t h=0^ (uint32_t)n; const uint32_t m=0x5bd1e995u; int i=0; while(n-i>=4){ uint32_t k; k=(uint32_t)d[i]|((uint32_t)d[i+1]<<8)|((uint32_t)d[i+2]<<16)|((uint32_t)d[i+3]<<24); k*=m; k^=k>>24; k*=m; h*=m; h^=k; i+=4;} int r=n-i; if(r>=3)h^=(uint32_t)d[i+2]<<16; if(r>=2)h^=(uint32_t)d[i+1]<<8; if(r>=1){h^=(uint32_t)d[i]; h*=m;} h^=h>>13; h*=m; h^=h>>15; return h; }
uint32_t rs_hash(const uint8_t* d, int n){ uint32_t a=63689u,b=378551u,h=0; for(int i=0;i<n;i++){ h=h*a+d[i]; a*=b; } return h; }
uint32_t js_hash(const uint8_t* d, int n){ uint32_t h=1315423911u; for(int i=0;i<n;i++) h^=((h<<5)+d[i]+(h>>2)); return h; }
uint32_t pjw_hash(const uint8_t* d, int n){ uint32_t h=0,t; for(int i=0;i<n;i++){ h=(h<<4)+d[i]; if((t=h&0xF0000000u)){ h^=t>>24; h&=~t; } } return h; }
uint32_t oat_hash(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++){ h+=d[i]; h+=h<<10; h^=h>>6; } h+=h<<3; h^=h>>11; h+=h<<15; return h; }
uint32_t fnv0_32(const uint8_t* d, int n){ uint32_t h=0; for(int i=0;i<n;i++){ h*=16777619u; h^=d[i]; } return h; }
uint32_t crc32_hash(const uint8_t* d, int n){ uint32_t h=~0u; for(int i=0;i<n;i++){ h^=d[i]; for(int b=0;b<8;b++) h=(h&1)?((h>>1)^0xEDB88320u):(h>>1);} return ~h; }
uint32_t rot_hash(const uint8_t* d, int n){ uint32_t h=(uint32_t)n; for(int i=0;i<n;i++) h=(h<<4)^(h>>28)^d[i]; return h; }
