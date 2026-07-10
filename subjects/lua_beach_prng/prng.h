#ifndef PRNG_H
#define PRNG_H
typedef struct { unsigned long long s[4]; } XState;
void seedstate(XState *st, unsigned long long seed);
unsigned long long nextrand(XState *st);
#endif
