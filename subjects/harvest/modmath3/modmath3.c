#include <stdint.h>
uint32_t pow2mod(uint32_t e, uint32_t m){ if(!m)return 0; uint64_t r=1%m,b=2%m; while(e){ if(e&1)r=(r*b)%m; b=(b*b)%m; e>>=1; } return (uint32_t)r; }
uint32_t factmod(uint32_t n, uint32_t m){ if(!m)return 0; uint64_t r=1%m; for(uint32_t i=2;i<=n;i++){ r=(r*i)%m; if(r==0)break; } return (uint32_t)r; }
uint32_t sumto_mod(uint32_t n, uint32_t m){ if(!m)return 0; uint64_t s=((uint64_t)n*(n+1)/2)%m; return (uint32_t)s; }
uint32_t geomsum_mod(uint32_t r, uint32_t n, uint32_t m){ if(!m)return 0; uint64_t sum=0,term=1%m; for(uint32_t i=0;i<n;i++){ sum=(sum+term)%m; term=(term*r)%m; } return (uint32_t)sum; }
uint32_t fibmod(uint32_t n, uint32_t m){ if(!m)return 0; uint64_t a=0,b=1%m; for(uint32_t i=0;i<n;i++){ uint64_t c=(a+b)%m; a=b; b=c; } return (uint32_t)a; }
uint32_t mulmod_add(uint32_t a, uint32_t b, uint32_t c, uint32_t m){ if(!m)return 0; return (uint32_t)((((uint64_t)a*b)%m+c)%m); }
uint32_t modexp3(uint32_t base, uint32_t e, uint32_t m){ if(m<=1)return 0; uint64_t r=1,b=base%m; while(e){ if(e&1)r=(r*b)%m; b=(b*b)%m; e>>=1; } return (uint32_t)r; }
uint32_t crt_pair(uint32_t r1, uint32_t r2, uint32_t m){ if(!m)return 0; return ((r1%m)+(r2%m))%m; }
