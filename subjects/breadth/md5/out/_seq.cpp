#include <cstdio>
#include <cstring>
#include <cstdint>
#include "md5.h"
int main(){
  static unsigned char in[65536]; unsigned char out[256];
  size_t n = fread(in,1,sizeof(in),stdin);
  MD5_CTX ctx;
  md5_init(&ctx);
  md5_update(&ctx, in, n);
  md5_final(&ctx, out);
  fwrite(out,1,16,stdout);
  return 0;
}
