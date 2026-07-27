#include <stdint.h>
uint8_t sat_mul_u8(uint8_t a, uint8_t b){ uint16_t p=(uint16_t)a*b; return p>0xFF?0xFF:(uint8_t)p; }
int16_t sat_sub_i16(int16_t a, int16_t b){ int32_t s=(int32_t)a-b; if(s>32767)return 32767; if(s<-32768)return -32768; return (int16_t)s; }
uint32_t abs_diff_u32(uint32_t a, uint32_t b){ return a>b?a-b:b-a; }
int32_t select_i32(int cond, int32_t a, int32_t b){ return cond?a:b; }
uint32_t wrap_inc(uint32_t x, uint32_t mod){ if(!mod)return 0; x++; return x>=mod?0:x; }
uint32_t clamp_add(uint32_t x, uint32_t d, uint32_t hi){ uint64_t s=(uint64_t)x+d; return s>hi?hi:(uint32_t)s; }
int32_t clamp_sym(int32_t x, int32_t bound){ if(bound<0)bound=-bound; if(x>bound)return bound; if(x<-bound)return -bound; return x; }
uint8_t alpha_blend(uint8_t a, uint8_t b, uint8_t t){ return (uint8_t)(((uint16_t)a*(255-t)+(uint16_t)b*t+127)/255); }
int32_t sign_extend8(uint8_t x){ return (int32_t)(int8_t)x; }
uint32_t rescale(uint32_t x, uint32_t in_max, uint32_t out_max){ if(!in_max)return 0; return (uint32_t)(((uint64_t)x*out_max)/in_max); }
int32_t clamp_to_i8(int32_t x){ if(x>127)return 127; if(x<-128)return -128; return x; }
uint32_t saturate_bits(uint32_t x, int bits){ uint32_t max=(bits>=32)?0xFFFFFFFFu:((1u<<bits)-1); return x>max?max:x; }
