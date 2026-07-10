/* Lua 5.4 xoshiro256** core — nextrand + rotl verbatim from lmathlib.c (native
 * 64-bit Rand64 path), with the u64[4] state wrapped in a struct so the
 * state-mutator oracle can carry it. Every u64 state is valid (no UB). */
#include "prng.h"
typedef unsigned long long Rand64;
#define trim64(x)  ((x) & 0xffffffffffffffffu)

static Rand64 rotl (Rand64 x, int n) {
  return (x << n) | (trim64(x) >> (64 - n));
}

unsigned long long nextrand (XState *st) {
  Rand64 *state = st->s;
  Rand64 state0 = state[0];
  Rand64 state1 = state[1];
  Rand64 state2 = state[2] ^ state0;
  Rand64 state3 = state[3] ^ state1;
  Rand64 res = rotl(state1 * 5, 7) * 9;
  state[0] = state0 ^ state3;
  state[1] = state1 ^ state2;
  state[2] = state2 ^ (state1 << 17);
  state[3] = rotl(state3, 45);
  return res;
}

/* Simple deterministic seeder (splitmix64-style) so the state-sequence oracle
 * has an init+op pair: seed -> state, then nextrand steps produce the sequence.
 * Any u64[4] state is valid for xoshiro256**, so this is a legitimate init. */
void seedstate (XState *st, unsigned long long seed) {
  unsigned long long z = seed;
  for (int i = 0; i < 4; i++) {
    z += 0x9E3779B97F4A7C15ull;
    unsigned long long x = z;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
    x = x ^ (x >> 31);
    st->s[i] = x;
  }
}
