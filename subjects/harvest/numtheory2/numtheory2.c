#include <stdint.h>
uint32_t sum_proper_divisors(uint32_t n){ if(n<2)return 0; uint32_t s=1; for(uint32_t i=2;(uint64_t)i*i<=n;i++){ if(n%i==0){ s+=i; if(i!=n/i)s+=n/i; } } return s; }
int is_perfect(uint32_t n){ if(n<2)return 0; uint32_t s=1; for(uint32_t i=2;(uint64_t)i*i<=n;i++){ if(n%i==0){ s+=i; if(i!=n/i)s+=n/i; } } return s==n; }
int is_abundant(uint32_t n){ if(n<2)return 0; uint32_t s=1; for(uint32_t i=2;(uint64_t)i*i<=n;i++){ if(n%i==0){ s+=i; if(i!=n/i)s+=n/i; } } return s>n; }
int is_square(uint32_t n){ uint32_t r=0,b=1u<<15; while(b){ uint32_t t=r|b; if((uint64_t)t*t<=n)r=t; b>>=1; } return (uint64_t)r*r==n; }
uint32_t digital_root(uint32_t n){ return n==0?0:1+(n-1)%9; }
uint32_t count_set_digits(uint32_t n){ uint32_t c=0; while(n){ if(n%10)c++; n/=10; } return c; }
uint32_t collatz_len(uint32_t n){ uint32_t c=0; uint64_t x=n; while(x>1&&c<1000){ x=(x&1)?(3*x+1):(x>>1); c++; } return c; }
uint32_t pentagonal(uint32_t n){ return n*(3*n-1)/2; }
uint32_t hexagonal(uint32_t n){ return n*(2*n-1); }
int is_coprime(uint32_t a, uint32_t b){ while(b){ uint32_t t=a%b; a=b; b=t; } return a==1; }
