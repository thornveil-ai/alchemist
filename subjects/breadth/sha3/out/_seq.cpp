#include <cstdio>
#include <cstring>
#include <cstdint>
#include "sha3.h"
int main(){
  static unsigned char in[65536]; unsigned char out[256];
  size_t n = fread(in,1,sizeof(in),stdin);
  sha3_ctx_t ctx;
  sha3_init(&ctx, 32);
  sha3_update(&ctx, in, n);
  sha3_final(out, &ctx);
  fwrite(out,1,32,stdout);
  return 0;
}
