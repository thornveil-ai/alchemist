#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef unsigned char BYTE;

void arcfour_key_setup(BYTE state[], const BYTE key[], int len);

void arcfour_generate_stream(BYTE state[], BYTE out[], size_t len);

void arcfour_key_setup(BYTE state[], const BYTE key[], int len)
{
 int i, j;
 BYTE t;

 for (i = 0; i < 256; ++i)
  state[i] = i;
 for (i = 0, j = 0; i < 256; ++i) {
  j = (j + state[i] + key[i % len]) % 256;
  t = state[i];
  state[i] = state[j];
  state[j] = t;
 }
}

void arcfour_generate_stream(BYTE state[], BYTE out[], size_t len)
{
 int i, j;
 size_t idx;
 BYTE t;

 for (idx = 0, i = 0, j = 0; idx < len; ++idx) {
  i = (i + 1) % 256;
  j = (j + state[i]) % 256;
  t = state[i];
  state[i] = state[j];
  state[j] = t;
  out[idx] = state[(state[i] + state[j]) % 256];
 }
}