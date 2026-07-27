#include <stdint.h>
uint32_t digit_count_base(uint32_t n, uint32_t base){ if(base<2)return 0; uint32_t c=0; if(n==0)return 1; while(n){ c++; n/=base; } return c; }
uint32_t digit_sum_base(uint32_t n, uint32_t base){ if(base<2)return 0; uint32_t s=0; while(n){ s+=n%base; n/=base; } return s; }
uint32_t reverse_base(uint32_t n, uint32_t base){ if(base<2)return 0; uint32_t r=0; while(n){ r=r*base+n%base; n/=base; } return r; }
int is_num_palindrome(uint32_t n, uint32_t base){ if(base<2)return 0; uint32_t r=0,o=n; while(n){ r=r*base+n%base; n/=base; } return r==o; }
uint32_t ipow_checked(uint32_t base, uint32_t exp){ uint32_t r=1; while(exp){ if(exp&1)r*=base; base*=base; exp>>=1; } return r; }
uint32_t iroot(uint32_t x, uint32_t n){ if(n==0)return 0; if(n==1)return x; uint32_t lo=0,hi=x; while(lo<hi){ uint32_t mid=lo+(hi-lo+1)/2; uint64_t p=1; int of=0; for(uint32_t i=0;i<n;i++){ p*=mid; if(p>x){of=1;break;} } if(!of)lo=mid; else hi=mid-1; } return lo; }
uint32_t ilog_base(uint32_t x, uint32_t base){ if(base<2||x==0)return 0; uint32_t l=0; while(x>=base){ x/=base; l++; } return l; }
uint32_t triangular(uint32_t n){ return n*(n+1)/2; }
uint32_t sum_squares(uint32_t n){ return n*(n+1)*(2*n+1)/6; }
uint32_t bit_length(uint32_t x){ uint32_t l=0; while(x){ l++; x>>=1; } return l; }
uint32_t count_trailing_zeros_dec(uint32_t n){ if(!n)return 0; uint32_t c=0; while(n%10==0){ c++; n/=10; } return c; }
uint32_t gcd3(uint32_t a, uint32_t b, uint32_t c){ while(b){uint32_t t=a%b;a=b;b=t;} while(c){uint32_t t=a%c;a=c;c=t;} return a; }
