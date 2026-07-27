#include <stdint.h>
#include <stddef.h>

#ifndef __libfixmath_fix16_h__
#define __libfixmath_fix16_h__

#ifdef __cplusplus
extern "C"
{
#endif

/* These options may let the optimizer to remove some calls to the functions.
 * Refer to http://gcc.gnu.org/onlinedocs/gcc/Function-Attributes.html
 */
#ifndef FIXMATH_FUNC_ATTRS
# ifdef __GNUC__
#   if __GNUC__ > 4 || (__GNUC__ == 4 && __GNUC_MINOR__ > 6)
#     define FIXMATH_FUNC_ATTRS __attribute__((leaf, nothrow, const))
#   else
#     define FIXMATH_FUNC_ATTRS __attribute__((nothrow, const))
#   endif
# else
#   define FIXMATH_FUNC_ATTRS
# endif
#endif

/* Automatically define FIXMATH_NO_HARD_DIVISION to maintain backwards
 * compatibility with usage of FIXMATH_OPTIMIZE_8BIT.
 */
#if defined(FIXMATH_OPTIMIZE_8BIT)
#  define FIXMATH_NO_HARD_DIVISION
#endif

#ifdef __KERNEL__

#else

#endif

typedef int32_t fix16_t;

static const fix16_t FOUR_DIV_PI  = 0x145F3;            /*!< Fix16 value of 4/PI */
static const fix16_t _FOUR_DIV_PI2 = 0xFFFF9840;        /*!< Fix16 value of -4/PI² */
static const fix16_t X4_CORRECTION_COMPONENT = 0x399A; 	/*!< Fix16 value of 0.225 */
static const fix16_t PI_DIV_4 = 0x0000C90F;             /*!< Fix16 value of PI/4 */
static const fix16_t THREE_PI_DIV_4 = 0x00025B2F;       /*!< Fix16 value of 3PI/4 */

static const fix16_t fix16_maximum  = 0x7FFFFFFF; /*!< the maximum value of fix16_t */
static const fix16_t fix16_minimum  = 0x80000000; /*!< the minimum value of fix16_t */
static const fix16_t fix16_overflow = 0x80000000; /*!< the value used to indicate overflows when FIXMATH_NO_OVERFLOW is not specified */

static const fix16_t fix16_pi  = 205887;     /*!< fix16_t value of pi */
static const fix16_t fix16_e   = 178145;     /*!< fix16_t value of e */
static const fix16_t fix16_one = 0x00010000; /*!< fix16_t value of 1 */
static const fix16_t fix16_eps = 1;          /*!< fix16_t epsilon */

/* Conversion functions between fix16_t and float/integer.
 * These are inlined to allow compiler to optimize away constant numbers
 */
static inline fix16_t fix16_from_int(int a)     { return a * fix16_one; }
static inline float   fix16_to_float(fix16_t a) { return (float)a / fix16_one; }
static inline double  fix16_to_dbl(fix16_t a)   { return (double)a / fix16_one; }

static inline int fix16_to_int(fix16_t a)
{
#ifdef FIXMATH_NO_ROUNDING
    return (a >> 16);
#else
	int result = a / fix16_one;
	fix16_t remainder = a % fix16_one;
	if (remainder >= (fix16_one >> 1))
		return result + 1;
	if (remainder <= -(fix16_one >> 1))
		return result - 1;
	return result;
#endif
}

static inline fix16_t fix16_from_float(float a)
{
	float temp = a * fix16_one;
#ifndef FIXMATH_NO_ROUNDING
	temp += (temp >= 0) ? 0.5f : -0.5f;
#endif
	return (fix16_t)temp;
}

static inline fix16_t fix16_from_dbl(double a)
{
	double temp = a * fix16_one;
    /* F16() and F16C() are both rounding allways, so this should as well */
//#ifndef FIXMATH_NO_ROUNDING
	temp += (double)((temp >= 0) ? 0.5f : -0.5f);
//#endif
	return (fix16_t)temp;
}

/* Macro for defining fix16_t constant values.
   The functions above can't be used from e.g. global variable initializers,
   and their names are quite long also. This macro is useful for constants
   springled alongside code, e.g. F16(1.234).

   Note that the argument is evaluated multiple times, and also otherwise
   you should only use this for constant values. For runtime-conversions,
   use the functions above.
*/
#define F16(x) ((fix16_t)(((x) >= 0) ? ((x) * 65536.0 + 0.5) : ((x) * 65536.0 - 0.5)))

static inline fix16_t fix16_abs(fix16_t x)
    { return (fix16_t)(x < 0 ? -(uint32_t)x : (uint32_t)x); }
static inline fix16_t fix16_floor(fix16_t x)
	{ return (x & 0xFFFF0000UL); }
static inline fix16_t fix16_ceil(fix16_t x)
	{ return (x & 0xFFFF0000UL) + (x & 0x0000FFFFUL ? fix16_one : 0); }
static inline fix16_t fix16_min(fix16_t x, fix16_t y)
	{ return (x < y ? x : y); }
static inline fix16_t fix16_max(fix16_t x, fix16_t y)
	{ return (x > y ? x : y); }
static inline fix16_t fix16_clamp(fix16_t x, fix16_t lo, fix16_t hi)
	{ return fix16_min(fix16_max(x, lo), hi); }

/* Subtraction and addition with (optional) overflow detection. */
#ifdef FIXMATH_NO_OVERFLOW

static inline fix16_t fix16_add(fix16_t inArg0, fix16_t inArg1) { return (inArg0 + inArg1); }
static inline fix16_t fix16_sub(fix16_t inArg0, fix16_t inArg1) { return (inArg0 - inArg1); }

#else

extern fix16_t fix16_add(fix16_t a, fix16_t b) FIXMATH_FUNC_ATTRS;
extern fix16_t fix16_sub(fix16_t a, fix16_t b) FIXMATH_FUNC_ATTRS;

/* Saturating arithmetic */
extern fix16_t fix16_sadd(fix16_t a, fix16_t b) FIXMATH_FUNC_ATTRS;
extern fix16_t fix16_ssub(fix16_t a, fix16_t b) FIXMATH_FUNC_ATTRS;

#endif

/*! Multiplies the two given fix16_t's and returns the result.
*/
extern fix16_t fix16_mul(fix16_t inArg0, fix16_t inArg1) FIXMATH_FUNC_ATTRS;

/*! Divides the first given fix16_t by the second and returns the result.
*/
extern fix16_t fix16_div(fix16_t inArg0, fix16_t inArg1) FIXMATH_FUNC_ATTRS;

#ifndef FIXMATH_NO_OVERFLOW
/*! Performs a saturated multiplication (overflow-protected) of the two given fix16_t's and returns the result.
*/
extern fix16_t fix16_smul(fix16_t inArg0, fix16_t inArg1) FIXMATH_FUNC_ATTRS;

/*! Performs a saturated division (overflow-protected) of the first fix16_t by the second and returns the result.
*/
extern fix16_t fix16_sdiv(fix16_t inArg0, fix16_t inArg1) FIXMATH_FUNC_ATTRS;
#endif

/*! Divides the first given fix16_t by the second and returns the result.
*/
extern fix16_t fix16_mod(fix16_t x, fix16_t y) FIXMATH_FUNC_ATTRS;

/*! Returns the linear interpolation: (inArg0 * (1 - inFract)) + (inArg1 * inFract)
*/
extern fix16_t fix16_lerp8(fix16_t inArg0, fix16_t inArg1, uint8_t inFract) FIXMATH_FUNC_ATTRS;
extern fix16_t fix16_lerp16(fix16_t inArg0, fix16_t inArg1, uint16_t inFract) FIXMATH_FUNC_ATTRS;
extern fix16_t fix16_lerp32(fix16_t inArg0, fix16_t inArg1, uint32_t inFract) FIXMATH_FUNC_ATTRS;

/*! Returns the sine of the given fix16_t.
*/
extern fix16_t fix16_sin_parabola(fix16_t inAngle) FIXMATH_FUNC_ATTRS;

/*! Returns the sine of the given fix16_t.
*/
extern fix16_t fix16_sin(fix16_t inAngle) FIXMATH_FUNC_ATTRS;

/*! Returns the cosine of the given fix16_t.
*/
extern fix16_t fix16_cos(fix16_t inAngle) FIXMATH_FUNC_ATTRS;

/*! Returns the tangent of the given fix16_t.
*/
extern fix16_t fix16_tan(fix16_t inAngle) FIXMATH_FUNC_ATTRS;

/*! Returns the arcsine of the given fix16_t.
*/
extern fix16_t fix16_asin(fix16_t inValue) FIXMATH_FUNC_ATTRS;

/*! Returns the arccosine of the given fix16_t.
*/
extern fix16_t fix16_acos(fix16_t inValue) FIXMATH_FUNC_ATTRS;

/*! Returns the arctangent of the given fix16_t.
*/
extern fix16_t fix16_atan(fix16_t inValue) FIXMATH_FUNC_ATTRS;

/*! Returns the arctangent of inY/inX.
*/
extern fix16_t fix16_atan2(fix16_t inY, fix16_t inX) FIXMATH_FUNC_ATTRS;

static const fix16_t fix16_rad_to_deg_mult = 3754936;
static inline fix16_t fix16_rad_to_deg(fix16_t radians)
	{ return fix16_mul(radians, fix16_rad_to_deg_mult); }

static const fix16_t fix16_deg_to_rad_mult = 1144;
static inline fix16_t fix16_deg_to_rad(fix16_t degrees)
	{ return fix16_mul(degrees, fix16_deg_to_rad_mult); }

/*! Returns the square root of the given fix16_t.
*/
extern fix16_t fix16_sqrt(fix16_t inValue) FIXMATH_FUNC_ATTRS;

/*! Returns the square of the given fix16_t.
*/
static inline fix16_t fix16_sq(fix16_t x)
	{ return fix16_mul(x, x); }

/*! Returns the exponent (e^) of the given fix16_t.
*/
extern fix16_t fix16_exp(fix16_t inValue) FIXMATH_FUNC_ATTRS;

/*! Returns the natural logarithm of the given fix16_t.
 */
extern fix16_t fix16_log(fix16_t inValue) FIXMATH_FUNC_ATTRS;

/*! Returns the base 2 logarithm of the given fix16_t.
 */
extern fix16_t fix16_log2(fix16_t x) FIXMATH_FUNC_ATTRS;

/*! Returns the saturated base 2 logarithm of the given fix16_t.
 */
extern fix16_t fix16_slog2(fix16_t x) FIXMATH_FUNC_ATTRS;

/*! Convert fix16_t value to a string.
 * Required buffer length for largest values is 13 bytes.
 */
extern void fix16_to_str(fix16_t value, char *buf, int decimals);

/*! Convert string to a fix16_t value
 * Ignores spaces at beginning and end. Returns fix16_overflow if
 * value is too large or there were garbage characters.
 */
extern fix16_t fix16_from_str(const char *buf);

static inline uint32_t fix_abs(fix16_t in)
{
    if(in == fix16_minimum)
    {
        // minimum negative number has same representation as
        // its absolute value in unsigned
        return 0x80000000;
    }
    else
    {
        return ((in >= 0)?(in):(-in));
    }
}

/** Helper macro for F16C. Replace token with its number of characters/digits. */
#define FIXMATH_TOKLEN(token) ( sizeof( #token ) - 1 )

/** Helper macro for F16C. Handles pow(10, n) for n from 0 to 8. */
#define FIXMATH_CONSTANT_POW10(times) ( \
  (times == 0) ? 1ULL \
        : (times == 1) ? 10ULL \
            : (times == 2) ? 100ULL \
                : (times == 3) ? 1000ULL \
                    : (times == 4) ? 10000ULL \
                        : (times == 5) ? 100000ULL \
                            : (times == 6) ? 1000000ULL \
                                : (times == 7) ? 10000000ULL \
                                    : 100000000ULL \
)

/** Helper macro for F16C, the type uint64_t is only used at compile time and
 *  shouldn't be visible in the generated code.
 *
 * @note We do not use fix16_one instead of 65536ULL, because the
 *       "use of a const variable in a constant expression is nonstandard in C".
 */
#define FIXMATH_CONVERT_MANTISSA(m) \
( (unsigned) \
    ( \
        ( \
            ( \
                (uint64_t)( ( ( 1 ## m ## ULL ) - FIXMATH_CONSTANT_POW10(FIXMATH_TOKLEN(m)) ) * FIXMATH_CONSTANT_POW10(5 - FIXMATH_TOKLEN(m)) ) \
                * 100000ULL * 65536ULL \
            ) \
            + 5000000000ULL /* rounding: + 0.5 */ \
        ) \
        / \
        10000000000LL \
    ) \
)

#define FIXMATH_COMBINE_I_M(i, m) \
( \
    ( \
        (    i ) \
        << 16 \
    ) \
    | \
    ( \
        FIXMATH_CONVERT_MANTISSA(m) \
        & 0xFFFF \
    ) \
)

/** Create int16_t (Q16.16) constant from separate integer and mantissa part.
 *
 * Only tested on 32-bit ARM Cortex-M0 / x86 Intel.
 *
 * This macro is needed when compiling with options like "--fpu=none",
 * which forbid all and every use of float and related types and
 * would thus make it impossible to have fix16_t constants.
 *
 * Just replace uses of F16() with F16C() like this:
 *   F16(123.1234) becomes F16C(123,1234)
 *
 * @warning Specification of any value outside the mentioned intervals
 *          WILL result in undefined behavior!
 *
 * @note Regardless of the specified minimum and maximum values for i and m below,
 *       the total value of the number represented by i and m MUST be in the interval
 *       ]-32768.00000:32767.99999[ else usage with this macro will yield undefined behavior.
 *
 * @param i Signed integer constant with a value in the interval ]-32768:32767[.
 * @param m Positive integer constant in the interval ]0:99999[ (fractional part/mantissa).
 */
#define F16C(i, m) \
( (fix16_t) \
    ( \
      (( #i[0] ) == '-') \
        ? -FIXMATH_COMBINE_I_M((unsigned)( ( (i) * -1) ), m) \
        : FIXMATH_COMBINE_I_M((unsigned)i, m) \
    ) \
)

#ifdef __cplusplus
}

#endif

#endif

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
 int64_t tempOut = int64_mul_i32_i32(inArg0, (((int32_t)1 << 8) - inFract));
 tempOut = int64_add(tempOut, int64_mul_i32_i32(inArg1, inFract));
 tempOut = int64_shift(tempOut, -8);
 return (fix16_t)int64_lo(tempOut);
}

fix16_t fix16_lerp16(fix16_t inArg0, fix16_t inArg1, uint16_t inFract)
{
 int64_t tempOut = int64_mul_i32_i32(inArg0, (((int32_t)1 << 16) - inFract));
 tempOut = int64_add(tempOut, int64_mul_i32_i32(inArg1, inFract));
 tempOut = int64_shift(tempOut, -16);
 return (fix16_t)int64_lo(tempOut);
}

fix16_t fix16_lerp32(fix16_t inArg0, fix16_t inArg1, uint32_t inFract)
{
 if(inFract == 0)
  return inArg0;
 int64_t inFract64 = int64_const(0, inFract);
 int64_t subbed = int64_sub(int64_const(1,0), inFract64);
 int64_t tempOut = int64_mul_i64_i32(subbed, inArg0);
 tempOut = int64_add(tempOut, int64_mul_i64_i32(inFract64, inArg1));
 return int64_hi(tempOut);
}

static fix16_t _fix16_exp_cache_index[4096] = { 0 };
static fix16_t _fix16_exp_cache_value[4096] = { 0 };

fix16_t fix16_exp(fix16_t inValue) {
 if(inValue == 0 ) return fix16_one;
 if(inValue == fix16_one) return fix16_e;
 if(inValue >= 681391 ) return fix16_maximum;
 if(inValue <= -772243 ) return 0;

    fix16_t tempIndex = (inValue ^ (inValue >> 4)) & 0x0FFF;
 if(_fix16_exp_cache_index[tempIndex] == inValue)
  return _fix16_exp_cache_value[tempIndex];
 
_Bool 
     neg = (inValue < 0);
 if (neg) inValue = -inValue;

 fix16_t result = inValue + fix16_one;
 fix16_t term = inValue;

 uint_fast8_t i;
 for (i = 2; i < 30; i++)
 {
  term = fix16_mul(term, fix16_div(inValue, fix16_from_int(i)));
  result += term;

  if ((term < 500) && ((i > 15) || (term < 20)))
   break;
 }

 if (neg) result = fix16_div(fix16_one, result);

 _fix16_exp_cache_index[tempIndex] = inValue;
 _fix16_exp_cache_value[tempIndex] = result;

 return result;
}

fix16_t fix16_log(fix16_t inValue)
{
 fix16_t guess = fix16_from_int(2);
 fix16_t delta;
 int scaling = 0;
 int count = 0;

 if (inValue <= 0)
  return fix16_minimum;

 const fix16_t e_to_fourth = 3578144;
 while (inValue > fix16_from_int(100))
 {
  inValue = fix16_div(inValue, e_to_fourth);
  scaling += 4;
 }

 while (inValue < fix16_one)
 {
  inValue = fix16_mul(inValue, e_to_fourth);
  scaling -= 4;
 }

 do
 {

  fix16_t e = fix16_exp(guess);
  delta = fix16_div(inValue - e, e);

  if (delta > fix16_from_int(3))
   delta = fix16_from_int(3);

  guess += delta;
 } while ((count++ < 10)
  && ((delta > 1) || (delta < -1)));

 return guess + fix16_from_int(scaling);
}

static inline fix16_t fix16_rs(fix16_t x)
{

  fix16_t y = (x >> 1) + (x & 1);
  return y;

}

static fix16_t fix16__log2_inner(fix16_t x)
{
 fix16_t result = 0;

 while(x >= fix16_from_int(2))
 {
  result++;
  x = fix16_rs(x);
 }

 if(x == 0) return (result << 16);

 uint_fast8_t i;
 for(i = 16; i > 0; i--)
 {
  x = fix16_mul(x, x);
  result <<= 1;
  if(x >= fix16_from_int(2))
  {
   result |= 1;
   x = fix16_rs(x);
  }
 }

  x = fix16_mul(x, x);
  if(x >= fix16_from_int(2)) result++;

 return result;
}
fix16_t fix16_log2(fix16_t x)
{

 if (x <= 0) return fix16_overflow;

 if (x < fix16_one)
 {

  if (x == 1) return fix16_from_int(-16);

  fix16_t inverse = fix16_div(fix16_one, x);
  return -fix16__log2_inner(inverse);
 }

 return fix16__log2_inner(x);
}

fix16_t fix16_slog2(fix16_t x)
{
 fix16_t retval = fix16_log2(x);

 if(retval == fix16_overflow)
  return fix16_minimum;
 return retval;
}

static fix16_t _fix16_sin_cache_index[4096] = { 0 };
static fix16_t _fix16_sin_cache_value[4096] = { 0 };

static fix16_t _fix16_atan_cache_index[2][4096] = { { 0 }, { 0 } };
static fix16_t _fix16_atan_cache_value[4096] = { 0 };

fix16_t fix16_sin_parabola(fix16_t inAngle)
{
 fix16_t abs_inAngle, retval;
 fix16_t mask;

 fix16_t abs_retval;

 mask = (inAngle >> (sizeof(fix16_t)*8 
                                            -1));
 abs_inAngle = (inAngle + mask) ^ mask;
 retval = fix16_mul(FOUR_DIV_PI, inAngle) + fix16_mul( fix16_mul(_FOUR_DIV_PI2, inAngle), abs_inAngle );

 mask = (retval >> (sizeof(fix16_t)*8 
                                           -1));
 abs_retval = (retval + mask) ^ mask;

 retval += fix16_mul(X4_CORRECTION_COMPONENT, fix16_mul(retval, abs_retval) - retval );

 return retval;
}

fix16_t fix16_sin(fix16_t inAngle)
{
 fix16_t tempAngle = inAngle % (fix16_pi << 1);
 if(tempAngle > fix16_pi)
  tempAngle -= (fix16_pi << 1);
 else if(tempAngle < -fix16_pi)
  tempAngle += (fix16_pi << 1);

 fix16_t tempIndex = ((inAngle >> 5) & 0x00000FFF);
 if(_fix16_sin_cache_index[tempIndex] == inAngle)
  return _fix16_sin_cache_value[tempIndex];

 fix16_t tempAngleSq = fix16_mul(tempAngle, tempAngle);

 fix16_t tempOut = tempAngle;
 tempAngle = fix16_mul(tempAngle, tempAngleSq);
 tempOut -= (tempAngle / 6);
 tempAngle = fix16_mul(tempAngle, tempAngleSq);
 tempOut += (tempAngle / 120);
 tempAngle = fix16_mul(tempAngle, tempAngleSq);
 tempOut -= (tempAngle / 5040);
 tempAngle = fix16_mul(tempAngle, tempAngleSq);
 tempOut += (tempAngle / 362880);
 tempAngle = fix16_mul(tempAngle, tempAngleSq);
 tempOut -= (tempAngle / 39916800);
 _fix16_sin_cache_index[tempIndex] = inAngle;
 _fix16_sin_cache_value[tempIndex] = tempOut;

 return tempOut;
}

fix16_t fix16_cos(fix16_t inAngle)
{
 return fix16_sin(inAngle + (fix16_pi >> 1));
}

fix16_t fix16_tan(fix16_t inAngle)
{

 return fix16_sdiv(fix16_sin(inAngle), fix16_cos(inAngle));

}

fix16_t fix16_asin(fix16_t x)
{
 if((x > fix16_one)
  || (x < -fix16_one))
  return 0;

 if(x == fix16_one)
  return (fix16_pi >> 1);
 if(x == -fix16_one)
  return -(fix16_pi >> 1);

 fix16_t out;
 out = (fix16_one - fix16_mul(x, x));
 out = fix16_div(x, fix16_sqrt(out));
 out = fix16_atan(out);
 return out;
}

fix16_t fix16_acos(fix16_t x)
{
 return ((fix16_pi >> 1) - fix16_asin(x));
}

fix16_t fix16_atan2(fix16_t inY , fix16_t inX)
{
 fix16_t abs_inY, mask, angle, r, r_3;

 if (inX == 0 && inY == 0)
  return 0;

 uintptr_t hash = (inX ^ inY);
 hash ^= hash >> 20;
 hash &= 0x0FFF;
 if((_fix16_atan_cache_index[0][hash] == inX) && (_fix16_atan_cache_index[1][hash] == inY))
  return _fix16_atan_cache_value[hash];

 mask = (inY >> (sizeof(fix16_t)*8 
                                        -1));
 abs_inY = (inY + mask) ^ mask;

 if (inX >= 0)
 {
  r = fix16_div( (inX - abs_inY), (inX + abs_inY));
  r_3 = fix16_mul(fix16_mul(r, r),r);
  angle = fix16_mul(0x00003240 , r_3) - fix16_mul(0x0000FB50,r) + PI_DIV_4;
 } else {
  r = fix16_div( (inX + abs_inY), (abs_inY - inX));
  r_3 = fix16_mul(fix16_mul(r, r),r);
  angle = fix16_mul(0x00003240 , r_3)
   - fix16_mul(0x0000FB50,r)
   + THREE_PI_DIV_4;
 }
 if (inY < 0)
 {
  angle = -angle;
 }

 _fix16_atan_cache_index[0][hash] = inX;
 _fix16_atan_cache_index[1][hash] = inY;
 _fix16_atan_cache_value[hash] = angle;

 return angle;
}

fix16_t fix16_atan(fix16_t x)
{
 return fix16_atan2(x, fix16_one);
}