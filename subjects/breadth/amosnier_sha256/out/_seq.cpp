#include <cstdio>
#include <cstring>
#include <cstdint>
#include "sha-256.h"
int main(){
  static unsigned char in[65536]; unsigned char out[256];
  size_t n = fread(in,1,sizeof(in),stdin);
  Sha_256 ctx;
  sha_256_init(&ctx, out);
  sha_256_write(&ctx, in, n);
  sha_256_close(&ctx);
  fwrite(out,1,32,stdout);
  return 0;
}
