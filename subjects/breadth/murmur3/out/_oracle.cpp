#include <cstdio>
#include <cstring>
#include <cstdint>
#include "murmur3.h"
int main(int argc, char** argv){
  const char* n = argv[1]; static uint8_t in[65536]; static uint8_t outbuf[262144];
  uint32_t l = (uint32_t)fread(in, 1, sizeof(in), stdin);
    if(!strcmp(n,"MurmurHash3_x86_32")) { MurmurHash3_x86_32((const void *)in, l, 0, (void *)outbuf); fwrite(outbuf,1,4,stdout); return 0; }
    if(!strcmp(n,"MurmurHash3_x86_128")) { MurmurHash3_x86_128((const void *)in, l, 0, (void *)outbuf); fwrite(outbuf,1,16,stdout); return 0; }
    if(!strcmp(n,"MurmurHash3_x64_128")) { MurmurHash3_x64_128((const void *)in, l, 0, (void *)outbuf); fwrite(outbuf,1,16,stdout); return 0; }
  return 1;
}
