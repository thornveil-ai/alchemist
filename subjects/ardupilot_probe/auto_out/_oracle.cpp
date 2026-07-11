#include <cstdio>
#include <cstring>
#include <cstdint>
#include "crc.h"
int main(int argc, char** argv){
  const char* n = argv[1]; static uint8_t in[65536];
  uint32_t l = (uint32_t)fread(in, 1, sizeof(in), stdin);
    if(!strcmp(n,"crc_crc8")) { printf("%llu",(unsigned long long)crc_crc8(in, l)); return 0; }
    if(!strcmp(n,"crc8_generic")) { printf("%llu",(unsigned long long)crc8_generic(in, l, 0, 0)); return 0; }
    if(!strcmp(n,"crc8_dvb_s2_update")) { printf("%llu",(unsigned long long)crc8_dvb_s2_update(0, in, l)); return 0; }
    if(!strcmp(n,"crc8_dvb_update")) { printf("%llu",(unsigned long long)crc8_dvb_update(0, in, l)); return 0; }
    if(!strcmp(n,"crc8_maxim")) { printf("%llu",(unsigned long long)crc8_maxim(in, l)); return 0; }
    if(!strcmp(n,"crc8_sae")) { printf("%llu",(unsigned long long)crc8_sae(in, l)); return 0; }
    if(!strcmp(n,"crc8_rds02uf")) { printf("%llu",(unsigned long long)crc8_rds02uf(in, l)); return 0; }
    if(!strcmp(n,"crc_xor_of_bytes")) { printf("%llu",(unsigned long long)crc_xor_of_bytes(in, l)); return 0; }
    if(!strcmp(n,"crc_xmodem")) { printf("%llu",(unsigned long long)crc_xmodem(in, l)); return 0; }
    if(!strcmp(n,"crc_crc32")) { printf("%llu",(unsigned long long)crc_crc32(0, in, l)); return 0; }
    if(!strcmp(n,"crc32_small")) { printf("%llu",(unsigned long long)crc32_small(0, in, l)); return 0; }
    if(!strcmp(n,"crc16_ccitt")) { printf("%llu",(unsigned long long)crc16_ccitt(in, l, 0)); return 0; }
    if(!strcmp(n,"crc16_ccitt_r")) { printf("%llu",(unsigned long long)crc16_ccitt_r(in, l, 0, 0)); return 0; }
    if(!strcmp(n,"crc16_ccitt_GDL90")) { printf("%llu",(unsigned long long)crc16_ccitt_GDL90(in, l, 0)); return 0; }
    if(!strcmp(n,"calc_crc_modbus")) { printf("%llu",(unsigned long long)calc_crc_modbus(in, l)); return 0; }
    if(!strcmp(n,"crc_fletcher16")) { printf("%llu",(unsigned long long)crc_fletcher16(in, l)); return 0; }
    if(!strcmp(n,"crc_crc24")) { printf("%llu",(unsigned long long)crc_crc24(in, l)); return 0; }
    if(!strcmp(n,"crc_sum8_with_carry")) { printf("%llu",(unsigned long long)crc_sum8_with_carry(in, l)); return 0; }
    if(!strcmp(n,"crc_sum_of_bytes_16")) { printf("%llu",(unsigned long long)crc_sum_of_bytes_16(in, l)); return 0; }
    if(!strcmp(n,"crc_sum_of_bytes")) { printf("%llu",(unsigned long long)crc_sum_of_bytes(in, l)); return 0; }
  return 1;
}
