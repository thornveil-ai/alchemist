#include <stdint.h>
uint32_t euler_totient(uint32_t n){ uint32_t result=n; for(uint32_t p=2; (uint64_t)p*p<=n; p++){ if(n%p==0){ while(n%p==0)n/=p; result-=result/p; } } if(n>1)result-=result/n; return result; }
uint32_t count_divisors(uint32_t n){ uint32_t c=0; for(uint32_t i=1;(uint64_t)i*i<=n;i++){ if(n%i==0){ c++; if(i!=n/i)c++; } } return c; }
uint32_t sum_divisors(uint32_t n){ uint32_t s=0; for(uint32_t i=1;(uint64_t)i*i<=n;i++){ if(n%i==0){ s+=i; if(i!=n/i)s+=n/i; } } return s; }
int mobius(uint32_t n){ if(n==1)return 1; int primes=0; for(uint32_t p=2;(uint64_t)p*p<=n;p++){ if(n%p==0){ n/=p; if(n%p==0)return 0; primes++; } } if(n>1)primes++; return (primes&1)?-1:1; }
int is_prime_det(uint32_t n){ if(n<2)return 0; if(n<4)return 1; if(!(n&1))return 0; for(uint32_t i=3;(uint64_t)i*i<=n;i+=2) if(n%i==0)return 0; return 1; }
uint32_t next_prime(uint32_t n){ if(n<2)return 2; uint32_t c=n+1; for(;;c++){ if(c<2)continue; int p=1; for(uint32_t i=2;(uint64_t)i*i<=c;i++) if(c%i==0){p=0;break;} if(p)return c; } }
uint32_t nth_fib(uint32_t n){ uint32_t a=0,b=1; for(uint32_t i=0;i<n;i++){ uint32_t t=a+b; a=b; b=t; } return a; }
uint32_t tribonacci(uint32_t n){ uint32_t a=0,b=0,c=1; for(uint32_t i=0;i<n;i++){ uint32_t t=a+b+c; a=b; b=c; c=t; } return a; }
uint32_t catalan_mod(uint32_t n, uint32_t m){ if(!m)return 0; uint64_t c=1%m; for(uint32_t i=0;i<n;i++){ c=c*(2*(2*i+1)); uint32_t d=i+2; c/=1; c%=((uint64_t)m*d); c%=m; } return (uint32_t)(c%m); }
uint32_t radical(uint32_t n){ uint32_t r=1; for(uint32_t p=2;(uint64_t)p*p<=n;p++){ if(n%p==0){ r*=p; while(n%p==0)n/=p; } } if(n>1)r*=n; return r; }
uint32_t largest_prime_factor(uint32_t n){ uint32_t last=1; while(!(n&1)&&n){ last=2; n>>=1; } for(uint32_t i=3;(uint64_t)i*i<=n;i+=2){ while(n%i==0){ last=i; n/=i; } } if(n>1)last=n; return last; }
