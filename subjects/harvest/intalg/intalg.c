#include <stdint.h>
uint32_t fib_mod(uint32_t n, uint32_t m){ if(!m)return 0; uint32_t a=0,b=1; for(uint32_t i=0;i<n;i++){ uint32_t c=(a+b)%m; a=b; b=c; } return a%m; }
uint32_t factorial_mod(uint32_t n, uint32_t m){ if(!m)return 0; uint64_t r=1%m; for(uint32_t i=2;i<=n;i++) r=(r*i)%m; return (uint32_t)r; }
int is_prime(uint32_t n){ if(n<2)return 0; if(n%2==0)return n==2; for(uint32_t i=3;(uint64_t)i*i<=n;i+=2) if(n%i==0)return 0; return 1; }
uint32_t count_primes_below(uint32_t n){ uint32_t c=0; for(uint32_t k=2;k<n;k++){ int p=1; for(uint32_t i=2;(uint64_t)i*i<=k;i++) if(k%i==0){p=0;break;} c+=(uint32_t)p; } return c; }
uint32_t digit_sum(uint32_t n){ uint32_t s=0; while(n){ s+=n%10; n/=10; } return s; }
uint32_t digital_root(uint32_t n){ return n==0?0:1+(n-1)%9; }
uint32_t reverse_decimal(uint32_t n){ uint32_t r=0; while(n){ r=r*10+n%10; n/=10; } return r; }
uint32_t bin_to_gray(uint32_t x){ return x^(x>>1); }
uint32_t gray_to_bin(uint32_t x){ x^=x>>16; x^=x>>8; x^=x>>4; x^=x>>2; x^=x>>1; return x; }
uint32_t collatz_steps(uint32_t n){ uint32_t s=0; while(n>1){ n=(n&1)?(3*n+1):(n>>1); s++; if(s>1000)break; } return s; }
uint32_t isqrt_newton(uint32_t x){ if(x==0)return 0; uint32_t r=x, last; do{ last=r; r=(r+x/r)>>1; }while(r<last); return r; }
