#include <stdint.h>
uint32_t crc32_step(uint32_t crc, uint8_t byte){ crc^=byte; for(int i=0;i<8;i++) crc=(crc&1)?((crc>>1)^0xEDB88320u):(crc>>1); return crc; }
uint32_t crc32c_step(uint32_t crc, uint8_t byte){ crc^=byte; for(int i=0;i<8;i++) crc=(crc&1)?((crc>>1)^0x82F63B78u):(crc>>1); return crc; }
uint16_t crc16_ccitt_step(uint16_t crc, uint8_t byte){ crc^=(uint16_t)byte<<8; for(int i=0;i<8;i++) crc=(crc&0x8000)?((crc<<1)^0x1021):(crc<<1); return crc; }
uint16_t crc16_ibm_step(uint16_t crc, uint8_t byte){ crc^=byte; for(int i=0;i<8;i++) crc=(crc&1)?((crc>>1)^0xA001):(crc>>1); return crc; }
uint8_t crc8_step(uint8_t crc, uint8_t byte){ crc^=byte; for(int i=0;i<8;i++) crc=(crc&0x80)?((crc<<1)^0x07):(crc<<1); return crc; }
uint8_t crc8_dallas_step(uint8_t crc, uint8_t byte){ crc^=byte; for(int i=0;i<8;i++) crc=(crc&1)?((crc>>1)^0x8C):(crc>>1); return crc; }
uint32_t adler_step(uint32_t adler, uint8_t byte){ uint32_t a=adler&0xFFFF,b=(adler>>16)&0xFFFF; a=(a+byte)%65521; b=(b+a)%65521; return (b<<16)|a; }
uint16_t fletcher16_step(uint16_t state, uint8_t byte){ uint16_t s1=state&0xFF,s2=(state>>8)&0xFF; s1=(s1+byte)%255; s2=(s2+s1)%255; return (uint16_t)((s2<<8)|s1); }
uint32_t xor_step(uint32_t acc, uint8_t byte){ return acc^byte; }
uint32_t sum_step(uint32_t acc, uint8_t byte){ return acc+byte; }
