#include <stdint.h>
#include <string.h>
/* LEB128 / zigzag as buf_transform (in -> out). Deterministic on any length. */
int uleb128_encode(const char* in, int inlen, char* out, int outcap){
    uint64_t v=0; unsigned char buf[8]; memset(buf,0,8); int n=inlen<8?inlen:8; if(n>0)memcpy(buf,in,n);
    memcpy(&v, buf, 8);
    int i=0; do { unsigned char byte=v&0x7f; v>>=7; if(v) byte|=0x80; if(i>=outcap)return -1; out[i++]=(char)byte; } while(v);
    return i;
}
int uleb128_decode(const char* in, int inlen, char* out, int outcap){
    uint64_t v=0; int shift=0, i=0; while(i<inlen && shift<64){ unsigned char b=(unsigned char)in[i++]; v|=(uint64_t)(b&0x7f)<<shift; if(!(b&0x80))break; shift+=7; }
    if(outcap<8)return -1; memcpy(out,&v,8); return 8;
}
uint64_t zigzag_encode(int64_t v){ return ((uint64_t)v<<1) ^ (uint64_t)(v>>63); }
int64_t zigzag_decode(uint64_t v){ return (int64_t)(v>>1) ^ -(int64_t)(v&1); }
uint32_t zigzag_encode32(int32_t v){ return ((uint32_t)v<<1) ^ (uint32_t)(v>>31); }
int32_t zigzag_decode32(uint32_t v){ return (int32_t)(v>>1) ^ -(int32_t)(v&1); }
