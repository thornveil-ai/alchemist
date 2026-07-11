#include <cstdio>
#include <cstdint>
#include <cstring>
#include "prng.c"
int main(){ unsigned char in[64]; int n=(int)fread(in,1,sizeof(in),stdin);
  unsigned long seed=0; for(int i=0;i<n&&i<8;i++) seed=(seed<<8)|in[i];
  prng_seed(seed);
  for(int i=0;i<8;i++){ unsigned long r=prng_next(); fwrite(&r,sizeof(r),1,stdout); }
  fwrite(&_state, sizeof(_state), 1, stdout);
  return 0; }
