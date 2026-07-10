/* Lua 5.4 luaV_shiftl — verbatim from lvm.c, with lua_Integer=long long,
 * lua_Unsigned=unsigned long long, NBITS=64, intop/casts inlined from
 * lvm.h/llimits.h. Pure (i64,i64)->i64 wraparound-shift. */
#include "shiftl.h"
typedef long long lua_Integer;
typedef unsigned long long lua_Unsigned;
#define NBITS 64
#define l_castS2U(i)  ((lua_Unsigned)(i))
#define l_castU2S(i)  ((lua_Integer)(i))
#define intop(op,v1,v2)  l_castU2S(l_castS2U(v1) op l_castS2U(v2))

lua_Integer luaV_shiftl (lua_Integer x, lua_Integer y) {
  if (y < 0) {  /* shift right? */
    if (y <= -NBITS) return 0;
    else return intop(>>, x, -y);
  }
  else {  /* shift left */
    if (y >= NBITS) return 0;
    else return intop(<<, x, y);
  }
}
