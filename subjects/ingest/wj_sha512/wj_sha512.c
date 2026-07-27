#include <stdint.h>
#include <stddef.h>
#include <string.h>

       

typedef struct
{
    uint64_t length;
    uint64_t state[8];
    uint32_t curlen;
    uint8_t buf[128];
} Sha512Context;

typedef struct
{
    uint8_t bytes [( 512 / 8 )];
} SHA512_HASH;
void
    Sha512Initialise
    (
        Sha512Context* Context
    );

void
    Sha512Update
    (
        Sha512Context* Context,
        void const* Buffer,
        uint32_t BufferSize
    );

void
    Sha512Finalise
    (
        Sha512Context* Context,
        SHA512_HASH* Digest
    );

void
    Sha512Calculate
    (
        void const* Buffer,
        uint32_t BufferSize,
        SHA512_HASH* Digest
    );

static const uint64_t K[80] = {
    0x428a2f98d728ae22ULL, 0x7137449123ef65cdULL, 0xb5c0fbcfec4d3b2fULL, 0xe9b5dba58189dbbcULL,
    0x3956c25bf348b538ULL, 0x59f111f1b605d019ULL, 0x923f82a4af194f9bULL, 0xab1c5ed5da6d8118ULL,
    0xd807aa98a3030242ULL, 0x12835b0145706fbeULL, 0x243185be4ee4b28cULL, 0x550c7dc3d5ffb4e2ULL,
    0x72be5d74f27b896fULL, 0x80deb1fe3b1696b1ULL, 0x9bdc06a725c71235ULL, 0xc19bf174cf692694ULL,
    0xe49b69c19ef14ad2ULL, 0xefbe4786384f25e3ULL, 0x0fc19dc68b8cd5b5ULL, 0x240ca1cc77ac9c65ULL,
    0x2de92c6f592b0275ULL, 0x4a7484aa6ea6e483ULL, 0x5cb0a9dcbd41fbd4ULL, 0x76f988da831153b5ULL,
    0x983e5152ee66dfabULL, 0xa831c66d2db43210ULL, 0xb00327c898fb213fULL, 0xbf597fc7beef0ee4ULL,
    0xc6e00bf33da88fc2ULL, 0xd5a79147930aa725ULL, 0x06ca6351e003826fULL, 0x142929670a0e6e70ULL,
    0x27b70a8546d22ffcULL, 0x2e1b21385c26c926ULL, 0x4d2c6dfc5ac42aedULL, 0x53380d139d95b3dfULL,
    0x650a73548baf63deULL, 0x766a0abb3c77b2a8ULL, 0x81c2c92e47edaee6ULL, 0x92722c851482353bULL,
    0xa2bfe8a14cf10364ULL, 0xa81a664bbc423001ULL, 0xc24b8b70d0f89791ULL, 0xc76c51a30654be30ULL,
    0xd192e819d6ef5218ULL, 0xd69906245565a910ULL, 0xf40e35855771202aULL, 0x106aa07032bbd1b8ULL,
    0x19a4c116b8d2d0c8ULL, 0x1e376c085141ab53ULL, 0x2748774cdf8eeb99ULL, 0x34b0bcb5e19b48a8ULL,
    0x391c0cb3c5c95a63ULL, 0x4ed8aa4ae3418acbULL, 0x5b9cca4f7763e373ULL, 0x682e6ff3d6b2b8a3ULL,
    0x748f82ee5defb2fcULL, 0x78a5636f43172f60ULL, 0x84c87814a1f0ab72ULL, 0x8cc702081a6439ecULL,
    0x90befffa23631e28ULL, 0xa4506cebde82bde9ULL, 0xbef9a3f7b2c67915ULL, 0xc67178f2e372532bULL,
    0xca273eceea26619cULL, 0xd186b8c721c0c207ULL, 0xeada7dd6cde0eb1eULL, 0xf57d4f7fee6ed178ULL,
    0x06f067aa72176fbaULL, 0x0a637dc5a2c898a6ULL, 0x113f9804bef90daeULL, 0x1b710b35131c471bULL,
    0x28db77f523047d84ULL, 0x32caab7b40c72493ULL, 0x3c9ebe0a15c9bebcULL, 0x431d67c49c100d4cULL,
    0x4cc5d4becb3e42b6ULL, 0x597f299cfc657e2aULL, 0x5fcb6fab3ad6faecULL, 0x6c44198c4a475817ULL
};
static
void
    TransformFunction
    (
        Sha512Context* Context,
        uint8_t const* Buffer
    )
{
    uint64_t S[8];
    uint64_t W[80];
    uint64_t t0;
    uint64_t t1;
    int i;

    for( i=0; i<8; i++ )
    {
        S[i] = Context->state[i];
    }

    for( i=0; i<16; i++ )
    {
        { W[i] = (((uint64_t)((Buffer + (8*i))[0] & 255))<<56)|(((uint64_t)((Buffer + (8*i))[1] & 255))<<48) | (((uint64_t)((Buffer + (8*i))[2] & 255))<<40)|(((uint64_t)((Buffer + (8*i))[3] & 255))<<32) | (((uint64_t)((Buffer + (8*i))[4] & 255))<<24)|(((uint64_t)((Buffer + (8*i))[5] & 255))<<16) | (((uint64_t)((Buffer + (8*i))[6] & 255))<<8)|(((uint64_t)((Buffer + (8*i))[7] & 255))); };
    }

    for( i=16; i<80; i++ )
    {
        W[i] = ((((W[i - 2]) >> (19)) | ((W[i - 2]) << (64 - (19)))) ^ (((W[i - 2]) >> (61)) | ((W[i - 2]) << (64 - (61)))) ^ (((W[i - 2])&0xFFFFFFFFFFFFFFFFULL)>>((uint64_t)6))) + W[i - 7] + ((((W[i - 15]) >> (1)) | ((W[i - 15]) << (64 - (1)))) ^ (((W[i - 15]) >> (8)) | ((W[i - 15]) << (64 - (8)))) ^ (((W[i - 15])&0xFFFFFFFFFFFFFFFFULL)>>((uint64_t)7))) + W[i - 16];
    }

     for( i=0; i<80; i+=8 )
     {
         t0 = S[7] + ((((S[4]) >> (14)) | ((S[4]) << (64 - (14)))) ^ (((S[4]) >> (18)) | ((S[4]) << (64 - (18)))) ^ (((S[4]) >> (41)) | ((S[4]) << (64 - (41))))) + (S[6] ^ (S[4] & (S[5] ^ S[6]))) + K[i+0] + W[i+0]; t1 = ((((S[0]) >> (28)) | ((S[0]) << (64 - (28)))) ^ (((S[0]) >> (34)) | ((S[0]) << (64 - (34)))) ^ (((S[0]) >> (39)) | ((S[0]) << (64 - (39))))) + (((S[0] | S[1]) & S[2]) | (S[0] & S[1])); S[3] += t0; S[7] = t0 + t1;;
         t0 = S[6] + ((((S[3]) >> (14)) | ((S[3]) << (64 - (14)))) ^ (((S[3]) >> (18)) | ((S[3]) << (64 - (18)))) ^ (((S[3]) >> (41)) | ((S[3]) << (64 - (41))))) + (S[5] ^ (S[3] & (S[4] ^ S[5]))) + K[i+1] + W[i+1]; t1 = ((((S[7]) >> (28)) | ((S[7]) << (64 - (28)))) ^ (((S[7]) >> (34)) | ((S[7]) << (64 - (34)))) ^ (((S[7]) >> (39)) | ((S[7]) << (64 - (39))))) + (((S[7] | S[0]) & S[1]) | (S[7] & S[0])); S[2] += t0; S[6] = t0 + t1;;
         t0 = S[5] + ((((S[2]) >> (14)) | ((S[2]) << (64 - (14)))) ^ (((S[2]) >> (18)) | ((S[2]) << (64 - (18)))) ^ (((S[2]) >> (41)) | ((S[2]) << (64 - (41))))) + (S[4] ^ (S[2] & (S[3] ^ S[4]))) + K[i+2] + W[i+2]; t1 = ((((S[6]) >> (28)) | ((S[6]) << (64 - (28)))) ^ (((S[6]) >> (34)) | ((S[6]) << (64 - (34)))) ^ (((S[6]) >> (39)) | ((S[6]) << (64 - (39))))) + (((S[6] | S[7]) & S[0]) | (S[6] & S[7])); S[1] += t0; S[5] = t0 + t1;;
         t0 = S[4] + ((((S[1]) >> (14)) | ((S[1]) << (64 - (14)))) ^ (((S[1]) >> (18)) | ((S[1]) << (64 - (18)))) ^ (((S[1]) >> (41)) | ((S[1]) << (64 - (41))))) + (S[3] ^ (S[1] & (S[2] ^ S[3]))) + K[i+3] + W[i+3]; t1 = ((((S[5]) >> (28)) | ((S[5]) << (64 - (28)))) ^ (((S[5]) >> (34)) | ((S[5]) << (64 - (34)))) ^ (((S[5]) >> (39)) | ((S[5]) << (64 - (39))))) + (((S[5] | S[6]) & S[7]) | (S[5] & S[6])); S[0] += t0; S[4] = t0 + t1;;
         t0 = S[3] + ((((S[0]) >> (14)) | ((S[0]) << (64 - (14)))) ^ (((S[0]) >> (18)) | ((S[0]) << (64 - (18)))) ^ (((S[0]) >> (41)) | ((S[0]) << (64 - (41))))) + (S[2] ^ (S[0] & (S[1] ^ S[2]))) + K[i+4] + W[i+4]; t1 = ((((S[4]) >> (28)) | ((S[4]) << (64 - (28)))) ^ (((S[4]) >> (34)) | ((S[4]) << (64 - (34)))) ^ (((S[4]) >> (39)) | ((S[4]) << (64 - (39))))) + (((S[4] | S[5]) & S[6]) | (S[4] & S[5])); S[7] += t0; S[3] = t0 + t1;;
         t0 = S[2] + ((((S[7]) >> (14)) | ((S[7]) << (64 - (14)))) ^ (((S[7]) >> (18)) | ((S[7]) << (64 - (18)))) ^ (((S[7]) >> (41)) | ((S[7]) << (64 - (41))))) + (S[1] ^ (S[7] & (S[0] ^ S[1]))) + K[i+5] + W[i+5]; t1 = ((((S[3]) >> (28)) | ((S[3]) << (64 - (28)))) ^ (((S[3]) >> (34)) | ((S[3]) << (64 - (34)))) ^ (((S[3]) >> (39)) | ((S[3]) << (64 - (39))))) + (((S[3] | S[4]) & S[5]) | (S[3] & S[4])); S[6] += t0; S[2] = t0 + t1;;
         t0 = S[1] + ((((S[6]) >> (14)) | ((S[6]) << (64 - (14)))) ^ (((S[6]) >> (18)) | ((S[6]) << (64 - (18)))) ^ (((S[6]) >> (41)) | ((S[6]) << (64 - (41))))) + (S[0] ^ (S[6] & (S[7] ^ S[0]))) + K[i+6] + W[i+6]; t1 = ((((S[2]) >> (28)) | ((S[2]) << (64 - (28)))) ^ (((S[2]) >> (34)) | ((S[2]) << (64 - (34)))) ^ (((S[2]) >> (39)) | ((S[2]) << (64 - (39))))) + (((S[2] | S[3]) & S[4]) | (S[2] & S[3])); S[5] += t0; S[1] = t0 + t1;;
         t0 = S[0] + ((((S[5]) >> (14)) | ((S[5]) << (64 - (14)))) ^ (((S[5]) >> (18)) | ((S[5]) << (64 - (18)))) ^ (((S[5]) >> (41)) | ((S[5]) << (64 - (41))))) + (S[7] ^ (S[5] & (S[6] ^ S[7]))) + K[i+7] + W[i+7]; t1 = ((((S[1]) >> (28)) | ((S[1]) << (64 - (28)))) ^ (((S[1]) >> (34)) | ((S[1]) << (64 - (34)))) ^ (((S[1]) >> (39)) | ((S[1]) << (64 - (39))))) + (((S[1] | S[2]) & S[3]) | (S[1] & S[2])); S[4] += t0; S[0] = t0 + t1;;
     }

    for( i=0; i<8; i++ )
    {
        Context->state[i] = Context->state[i] + S[i];
    }
}
void
    Sha512Initialise
    (
        Sha512Context* Context
    )
{
    Context->curlen = 0;
    Context->length = 0;
    Context->state[0] = 0x6a09e667f3bcc908ULL;
    Context->state[1] = 0xbb67ae8584caa73bULL;
    Context->state[2] = 0x3c6ef372fe94f82bULL;
    Context->state[3] = 0xa54ff53a5f1d36f1ULL;
    Context->state[4] = 0x510e527fade682d1ULL;
    Context->state[5] = 0x9b05688c2b3e6c1fULL;
    Context->state[6] = 0x1f83d9abfb41bd6bULL;
    Context->state[7] = 0x5be0cd19137e2179ULL;
}

void
    Sha512Update
    (
        Sha512Context* Context,
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
        if( Context->curlen == 0 && BufferSize >= 128 )
        {
           TransformFunction( Context, (uint8_t *)Buffer );
           Context->length += 128 * 8;
           Buffer = (uint8_t*)Buffer + 128;
           BufferSize -= 128;
        }
        else
        {
           n = ( ((BufferSize)<((128 - Context->curlen)))?(BufferSize):((128 - Context->curlen)) );
           memcpy( Context->buf + Context->curlen, Buffer, (size_t)n );
           Context->curlen += n;
           Buffer = (uint8_t*)Buffer + n;
           BufferSize -= n;
           if( Context->curlen == 128 )
           {
              TransformFunction( Context, Context->buf );
              Context->length += 8*128;
              Context->curlen = 0;
           }
       }
    }
}

void
    Sha512Finalise
    (
        Sha512Context* Context,
        SHA512_HASH* Digest
    )
{
    int i;

    if( Context->curlen >= sizeof(Context->buf) )
    {
       return;
    }

    Context->length += Context->curlen * 8ULL;

    Context->buf[Context->curlen++] = (uint8_t)0x80;

    if( Context->curlen > 112 )
    {
        while( Context->curlen < 128 )
        {
            Context->buf[Context->curlen++] = (uint8_t)0;
        }
        TransformFunction( Context, Context->buf );
        Context->curlen = 0;
    }

    while( Context->curlen < 120 )
    {
        Context->buf[Context->curlen++] = (uint8_t)0;
    }

    { (Context->buf+120)[0] = (uint8_t)(((Context->length)>>56)&255); (Context->buf+120)[1] = (uint8_t)(((Context->length)>>48)&255); (Context->buf+120)[2] = (uint8_t)(((Context->length)>>40)&255); (Context->buf+120)[3] = (uint8_t)(((Context->length)>>32)&255); (Context->buf+120)[4] = (uint8_t)(((Context->length)>>24)&255); (Context->buf+120)[5] = (uint8_t)(((Context->length)>>16)&255); (Context->buf+120)[6] = (uint8_t)(((Context->length)>>8)&255); (Context->buf+120)[7] = (uint8_t)((Context->length)&255); };
    TransformFunction( Context, Context->buf );

    for( i=0; i<8; i++ )
    {
        { (Digest->bytes+(8*i))[0] = (uint8_t)(((Context->state[i])>>56)&255); (Digest->bytes+(8*i))[1] = (uint8_t)(((Context->state[i])>>48)&255); (Digest->bytes+(8*i))[2] = (uint8_t)(((Context->state[i])>>40)&255); (Digest->bytes+(8*i))[3] = (uint8_t)(((Context->state[i])>>32)&255); (Digest->bytes+(8*i))[4] = (uint8_t)(((Context->state[i])>>24)&255); (Digest->bytes+(8*i))[5] = (uint8_t)(((Context->state[i])>>16)&255); (Digest->bytes+(8*i))[6] = (uint8_t)(((Context->state[i])>>8)&255); (Digest->bytes+(8*i))[7] = (uint8_t)((Context->state[i])&255); };
    }
}

void
    Sha512Calculate
    (
        void const* Buffer,
        uint32_t BufferSize,
        SHA512_HASH* Digest
    )
{
    Sha512Context context;

    Sha512Initialise( &context );
    Sha512Update( &context, Buffer, BufferSize );
    Sha512Finalise( &context, Digest );
}