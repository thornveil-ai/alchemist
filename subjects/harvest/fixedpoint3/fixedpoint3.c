#include <stdint.h>
int32_t q24_8_mul(int32_t a, int32_t b){ return (int32_t)(((int64_t)a*b)>>8); }
int32_t q24_8_div(int32_t a, int32_t b){ if(!b)return 0; return (int32_t)(((int64_t)a<<8)/b); }
int32_t q24_8_from_int(int32_t x){ return x<<8; }
int32_t q24_8_to_int(int32_t x){ return x>>8; }
int32_t q24_8_floor(int32_t x){ return x&(int32_t)0xFFFFFF00u; }
int32_t q24_8_frac(int32_t x){ return x&0xFF; }
int32_t q24_8_round(int32_t x){ return (x+0x80)&(int32_t)0xFFFFFF00u; }
int32_t q16_16_mul_sat(int32_t a, int32_t b){ int64_t p=((int64_t)a*b)>>16; if(p>2147483647LL)return 2147483647; if(p<-2147483648LL)return (-2147483647-1); return (int32_t)p; }
int32_t q16_16_recip(int32_t x){ if(!x)return 0; return (int32_t)(((int64_t)1<<32)/x); }
int32_t q8_8_mul(int32_t a, int32_t b){ return (int32_t)(((int64_t)a*b)>>8); }
int32_t q_lerp16(int32_t a, int32_t b, int32_t t){ return a+(int32_t)(((int64_t)(b-a)*t)>>16); }
int32_t q24_8_abs(int32_t x){ return x<0?-x:x; }
