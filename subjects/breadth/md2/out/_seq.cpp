#include <cstdio>
#include <cstring>
#include <cstdint>
#include "md2.h"
int main(){
  static unsigned char in[65536]; unsigned char out[256];
  size_t n = fread(in,1,sizeof(in),stdin);
  MD2_CTX ctx;
  md2_init(&ctx);
  md2_update(&ctx, in, n);
  md2_final(&ctx, out);
  fwrite(out,1,16,stdout);
  return 0;
}
