#include <stdint.h>
int ch_to_upper(int c){ return (c>='a'&&c<='z')?c-32:c; }
int ch_to_lower(int c){ return (c>='A'&&c<='Z')?c+32:c; }
int ch_is_alpha(int c){ return (c>='a'&&c<='z')||(c>='A'&&c<='Z'); }
int ch_is_digit(int c){ return c>='0'&&c<='9'; }
int ch_is_alnum(int c){ return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9'); }
int ch_is_space(int c){ return c==' '||c=='\t'||c=='\n'||c=='\r'||c=='\v'||c=='\f'; }
int ch_is_punct(int c){ return c>=33&&c<=126&&!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')); }
int ch_swap_case(int c){ if(c>='a'&&c<='z')return c-32; if(c>='A'&&c<='Z')return c+32; return c; }
int ch_hex_val(int c){ if(c>='0'&&c<='9')return c-'0'; if(c>='a'&&c<='f')return c-'a'+10; if(c>='A'&&c<='F')return c-'A'+10; return -1; }
int ch_caesar(int c, int shift){ if(c>='a'&&c<='z')return 'a'+((c-'a'+shift)%26+26)%26; if(c>='A'&&c<='Z')return 'A'+((c-'A'+shift)%26+26)%26; return c; }
int ch_rot13(int c){ if(c>='a'&&c<='z')return 'a'+(c-'a'+13)%26; if(c>='A'&&c<='Z')return 'A'+(c-'A'+13)%26; return c; }
int ch_digit_val(int c, int base){ int v=-1; if(c>='0'&&c<='9')v=c-'0'; else if(c>='a'&&c<='z')v=c-'a'+10; else if(c>='A'&&c<='Z')v=c-'A'+10; return (v>=0&&v<base)?v:-1; }
