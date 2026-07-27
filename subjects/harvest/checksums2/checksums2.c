#include <stdint.h>
uint16_t fletcher16(const uint8_t* d, int n){ uint16_t s1=0,s2=0; for(int i=0;i<n;i++){ s1=(s1+d[i])%255; s2=(s2+s1)%255; } return (uint16_t)((s2<<8)|s1); }
uint32_t fletcher32(const uint8_t* d, int n){ uint32_t s1=0xffff,s2=0xffff; int i=0; while(i<n){ int block=(n-i<359)?(n-i):359; for(int j=0;j<block;j++){ s1+=d[i++]; s2+=s1; } s1=(s1&0xffff)+(s1>>16); s2=(s2&0xffff)+(s2>>16); } s1=(s1&0xffff)+(s1>>16); s2=(s2&0xffff)+(s2>>16); return (s2<<16)|s1; }
uint32_t adler32c(const uint8_t* d, int n){ uint32_t a=1,b=0; for(int i=0;i<n;i++){ a=(a+d[i])%65521; b=(b+a)%65521; } return (b<<16)|a; }
uint16_t internet_checksum(const uint8_t* d, int n){ uint32_t sum=0; int i=0; while(i+1<n){ sum+=(d[i]<<8)|d[i+1]; i+=2; } if(i<n)sum+=d[i]<<8; while(sum>>16)sum=(sum&0xffff)+(sum>>16); return (uint16_t)(~sum); }
uint8_t xor_checksum(const uint8_t* d, int n){ uint8_t c=0; for(int i=0;i<n;i++)c^=d[i]; return c; }
uint8_t lrc_checksum(const uint8_t* d, int n){ uint8_t s=0; for(int i=0;i<n;i++)s+=d[i]; return (uint8_t)(-(int8_t)s); }
uint32_t bsd_checksum(const uint8_t* d, int n){ uint32_t c=0; for(int i=0;i<n;i++){ c=(c>>1)+((c&1)<<15); c+=d[i]; c&=0xffff; } return c; }
uint32_t sysv_checksum(const uint8_t* d, int n){ uint32_t s=0; for(int i=0;i<n;i++)s+=d[i]; uint32_t r=(s&0xffff)+((s&0xffffffff)>>16); return (r&0xffff)+(r>>16); }
int luhn_check(const uint8_t* d, int n){ int sum=0,alt=0; for(int i=n-1;i>=0;i--){ int x=d[i]-'0'; if(x<0||x>9)return -1; if(alt){ x*=2; if(x>9)x-=9; } sum+=x; alt^=1; } return sum%10==0; }
uint8_t crc8_maxim(const uint8_t* d, int n){ uint8_t crc=0; for(int i=0;i<n;i++){ crc^=d[i]; for(int b=0;b<8;b++) crc=(crc&1)?((crc>>1)^0x8C):(crc>>1); } return crc; }
