#include <stdint.h>
uint32_t mulmod32(uint32_t a, uint32_t b, uint32_t m){ if(!m)return 0; return (uint32_t)(((uint64_t)a*b)%m); }
uint32_t addmod32(uint32_t a, uint32_t b, uint32_t m){ if(!m)return 0; return (uint32_t)(((uint64_t)a+b)%m); }
uint32_t powmod32(uint32_t base, uint32_t exp, uint32_t m){ if(!m)return 0; uint64_t r=1%m, b=base%m; while(exp){ if(exp&1)r=(r*b)%m; b=(b*b)%m; exp>>=1; } return (uint32_t)r; }
uint32_t gcd32(uint32_t a, uint32_t b){ while(b){ uint32_t t=a%b; a=b; b=t; } return a; }
uint32_t gcd_binary(uint32_t u, uint32_t v){ if(!u)return v; if(!v)return u; int s=0; while(!((u|v)&1)){ u>>=1; v>>=1; s++; } while(!(u&1))u>>=1; do{ while(!(v&1))v>>=1; if(u>v){uint32_t t=u;u=v;v=t;} v-=u; }while(v); return u<<s; }
uint32_t lcm32(uint32_t a, uint32_t b){ if(!a||!b)return 0; uint32_t g=a; uint32_t x=a,y=b; while(y){uint32_t t=x%y;x=y;y=t;} g=x; return (uint32_t)(((uint64_t)a/g)*b); }
uint32_t modinv32(uint32_t a, uint32_t m){ if(m<=1)return 0; int64_t t=0,newt=1,r=m,newr=a%m; while(newr){ int64_t q=r/newr; int64_t tmp=t-q*newt; t=newt; newt=tmp; tmp=r-q*newr; r=newr; newr=tmp; } if(r>1)return 0; if(t<0)t+=m; return (uint32_t)t; }
uint32_t isqrt32(uint32_t x){ uint32_t res=0, bit=1u<<30; while(bit>x)bit>>=2; while(bit){ if(x>=res+bit){ x-=res+bit; res=(res>>1)+bit; } else res>>=1; bit>>=2; } return res; }
uint32_t icbrt32(uint32_t x){ uint32_t y=0; for(int s=30;s>=0;s-=3){ y<<=1; uint32_t b=(3*y*(y+1)+1)<<s; if(x>=b && (b>>s)==(3*y*(y+1)+1)){ x-=b; y++; } } return y; }
uint32_t ilog2_32(uint32_t x){ uint32_t r=0; while(x>>=1)r++; return r; }
uint32_t ipow32(uint32_t base, uint32_t exp){ uint32_t r=1; while(exp){ if(exp&1)r*=base; base*=base; exp>>=1; } return r; }
