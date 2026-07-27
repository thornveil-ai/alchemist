#include <stdint.h>
#include <stddef.h>
#include <string.h>

       

typedef struct
{
    uint32_t lo;
    uint32_t hi;
    uint32_t a;
    uint32_t b;
    uint32_t c;
    uint32_t d;
    uint8_t buffer[64];
    uint32_t block[16];
} Md5Context;

typedef struct
{
    uint8_t bytes [( 128 / 8 )];
} MD5_HASH;
void
    Md5Initialise
    (
        Md5Context* Context
    );

void
    Md5Update
    (
        Md5Context* Context,
        void const* Buffer,
        uint32_t BufferSize
    );

void
    Md5Finalise
    (
        Md5Context* Context,
        MD5_HASH* Digest
    );

void
    Md5Calculate
    (
        void const* Buffer,
        uint32_t BufferSize,
        MD5_HASH* Digest
    );

static
void*
    TransformFunction
    (
        Md5Context* ctx,
        void const* data,
        uintmax_t size
    )
{
    uint8_t* ptr;
    uint32_t a;
    uint32_t b;
    uint32_t c;
    uint32_t d;
    uint32_t saved_a;
    uint32_t saved_b;
    uint32_t saved_c;
    uint32_t saved_d;
    ptr = (uint8_t*)data;

    a = ctx->a;
    b = ctx->b;
    c = ctx->c;
    d = ctx->d;

    do
    {
        saved_a = a;
        saved_b = b;
        saved_c = c;
        saved_d = d;

        (a) += ( ((d)) ^ (((b)) & (((c)) ^ ((d)))) ) + ((ctx->block[(0)] = ((uint32_t)ptr[(0)*4 + 0] << 0 ) | ((uint32_t)ptr[(0)*4 + 1] << 8 ) | ((uint32_t)ptr[(0)*4 + 2] << 16) | ((uint32_t)ptr[(0)*4 + 3] << 24) )) + (0xd76aa478); (a) = (((a) << (7)) | (((a) & 0xffffffff) >> (32 - (7)))); (a) += (b);
        (d) += ( ((c)) ^ (((a)) & (((b)) ^ ((c)))) ) + ((ctx->block[(1)] = ((uint32_t)ptr[(1)*4 + 0] << 0 ) | ((uint32_t)ptr[(1)*4 + 1] << 8 ) | ((uint32_t)ptr[(1)*4 + 2] << 16) | ((uint32_t)ptr[(1)*4 + 3] << 24) )) + (0xe8c7b756); (d) = (((d) << (12)) | (((d) & 0xffffffff) >> (32 - (12)))); (d) += (a);
        (c) += ( ((b)) ^ (((d)) & (((a)) ^ ((b)))) ) + ((ctx->block[(2)] = ((uint32_t)ptr[(2)*4 + 0] << 0 ) | ((uint32_t)ptr[(2)*4 + 1] << 8 ) | ((uint32_t)ptr[(2)*4 + 2] << 16) | ((uint32_t)ptr[(2)*4 + 3] << 24) )) + (0x242070db); (c) = (((c) << (17)) | (((c) & 0xffffffff) >> (32 - (17)))); (c) += (d);
        (b) += ( ((a)) ^ (((c)) & (((d)) ^ ((a)))) ) + ((ctx->block[(3)] = ((uint32_t)ptr[(3)*4 + 0] << 0 ) | ((uint32_t)ptr[(3)*4 + 1] << 8 ) | ((uint32_t)ptr[(3)*4 + 2] << 16) | ((uint32_t)ptr[(3)*4 + 3] << 24) )) + (0xc1bdceee); (b) = (((b) << (22)) | (((b) & 0xffffffff) >> (32 - (22)))); (b) += (c);
        (a) += ( ((d)) ^ (((b)) & (((c)) ^ ((d)))) ) + ((ctx->block[(4)] = ((uint32_t)ptr[(4)*4 + 0] << 0 ) | ((uint32_t)ptr[(4)*4 + 1] << 8 ) | ((uint32_t)ptr[(4)*4 + 2] << 16) | ((uint32_t)ptr[(4)*4 + 3] << 24) )) + (0xf57c0faf); (a) = (((a) << (7)) | (((a) & 0xffffffff) >> (32 - (7)))); (a) += (b);
        (d) += ( ((c)) ^ (((a)) & (((b)) ^ ((c)))) ) + ((ctx->block[(5)] = ((uint32_t)ptr[(5)*4 + 0] << 0 ) | ((uint32_t)ptr[(5)*4 + 1] << 8 ) | ((uint32_t)ptr[(5)*4 + 2] << 16) | ((uint32_t)ptr[(5)*4 + 3] << 24) )) + (0x4787c62a); (d) = (((d) << (12)) | (((d) & 0xffffffff) >> (32 - (12)))); (d) += (a);
        (c) += ( ((b)) ^ (((d)) & (((a)) ^ ((b)))) ) + ((ctx->block[(6)] = ((uint32_t)ptr[(6)*4 + 0] << 0 ) | ((uint32_t)ptr[(6)*4 + 1] << 8 ) | ((uint32_t)ptr[(6)*4 + 2] << 16) | ((uint32_t)ptr[(6)*4 + 3] << 24) )) + (0xa8304613); (c) = (((c) << (17)) | (((c) & 0xffffffff) >> (32 - (17)))); (c) += (d);
        (b) += ( ((a)) ^ (((c)) & (((d)) ^ ((a)))) ) + ((ctx->block[(7)] = ((uint32_t)ptr[(7)*4 + 0] << 0 ) | ((uint32_t)ptr[(7)*4 + 1] << 8 ) | ((uint32_t)ptr[(7)*4 + 2] << 16) | ((uint32_t)ptr[(7)*4 + 3] << 24) )) + (0xfd469501); (b) = (((b) << (22)) | (((b) & 0xffffffff) >> (32 - (22)))); (b) += (c);
        (a) += ( ((d)) ^ (((b)) & (((c)) ^ ((d)))) ) + ((ctx->block[(8)] = ((uint32_t)ptr[(8)*4 + 0] << 0 ) | ((uint32_t)ptr[(8)*4 + 1] << 8 ) | ((uint32_t)ptr[(8)*4 + 2] << 16) | ((uint32_t)ptr[(8)*4 + 3] << 24) )) + (0x698098d8); (a) = (((a) << (7)) | (((a) & 0xffffffff) >> (32 - (7)))); (a) += (b);
        (d) += ( ((c)) ^ (((a)) & (((b)) ^ ((c)))) ) + ((ctx->block[(9)] = ((uint32_t)ptr[(9)*4 + 0] << 0 ) | ((uint32_t)ptr[(9)*4 + 1] << 8 ) | ((uint32_t)ptr[(9)*4 + 2] << 16) | ((uint32_t)ptr[(9)*4 + 3] << 24) )) + (0x8b44f7af); (d) = (((d) << (12)) | (((d) & 0xffffffff) >> (32 - (12)))); (d) += (a);
        (c) += ( ((b)) ^ (((d)) & (((a)) ^ ((b)))) ) + ((ctx->block[(10)] = ((uint32_t)ptr[(10)*4 + 0] << 0 ) | ((uint32_t)ptr[(10)*4 + 1] << 8 ) | ((uint32_t)ptr[(10)*4 + 2] << 16) | ((uint32_t)ptr[(10)*4 + 3] << 24) )) + (0xffff5bb1); (c) = (((c) << (17)) | (((c) & 0xffffffff) >> (32 - (17)))); (c) += (d);
        (b) += ( ((a)) ^ (((c)) & (((d)) ^ ((a)))) ) + ((ctx->block[(11)] = ((uint32_t)ptr[(11)*4 + 0] << 0 ) | ((uint32_t)ptr[(11)*4 + 1] << 8 ) | ((uint32_t)ptr[(11)*4 + 2] << 16) | ((uint32_t)ptr[(11)*4 + 3] << 24) )) + (0x895cd7be); (b) = (((b) << (22)) | (((b) & 0xffffffff) >> (32 - (22)))); (b) += (c);
        (a) += ( ((d)) ^ (((b)) & (((c)) ^ ((d)))) ) + ((ctx->block[(12)] = ((uint32_t)ptr[(12)*4 + 0] << 0 ) | ((uint32_t)ptr[(12)*4 + 1] << 8 ) | ((uint32_t)ptr[(12)*4 + 2] << 16) | ((uint32_t)ptr[(12)*4 + 3] << 24) )) + (0x6b901122); (a) = (((a) << (7)) | (((a) & 0xffffffff) >> (32 - (7)))); (a) += (b);
        (d) += ( ((c)) ^ (((a)) & (((b)) ^ ((c)))) ) + ((ctx->block[(13)] = ((uint32_t)ptr[(13)*4 + 0] << 0 ) | ((uint32_t)ptr[(13)*4 + 1] << 8 ) | ((uint32_t)ptr[(13)*4 + 2] << 16) | ((uint32_t)ptr[(13)*4 + 3] << 24) )) + (0xfd987193); (d) = (((d) << (12)) | (((d) & 0xffffffff) >> (32 - (12)))); (d) += (a);
        (c) += ( ((b)) ^ (((d)) & (((a)) ^ ((b)))) ) + ((ctx->block[(14)] = ((uint32_t)ptr[(14)*4 + 0] << 0 ) | ((uint32_t)ptr[(14)*4 + 1] << 8 ) | ((uint32_t)ptr[(14)*4 + 2] << 16) | ((uint32_t)ptr[(14)*4 + 3] << 24) )) + (0xa679438e); (c) = (((c) << (17)) | (((c) & 0xffffffff) >> (32 - (17)))); (c) += (d);
        (b) += ( ((a)) ^ (((c)) & (((d)) ^ ((a)))) ) + ((ctx->block[(15)] = ((uint32_t)ptr[(15)*4 + 0] << 0 ) | ((uint32_t)ptr[(15)*4 + 1] << 8 ) | ((uint32_t)ptr[(15)*4 + 2] << 16) | ((uint32_t)ptr[(15)*4 + 3] << 24) )) + (0x49b40821); (b) = (((b) << (22)) | (((b) & 0xffffffff) >> (32 - (22)))); (b) += (c);

        (a) += ( ((c)) ^ (((d)) & (((b)) ^ ((c)))) ) + ((ctx->block[(1)])) + (0xf61e2562); (a) = (((a) << (5)) | (((a) & 0xffffffff) >> (32 - (5)))); (a) += (b);
        (d) += ( ((b)) ^ (((c)) & (((a)) ^ ((b)))) ) + ((ctx->block[(6)])) + (0xc040b340); (d) = (((d) << (9)) | (((d) & 0xffffffff) >> (32 - (9)))); (d) += (a);
        (c) += ( ((a)) ^ (((b)) & (((d)) ^ ((a)))) ) + ((ctx->block[(11)])) + (0x265e5a51); (c) = (((c) << (14)) | (((c) & 0xffffffff) >> (32 - (14)))); (c) += (d);
        (b) += ( ((d)) ^ (((a)) & (((c)) ^ ((d)))) ) + ((ctx->block[(0)])) + (0xe9b6c7aa); (b) = (((b) << (20)) | (((b) & 0xffffffff) >> (32 - (20)))); (b) += (c);
        (a) += ( ((c)) ^ (((d)) & (((b)) ^ ((c)))) ) + ((ctx->block[(5)])) + (0xd62f105d); (a) = (((a) << (5)) | (((a) & 0xffffffff) >> (32 - (5)))); (a) += (b);
        (d) += ( ((b)) ^ (((c)) & (((a)) ^ ((b)))) ) + ((ctx->block[(10)])) + (0x02441453); (d) = (((d) << (9)) | (((d) & 0xffffffff) >> (32 - (9)))); (d) += (a);
        (c) += ( ((a)) ^ (((b)) & (((d)) ^ ((a)))) ) + ((ctx->block[(15)])) + (0xd8a1e681); (c) = (((c) << (14)) | (((c) & 0xffffffff) >> (32 - (14)))); (c) += (d);
        (b) += ( ((d)) ^ (((a)) & (((c)) ^ ((d)))) ) + ((ctx->block[(4)])) + (0xe7d3fbc8); (b) = (((b) << (20)) | (((b) & 0xffffffff) >> (32 - (20)))); (b) += (c);
        (a) += ( ((c)) ^ (((d)) & (((b)) ^ ((c)))) ) + ((ctx->block[(9)])) + (0x21e1cde6); (a) = (((a) << (5)) | (((a) & 0xffffffff) >> (32 - (5)))); (a) += (b);
        (d) += ( ((b)) ^ (((c)) & (((a)) ^ ((b)))) ) + ((ctx->block[(14)])) + (0xc33707d6); (d) = (((d) << (9)) | (((d) & 0xffffffff) >> (32 - (9)))); (d) += (a);
        (c) += ( ((a)) ^ (((b)) & (((d)) ^ ((a)))) ) + ((ctx->block[(3)])) + (0xf4d50d87); (c) = (((c) << (14)) | (((c) & 0xffffffff) >> (32 - (14)))); (c) += (d);
        (b) += ( ((d)) ^ (((a)) & (((c)) ^ ((d)))) ) + ((ctx->block[(8)])) + (0x455a14ed); (b) = (((b) << (20)) | (((b) & 0xffffffff) >> (32 - (20)))); (b) += (c);
        (a) += ( ((c)) ^ (((d)) & (((b)) ^ ((c)))) ) + ((ctx->block[(13)])) + (0xa9e3e905); (a) = (((a) << (5)) | (((a) & 0xffffffff) >> (32 - (5)))); (a) += (b);
        (d) += ( ((b)) ^ (((c)) & (((a)) ^ ((b)))) ) + ((ctx->block[(2)])) + (0xfcefa3f8); (d) = (((d) << (9)) | (((d) & 0xffffffff) >> (32 - (9)))); (d) += (a);
        (c) += ( ((a)) ^ (((b)) & (((d)) ^ ((a)))) ) + ((ctx->block[(7)])) + (0x676f02d9); (c) = (((c) << (14)) | (((c) & 0xffffffff) >> (32 - (14)))); (c) += (d);
        (b) += ( ((d)) ^ (((a)) & (((c)) ^ ((d)))) ) + ((ctx->block[(12)])) + (0x8d2a4c8a); (b) = (((b) << (20)) | (((b) & 0xffffffff) >> (32 - (20)))); (b) += (c);

        (a) += ( ((b)) ^ ((c)) ^ ((d)) ) + ((ctx->block[(5)])) + (0xfffa3942); (a) = (((a) << (4)) | (((a) & 0xffffffff) >> (32 - (4)))); (a) += (b);
        (d) += ( ((a)) ^ ((b)) ^ ((c)) ) + ((ctx->block[(8)])) + (0x8771f681); (d) = (((d) << (11)) | (((d) & 0xffffffff) >> (32 - (11)))); (d) += (a);
        (c) += ( ((d)) ^ ((a)) ^ ((b)) ) + ((ctx->block[(11)])) + (0x6d9d6122); (c) = (((c) << (16)) | (((c) & 0xffffffff) >> (32 - (16)))); (c) += (d);
        (b) += ( ((c)) ^ ((d)) ^ ((a)) ) + ((ctx->block[(14)])) + (0xfde5380c); (b) = (((b) << (23)) | (((b) & 0xffffffff) >> (32 - (23)))); (b) += (c);
        (a) += ( ((b)) ^ ((c)) ^ ((d)) ) + ((ctx->block[(1)])) + (0xa4beea44); (a) = (((a) << (4)) | (((a) & 0xffffffff) >> (32 - (4)))); (a) += (b);
        (d) += ( ((a)) ^ ((b)) ^ ((c)) ) + ((ctx->block[(4)])) + (0x4bdecfa9); (d) = (((d) << (11)) | (((d) & 0xffffffff) >> (32 - (11)))); (d) += (a);
        (c) += ( ((d)) ^ ((a)) ^ ((b)) ) + ((ctx->block[(7)])) + (0xf6bb4b60); (c) = (((c) << (16)) | (((c) & 0xffffffff) >> (32 - (16)))); (c) += (d);
        (b) += ( ((c)) ^ ((d)) ^ ((a)) ) + ((ctx->block[(10)])) + (0xbebfbc70); (b) = (((b) << (23)) | (((b) & 0xffffffff) >> (32 - (23)))); (b) += (c);
        (a) += ( ((b)) ^ ((c)) ^ ((d)) ) + ((ctx->block[(13)])) + (0x289b7ec6); (a) = (((a) << (4)) | (((a) & 0xffffffff) >> (32 - (4)))); (a) += (b);
        (d) += ( ((a)) ^ ((b)) ^ ((c)) ) + ((ctx->block[(0)])) + (0xeaa127fa); (d) = (((d) << (11)) | (((d) & 0xffffffff) >> (32 - (11)))); (d) += (a);
        (c) += ( ((d)) ^ ((a)) ^ ((b)) ) + ((ctx->block[(3)])) + (0xd4ef3085); (c) = (((c) << (16)) | (((c) & 0xffffffff) >> (32 - (16)))); (c) += (d);
        (b) += ( ((c)) ^ ((d)) ^ ((a)) ) + ((ctx->block[(6)])) + (0x04881d05); (b) = (((b) << (23)) | (((b) & 0xffffffff) >> (32 - (23)))); (b) += (c);
        (a) += ( ((b)) ^ ((c)) ^ ((d)) ) + ((ctx->block[(9)])) + (0xd9d4d039); (a) = (((a) << (4)) | (((a) & 0xffffffff) >> (32 - (4)))); (a) += (b);
        (d) += ( ((a)) ^ ((b)) ^ ((c)) ) + ((ctx->block[(12)])) + (0xe6db99e5); (d) = (((d) << (11)) | (((d) & 0xffffffff) >> (32 - (11)))); (d) += (a);
        (c) += ( ((d)) ^ ((a)) ^ ((b)) ) + ((ctx->block[(15)])) + (0x1fa27cf8); (c) = (((c) << (16)) | (((c) & 0xffffffff) >> (32 - (16)))); (c) += (d);
        (b) += ( ((c)) ^ ((d)) ^ ((a)) ) + ((ctx->block[(2)])) + (0xc4ac5665); (b) = (((b) << (23)) | (((b) & 0xffffffff) >> (32 - (23)))); (b) += (c);

        (a) += ( ((c)) ^ (((b)) | ~((d))) ) + ((ctx->block[(0)])) + (0xf4292244); (a) = (((a) << (6)) | (((a) & 0xffffffff) >> (32 - (6)))); (a) += (b);
        (d) += ( ((b)) ^ (((a)) | ~((c))) ) + ((ctx->block[(7)])) + (0x432aff97); (d) = (((d) << (10)) | (((d) & 0xffffffff) >> (32 - (10)))); (d) += (a);
        (c) += ( ((a)) ^ (((d)) | ~((b))) ) + ((ctx->block[(14)])) + (0xab9423a7); (c) = (((c) << (15)) | (((c) & 0xffffffff) >> (32 - (15)))); (c) += (d);
        (b) += ( ((d)) ^ (((c)) | ~((a))) ) + ((ctx->block[(5)])) + (0xfc93a039); (b) = (((b) << (21)) | (((b) & 0xffffffff) >> (32 - (21)))); (b) += (c);
        (a) += ( ((c)) ^ (((b)) | ~((d))) ) + ((ctx->block[(12)])) + (0x655b59c3); (a) = (((a) << (6)) | (((a) & 0xffffffff) >> (32 - (6)))); (a) += (b);
        (d) += ( ((b)) ^ (((a)) | ~((c))) ) + ((ctx->block[(3)])) + (0x8f0ccc92); (d) = (((d) << (10)) | (((d) & 0xffffffff) >> (32 - (10)))); (d) += (a);
        (c) += ( ((a)) ^ (((d)) | ~((b))) ) + ((ctx->block[(10)])) + (0xffeff47d); (c) = (((c) << (15)) | (((c) & 0xffffffff) >> (32 - (15)))); (c) += (d);
        (b) += ( ((d)) ^ (((c)) | ~((a))) ) + ((ctx->block[(1)])) + (0x85845dd1); (b) = (((b) << (21)) | (((b) & 0xffffffff) >> (32 - (21)))); (b) += (c);
        (a) += ( ((c)) ^ (((b)) | ~((d))) ) + ((ctx->block[(8)])) + (0x6fa87e4f); (a) = (((a) << (6)) | (((a) & 0xffffffff) >> (32 - (6)))); (a) += (b);
        (d) += ( ((b)) ^ (((a)) | ~((c))) ) + ((ctx->block[(15)])) + (0xfe2ce6e0); (d) = (((d) << (10)) | (((d) & 0xffffffff) >> (32 - (10)))); (d) += (a);
        (c) += ( ((a)) ^ (((d)) | ~((b))) ) + ((ctx->block[(6)])) + (0xa3014314); (c) = (((c) << (15)) | (((c) & 0xffffffff) >> (32 - (15)))); (c) += (d);
        (b) += ( ((d)) ^ (((c)) | ~((a))) ) + ((ctx->block[(13)])) + (0x4e0811a1); (b) = (((b) << (21)) | (((b) & 0xffffffff) >> (32 - (21)))); (b) += (c);
        (a) += ( ((c)) ^ (((b)) | ~((d))) ) + ((ctx->block[(4)])) + (0xf7537e82); (a) = (((a) << (6)) | (((a) & 0xffffffff) >> (32 - (6)))); (a) += (b);
        (d) += ( ((b)) ^ (((a)) | ~((c))) ) + ((ctx->block[(11)])) + (0xbd3af235); (d) = (((d) << (10)) | (((d) & 0xffffffff) >> (32 - (10)))); (d) += (a);
        (c) += ( ((a)) ^ (((d)) | ~((b))) ) + ((ctx->block[(2)])) + (0x2ad7d2bb); (c) = (((c) << (15)) | (((c) & 0xffffffff) >> (32 - (15)))); (c) += (d);
        (b) += ( ((d)) ^ (((c)) | ~((a))) ) + ((ctx->block[(9)])) + (0xeb86d391); (b) = (((b) << (21)) | (((b) & 0xffffffff) >> (32 - (21)))); (b) += (c);

        a += saved_a;
        b += saved_b;
        c += saved_c;
        d += saved_d;

        ptr += 64;
    } while( size -= 64 );

    ctx->a = a;
    ctx->b = b;
    ctx->c = c;
    ctx->d = d;

    return ptr;
}
void
    Md5Initialise
    (
        Md5Context* Context
    )
{
    Context->a = 0x67452301;
    Context->b = 0xefcdab89;
    Context->c = 0x98badcfe;
    Context->d = 0x10325476;

    Context->lo = 0;
    Context->hi = 0;
}

void
    Md5Update
    (
        Md5Context* Context,
        void const* Buffer,
        uint32_t BufferSize
    )
{
    uint32_t saved_lo;
    uint32_t used;
    uint32_t free;

    saved_lo = Context->lo;
    if( (Context->lo = (saved_lo + BufferSize) & 0x1fffffff) < saved_lo )
    {
        Context->hi++;
    }
    Context->hi += (uint32_t)( BufferSize >> 29 );

    used = saved_lo & 0x3f;

    if( used )
    {
        free = 64 - used;

        if( BufferSize < free )
        {
            memcpy( &Context->buffer[used], Buffer, BufferSize );
            return;
        }

        memcpy( &Context->buffer[used], Buffer, free );
        Buffer = (uint8_t*)Buffer + free;
        BufferSize -= free;
        TransformFunction(Context, Context->buffer, 64);
    }

    if( BufferSize >= 64 )
    {
        Buffer = TransformFunction( Context, Buffer, BufferSize & ~(unsigned long)0x3f );
        BufferSize &= 0x3f;
    }

    memcpy( Context->buffer, Buffer, BufferSize );
}

void
    Md5Finalise
    (
        Md5Context* Context,
        MD5_HASH* Digest
    )
{
    uint32_t used;
    uint32_t free;

    used = Context->lo & 0x3f;

    Context->buffer[used++] = 0x80;

    free = 64 - used;

    if(free < 8)
    {
        memset( &Context->buffer[used], 0, free );
        TransformFunction( Context, Context->buffer, 64 );
        used = 0;
        free = 64;
    }

    memset( &Context->buffer[used], 0, free - 8 );

    Context->lo <<= 3;
    Context->buffer[56] = (uint8_t)( Context->lo );
    Context->buffer[57] = (uint8_t)( Context->lo >> 8 );
    Context->buffer[58] = (uint8_t)( Context->lo >> 16 );
    Context->buffer[59] = (uint8_t)( Context->lo >> 24 );
    Context->buffer[60] = (uint8_t)( Context->hi );
    Context->buffer[61] = (uint8_t)( Context->hi >> 8 );
    Context->buffer[62] = (uint8_t)( Context->hi >> 16 );
    Context->buffer[63] = (uint8_t)( Context->hi >> 24 );

    TransformFunction( Context, Context->buffer, 64 );

    Digest->bytes[0] = (uint8_t)( Context->a );
    Digest->bytes[1] = (uint8_t)( Context->a >> 8 );
    Digest->bytes[2] = (uint8_t)( Context->a >> 16 );
    Digest->bytes[3] = (uint8_t)( Context->a >> 24 );
    Digest->bytes[4] = (uint8_t)( Context->b );
    Digest->bytes[5] = (uint8_t)( Context->b >> 8 );
    Digest->bytes[6] = (uint8_t)( Context->b >> 16 );
    Digest->bytes[7] = (uint8_t)( Context->b >> 24 );
    Digest->bytes[8] = (uint8_t)( Context->c );
    Digest->bytes[9] = (uint8_t)( Context->c >> 8 );
    Digest->bytes[10] = (uint8_t)( Context->c >> 16 );
    Digest->bytes[11] = (uint8_t)( Context->c >> 24 );
    Digest->bytes[12] = (uint8_t)( Context->d );
    Digest->bytes[13] = (uint8_t)( Context->d >> 8 );
    Digest->bytes[14] = (uint8_t)( Context->d >> 16 );
    Digest->bytes[15] = (uint8_t)( Context->d >> 24 );
}

void
    Md5Calculate
    (
        void const* Buffer,
        uint32_t BufferSize,
        MD5_HASH* Digest
    )
{
    Md5Context context;

    Md5Initialise( &context );
    Md5Update( &context, Buffer, BufferSize );
    Md5Finalise( &context, Digest );
}