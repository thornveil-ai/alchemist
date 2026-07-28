/*********************************************************************
* ChaCha20 stream cipher — RFC 8439 reference implementation.
* Public-domain algorithm (D. J. Bernstein); this is a clean-room
* transcription of the RFC 8439 pseudocode for the Alchemist corpus.
* 256-bit key, 96-bit nonce, 32-bit block counter.
*********************************************************************/
#include <stdint.h>
#include <stddef.h>

typedef uint8_t  BYTE;
typedef uint32_t WORD;

static WORD rotl32(WORD x, int n)
{
	return (x << n) | (x >> (32 - n));
}

static WORD load32_le(const BYTE *p)
{
	return (WORD)p[0] | ((WORD)p[1] << 8) | ((WORD)p[2] << 16) | ((WORD)p[3] << 24);
}

static void store32_le(BYTE *p, WORD w)
{
	p[0] = (BYTE)(w);
	p[1] = (BYTE)(w >> 8);
	p[2] = (BYTE)(w >> 16);
	p[3] = (BYTE)(w >> 24);
}

static void quarter_round(WORD *s, int a, int b, int c, int d)
{
	s[a] += s[b]; s[d] ^= s[a]; s[d] = rotl32(s[d], 16);
	s[c] += s[d]; s[b] ^= s[c]; s[b] = rotl32(s[b], 12);
	s[a] += s[b]; s[d] ^= s[a]; s[d] = rotl32(s[d], 8);
	s[c] += s[d]; s[b] ^= s[c]; s[b] = rotl32(s[b], 7);
}

static void chacha20_block(const BYTE key[32], WORD counter, const BYTE nonce[12], BYTE out[64])
{
	WORD state[16];
	WORD working[16];
	int i;

	state[0] = 0x61707865;
	state[1] = 0x3320646e;
	state[2] = 0x79622d32;
	state[3] = 0x6b206574;
	for (i = 0; i < 8; ++i)
		state[4 + i] = load32_le(key + 4 * i);
	state[12] = counter;
	state[13] = load32_le(nonce + 0);
	state[14] = load32_le(nonce + 4);
	state[15] = load32_le(nonce + 8);

	for (i = 0; i < 16; ++i)
		working[i] = state[i];

	for (i = 0; i < 10; ++i) {
		quarter_round(working, 0, 4, 8, 12);
		quarter_round(working, 1, 5, 9, 13);
		quarter_round(working, 2, 6, 10, 14);
		quarter_round(working, 3, 7, 11, 15);
		quarter_round(working, 0, 5, 10, 15);
		quarter_round(working, 1, 6, 11, 12);
		quarter_round(working, 2, 7, 8, 13);
		quarter_round(working, 3, 4, 9, 14);
	}

	for (i = 0; i < 16; ++i)
		store32_le(out + 4 * i, working[i] + state[i]);
}

void chacha20_xor(const BYTE key[32], const BYTE nonce[12], WORD counter,
                  const BYTE in[], BYTE out[], size_t len)
{
	BYTE ks[64];
	size_t i, off = 0;

	while (len - off >= 64) {
		chacha20_block(key, counter, nonce, ks);
		for (i = 0; i < 64; ++i)
			out[off + i] = in[off + i] ^ ks[i];
		counter += 1;
		off += 64;
	}
	if (off < len) {
		chacha20_block(key, counter, nonce, ks);
		for (i = 0; off + i < len; ++i)
			out[off + i] = in[off + i] ^ ks[i];
	}
}
