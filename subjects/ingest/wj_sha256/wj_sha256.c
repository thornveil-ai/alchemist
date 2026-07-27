#include <stdint.h>
#include <stddef.h>
#include <string.h>

       

typedef struct
{
    uint64_t length;
    uint32_t state[8];
    uint32_t curlen;
    uint8_t buf[64];
} Sha256Context;

typedef struct
{
    uint8_t bytes [( 256 / 8 )];
} SHA256_HASH;
void
    Sha256Initialise
    (
        Sha256Context* Context
    );

void
    Sha256Update
    (
        Sha256Context* Context,
        void const* Buffer,
        uint32_t BufferSize
    );

void
    Sha256Finalise
    (
        Sha256Context* Context,
        SHA256_HASH* Digest
    );

void
    Sha256Calculate
    (
        void const* Buffer,
        uint32_t BufferSize,
        SHA256_HASH* Digest
    );

static const uint32_t K[64] = {
    0x428a2f98UL, 0x71374491UL, 0xb5c0fbcfUL, 0xe9b5dba5UL, 0x3956c25bUL,
    0x59f111f1UL, 0x923f82a4UL, 0xab1c5ed5UL, 0xd807aa98UL, 0x12835b01UL,
    0x243185beUL, 0x550c7dc3UL, 0x72be5d74UL, 0x80deb1feUL, 0x9bdc06a7UL,
    0xc19bf174UL, 0xe49b69c1UL, 0xefbe4786UL, 0x0fc19dc6UL, 0x240ca1ccUL,
    0x2de92c6fUL, 0x4a7484aaUL, 0x5cb0a9dcUL, 0x76f988daUL, 0x983e5152UL,
    0xa831c66dUL, 0xb00327c8UL, 0xbf597fc7UL, 0xc6e00bf3UL, 0xd5a79147UL,
    0x06ca6351UL, 0x14292967UL, 0x27b70a85UL, 0x2e1b2138UL, 0x4d2c6dfcUL,
    0x53380d13UL, 0x650a7354UL, 0x766a0abbUL, 0x81c2c92eUL, 0x92722c85UL,
    0xa2bfe8a1UL, 0xa81a664bUL, 0xc24b8b70UL, 0xc76c51a3UL, 0xd192e819UL,
    0xd6990624UL, 0xf40e3585UL, 0x106aa070UL, 0x19a4c116UL, 0x1e376c08UL,
    0x2748774cUL, 0x34b0bcb5UL, 0x391c0cb3UL, 0x4ed8aa4aUL, 0x5b9cca4fUL,
    0x682e6ff3UL, 0x748f82eeUL, 0x78a5636fUL, 0x84c87814UL, 0x8cc70208UL,
    0x90befffaUL, 0xa4506cebUL, 0xbef9a3f7UL, 0xc67178f2UL
};
static
void
    TransformFunction
    (
        Sha256Context* Context,
        uint8_t const* Buffer
    )
{
    uint32_t S[8];
    uint32_t W[64];
    uint32_t t0;
    uint32_t t1;
    uint32_t t;
    int i;

    for( i=0; i<8; i++ )
    {
        S[i] = Context->state[i];
    }

    for( i=0; i<16; i++ )
    {
        { W[i] = ((uint32_t)((Buffer + (4*i))[0] & 255)<<24) | ((uint32_t)((Buffer + (4*i))[1] & 255)<<16) | ((uint32_t)((Buffer + (4*i))[2] & 255)<<8) | ((uint32_t)((Buffer + (4*i))[3] & 255)); };
    }

    for( i=16; i<64; i++ )
    {
        W[i] = (((((W[i-2])) >> ((17))) | (((W[i-2])) << (32 - ((17))))) ^ ((((W[i-2])) >> ((19))) | (((W[i-2])) << (32 - ((19))))) ^ (((W[i-2])&0xFFFFFFFFUL)>>(10))) + W[i-7] + (((((W[i-15])) >> ((7))) | (((W[i-15])) << (32 - ((7))))) ^ ((((W[i-15])) >> ((18))) | (((W[i-15])) << (32 - ((18))))) ^ (((W[i-15])&0xFFFFFFFFUL)>>(3))) + W[i-16];
    }

    for( i=0; i<64; i++ )
    {
        t0 = S[7] + (((((S[4])) >> ((6))) | (((S[4])) << (32 - ((6))))) ^ ((((S[4])) >> ((11))) | (((S[4])) << (32 - ((11))))) ^ ((((S[4])) >> ((25))) | (((S[4])) << (32 - ((25)))))) + (S[6] ^ (S[4] & (S[5] ^ S[6]))) + K[i] + W[i]; t1 = (((((S[0])) >> ((2))) | (((S[0])) << (32 - ((2))))) ^ ((((S[0])) >> ((13))) | (((S[0])) << (32 - ((13))))) ^ ((((S[0])) >> ((22))) | (((S[0])) << (32 - ((22)))))) + (((S[0] | S[1]) & S[2]) | (S[0] & S[1])); S[3] += t0; S[7] = t0 + t1;;
        t = S[7];
        S[7] = S[6];
        S[6] = S[5];
        S[5] = S[4];
        S[4] = S[3];
        S[3] = S[2];
        S[2] = S[1];
        S[1] = S[0];
        S[0] = t;
    }

    for( i=0; i<8; i++ )
    {
        Context->state[i] = Context->state[i] + S[i];
    }
}
void
    Sha256Initialise
    (
        Sha256Context* Context
    )
{
    Context->curlen = 0;
    Context->length = 0;
    Context->state[0] = 0x6A09E667UL;
    Context->state[1] = 0xBB67AE85UL;
    Context->state[2] = 0x3C6EF372UL;
    Context->state[3] = 0xA54FF53AUL;
    Context->state[4] = 0x510E527FUL;
    Context->state[5] = 0x9B05688CUL;
    Context->state[6] = 0x1F83D9ABUL;
    Context->state[7] = 0x5BE0CD19UL;
}

void
    Sha256Update
    (
        Sha256Context* Context,
        void const* Buffer,
        uint32_t BufferSize
    )
{
    uint32_t n;

    if( Context->curlen >= sizeof(Context->buf) )
    {
       return;
    }

    while( BufferSize > 0 )
    {
        if( Context->curlen == 0 && BufferSize >= 64 )
        {
           TransformFunction( Context, (uint8_t*)Buffer );
           Context->length += 64 * 8;
           Buffer = (uint8_t*)Buffer + 64;
           BufferSize -= 64;
        }
        else
        {
           n = ( ((BufferSize)<((64 - Context->curlen)))?(BufferSize):((64 - Context->curlen)) );
           memcpy( Context->buf + Context->curlen, Buffer, (size_t)n );
           Context->curlen += n;
           Buffer = (uint8_t*)Buffer + n;
           BufferSize -= n;
           if( Context->curlen == 64 )
           {
              TransformFunction( Context, Context->buf );
              Context->length += 8*64;
              Context->curlen = 0;
           }
       }
    }
}

void
    Sha256Finalise
    (
        Sha256Context* Context,
        SHA256_HASH* Digest
    )
{
    int i;

    if( Context->curlen >= sizeof(Context->buf) )
    {
       return;
    }

    Context->length += Context->curlen * 8;

    Context->buf[Context->curlen++] = (uint8_t)0x80;

    if( Context->curlen > 56 )
    {
        while( Context->curlen < 64 )
        {
            Context->buf[Context->curlen++] = (uint8_t)0;
        }
        TransformFunction(Context, Context->buf);
        Context->curlen = 0;
    }

    while( Context->curlen < 56 )
    {
        Context->buf[Context->curlen++] = (uint8_t)0;
    }

    { (Context->buf+56)[0] = (uint8_t)(((Context->length)>>56)&255); (Context->buf+56)[1] = (uint8_t)(((Context->length)>>48)&255); (Context->buf+56)[2] = (uint8_t)(((Context->length)>>40)&255); (Context->buf+56)[3] = (uint8_t)(((Context->length)>>32)&255); (Context->buf+56)[4] = (uint8_t)(((Context->length)>>24)&255); (Context->buf+56)[5] = (uint8_t)(((Context->length)>>16)&255); (Context->buf+56)[6] = (uint8_t)(((Context->length)>>8)&255); (Context->buf+56)[7] = (uint8_t)((Context->length)&255); };
    TransformFunction( Context, Context->buf );

    for( i=0; i<8; i++ )
    {
        { (Digest->bytes+(4*i))[0] = (uint8_t)(((Context->state[i])>>24)&255); (Digest->bytes+(4*i))[1] = (uint8_t)(((Context->state[i])>>16)&255); (Digest->bytes+(4*i))[2] = (uint8_t)(((Context->state[i])>>8)&255); (Digest->bytes+(4*i))[3] = (uint8_t)((Context->state[i])&255); };
    }
}

void
    Sha256Calculate
    (
        void const* Buffer,
        uint32_t BufferSize,
        SHA256_HASH* Digest
    )
{
    Sha256Context context;

    Sha256Initialise( &context );
    Sha256Update( &context, Buffer, BufferSize );
    Sha256Finalise( &context, Digest );
}