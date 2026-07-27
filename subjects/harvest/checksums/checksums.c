#include <stdint.h>
uint32_t adler32(const uint8_t* d, int n){ uint32_t a=1,b=0; for(int i=0;i<n;i++){ a=(a+d[i])%65521u; b=(b+a)%65521u; } return (b<<16)|a; }
uint16_t fletcher16(const uint8_t* d, int n){ uint16_t s1=0,s2=0; for(int i=0;i<n;i++){ s1=(s1+d[i])%255; s2=(s2+s1)%255; } return (uint16_t)((s2<<8)|s1); }
uint32_t fletcher32(const uint8_t* d, int n){ uint32_t s1=0,s2=0; for(int i=0;i<n;i++){ s1=(s1+d[i])%65535u; s2=(s2+s1)%65535u; } return (s2<<16)|s1; }
uint16_t inet_checksum(const uint8_t* d, int n){ uint32_t s=0; int i; for(i=0;i+1<n;i+=2) s+=(uint32_t)((d[i]<<8)|d[i+1]); if(i<n) s+=(uint32_t)(d[i]<<8); while(s>>16) s=(s&0xffff)+(s>>16); return (uint16_t)(~s); }
uint8_t xor8(const uint8_t* d, int n){ uint8_t x=0; for(int i=0;i<n;i++) x^=d[i]; return x; }
uint8_t sum8(const uint8_t* d, int n){ uint8_t s=0; for(int i=0;i<n;i++) s=(uint8_t)(s+d[i]); return s; }
uint16_t sum16(const uint8_t* d, int n){ uint16_t s=0; for(int i=0;i<n;i++) s=(uint16_t)(s+d[i]); return s; }
uint8_t twos_comp_checksum(const uint8_t* d, int n){ uint8_t s=0; for(int i=0;i<n;i++) s=(uint8_t)(s+d[i]); return (uint8_t)(-s); }
uint32_t bsd_sum16(const uint8_t* d, int n){ uint32_t c=0; for(int i=0;i<n;i++){ c=(c>>1)|((c&1)<<15); c=(c+d[i])&0xffff; } return c; }
