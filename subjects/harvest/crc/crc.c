#include <stdint.h>
/* bit-by-bit CRCs — many standard variants (poly/init/refin/refout differ). */
uint8_t crc8(const uint8_t* d, int n){ uint8_t c=0; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&0x80)?(uint8_t)((c<<1)^0x07):(uint8_t)(c<<1);} return c; }
uint8_t crc8_ccitt(const uint8_t* d, int n){ uint8_t c=0; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&0x80)?(uint8_t)((c<<1)^0x07):(uint8_t)(c<<1);} return c; }
uint8_t crc8_maxim(const uint8_t* d, int n){ uint8_t c=0; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&1)?(uint8_t)((c>>1)^0x8C):(uint8_t)(c>>1);} return c; }
uint16_t crc16_ccitt_false(const uint8_t* d, int n){ uint16_t c=0xFFFF; for(int i=0;i<n;i++){ c^=(uint16_t)d[i]<<8; for(int b=0;b<8;b++) c=(c&0x8000)?(uint16_t)((c<<1)^0x1021):(uint16_t)(c<<1);} return c; }
uint16_t crc16_xmodem(const uint8_t* d, int n){ uint16_t c=0; for(int i=0;i<n;i++){ c^=(uint16_t)d[i]<<8; for(int b=0;b<8;b++) c=(c&0x8000)?(uint16_t)((c<<1)^0x1021):(uint16_t)(c<<1);} return c; }
uint16_t crc16_kermit(const uint8_t* d, int n){ uint16_t c=0; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&1)?(uint16_t)((c>>1)^0x8408):(uint16_t)(c>>1);} return c; }
uint16_t crc16_modbus(const uint8_t* d, int n){ uint16_t c=0xFFFF; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&1)?(uint16_t)((c>>1)^0xA001):(uint16_t)(c>>1);} return c; }
uint16_t crc16_ibm(const uint8_t* d, int n){ uint16_t c=0; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&1)?(uint16_t)((c>>1)^0xA001):(uint16_t)(c>>1);} return c; }
uint16_t crc16_dnp(const uint8_t* d, int n){ uint16_t c=0; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&1)?(uint16_t)((c>>1)^0xA6BC):(uint16_t)(c>>1);} return (uint16_t)~c; }
uint32_t crc32(const uint8_t* d, int n){ uint32_t c=0xFFFFFFFFu; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&1)?((c>>1)^0xEDB88320u):(c>>1);} return ~c; }
uint32_t crc32c(const uint8_t* d, int n){ uint32_t c=0xFFFFFFFFu; for(int i=0;i<n;i++){ c^=d[i]; for(int b=0;b<8;b++) c=(c&1)?((c>>1)^0x82F63B78u):(c>>1);} return ~c; }
uint32_t crc32_bzip2(const uint8_t* d, int n){ uint32_t c=0xFFFFFFFFu; for(int i=0;i<n;i++){ c^=(uint32_t)d[i]<<24; for(int b=0;b<8;b++) c=(c&0x80000000u)?((c<<1)^0x04C11DB7u):(c<<1);} return ~c; }
