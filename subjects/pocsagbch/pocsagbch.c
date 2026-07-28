#include <stdint.h>
uint32_t poc_bch_encode(uint32_t cw){
    cw &= 0xFFFFF800u; uint32_t reg=cw; int bit;
    for(bit=31;bit>=11;--bit) if(reg&(1u<<bit)) reg^=(0x769u<<(bit-10));
    cw|=(reg&0x000007FEu);
    uint32_t p=cw; p^=p>>16;p^=p>>8;p^=p>>4;p^=p>>2;p^=p>>1; cw|=(p&1u);
    return cw;
}
/* BCH syndrome over the 31 code bits (bits 31..1); 0 => no detectable error. */
uint32_t poc_bch_syndrome(uint32_t cw){
    uint32_t reg = cw & 0xFFFFF800u; int bit;
    for(bit=31;bit>=11;--bit) if(reg&(1u<<bit)) reg^=(0x769u<<(bit-10));
    return ((cw & 0x000007FEu) ^ (reg & 0x000007FEu));
}
/* Overall even parity of the 32-bit codeword (0 => even parity holds). */
uint32_t poc_parity(uint32_t cw){
    uint32_t p=cw; p^=p>>16;p^=p>>8;p^=p>>4;p^=p>>2;p^=p>>1; return p&1u;
}
