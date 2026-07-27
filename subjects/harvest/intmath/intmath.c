#include <stdint.h>
int32_t iabs32(int32_t x){ return x<0 ? -x : x; }
int32_t imin32(int32_t a, int32_t b){ return a<b?a:b; }
int32_t imax32(int32_t a, int32_t b){ return a>b?a:b; }
int32_t iclamp32(int32_t x, int32_t lo, int32_t hi){ if(x<lo)return lo; if(x>hi)return hi; return x; }
int32_t isign32(int32_t x){ return (x>0)-(x<0); }
uint32_t umin32(uint32_t a, uint32_t b){ return a<b?a:b; }
uint32_t umax32(uint32_t a, uint32_t b){ return a>b?a:b; }
uint32_t sat_add_u32(uint32_t a, uint32_t b){ uint32_t s=a+b; return s<a?0xFFFFFFFFu:s; }
uint32_t sat_sub_u32(uint32_t a, uint32_t b){ return a>b?a-b:0u; }
int32_t sat_add_i32(int32_t a, int32_t b){ int64_t s=(int64_t)a+b; if(s>2147483647LL)return 2147483647; if(s<-2147483648LL)return (int32_t)(-2147483648LL); return (int32_t)s; }
uint32_t mulmod_u32(uint32_t a, uint32_t b, uint32_t m){ return m? (uint32_t)(((uint64_t)a*b)%m):0u; }
uint32_t powmod_u32(uint32_t base, uint32_t exp, uint32_t m){ if(!m)return 0u; uint64_t r=1, b=base%m; while(exp){ if(exp&1) r=(r*b)%m; b=(b*b)%m; exp>>=1;} return (uint32_t)r; }
uint32_t lcm_u32(uint32_t a, uint32_t b){ if(!a||!b)return 0u; uint32_t x=a,y=b; while(y){uint32_t t=y; y=x%y; x=t;} return (a/x)*b; }
