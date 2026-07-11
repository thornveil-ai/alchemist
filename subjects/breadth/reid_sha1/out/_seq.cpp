#include <cstdio>
#include <cstring>
#include <cstdint>
#include "sha1.h"
int main(){
  static unsigned char in[65536]; unsigned char out[256];
  size_t n = fread(in,1,sizeof(in),stdin);
  SHA1_CTX ctx;
  SHA1Init(&ctx);
  SHA1Update(&ctx, in, n);
  SHA1Final(out, &ctx);
  fwrite(out,1,32,stdout);
  return 0;
}
