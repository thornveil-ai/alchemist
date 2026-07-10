/* Lua 5.4 string hash — verbatim from lstring.c, with the two macros it uses
 * inlined verbatim from llimits.h (cast_uint, cast_byte). Byte-exact target. */
#include "lua_hash.h"

#define cast(t, exp)    ((t)(exp))
#define cast_uint(i)    cast(unsigned int, (i))
#define cast_byte(i)    cast(unsigned char, (i))

unsigned int luaS_hash (const char *str, size_t l, unsigned int seed) {
  unsigned int h = seed ^ cast_uint(l);
  for (; l > 0; l--)
    h ^= ((h<<5) + (h>>2) + cast_byte(str[l - 1]));
  return h;
}
