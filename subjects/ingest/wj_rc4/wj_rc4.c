#include <stdint.h>
#include <stddef.h>
#include <string.h>

       

typedef struct
{
    uint32_t i;
    uint32_t j;
    uint8_t S[256];
} Rc4Context;
int
    Rc4Initialise
    (
        Rc4Context* Context,
        void const* Key,
        uint32_t KeySize,
        uint32_t DropN
    );

void
    Rc4Output
    (
        Rc4Context* Context,
        void* Buffer,
        uint32_t Size
    );

void
    Rc4Xor
    (
        Rc4Context* Context,
        void const* InBuffer,
        void* OutBuffer,
        uint32_t Size
    );
int
    Rc4XorWithKey
    (
        uint8_t const* Key,
        uint32_t KeySize,
        uint32_t DropN,
        void const* InBuffer,
        void* OutBuffer,
        uint32_t BufferSize
    );

int
    Rc4Initialise
    (
        Rc4Context* Context,
        void const* Key,
        uint32_t KeySize,
        uint32_t DropN
    )
{
    uint32_t i;
    uint32_t j;
    uint32_t n;

    if( 0 == KeySize )
    {

        return -1;
    }

    for( i=0; i<256; i++ )
    {
        Context->S[i] = (uint8_t)i;
    }

    j = 0;
    for( i=0; i<256; i++ )
    {
        j = ( j + Context->S[i] + ((uint8_t*)Key)[i % KeySize] ) % 256;
        { uint8_t temp = Context->S[i]; Context->S[i] = Context->S[j]; Context->S[j] = temp; };
    }

    i = 0;
    j = 0;

    for( n=0; n<DropN; n++ )
    {
        i = ( i + 1 ) % 256;
        j = ( j + Context->S[i] ) % 256;
        { uint8_t temp = Context->S[i]; Context->S[i] = Context->S[j]; Context->S[j] = temp; };
    }

    Context->i = i;
    Context->j = j;

    return 0;
}

void
    Rc4Output
    (
        Rc4Context* Context,
        void* Buffer,
        uint32_t Size
    )
{
    uint32_t n;

    for( n=0; n<Size; n++ )
    {
        Context->i = ( Context->i + 1 ) % 256;
        Context->j = ( Context->j + Context->S[Context->i] ) % 256;
        { uint8_t temp = Context->S[Context->i]; Context->S[Context->i] = Context->S[Context->j]; Context->S[Context->j] = temp; };

        ((uint8_t*)Buffer)[n] = Context->S[ (Context->S[Context->i] + Context->S[Context->j]) % 256 ];
    }
}

void
    Rc4Xor
    (
        Rc4Context* Context,
        void const* InBuffer,
        void* OutBuffer,
        uint32_t Size
    )
{
    uint32_t n;

    for( n=0; n<Size; n++ )
    {
        Context->i = ( Context->i + 1 ) % 256;
        Context->j = ( Context->j + Context->S[Context->i] ) % 256;
        { uint8_t temp = Context->S[Context->i]; Context->S[Context->i] = Context->S[Context->j]; Context->S[Context->j] = temp; };

        ((uint8_t*)OutBuffer)[n] = ((uint8_t*)InBuffer)[n]
            ^ ( Context->S[ (Context->S[Context->i] + Context->S[Context->j]) % 256 ] );
    }
}
int
    Rc4XorWithKey
    (
        uint8_t const* Key,
        uint32_t KeySize,
        uint32_t DropN,
        void const* InBuffer,
        void* OutBuffer,
        uint32_t BufferSize
    )
{
    Rc4Context context;

    if( 0 != Rc4Initialise( &context, Key, KeySize, DropN ) )
    {
        return -1;
    }
    Rc4Xor( &context, InBuffer, OutBuffer, BufferSize );
    return 0;
}