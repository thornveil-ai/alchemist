#include <cstdio>
#include <cstring>
#include <cstdint>
int main(int argc, char** argv){
  const char* n = argv[1]; static uint8_t in[65536]; static uint8_t outbuf[262144];
  uint32_t l = (uint32_t)fread(in, 1, sizeof(in), stdin);
    if(!strcmp(n,"fnv1a")) { printf("%llu",(unsigned long long)fnv1a((const unsigned char *)in, l)); return 0; }
  return 1;
}
