#include <cstdio>
#include <cstring>
#include <cstdint>
#include "sha256.h"
int main(){
  static unsigned char in[65536]; unsigned char out[256];
  size_t n = fread(in,1,sizeof(in),stdin);
  SHA256_CTX ctx;
  sha256_init(&ctx);
  sha256_update(&ctx, in, n);
  sha256_final(&ctx, out);
  fwrite(out,1,32,stdout);
  return 0;
}
