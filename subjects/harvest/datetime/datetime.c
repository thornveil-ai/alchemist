#include <stdint.h>
int is_leap_year(int y){ return (y%4==0&&y%100!=0)||(y%400==0); }
int days_in_month(int y, int m){ if(m<1||m>12)return 0; int d[]={31,28,31,30,31,30,31,31,30,31,30,31}; if(m==2&&((y%4==0&&y%100!=0)||y%400==0))return 29; return d[m-1]; }
int day_of_year(int y, int m, int d){ int cum[]={0,31,59,90,120,151,181,212,243,273,304,334}; int doy=cum[m-1]+d; if(m>2&&((y%4==0&&y%100!=0)||y%400==0))doy++; return doy; }
int zeller_weekday(int y, int m, int d){ if(m<3){m+=12;y--;} int k=y%100,j=y/100; int h=(d+13*(m+1)/5+k+k/4+j/4+5*j)%7; return (h+6)%7; }
int32_t days_from_civil(int y, int m, int d){ y-=m<=2; int era=(y>=0?y:y-399)/400; int yoe=y-era*400; int doy=(153*(m+(m>2?-3:9))+2)/5+d-1; int doe=yoe*365+yoe/4-yoe/100+doy; return era*146097+doe-719468; }
int hms_to_secs(int h, int m, int s){ return h*3600+m*60+s; }
int secs_to_hour(int secs){ return (secs/3600)%24; }
int secs_to_min(int secs){ return (secs/60)%60; }
int quarter_of_month(int m){ return (m-1)/3+1; }
int weekday_of_days(int32_t days){ return (int)(((days%7)+7+4)%7); }
