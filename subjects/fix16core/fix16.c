#include <stdint.h>
#include <stddef.h>



typedef int32_t fix16_t;

static const fix16_t FOUR_DIV_PI = 0x145F3;
static const fix16_t _FOUR_DIV_PI2 = 0xFFFF9840;
static const fix16_t X4_CORRECTION_COMPONENT = 0x399A;
static const fix16_t PI_DIV_4 = 0x0000C90F;
static const fix16_t THREE_PI_DIV_4 = 0x00025B2F;

static const fix16_t fix16_maximum = 0x7FFFFFFF;
static const fix16_t fix16_minimum = 0x80000000;
static const fix16_t fix16_overflow = 0x80000000;

static const fix16_t fix16_pi = 205887;
static const fix16_t fix16_e = 178145;
static const fix16_t fix16_one = 0x00010000;
static const fix16_t fix16_eps = 1;








static inline int fix16_to_int(fix16_t a)
{



 int result = a / fix16_one;
 fix16_t remainder = a % fix16_one;
 if (remainder >= (fix16_one >> 1))
  return result + 1;
 if (remainder <= -(fix16_one >> 1))
  return result - 1;
 return result;

}

static inline fix16_t fix16_from_float(float a)
{
 float temp = a * fix16_one;

 temp += (temp >= 0) ? 0.5f : -0.5f;

 return (fix16_t)temp;
}

static inline fix16_t fix16_from_dbl(double a)
{
 double temp = a * fix16_one;


 temp += (double)((temp >= 0) ? 0.5f : -0.5f);

 return (fix16_t)temp;
}






extern fix16_t fix16_add(fix16_t a, fix16_t b) __attribute__((leaf, nothrow, const));
extern fix16_t fix16_sub(fix16_t a, fix16_t b) __attribute__((leaf, nothrow, const));


extern fix16_t fix16_sadd(fix16_t a, fix16_t b) __attribute__((leaf, nothrow, const));
extern fix16_t fix16_ssub(fix16_t a, fix16_t b) __attribute__((leaf, nothrow, const));





extern fix16_t fix16_mul(fix16_t inArg0, fix16_t inArg1) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_div(fix16_t inArg0, fix16_t inArg1) __attribute__((leaf, nothrow, const));




extern fix16_t fix16_smul(fix16_t inArg0, fix16_t inArg1) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_sdiv(fix16_t inArg0, fix16_t inArg1) __attribute__((leaf, nothrow, const));




extern fix16_t fix16_mod(fix16_t x, fix16_t y) __attribute__((leaf, nothrow, const));





extern fix16_t fix16_lerp8(fix16_t inArg0, fix16_t inArg1, uint8_t inFract) __attribute__((leaf, nothrow, const));
extern fix16_t fix16_lerp16(fix16_t inArg0, fix16_t inArg1, uint16_t inFract) __attribute__((leaf, nothrow, const));
extern fix16_t fix16_lerp32(fix16_t inArg0, fix16_t inArg1, uint32_t inFract) __attribute__((leaf, nothrow, const));





extern fix16_t fix16_sin_parabola(fix16_t inAngle) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_sin(fix16_t inAngle) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_cos(fix16_t inAngle) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_tan(fix16_t inAngle) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_asin(fix16_t inValue) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_acos(fix16_t inValue) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_atan(fix16_t inValue) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_atan2(fix16_t inY, fix16_t inX) __attribute__((leaf, nothrow, const));

static const fix16_t fix16_rad_to_deg_mult = 3754936;


static const fix16_t fix16_deg_to_rad_mult = 1144;






extern fix16_t fix16_sqrt(fix16_t inValue) __attribute__((leaf, nothrow, const));







extern fix16_t fix16_exp(fix16_t inValue) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_log(fix16_t inValue) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_log2(fix16_t x) __attribute__((leaf, nothrow, const));



extern fix16_t fix16_slog2(fix16_t x) __attribute__((leaf, nothrow, const));




extern void fix16_to_str(fix16_t value, char *buf, int decimals);





extern fix16_t fix16_from_str(const char *buf);

static inline uint32_t fix_abs(fix16_t in)
{
    if(in == fix16_minimum)
    {


        return 0x80000000;
    }
    else
    {
        return ((in >= 0)?(in):(-in));
    }
}



























fix16_t fix16_add(fix16_t a, fix16_t b)
{


    uint32_t _a = a;
    uint32_t _b = b;
 uint32_t sum = _a + _b;



 if (!((_a ^ _b) & 0x80000000) && ((_a ^ sum) & 0x80000000))
  return fix16_overflow;

 return sum;
}

fix16_t fix16_sub(fix16_t a, fix16_t b)
{
    uint32_t _a = a;
    uint32_t _b = b;
 uint32_t diff = _a - _b;



 if (((_a ^ _b) & 0x80000000) && ((_a ^ diff) & 0x80000000))
  return fix16_overflow;

 return diff;
}


fix16_t fix16_sadd(fix16_t a, fix16_t b)
{
 fix16_t result = fix16_add(a, b);

 if (result == fix16_overflow)
  return (a >= 0) ? fix16_maximum : fix16_minimum;

 return result;
}

fix16_t fix16_ssub(fix16_t a, fix16_t b)
{
 fix16_t result = fix16_sub(a, b);

 if (result == fix16_overflow)
  return (a >= 0) ? fix16_maximum : fix16_minimum;

 return result;
}
fix16_t fix16_mul(fix16_t inArg0, fix16_t inArg1)
{
 int64_t product = (int64_t)inArg0 * inArg1;



 uint32_t upper = (product >> 47);


 if (product < 0)
 {

  if (~upper)
    return fix16_overflow;




  product--;

 }
 else
 {

  if (upper)
    return fix16_overflow;

 }




 fix16_t result = product >> 16;
 result += (product & 0x8000) >> 15;

 return result;

}
fix16_t fix16_smul(fix16_t inArg0, fix16_t inArg1)
{
 fix16_t result = fix16_mul(inArg0, inArg1);

 if (result == fix16_overflow)
 {
  if ((inArg0 >= 0) == (inArg1 >= 0))
   return fix16_maximum;
  else
   return fix16_minimum;
 }

 return result;
}
fix16_t fix16_div(fix16_t a, fix16_t b)
{



 if (b == 0)
   return fix16_minimum;

    uint32_t remainder = fix_abs(a);
    uint32_t divider = fix_abs(b);
    uint64_t quotient = 0;
    int bit_pos = 17;




 if (divider & 0xFFF00000)
 {
  uint32_t shifted_div = ((divider >> 17) + 1);
        quotient = remainder / shifted_div;
        uint64_t tmp = ((uint64_t)quotient * (uint64_t)divider) >> 17;
        remainder -= (uint32_t)(tmp);
    }


 while (!(divider & 0xF) && bit_pos >= 4)
 {
  divider >>= 4;
  bit_pos -= 4;
 }

 while (remainder && bit_pos >= 0)
 {

  int shift = (__builtin_clzl(remainder) - (8 * sizeof(long) - 32));
  if (shift > bit_pos) shift = bit_pos;
  remainder <<= shift;
  bit_pos -= shift;

  uint32_t div = remainder / divider;
        remainder = remainder % divider;
        quotient += (uint64_t)div << bit_pos;


  if (div & ~(0xFFFFFFFF >> bit_pos))
    return fix16_overflow;


  remainder <<= 1;
  bit_pos--;
 }



 quotient++;


 fix16_t result = quotient >> 1;


 if ((a ^ b) & 0x80000000)
 {

  if (result == fix16_minimum)
    return fix16_overflow;


  result = -result;
 }

 return result;
}
fix16_t fix16_sdiv(fix16_t inArg0, fix16_t inArg1)
{
 fix16_t result = fix16_div(inArg0, inArg1);

 if (result == fix16_overflow)
 {
  if ((inArg0 >= 0) == (inArg1 >= 0))
   return fix16_maximum;
  else
   return fix16_minimum;
 }

 return result;
}


fix16_t fix16_mod(fix16_t x, fix16_t y)
{
  x %= y;


 return x;
}

fix16_t fix16_lerp8(fix16_t inArg0, fix16_t inArg1, uint8_t inFract)
{
 int64_t tempOut = (((int64_t)(inArg0) * ((((int32_t)1 << 8) - inFract))));
 tempOut = (((tempOut) + ((((int64_t)(inArg1) * (inFract))))));
 tempOut = (((-8) < 0 ? ((tempOut) >> -(-8)) : ((tempOut) << (-8))));
 return (fix16_t)(((tempOut) & ((1ULL << 32) - 1)));
}

fix16_t fix16_lerp16(fix16_t inArg0, fix16_t inArg1, uint16_t inFract)
{
 int64_t tempOut = (((int64_t)(inArg0) * ((((int32_t)1 << 16) - inFract))));
 tempOut = (((tempOut) + ((((int64_t)(inArg1) * (inFract))))));
 tempOut = (((-16) < 0 ? ((tempOut) >> -(-16)) : ((tempOut) << (-16))));
 return (fix16_t)(((tempOut) & ((1ULL << 32) - 1)));
}

fix16_t fix16_lerp32(fix16_t inArg0, fix16_t inArg1, uint32_t inFract)
{
 if(inFract == 0)
  return inArg0;
 int64_t inFract64 = ((((int64_t)(0) << 32) | (inFract)));
 int64_t subbed = (((((((int64_t)(1) << 32) | (0)))) - (inFract64)));
 int64_t tempOut = (((subbed) * (inArg0)));
 tempOut = (((tempOut) + ((((inFract64) * (inArg1))))));
 return (((tempOut) >> 32));
}