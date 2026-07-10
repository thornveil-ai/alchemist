#ifndef PRNG_H
#define PRNG_H
typedef struct { unsigned long long s[4]; } XState;
unsigned long long nextrand(XState *st);
#endif
