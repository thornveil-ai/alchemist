#include <stdint.h>
/* Q16.16 and Q8.8 fixed-point (harder arithmetic -> DPO near-misses). */
int32_t q16_mul(int32_t a, int32_t b){ int64_t t=(int64_t)a*b; return (int32_t)(t>>16); }
int32_t q16_mul_round(int32_t a, int32_t b){ int64_t t=(int64_t)a*b; t+=0x8000; return (int32_t)(t>>16); }
int32_t q16_div(int32_t a, int32_t b){ if(b==0) return 0; int64_t t=((int64_t)a<<16); return (int32_t)(t/b); }
int32_t q16_from_int(int32_t x){ return x<<16; }
int32_t q16_to_int(int32_t x){ return x>>16; }
int32_t q16_floor(int32_t x){ return x&(int32_t)0xFFFF0000u; }
int32_t q16_ceil(int32_t x){ return (x&0xFFFF)?((x&(int32_t)0xFFFF0000u)+0x10000):x; }
int32_t q16_lerp(int32_t a, int32_t b, int32_t t){ return a + (int32_t)(((int64_t)(b-a)*t)>>16); }
int16_t q8_mul(int16_t a, int16_t b){ int32_t t=(int32_t)a*b; return (int16_t)(t>>8); }
int16_t q8_div(int16_t a, int16_t b){ if(b==0) return 0; int32_t t=((int32_t)a<<8); return (int16_t)(t/b); }
int32_t q16_abs(int32_t x){ return x<0?-x:x; }
