#include <stdint.h>
#include <stddef.h>
#include <string.h>

struct bn
{
  uint32_t array[(128 / 4)];
};

enum { SMALLER = -1, EQUAL = 0, LARGER = 1 };

void bignum_init(struct bn* n);
void bignum_from_int(struct bn* n, uint64_t i);
int bignum_to_int(struct bn* n);
void bignum_from_string(struct bn* n, char* str, int nbytes);
void bignum_to_string(struct bn* n, char* str, int maxsize);

void bignum_add(struct bn* a, struct bn* b, struct bn* c);
void bignum_sub(struct bn* a, struct bn* b, struct bn* c);
void bignum_mul(struct bn* a, struct bn* b, struct bn* c);
void bignum_div(struct bn* a, struct bn* b, struct bn* c);
void bignum_mod(struct bn* a, struct bn* b, struct bn* c);
void bignum_divmod(struct bn* a, struct bn* b, struct bn* c, struct bn* d);

void bignum_and(struct bn* a, struct bn* b, struct bn* c);
void bignum_or(struct bn* a, struct bn* b, struct bn* c);
void bignum_xor(struct bn* a, struct bn* b, struct bn* c);
void bignum_lshift(struct bn* a, struct bn* b, int nbits);
void bignum_rshift(struct bn* a, struct bn* b, int nbits);

int bignum_cmp(struct bn* a, struct bn* b);
int bignum_is_zero(struct bn* n);
void bignum_inc(struct bn* n);
void bignum_dec(struct bn* n);
void bignum_pow(struct bn* a, struct bn* b, struct bn* c);
void bignum_isqrt(struct bn* a, struct bn* b);
void bignum_assign(struct bn* dst, struct bn* src);

static void _lshift_one_bit(struct bn* a);
static void _rshift_one_bit(struct bn* a);
static void _lshift_word(struct bn* a, int nwords);
static void _rshift_word(struct bn* a, int nwords);

void bignum_init(struct bn* n)
{
  
 ((void) sizeof ((
 n && "n is null"
 ) ? 1 : 0), __extension__ ({ if (
 n && "n is null"
 ) ; else __assert_fail (
 "n && \"n is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 39, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    n->array[i] = 0;
  }
}

void bignum_from_int(struct bn* n, uint64_t i)
{
  
 ((void) sizeof ((
 n && "n is null"
 ) ? 1 : 0), __extension__ ({ if (
 n && "n is null"
 ) ; else __assert_fail (
 "n && \"n is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 51, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  bignum_init(n);
  n->array[0] = i;
  uint64_t num_32 = 32;
  uint64_t tmp = i >> num_32;
  n->array[1] = tmp;

}

int bignum_to_int(struct bn* n)
{
  
 ((void) sizeof ((
 n && "n is null"
 ) ? 1 : 0), __extension__ ({ if (
 n && "n is null"
 ) ; else __assert_fail (
 "n && \"n is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 77, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int ret = 0;
  ret += n->array[0];

  return ret;
}

void bignum_from_string(struct bn* n, char* str, int nbytes)
{
  
 ((void) sizeof ((
 n && "n is null"
 ) ? 1 : 0), __extension__ ({ if (
 n && "n is null"
 ) ; else __assert_fail (
 "n && \"n is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 100, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 str && "str is null"
 ) ? 1 : 0), __extension__ ({ if (
 str && "str is null"
 ) ; else __assert_fail (
 "str && \"str is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 101, __extension__ __PRETTY_FUNCTION__); }))
                            ;
  
 ((void) sizeof ((
 nbytes > 0 && "nbytes must be positive"
 ) ? 1 : 0), __extension__ ({ if (
 nbytes > 0 && "nbytes must be positive"
 ) ; else __assert_fail (
 "nbytes > 0 && \"nbytes must be positive\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 102, __extension__ __PRETTY_FUNCTION__); }))
                                               ;
  
 ((void) sizeof ((
 (nbytes & 1) == 0 && "string format must be in hex -> equal number of bytes"
 ) ? 1 : 0), __extension__ ({ if (
 (nbytes & 1) == 0 && "string format must be in hex -> equal number of bytes"
 ) ; else __assert_fail (
 "(nbytes & 1) == 0 && \"string format must be in hex -> equal number of bytes\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 103, __extension__ __PRETTY_FUNCTION__); }))
                                                                                    ;
  
 ((void) sizeof ((
 (nbytes % (sizeof(uint32_t) * 2)) == 0 && "string length must be a multiple of (sizeof(DTYPE) * 2) characters"
 ) ? 1 : 0), __extension__ ({ if (
 (nbytes % (sizeof(uint32_t) * 2)) == 0 && "string length must be a multiple of (sizeof(DTYPE) * 2) characters"
 ) ; else __assert_fail (
 "(nbytes % (sizeof(uint32_t) * 2)) == 0 && \"string length must be a multiple of (sizeof(DTYPE) * 2) characters\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 104, __extension__ __PRETTY_FUNCTION__); }))
                                                                                                                   ;

  bignum_init(n);

  uint32_t tmp;
  int i = nbytes - (2 * 4);
  int j = 0;

  while (i >= 0)
  {
    tmp = 0;
    sscanf(&str[i], "%8x", &tmp);
    n->array[j] = tmp;
    i -= (2 * 4);
    j += 1;
  }
}

void bignum_to_string(struct bn* n, char* str, int nbytes)
{
  
 ((void) sizeof ((
 n && "n is null"
 ) ? 1 : 0), __extension__ ({ if (
 n && "n is null"
 ) ; else __assert_fail (
 "n && \"n is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 127, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 str && "str is null"
 ) ? 1 : 0), __extension__ ({ if (
 str && "str is null"
 ) ; else __assert_fail (
 "str && \"str is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 128, __extension__ __PRETTY_FUNCTION__); }))
                            ;
  
 ((void) sizeof ((
 nbytes > 0 && "nbytes must be positive"
 ) ? 1 : 0), __extension__ ({ if (
 nbytes > 0 && "nbytes must be positive"
 ) ; else __assert_fail (
 "nbytes > 0 && \"nbytes must be positive\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 129, __extension__ __PRETTY_FUNCTION__); }))
                                               ;
  
 ((void) sizeof ((
 (nbytes & 1) == 0 && "string format must be in hex -> equal number of bytes"
 ) ? 1 : 0), __extension__ ({ if (
 (nbytes & 1) == 0 && "string format must be in hex -> equal number of bytes"
 ) ; else __assert_fail (
 "(nbytes & 1) == 0 && \"string format must be in hex -> equal number of bytes\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 130, __extension__ __PRETTY_FUNCTION__); }))
                                                                                    ;

  int j = (128 / 4) - 1;
  int i = 0;

  while ((j >= 0) && (nbytes > (i + 1)))
  {
    sprintf(&str[i], "%.08x", n->array[j]);
    i += (2 * 4);
    j -= 1;
  }

  j = 0;
  while (str[j] == '0')
  {
    j += 1;
  }

  for (i = 0; i < (nbytes - j); ++i)
  {
    str[i] = str[i + j];
  }

  str[i] = 0;
}

void bignum_dec(struct bn* n)
{
  
 ((void) sizeof ((
 n && "n is null"
 ) ? 1 : 0), __extension__ ({ if (
 n && "n is null"
 ) ; else __assert_fail (
 "n && \"n is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 163, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  uint32_t tmp;
  uint32_t res;

  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    tmp = n->array[i];
    res = tmp - 1;
    n->array[i] = res;

    if (!(res > tmp))
    {
      break;
    }
  }
}

void bignum_inc(struct bn* n)
{
  
 ((void) sizeof ((
 n && "n is null"
 ) ? 1 : 0), __extension__ ({ if (
 n && "n is null"
 ) ; else __assert_fail (
 "n && \"n is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 185, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  uint32_t res;
  uint64_t tmp;

  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    tmp = n->array[i];
    res = tmp + 1;
    n->array[i] = res;

    if (res > tmp)
    {
      break;
    }
  }
}

void bignum_add(struct bn* a, struct bn* b, struct bn* c)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 207, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 208, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 209, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  uint64_t tmp;
  int carry = 0;
  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    tmp = (uint64_t)a->array[i] + b->array[i] + carry;
    carry = (tmp > ((uint64_t)0xFFFFFFFF));
    c->array[i] = (tmp & ((uint64_t)0xFFFFFFFF));
  }
}

void bignum_sub(struct bn* a, struct bn* b, struct bn* c)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 225, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 226, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 227, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  uint64_t res;
  uint64_t tmp1;
  uint64_t tmp2;
  int borrow = 0;
  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    tmp1 = (uint64_t)a->array[i] + (((uint64_t)0xFFFFFFFF) + 1);
    tmp2 = (uint64_t)b->array[i] + borrow;;
    res = (tmp1 - tmp2);
    c->array[i] = (uint32_t)(res & ((uint64_t)0xFFFFFFFF));
    borrow = (res <= ((uint64_t)0xFFFFFFFF));
  }
}

void bignum_mul(struct bn* a, struct bn* b, struct bn* c)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 247, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 248, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 249, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  struct bn row;
  struct bn tmp;
  int i, j;

  bignum_init(c);

  for (i = 0; i < (128 / 4); ++i)
  {
    bignum_init(&row);

    for (j = 0; j < (128 / 4); ++j)
    {
      if (i + j < (128 / 4))
      {
        bignum_init(&tmp);
        uint64_t intermediate = ((uint64_t)a->array[i] * (uint64_t)b->array[j]);
        bignum_from_int(&tmp, intermediate);
        _lshift_word(&tmp, i + j);
        bignum_add(&tmp, &row, &row);
      }
    }
    bignum_add(c, &row, c);
  }
}

void bignum_div(struct bn* a, struct bn* b, struct bn* c)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 279, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 280, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 281, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  struct bn current;
  struct bn denom;
  struct bn tmp;

  bignum_from_int(&current, 1);
  bignum_assign(&denom, b);
  bignum_assign(&tmp, a);

  const uint64_t half_max = 1 + (uint64_t)(((uint64_t)0xFFFFFFFF) / 2);
  
 _Bool 
      overflow = 
                 0
                      ;
  while (bignum_cmp(&denom, a) != LARGER)
  {
    if (denom.array[(128 / 4) - 1] >= half_max)
    {
      overflow = 
                1
                    ;
      break;
    }
    _lshift_one_bit(&current);
    _lshift_one_bit(&denom);
  }
  if (!overflow)
  {
    _rshift_one_bit(&denom);
    _rshift_one_bit(&current);
  }
  bignum_init(c);

  while (!bignum_is_zero(&current))
  {
    if (bignum_cmp(&tmp, &denom) != SMALLER)
    {
      bignum_sub(&tmp, &denom, &tmp);
      bignum_or(c, &current, c);
    }
    _rshift_one_bit(&current);
    _rshift_one_bit(&denom);
  }
}

void bignum_lshift(struct bn* a, struct bn* b, int nbits)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 325, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 326, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 nbits >= 0 && "no negative shifts"
 ) ? 1 : 0), __extension__ ({ if (
 nbits >= 0 && "no negative shifts"
 ) ; else __assert_fail (
 "nbits >= 0 && \"no negative shifts\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 327, __extension__ __PRETTY_FUNCTION__); }))
                                          ;

  bignum_assign(b, a);

  const int nbits_pr_word = (4 * 8);
  int nwords = nbits / nbits_pr_word;
  if (nwords != 0)
  {
    _lshift_word(b, nwords);
    nbits -= (nwords * nbits_pr_word);
  }

  if (nbits != 0)
  {
    int i;
    for (i = ((128 / 4) - 1); i > 0; --i)
    {
      b->array[i] = (b->array[i] << nbits) | (b->array[i - 1] >> ((8 * 4) - nbits));
    }
    b->array[i] <<= nbits;
  }
}

void bignum_rshift(struct bn* a, struct bn* b, int nbits)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 353, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 354, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 nbits >= 0 && "no negative shifts"
 ) ? 1 : 0), __extension__ ({ if (
 nbits >= 0 && "no negative shifts"
 ) ; else __assert_fail (
 "nbits >= 0 && \"no negative shifts\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 355, __extension__ __PRETTY_FUNCTION__); }))
                                          ;

  bignum_assign(b, a);

  const int nbits_pr_word = (4 * 8);
  int nwords = nbits / nbits_pr_word;
  if (nwords != 0)
  {
    _rshift_word(b, nwords);
    nbits -= (nwords * nbits_pr_word);
  }

  if (nbits != 0)
  {
    int i;
    for (i = 0; i < ((128 / 4) - 1); ++i)
    {
      b->array[i] = (b->array[i] >> nbits) | (b->array[i + 1] << ((8 * 4) - nbits));
    }
    b->array[i] >>= nbits;
  }

}

void bignum_mod(struct bn* a, struct bn* b, struct bn* c)
{

  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 385, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 386, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 387, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  struct bn tmp;

  bignum_divmod(a,b,&tmp,c);
}

void bignum_divmod(struct bn* a, struct bn* b, struct bn* c, struct bn* d)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 405, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 406, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 407, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  struct bn tmp;

  bignum_div(a, b, c);

  bignum_mul(c, b, &tmp);

  bignum_sub(a, &tmp, d);
}

void bignum_and(struct bn* a, struct bn* b, struct bn* c)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 424, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 425, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 426, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    c->array[i] = (a->array[i] & b->array[i]);
  }
}

void bignum_or(struct bn* a, struct bn* b, struct bn* c)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 438, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 439, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 440, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    c->array[i] = (a->array[i] | b->array[i]);
  }
}

void bignum_xor(struct bn* a, struct bn* b, struct bn* c)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 452, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 453, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 454, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    c->array[i] = (a->array[i] ^ b->array[i]);
  }
}

int bignum_cmp(struct bn* a, struct bn* b)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 466, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 467, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int i = (128 / 4);
  do
  {
    i -= 1;
    if (a->array[i] > b->array[i])
    {
      return LARGER;
    }
    else if (a->array[i] < b->array[i])
    {
      return SMALLER;
    }
  }
  while (i != 0);

  return EQUAL;
}

int bignum_is_zero(struct bn* n)
{
  
 ((void) sizeof ((
 n && "n is null"
 ) ? 1 : 0), __extension__ ({ if (
 n && "n is null"
 ) ; else __assert_fail (
 "n && \"n is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 490, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    if (n->array[i])
    {
      return 0;
    }
  }

  return 1;
}

void bignum_pow(struct bn* a, struct bn* b, struct bn* c)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 507, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 508, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 c && "c is null"
 ) ? 1 : 0), __extension__ ({ if (
 c && "c is null"
 ) ; else __assert_fail (
 "c && \"c is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 509, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  struct bn tmp;

  bignum_init(c);

  if (bignum_cmp(b, c) == EQUAL)
  {

    bignum_inc(c);
  }
  else
  {
    struct bn bcopy;
    bignum_assign(&bcopy, b);

    bignum_assign(&tmp, a);

    bignum_dec(&bcopy);

    while (!bignum_is_zero(&bcopy))
    {

      bignum_mul(&tmp, a, c);

      bignum_dec(&bcopy);

      bignum_assign(&tmp, c);
    }

    bignum_assign(c, &tmp);
  }
}

void bignum_isqrt(struct bn *a, struct bn* b)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 549, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 b && "b is null"
 ) ? 1 : 0), __extension__ ({ if (
 b && "b is null"
 ) ; else __assert_fail (
 "b && \"b is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 550, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  struct bn low, high, mid, tmp;

  bignum_init(&low);
  bignum_assign(&high, a);
  bignum_rshift(&high, &mid, 1);
  bignum_inc(&mid);

  while (bignum_cmp(&high, &low) > 0)
  {
    bignum_mul(&mid, &mid, &tmp);
    if (bignum_cmp(&tmp, a) > 0)
    {
      bignum_assign(&high, &mid);
      bignum_dec(&high);
    }
    else
    {
      bignum_assign(&low, &mid);
    }
    bignum_sub(&high,&low,&mid);
    _rshift_one_bit(&mid);
    bignum_add(&low,&mid,&mid);
    bignum_inc(&mid);
  }
  bignum_assign(b,&low);
}

void bignum_assign(struct bn* dst, struct bn* src)
{
  
 ((void) sizeof ((
 dst && "dst is null"
 ) ? 1 : 0), __extension__ ({ if (
 dst && "dst is null"
 ) ; else __assert_fail (
 "dst && \"dst is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 582, __extension__ __PRETTY_FUNCTION__); }))
                            ;
  
 ((void) sizeof ((
 src && "src is null"
 ) ? 1 : 0), __extension__ ({ if (
 src && "src is null"
 ) ; else __assert_fail (
 "src && \"src is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 583, __extension__ __PRETTY_FUNCTION__); }))
                            ;

  int i;
  for (i = 0; i < (128 / 4); ++i)
  {
    dst->array[i] = src->array[i];
  }
}

static void _rshift_word(struct bn* a, int nwords)
{

  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 597, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 nwords >= 0 && "no negative shifts"
 ) ? 1 : 0), __extension__ ({ if (
 nwords >= 0 && "no negative shifts"
 ) ; else __assert_fail (
 "nwords >= 0 && \"no negative shifts\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 598, __extension__ __PRETTY_FUNCTION__); }))
                                           ;

  int i;
  if (nwords >= (128 / 4))
  {
    for (i = 0; i < (128 / 4); ++i)
    {
      a->array[i] = 0;
    }
    return;
  }

  for (i = 0; i < (128 / 4) - nwords; ++i)
  {
    a->array[i] = a->array[i + nwords];
  }
  for (; i < (128 / 4); ++i)
  {
    a->array[i] = 0;
  }
}

static void _lshift_word(struct bn* a, int nwords)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 623, __extension__ __PRETTY_FUNCTION__); }))
                        ;
  
 ((void) sizeof ((
 nwords >= 0 && "no negative shifts"
 ) ? 1 : 0), __extension__ ({ if (
 nwords >= 0 && "no negative shifts"
 ) ; else __assert_fail (
 "nwords >= 0 && \"no negative shifts\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 624, __extension__ __PRETTY_FUNCTION__); }))
                                           ;

  int i;

  for (i = ((128 / 4) - 1); i >= nwords; --i)
  {
    a->array[i] = a->array[i - nwords];
  }

  for (; i >= 0; --i)
  {
    a->array[i] = 0;
  }
}

static void _lshift_one_bit(struct bn* a)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 642, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int i;
  for (i = ((128 / 4) - 1); i > 0; --i)
  {
    a->array[i] = (a->array[i] << 1) | (a->array[i - 1] >> ((8 * 4) - 1));
  }
  a->array[0] <<= 1;
}

static void _rshift_one_bit(struct bn* a)
{
  
 ((void) sizeof ((
 a && "a is null"
 ) ? 1 : 0), __extension__ ({ if (
 a && "a is null"
 ) ; else __assert_fail (
 "a && \"a is null\""
 , "/data/rigrun/projects/alchemist/subjects/ingest/tiny_bignum/bn.c", 655, __extension__ __PRETTY_FUNCTION__); }))
                        ;

  int i;
  for (i = 0; i < ((128 / 4) - 1); ++i)
  {
    a->array[i] = (a->array[i] >> 1) | (a->array[i + 1] << ((8 * 4) - 1));
  }
  a->array[(128 / 4) - 1] >>= 1;
}