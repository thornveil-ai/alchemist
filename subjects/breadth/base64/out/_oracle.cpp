#include <cstdio>
#include <cstring>
#include <cstdint>
#include "base64.h"
int main(int argc, char** argv){
  const char* n = argv[1]; static uint8_t in[65536]; static uint8_t outbuf[262144];
  uint32_t l = (uint32_t)fread(in, 1, sizeof(in), stdin);
    if(!strcmp(n,"base64_encode")) { unsigned long long m=(unsigned long long)base64_encode((const unsigned char *)in, l, (char *)outbuf); fwrite(outbuf,1,(size_t)m,stdout); return 0; }
    if(!strcmp(n,"base64_decode")) { unsigned long long m=(unsigned long long)base64_decode((const char *)in, l, (unsigned char *)outbuf); fwrite(outbuf,1,(size_t)m,stdout); return 0; }
  return 1;
}
