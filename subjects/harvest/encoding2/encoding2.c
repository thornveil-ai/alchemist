#include <stdint.h>
uint32_t zigzag_enc32(int32_t n){ return (uint32_t)((n<<1)^(n>>31)); }
int32_t zigzag_dec32(uint32_t n){ return (int32_t)((n>>1)^(-(int32_t)(n&1))); }
uint64_t zigzag_enc64(int64_t n){ return (uint64_t)((n<<1)^(n>>63)); }
int64_t zigzag_dec64(uint64_t n){ return (int64_t)((n>>1)^(-(int64_t)(n&1))); }
uint32_t gray_enc(uint32_t x){ return x^(x>>1); }
uint32_t gray_dec(uint32_t g){ g^=g>>16; g^=g>>8; g^=g>>4; g^=g>>2; g^=g>>1; return g; }
uint32_t bin_to_bcd(uint32_t v){ uint32_t bcd=0; int shift=0; while(v){ bcd|=(v%10)<<(shift*4); v/=10; shift++; } return bcd; }
uint32_t bcd_to_bin(uint32_t bcd){ uint32_t v=0, mul=1; while(bcd){ v+=(bcd&0xF)*mul; mul*=10; bcd>>=4; } return v; }
int hex_val(int c){ if(c>='0'&&c<='9')return c-'0'; if(c>='a'&&c<='f')return c-'a'+10; if(c>='A'&&c<='F')return c-'A'+10; return -1; }
uint8_t nibble_swap(uint8_t x){ return (uint8_t)((x<<4)|(x>>4)); }
uint32_t interleave_zero(uint16_t x){ uint32_t r=x; r=(r|(r<<8))&0x00FF00FFu; r=(r|(r<<4))&0x0F0F0F0Fu; r=(r|(r<<2))&0x33333333u; r=(r|(r<<1))&0x55555555u; return r; }
