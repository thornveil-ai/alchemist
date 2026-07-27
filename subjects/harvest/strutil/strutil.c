#include <stdint.h>
int str_len(const char* s, int n){ int i=0; while(i<n && s[i]) i++; return i; }
int count_byte(const char* d, int n, int target){ int c=0; for(int i=0;i<n;i++) if((unsigned char)d[i]==(unsigned char)target) c++; return c; }
int all_ascii(const char* d, int n){ for(int i=0;i<n;i++) if((unsigned char)d[i]>127) return 0; return 1; }
int32_t atoi_simple(const char* d, int n){ int i=0,sign=1; int32_t v=0; if(i<n&&d[i]=='-'){sign=-1;i++;} else if(i<n&&d[i]=='+')i++; while(i<n && d[i]>='0'&&d[i]<='9'){ v=v*10+(d[i]-'0'); i++; } return v*sign; }
int is_palindrome(const char* d, int n){ int i=0,j=n-1; while(i<j){ if(d[i]!=d[j])return 0; i++; j--; } return 1; }
uint32_t sum_bytes(const char* d, int n){ uint32_t s=0; for(int i=0;i<n;i++) s+=(unsigned char)d[i]; return s; }
int count_words(const char* d, int n){ int c=0,in=0; for(int i=0;i<n;i++){ int sp=(d[i]==' '||d[i]=='\t'||d[i]=='\n'); if(!sp&&!in){c++;in=1;} else if(sp) in=0; } return c; }
int hexval(int ch){ if(ch>='0'&&ch<='9')return ch-'0'; if(ch>='a'&&ch<='f')return ch-'a'+10; if(ch>='A'&&ch<='F')return ch-'A'+10; return -1; }
int to_upper_count(const char* d, int n){ int c=0; for(int i=0;i<n;i++) if(d[i]>='a'&&d[i]<='z') c++; return c; }
