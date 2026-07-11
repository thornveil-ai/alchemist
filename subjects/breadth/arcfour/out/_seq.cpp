#include <cstdio>
#include <cstring>
#include <cstdint>
#include "arcfour.h"
int main(){ static unsigned char in[65536]; int l=(int)fread(in,1,sizeof(in),stdin);
  unsigned char state[256]; unsigned char out[64];
  arcfour_key_setup(state, in, l); arcfour_generate_stream(state, out, 64);
  fwrite(out,1,64,stdout); return 0; }
