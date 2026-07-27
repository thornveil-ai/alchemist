#include <stdint.h>
uint8_t sat_add_u8(uint8_t a, uint8_t b){ uint16_t s=(uint16_t)a+b; return s>0xFF?0xFF:(uint8_t)s; }
uint8_t sat_sub_u8(uint8_t a, uint8_t b){ return a>b?(uint8_t)(a-b):0; }
uint16_t sat_add_u16(uint16_t a, uint16_t b){ uint32_t s=(uint32_t)a+b; return s>0xFFFF?0xFFFF:(uint16_t)s; }
int32_t sat_add_i32(int32_t a, int32_t b){ int64_t s=(int64_t)a+b; if(s>2147483647LL)return 2147483647; if(s<(-2147483647LL-1))return (-2147483647-1); return (int32_t)s; }
int32_t clamp_i32(int32_t x, int32_t lo, int32_t hi){ if(x<lo)return lo; if(x>hi)return hi; return x; }
uint32_t clamp_u32(uint32_t x, uint32_t lo, uint32_t hi){ if(x<lo)return lo; if(x>hi)return hi; return x; }
int32_t abs_i32(int32_t x){ int32_t m=x>>31; return (x^m)-m; }
int32_t sign_i32(int32_t x){ return (x>0)-(x<0); }
uint32_t midpoint_u32(uint32_t a, uint32_t b){ return (a&b)+((a^b)>>1); }
int32_t min3_i32(int32_t a, int32_t b, int32_t c){ int32_t m=a<b?a:b; return m<c?m:c; }
int32_t max3_i32(int32_t a, int32_t b, int32_t c){ int32_t m=a>b?a:b; return m>c?m:c; }
int32_t lerp_i32(int32_t a, int32_t b, int32_t t){ return a+(int32_t)(((int64_t)(b-a)*t)>>16); }
uint32_t reflect_clamp(int32_t x, uint32_t n){ if(n==0)return 0; if(x<0)x=-x; uint32_t ux=(uint32_t)x; return ux%n; }
