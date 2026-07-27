#include <stdint.h>
uint32_t sum_u8(const uint8_t* d, int n){ uint32_t s=0; for(int i=0;i<n;i++)s+=d[i]; return s; }
uint8_t max_u8(const uint8_t* d, int n){ if(n<=0)return 0; uint8_t m=d[0]; for(int i=1;i<n;i++) if(d[i]>m)m=d[i]; return m; }
uint8_t min_u8(const uint8_t* d, int n){ if(n<=0)return 0; uint8_t m=d[0]; for(int i=1;i<n;i++) if(d[i]<m)m=d[i]; return m; }
int argmax_u8(const uint8_t* d, int n){ if(n<=0)return -1; int mi=0; for(int i=1;i<n;i++) if(d[i]>d[mi])mi=i; return mi; }
uint32_t count_nonzero(const uint8_t* d, int n){ uint32_t c=0; for(int i=0;i<n;i++) if(d[i])c++; return c; }
uint32_t popcount_buf(const uint8_t* d, int n){ uint32_t c=0; for(int i=0;i<n;i++){ uint8_t x=d[i]; while(x){c+=x&1;x>>=1;} } return c; }
uint32_t dot_u8(const uint8_t* d, int n){ uint32_t s=0; for(int i=0;i+1<n;i+=2) s+=(uint32_t)d[i]*d[i+1]; return s; }
uint32_t max_run_equal(const uint8_t* d, int n){ if(n<=0)return 0; uint32_t best=1,cur=1; for(int i=1;i<n;i++){ if(d[i]==d[i-1]){cur++; if(cur>best)best=cur;} else cur=1; } return best; }
uint32_t range_u8(const uint8_t* d, int n){ if(n<=0)return 0; uint8_t mn=d[0],mx=d[0]; for(int i=1;i<n;i++){ if(d[i]<mn)mn=d[i]; if(d[i]>mx)mx=d[i]; } return (uint32_t)(mx-mn); }
uint32_t checksum_weighted(const uint8_t* d, int n){ uint32_t s=0; for(int i=0;i<n;i++) s+=(uint32_t)(i+1)*d[i]; return s; }
