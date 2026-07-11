#include <cstdio>
#include <cstring>
#include <cstdint>
#include "siphash.h"
int main(int argc, char** argv){
  const char* n = argv[1]; static uint8_t in[65536]; static uint8_t outbuf[262144];
  uint32_t l = (uint32_t)fread(in, 1, sizeof(in), stdin);
    if(!strcmp(n,"siphash")) { unsigned long long m=(unsigned long long)siphash((const void *)in, l, (const void *)in, (uint8_t *)outbuf, l); fwrite(outbuf,1,(size_t)m,stdout); return 0; }
  return 1;
}
