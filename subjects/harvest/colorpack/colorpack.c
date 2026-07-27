#include <stdint.h>
uint16_t rgb565_pack(uint8_t r, uint8_t g, uint8_t b){ return (uint16_t)(((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)); }
uint8_t rgb565_red(uint16_t c){ return (uint8_t)(((c>>11)&0x1F)*255/31); }
uint8_t rgb565_green(uint16_t c){ return (uint8_t)(((c>>5)&0x3F)*255/63); }
uint8_t rgb565_blue(uint16_t c){ return (uint8_t)((c&0x1F)*255/31); }
uint32_t argb_pack(uint8_t a, uint8_t r, uint8_t g, uint8_t b){ return ((uint32_t)a<<24)|((uint32_t)r<<16)|((uint32_t)g<<8)|b; }
uint8_t luminance601(uint8_t r, uint8_t g, uint8_t b){ return (uint8_t)(((uint32_t)r*299+(uint32_t)g*587+(uint32_t)b*114)/1000); }
uint8_t luminance709(uint8_t r, uint8_t g, uint8_t b){ return (uint8_t)(((uint32_t)r*2126+(uint32_t)g*7152+(uint32_t)b*722)/10000); }
uint8_t channel_blend(uint8_t a, uint8_t b, uint8_t t){ return (uint8_t)(((uint32_t)a*(255-t)+(uint32_t)b*t)/255); }
uint8_t channel_multiply(uint8_t a, uint8_t b){ return (uint8_t)(((uint32_t)a*b+127)/255); }
uint8_t channel_screen(uint8_t a, uint8_t b){ return (uint8_t)(255-((uint32_t)(255-a)*(255-b))/255); }
uint32_t rgb_to_grayscale(uint32_t rgb){ uint8_t r=(rgb>>16)&0xFF,g=(rgb>>8)&0xFF,b=rgb&0xFF; uint8_t y=(uint8_t)(((uint32_t)r*77+(uint32_t)g*150+(uint32_t)b*29)>>8); return ((uint32_t)y<<16)|((uint32_t)y<<8)|y; }
