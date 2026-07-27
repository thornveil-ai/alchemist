#include <stdint.h>
uint32_t submod32(uint32_t a, uint32_t b, uint32_t m){ if(!m)return 0; a%=m; b%=m; return (a>=b)?(a-b):(a+m-b); }
uint32_t negmod32(uint32_t a, uint32_t m){ if(!m)return 0; a%=m; return a?(m-a):0; }
uint64_t mulmod64(uint64_t a, uint64_t b, uint64_t m){ if(!m)return 0; return (uint64_t)(((unsigned __int128)a*b)%m); }
uint32_t doublemod(uint32_t a, uint32_t m){ if(!m)return 0; a%=m; return (a+a)%m; }
uint32_t divmod_floor(int32_t a, int32_t b){ if(!b)return 0; int32_t q=a/b; if((a%b!=0)&&((a<0)!=(b<0)))q--; return (uint32_t)q; }
uint32_t mod_floored(int32_t a, int32_t b){ if(!b)return 0; int32_t r=a%b; if(r!=0&&((r<0)!=(b<0)))r+=b; return (uint32_t)r; }
uint32_t binomial_mod(uint32_t n, uint32_t k, uint32_t m){ if(!m||k>n)return 0; if(k>n-k)k=n-k; uint64_t r=1%m; for(uint32_t i=0;i<k;i++){ r=(r*((n-i)%m))%m; } return (uint32_t)r; }
uint32_t chinese2(uint32_t a1, uint32_t n1, uint32_t a2, uint32_t n2){ if(!n1||!n2)return 0; uint64_t x=a1; while(x%n2!=a2%n2)x+=n1; return (uint32_t)(x%((uint64_t)n1*n2)); }
uint32_t order_hint(uint32_t a, uint32_t m){ if(m<=1)return 0; a%=m; if(!a)return 0; uint64_t cur=a; for(uint32_t k=1;k<=m;k++){ if(cur==1)return k; cur=(cur*a)%m; } return 0; }
uint32_t sqrmod(uint32_t a, uint32_t m){ if(!m)return 0; return (uint32_t)(((uint64_t)(a%m)*(a%m))%m); }
