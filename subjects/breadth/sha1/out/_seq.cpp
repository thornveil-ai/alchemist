#include <cstdio>
#include <cstring>
#include <cstdint>
#include "sha1.h"
int main(){
  static unsigned char in[65536]; unsigned char out[256];
  size_t n = fread(in,1,sizeof(in),stdin);
  SHA1_CTX ctx;
  sha1_init(&ctx);
  sha1_update(&ctx, in, n);
  sha1_final(&ctx, out);
  fwrite(out,1,20,stdout);
  return 0;
}
