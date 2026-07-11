#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include "heapbuf.c"
int main(){ unsigned char in[64]; int n=(int)fread(in,1,sizeof(in),stdin);
  unsigned long sz = (n>0? in[0]:0) + 1;  // 1..256
  unsigned char fill = (n>2)?in[2]:0;
  unsigned char* p = make_buffer(sz, fill);
  fwrite(p, sizeof(unsigned char), sz, stdout);  // CONTENTS, never the pointer
  free(p); return 0; }
