#include <stdint.h>
#include <stddef.h>
#include <string.h>

typedef unsigned char BYTE;
typedef unsigned int WORD;

typedef struct {
   BYTE data[64];
   WORD datalen;
   unsigned long long bitlen;
   WORD state[4];
} MD5_CTX;

void md5_init(MD5_CTX *ctx);
void md5_update(MD5_CTX *ctx, const BYTE data[], size_t len);
void md5_final(MD5_CTX *ctx, BYTE hash[]);
void md5_transform(MD5_CTX *ctx, const BYTE data[])
{
 WORD a, b, c, d, m[16], i, j;

 for (i = 0, j = 0; i < 16; ++i, j += 4)
  m[i] = (data[j]) + (data[j + 1] << 8) + (data[j + 2] << 16) + (data[j + 3] << 24);

 a = ctx->state[0];
 b = ctx->state[1];
 c = ctx->state[2];
 d = ctx->state[3];

 { a += ((b & c) | (~b & d)) + m[0] + 0xd76aa478; a = b + ((a << 7) | (a >> (32-7))); };
 { d += ((a & b) | (~a & c)) + m[1] + 0xe8c7b756; d = a + ((d << 12) | (d >> (32-12))); };
 { c += ((d & a) | (~d & b)) + m[2] + 0x242070db; c = d + ((c << 17) | (c >> (32-17))); };
 { b += ((c & d) | (~c & a)) + m[3] + 0xc1bdceee; b = c + ((b << 22) | (b >> (32-22))); };
 { a += ((b & c) | (~b & d)) + m[4] + 0xf57c0faf; a = b + ((a << 7) | (a >> (32-7))); };
 { d += ((a & b) | (~a & c)) + m[5] + 0x4787c62a; d = a + ((d << 12) | (d >> (32-12))); };
 { c += ((d & a) | (~d & b)) + m[6] + 0xa8304613; c = d + ((c << 17) | (c >> (32-17))); };
 { b += ((c & d) | (~c & a)) + m[7] + 0xfd469501; b = c + ((b << 22) | (b >> (32-22))); };
 { a += ((b & c) | (~b & d)) + m[8] + 0x698098d8; a = b + ((a << 7) | (a >> (32-7))); };
 { d += ((a & b) | (~a & c)) + m[9] + 0x8b44f7af; d = a + ((d << 12) | (d >> (32-12))); };
 { c += ((d & a) | (~d & b)) + m[10] + 0xffff5bb1; c = d + ((c << 17) | (c >> (32-17))); };
 { b += ((c & d) | (~c & a)) + m[11] + 0x895cd7be; b = c + ((b << 22) | (b >> (32-22))); };
 { a += ((b & c) | (~b & d)) + m[12] + 0x6b901122; a = b + ((a << 7) | (a >> (32-7))); };
 { d += ((a & b) | (~a & c)) + m[13] + 0xfd987193; d = a + ((d << 12) | (d >> (32-12))); };
 { c += ((d & a) | (~d & b)) + m[14] + 0xa679438e; c = d + ((c << 17) | (c >> (32-17))); };
 { b += ((c & d) | (~c & a)) + m[15] + 0x49b40821; b = c + ((b << 22) | (b >> (32-22))); };

 { a += ((b & d) | (c & ~d)) + m[1] + 0xf61e2562; a = b + ((a << 5) | (a >> (32-5))); };
 { d += ((a & c) | (b & ~c)) + m[6] + 0xc040b340; d = a + ((d << 9) | (d >> (32-9))); };
 { c += ((d & b) | (a & ~b)) + m[11] + 0x265e5a51; c = d + ((c << 14) | (c >> (32-14))); };
 { b += ((c & a) | (d & ~a)) + m[0] + 0xe9b6c7aa; b = c + ((b << 20) | (b >> (32-20))); };
 { a += ((b & d) | (c & ~d)) + m[5] + 0xd62f105d; a = b + ((a << 5) | (a >> (32-5))); };
 { d += ((a & c) | (b & ~c)) + m[10] + 0x02441453; d = a + ((d << 9) | (d >> (32-9))); };
 { c += ((d & b) | (a & ~b)) + m[15] + 0xd8a1e681; c = d + ((c << 14) | (c >> (32-14))); };
 { b += ((c & a) | (d & ~a)) + m[4] + 0xe7d3fbc8; b = c + ((b << 20) | (b >> (32-20))); };
 { a += ((b & d) | (c & ~d)) + m[9] + 0x21e1cde6; a = b + ((a << 5) | (a >> (32-5))); };
 { d += ((a & c) | (b & ~c)) + m[14] + 0xc33707d6; d = a + ((d << 9) | (d >> (32-9))); };
 { c += ((d & b) | (a & ~b)) + m[3] + 0xf4d50d87; c = d + ((c << 14) | (c >> (32-14))); };
 { b += ((c & a) | (d & ~a)) + m[8] + 0x455a14ed; b = c + ((b << 20) | (b >> (32-20))); };
 { a += ((b & d) | (c & ~d)) + m[13] + 0xa9e3e905; a = b + ((a << 5) | (a >> (32-5))); };
 { d += ((a & c) | (b & ~c)) + m[2] + 0xfcefa3f8; d = a + ((d << 9) | (d >> (32-9))); };
 { c += ((d & b) | (a & ~b)) + m[7] + 0x676f02d9; c = d + ((c << 14) | (c >> (32-14))); };
 { b += ((c & a) | (d & ~a)) + m[12] + 0x8d2a4c8a; b = c + ((b << 20) | (b >> (32-20))); };

 { a += (b ^ c ^ d) + m[5] + 0xfffa3942; a = b + ((a << 4) | (a >> (32-4))); };
 { d += (a ^ b ^ c) + m[8] + 0x8771f681; d = a + ((d << 11) | (d >> (32-11))); };
 { c += (d ^ a ^ b) + m[11] + 0x6d9d6122; c = d + ((c << 16) | (c >> (32-16))); };
 { b += (c ^ d ^ a) + m[14] + 0xfde5380c; b = c + ((b << 23) | (b >> (32-23))); };
 { a += (b ^ c ^ d) + m[1] + 0xa4beea44; a = b + ((a << 4) | (a >> (32-4))); };
 { d += (a ^ b ^ c) + m[4] + 0x4bdecfa9; d = a + ((d << 11) | (d >> (32-11))); };
 { c += (d ^ a ^ b) + m[7] + 0xf6bb4b60; c = d + ((c << 16) | (c >> (32-16))); };
 { b += (c ^ d ^ a) + m[10] + 0xbebfbc70; b = c + ((b << 23) | (b >> (32-23))); };
 { a += (b ^ c ^ d) + m[13] + 0x289b7ec6; a = b + ((a << 4) | (a >> (32-4))); };
 { d += (a ^ b ^ c) + m[0] + 0xeaa127fa; d = a + ((d << 11) | (d >> (32-11))); };
 { c += (d ^ a ^ b) + m[3] + 0xd4ef3085; c = d + ((c << 16) | (c >> (32-16))); };
 { b += (c ^ d ^ a) + m[6] + 0x04881d05; b = c + ((b << 23) | (b >> (32-23))); };
 { a += (b ^ c ^ d) + m[9] + 0xd9d4d039; a = b + ((a << 4) | (a >> (32-4))); };
 { d += (a ^ b ^ c) + m[12] + 0xe6db99e5; d = a + ((d << 11) | (d >> (32-11))); };
 { c += (d ^ a ^ b) + m[15] + 0x1fa27cf8; c = d + ((c << 16) | (c >> (32-16))); };
 { b += (c ^ d ^ a) + m[2] + 0xc4ac5665; b = c + ((b << 23) | (b >> (32-23))); };

 { a += (c ^ (b | ~d)) + m[0] + 0xf4292244; a = b + ((a << 6) | (a >> (32-6))); };
 { d += (b ^ (a | ~c)) + m[7] + 0x432aff97; d = a + ((d << 10) | (d >> (32-10))); };
 { c += (a ^ (d | ~b)) + m[14] + 0xab9423a7; c = d + ((c << 15) | (c >> (32-15))); };
 { b += (d ^ (c | ~a)) + m[5] + 0xfc93a039; b = c + ((b << 21) | (b >> (32-21))); };
 { a += (c ^ (b | ~d)) + m[12] + 0x655b59c3; a = b + ((a << 6) | (a >> (32-6))); };
 { d += (b ^ (a | ~c)) + m[3] + 0x8f0ccc92; d = a + ((d << 10) | (d >> (32-10))); };
 { c += (a ^ (d | ~b)) + m[10] + 0xffeff47d; c = d + ((c << 15) | (c >> (32-15))); };
 { b += (d ^ (c | ~a)) + m[1] + 0x85845dd1; b = c + ((b << 21) | (b >> (32-21))); };
 { a += (c ^ (b | ~d)) + m[8] + 0x6fa87e4f; a = b + ((a << 6) | (a >> (32-6))); };
 { d += (b ^ (a | ~c)) + m[15] + 0xfe2ce6e0; d = a + ((d << 10) | (d >> (32-10))); };
 { c += (a ^ (d | ~b)) + m[6] + 0xa3014314; c = d + ((c << 15) | (c >> (32-15))); };
 { b += (d ^ (c | ~a)) + m[13] + 0x4e0811a1; b = c + ((b << 21) | (b >> (32-21))); };
 { a += (c ^ (b | ~d)) + m[4] + 0xf7537e82; a = b + ((a << 6) | (a >> (32-6))); };
 { d += (b ^ (a | ~c)) + m[11] + 0xbd3af235; d = a + ((d << 10) | (d >> (32-10))); };
 { c += (a ^ (d | ~b)) + m[2] + 0x2ad7d2bb; c = d + ((c << 15) | (c >> (32-15))); };
 { b += (d ^ (c | ~a)) + m[9] + 0xeb86d391; b = c + ((b << 21) | (b >> (32-21))); };

 ctx->state[0] += a;
 ctx->state[1] += b;
 ctx->state[2] += c;
 ctx->state[3] += d;
}

void md5_init(MD5_CTX *ctx)
{
 ctx->datalen = 0;
 ctx->bitlen = 0;
 ctx->state[0] = 0x67452301;
 ctx->state[1] = 0xEFCDAB89;
 ctx->state[2] = 0x98BADCFE;
 ctx->state[3] = 0x10325476;
}

void md5_update(MD5_CTX *ctx, const BYTE data[], size_t len)
{
 size_t i;

 for (i = 0; i < len; ++i) {
  ctx->data[ctx->datalen] = data[i];
  ctx->datalen++;
  if (ctx->datalen == 64) {
   md5_transform(ctx, ctx->data);
   ctx->bitlen += 512;
   ctx->datalen = 0;
  }
 }
}

void md5_final(MD5_CTX *ctx, BYTE hash[])
{
 size_t i;

 i = ctx->datalen;

 if (ctx->datalen < 56) {
  ctx->data[i++] = 0x80;
  while (i < 56)
   ctx->data[i++] = 0x00;
 }
 else if (ctx->datalen >= 56) {
  ctx->data[i++] = 0x80;
  while (i < 64)
   ctx->data[i++] = 0x00;
  md5_transform(ctx, ctx->data);
  memset(ctx->data, 0, 56);
 }

 ctx->bitlen += ctx->datalen * 8;
 ctx->data[56] = ctx->bitlen;
 ctx->data[57] = ctx->bitlen >> 8;
 ctx->data[58] = ctx->bitlen >> 16;
 ctx->data[59] = ctx->bitlen >> 24;
 ctx->data[60] = ctx->bitlen >> 32;
 ctx->data[61] = ctx->bitlen >> 40;
 ctx->data[62] = ctx->bitlen >> 48;
 ctx->data[63] = ctx->bitlen >> 56;
 md5_transform(ctx, ctx->data);

 for (i = 0; i < 4; ++i) {
  hash[i] = (ctx->state[0] >> (i * 8)) & 0x000000ff;
  hash[i + 4] = (ctx->state[1] >> (i * 8)) & 0x000000ff;
  hash[i + 8] = (ctx->state[2] >> (i * 8)) & 0x000000ff;
  hash[i + 12] = (ctx->state[3] >> (i * 8)) & 0x000000ff;
 }
}