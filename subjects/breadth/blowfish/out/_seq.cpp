#include <cstdio>
#include <cstring>
#include <cstdint>
#include "blowfish.h"
int main(){ static unsigned char in[65536]; int l=(int)fread(in,1,sizeof(in),stdin);
  BLOWFISH_KEY sched; unsigned char block[8]={0, 1, 2, 3, 4, 5, 6, 7}; unsigned char out[8];
  blowfish_key_setup((const unsigned char *)in, &sched, l); blowfish_encrypt((const unsigned char *)block, (unsigned char *)out, &sched);
  fwrite(out,1,8,stdout); return 0; }
