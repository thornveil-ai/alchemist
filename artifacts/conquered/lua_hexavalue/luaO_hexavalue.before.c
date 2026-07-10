/* Lua 5.4 luaO_hexavalue — verbatim from lobject.c; lctype macros use the
 * default C-locale definitions (lisdigit=isdigit, ltolower=tolower). */
#include <ctype.h>
#include "hexa.h"
#define lisdigit(c)  (isdigit(c))
#define ltolower(c)  (tolower(c))
int luaO_hexavalue (int c) {
  if (lisdigit(c)) return c - '0';
  else return (ltolower(c) - 'a') + 10;
}
