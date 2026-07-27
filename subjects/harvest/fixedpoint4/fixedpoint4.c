#include <stdint.h>
int32_t q12_4_mul(int32_t a, int32_t b){ return (int32_t)(((int64_t)a*b)>>4); }
int32_t q12_4_div(int32_t a, int32_t b){ if(!b)return 0; return (int32_t)(((int64_t)a<<4)/b); }
int32_t q4_12_mul(int32_t a, int32_t b){ return (int32_t)(((int64_t)a*b)>>12); }
int32_t q2_30_mul(int32_t a, int32_t b){ return (int32_t)(((int64_t)a*b)>>30); }
int32_t q12_4_from_int(int32_t x){ return x<<4; }
int32_t q12_4_to_int(int32_t x){ return x>>4; }
int32_t q12_4_round(int32_t x){ return (x+8)>>4; }
uint32_t ufixed_mul(uint32_t a, uint32_t b, int shift){ return (uint32_t)(((uint64_t)a*b)>>shift); }
int32_t q_saturate(int64_t x){ if(x>2147483647LL)return 2147483647; if(x<-2147483648LL)return (-2147483647-1); return (int32_t)x; }
int32_t q16_16_frac(int32_t x){ return x&0xFFFF; }
int32_t q8_24_mul(int32_t a, int32_t b){ return (int32_t)(((int64_t)a*b)>>24); }
