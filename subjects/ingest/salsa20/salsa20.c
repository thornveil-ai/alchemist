/*********************************************************************
* Salsa20/20 stream cipher — reference implementation.
* Public-domain algorithm (D. J. Bernstein, eSTREAM/ECRYPT); this is a
* clean-room transcription of the Salsa20 specification for the Alchemist
* corpus. 256-bit key, 64-bit nonce, 64-bit block counter.
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

static void salsa20_block(const WORD in[16], BYTE out[64])
{
	WORD x[16];
	int i;

	for (i = 0; i < 16; ++i)
		x[i] = in[i];

	for (i = 0; i < 10; ++i) {
		/* column round */
		x[4]  ^= rotl32(x[0]  + x[12], 7);
		x[8]  ^= rotl32(x[4]  + x[0],  9);
		x[12] ^= rotl32(x[8]  + x[4],  13);
		x[0]  ^= rotl32(x[12] + x[8],  18);
		x[9]  ^= rotl32(x[5]  + x[1],  7);
		x[13] ^= rotl32(x[9]  + x[5],  9);
		x[1]  ^= rotl32(x[13] + x[9],  13);
		x[5]  ^= rotl32(x[1]  + x[13], 18);
		x[14] ^= rotl32(x[10] + x[6],  7);
		x[2]  ^= rotl32(x[14] + x[10], 9);
		x[6]  ^= rotl32(x[2]  + x[14], 13);
		x[10] ^= rotl32(x[6]  + x[2],  18);
		x[3]  ^= rotl32(x[15] + x[11], 7);
		x[7]  ^= rotl32(x[3]  + x[15], 9);
		x[11] ^= rotl32(x[7]  + x[3],  13);
		x[15] ^= rotl32(x[11] + x[7],  18);
		/* row round */
		x[1]  ^= rotl32(x[0]  + x[3],  7);
		x[2]  ^= rotl32(x[1]  + x[0],  9);
		x[3]  ^= rotl32(x[2]  + x[1],  13);
		x[0]  ^= rotl32(x[3]  + x[2],  18);
		x[6]  ^= rotl32(x[5]  + x[4],  7);
		x[7]  ^= rotl32(x[6]  + x[5],  9);
		x[4]  ^= rotl32(x[7]  + x[6],  13);
		x[5]  ^= rotl32(x[4]  + x[7],  18);
		x[11] ^= rotl32(x[10] + x[9],  7);
		x[8]  ^= rotl32(x[11] + x[10], 9);
		x[9]  ^= rotl32(x[8]  + x[11], 13);
		x[10] ^= rotl32(x[9]  + x[8],  18);
		x[12] ^= rotl32(x[15] + x[14], 7);
		x[13] ^= rotl32(x[12] + x[15], 9);
		x[14] ^= rotl32(x[13] + x[12], 13);
		x[15] ^= rotl32(x[14] + x[13], 18);
	}

	for (i = 0; i < 16; ++i)
		store32_le(out + 4 * i, x[i] + in[i]);
}

void salsa20_xor(const BYTE key[32], const BYTE nonce[8], uint64_t counter,
                 const BYTE in[], BYTE out[], size_t len)
{
	WORD state[16];
	BYTE ks[64];
	size_t i, off = 0;

	state[0]  = 0x61707865;
	state[1]  = load32_le(key + 0);
	state[2]  = load32_le(key + 4);
	state[3]  = load32_le(key + 8);
	state[4]  = load32_le(key + 12);
	state[5]  = 0x3320646e;
	state[6]  = load32_le(nonce + 0);
	state[7]  = load32_le(nonce + 4);
	state[8]  = (WORD)(counter & 0xffffffff);
	state[9]  = (WORD)(counter >> 32);
	state[10] = 0x79622d32;
	state[11] = load32_le(key + 16);
	state[12] = load32_le(key + 20);
	state[13] = load32_le(key + 24);
	state[14] = load32_le(key + 28);
	state[15] = 0x6b206574;

	while (len - off >= 64) {
		salsa20_block(state, ks);
		for (i = 0; i < 64; ++i)
			out[off + i] = in[off + i] ^ ks[i];
		counter += 1;
		state[8] = (WORD)(counter & 0xffffffff);
		state[9] = (WORD)(counter >> 32);
		off += 64;
	}
	if (off < len) {
		salsa20_block(state, ks);
		for (i = 0; off + i < len; ++i)
			out[off + i] = in[off + i] ^ ks[i];
	}
}
