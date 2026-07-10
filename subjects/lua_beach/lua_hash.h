#ifndef LUA_HASH_H
#define LUA_HASH_H
#include <stddef.h>
/* Lua 5.4 string hash (from lstring.c / llimits.h), extracted verbatim. */
unsigned int luaS_hash(const char *str, size_t l, unsigned int seed);
#endif
