#include "prng.h"
static unsigned long _state = 0;
void prng_seed(unsigned long s) { _state = s; }
unsigned long prng_next(void) { _state = _state * 6364136223846793005UL + 1442695040888963407UL; return _state >> 33; }
