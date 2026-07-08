#include "mathlib.h"
#include <stdio.h>
int main(void) { printf("%u\n", ml_checksum((const unsigned char*)"hi", 2)); return 0; }
