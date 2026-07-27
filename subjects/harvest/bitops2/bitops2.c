#include <stdint.h>
uint8_t reverse_bits8(uint8_t x){ x=(x>>4)|(x<<4); x=((x&0xCC)>>2)|((x&0x33)<<2); x=((x&0xAA)>>1)|((x&0x55)<<1); return x; }
uint16_t reverse_bits16(uint16_t x){ x=(x>>8)|(x<<8); x=((x&0xF0F0)>>4)|((x&0x0F0F)<<4); x=((x&0xCCCC)>>2)|((x&0x3333)<<2); x=((x&0xAAAA)>>1)|((x&0x5555)<<1); return x; }
uint32_t reverse_bits32(uint32_t x){ x=(x>>16)|(x<<16); x=((x&0xFF00FF00u)>>8)|((x&0x00FF00FFu)<<8); x=((x&0xF0F0F0F0u)>>4)|((x&0x0F0F0F0Fu)<<4); x=((x&0xCCCCCCCCu)>>2)|((x&0x33333333u)<<2); x=((x&0xAAAAAAAAu)>>1)|((x&0x55555555u)<<1); return x; }
uint32_t bswap32(uint32_t x){ return ((x&0xFF)<<24)|((x&0xFF00)<<8)|((x>>8)&0xFF00)|((x>>24)&0xFF); }
uint64_t bswap64(uint64_t x){ x=((x&0x00000000FFFFFFFFull)<<32)|((x>>32)&0x00000000FFFFFFFFull); x=((x&0x0000FFFF0000FFFFull)<<16)|((x>>16)&0x0000FFFF0000FFFFull); x=((x&0x00FF00FF00FF00FFull)<<8)|((x>>8)&0x00FF00FF00FF00FFull); return x; }
int nlz32(uint32_t x){ if(!x)return 32; int n=0; if(x<=0x0000FFFFu){n+=16;x<<=16;} if(x<=0x00FFFFFFu){n+=8;x<<=8;} if(x<=0x0FFFFFFFu){n+=4;x<<=4;} if(x<=0x3FFFFFFFu){n+=2;x<<=2;} if(x<=0x7FFFFFFFu){n+=1;} return n; }
int ntz32(uint32_t x){ if(!x)return 32; int n=0; while(!(x&1)){x>>=1;n++;} return n; }
int popcount64(uint64_t x){ x=x-((x>>1)&0x5555555555555555ull); x=(x&0x3333333333333333ull)+((x>>2)&0x3333333333333333ull); x=(x+(x>>4))&0x0F0F0F0F0F0F0F0Full; return (int)((x*0x0101010101010101ull)>>56); }
int parity32(uint32_t x){ x^=x>>16; x^=x>>8; x^=x>>4; x&=0xF; return (0x6996>>x)&1; }
int is_pow2(uint32_t x){ return x && !(x&(x-1)); }
uint32_t round_up_pow2(uint32_t x){ if(x<=1)return 1; x--; x|=x>>1; x|=x>>2; x|=x>>4; x|=x>>8; x|=x>>16; return x+1; }
uint32_t clear_lowest_set(uint32_t x){ return x&(x-1); }
uint32_t isolate_lowest_set(uint32_t x){ return x&(uint32_t)(-(int32_t)x); }
uint32_t sign_extend_bits(uint32_t x, int bits){ uint32_t m=1u<<(bits-1); return (x^m)-m; }
uint16_t morton_encode8(uint8_t a, uint8_t b){ uint32_t x=a,y=b; x=(x|(x<<4))&0x0F0F; x=(x|(x<<2))&0x3333; x=(x|(x<<1))&0x5555; y=(y|(y<<4))&0x0F0F; y=(y|(y<<2))&0x3333; y=(y|(y<<1))&0x5555; return (uint16_t)(x|(y<<1)); }
