/* Auto-compiled shim that exposes zlib's static-local state-mutating
   functions as testable DLL entry points.

   Strategy: pull zlib's source files into a single compile unit. Static
   locals are then in-scope for the shim's extern entry points.

   Each state-mutator function gets:
     - shim_reset() — zeros the shared deflate_state g_state
     - shim_set_<field>(value) — set one field
     - shim_get_<field>(out_ptr, ...) — read one field
     - shim_run_<fn>() — execute the target function on g_state

   The Python fuzz harness:
     1. shim_reset()
     2. shim_set_<field> for each pre-state field
     3. shim_run_<fn>()
     4. shim_get_<field> for each post-state field
     5. Records (pre, post) as a test vector.
*/

#include <stddef.h>
#include <string.h>

/* Include zlib's aggregated headers. Internal state structs (deflate_state,
   inflate_state) live in deflate.h / inflate.h. We compile those .c files
   directly below so static-local helpers become available in this CU.
*/
#include "../zconf.h"
#include "../zutil.h"
#include "../deflate.h"

/* Slurp the zlib source bodies that hold state-mutating helpers.
   Order matters: trees.c uses statics only in trees; deflate.c references
   adler32/crc32 from adler32.c/crc32.c; zutil.c provides zcalloc/zcfree/z_errmsg. */
#include "../adler32.c"
#include "../crc32.c"
#include "../zutil.c"
#include "../trees.c"
#include "../deflate.c"

/* Single shared state buffer — reset between test vectors. */
static deflate_state g_state;

/* Pending buffer backing store (2048 bytes is more than enough for fuzz). */
#define PENDING_BUF_SIZE 2048
static unsigned char g_pending_buf[PENDING_BUF_SIZE];

#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

EXPORT void shim_reset(void) {
    memset(&g_state, 0, sizeof(g_state));
    memset(g_pending_buf, 0, PENDING_BUF_SIZE);
    g_state.pending_buf = g_pending_buf;
    g_state.pending_buf_size = PENDING_BUF_SIZE;
}

/* ---------- bi_buf / bi_valid / pending ---------- */

EXPORT void shim_set_bi_buf(unsigned short v) { g_state.bi_buf = v; }
EXPORT unsigned short shim_get_bi_buf(void) { return g_state.bi_buf; }

EXPORT void shim_set_bi_valid(int v) { g_state.bi_valid = v; }
EXPORT int shim_get_bi_valid(void) { return g_state.bi_valid; }

EXPORT void shim_set_pending(const unsigned char *buf, unsigned n) {
    if (n > PENDING_BUF_SIZE) n = PENDING_BUF_SIZE;
    memcpy(g_pending_buf, buf, n);
    g_state.pending = n;
}
EXPORT unsigned shim_get_pending_len(void) { return g_state.pending; }
EXPORT void shim_get_pending(unsigned char *out, unsigned max) {
    unsigned n = g_state.pending;
    if (n > max) n = max;
    memcpy(out, g_pending_buf, n);
}

/* ---------- hash chains ---------- */

EXPORT void shim_set_w_size(unsigned long v) { g_state.w_size = (uInt)v; }
EXPORT unsigned long shim_get_w_size(void) { return (unsigned long)g_state.w_size; }
EXPORT void shim_set_hash_size(unsigned long v) {
    g_state.hash_size = (uInt)v;
}

/* Note: head/prev are Pos* pointers to allocated memory. For simplicity,
   we let the caller fuzz sizes that match the static allocation we do
   here. */

#define HASH_MAX 1024
static Pos g_head[HASH_MAX];
static Pos g_prev[HASH_MAX];

EXPORT void shim_set_head(const unsigned short *src, unsigned n) {
    if (n > HASH_MAX) n = HASH_MAX;
    for (unsigned i = 0; i < n; i++) g_head[i] = (Pos)src[i];
    g_state.head = g_head;
}
EXPORT void shim_get_head(unsigned short *out, unsigned n) {
    if (n > HASH_MAX) n = HASH_MAX;
    for (unsigned i = 0; i < n; i++) out[i] = (unsigned short)g_head[i];
}

EXPORT void shim_set_prev(const unsigned short *src, unsigned n) {
    if (n > HASH_MAX) n = HASH_MAX;
    for (unsigned i = 0; i < n; i++) g_prev[i] = (Pos)src[i];
    g_state.prev = g_prev;
}
EXPORT void shim_get_prev(unsigned short *out, unsigned n) {
    if (n > HASH_MAX) n = HASH_MAX;
    for (unsigned i = 0; i < n; i++) out[i] = (unsigned short)g_prev[i];
}

/* ---------- tree counters ---------- */

EXPORT void shim_set_opt_len(unsigned long v) { g_state.opt_len = (ulg)v; }
EXPORT unsigned long shim_get_opt_len(void) { return g_state.opt_len; }

EXPORT void shim_set_static_len(unsigned long v) {
    g_state.static_len = (ulg)v;
}
EXPORT unsigned long shim_get_static_len(void) { return g_state.static_len; }

EXPORT void shim_set_sym_next(unsigned v) { g_state.sym_next = v; }
EXPORT unsigned shim_get_sym_next(void) { return g_state.sym_next; }

EXPORT void shim_set_matches(unsigned v) { g_state.matches = v; }
EXPORT unsigned shim_get_matches(void) { return g_state.matches; }

/* ---------- Function runners ---------- */

EXPORT void shim_run_bi_flush(void) { bi_flush(&g_state); }
EXPORT void shim_run_bi_windup(void) { bi_windup(&g_state); }
EXPORT void shim_run_slide_hash(void) { slide_hash(&g_state); }
EXPORT void shim_run_init_block(void) { init_block(&g_state); }
EXPORT void shim_run_tr_init(void) { _tr_init(&g_state); }
EXPORT void shim_run_detect_data_type(int *result) {
    *result = detect_data_type(&g_state);
}

/* send_bits is a macro in zlib's trees.c — use an intermediate pointer
   variable so the token expansion doesn't trip over operator precedence. */
EXPORT void shim_run_send_bits(int value, int length) {
    deflate_state *s = &g_state;
    send_bits(s, value, length);
}

/* bi_reverse is pure — takes code + len, returns reversed */
EXPORT unsigned shim_run_bi_reverse(unsigned code, int len) {
    return bi_reverse(code, len);
}

/* _tr_align: flush to byte boundary, emit EOB */
EXPORT void shim_run_tr_align(void) {
    deflate_state *s = &g_state;
    /* Requires static tables initialized */
    tr_static_init();
    _tr_align(s);
}

/* _tr_stored_block: writes a stored block with buffered data */
EXPORT void shim_run_tr_stored_block(const unsigned char *buf, unsigned long stored_len, int last) {
    deflate_state *s = &g_state;
    tr_static_init();
    _tr_stored_block(s, (charf *)buf, stored_len, last);
}

/* Additional field getters/setters for head/prev are already in place.
   Let's add fields for dyn_ltree freq (for detect_data_type). */

EXPORT void shim_set_dyn_ltree_freq(const unsigned short *freqs, unsigned n) {
    deflate_state *s = &g_state;
    unsigned max = n < HEAP_SIZE ? n : HEAP_SIZE;
    for (unsigned i = 0; i < max; i++) {
        s->dyn_ltree[i].Freq = (ush)freqs[i];
    }
}

/* ---------- Huffman heap state (pqdownheap / build_tree) ---------- */

EXPORT void shim_set_heap(const int *src, unsigned n) {
    deflate_state *s = &g_state;
    unsigned max = n < 2 * L_CODES + 1 ? n : 2 * L_CODES + 1;
    for (unsigned i = 0; i < max; i++) s->heap[i] = src[i];
}
EXPORT void shim_get_heap(int *out, unsigned n) {
    deflate_state *s = &g_state;
    unsigned max = n < 2 * L_CODES + 1 ? n : 2 * L_CODES + 1;
    for (unsigned i = 0; i < max; i++) out[i] = s->heap[i];
}

EXPORT void shim_set_heap_len(int v) { g_state.heap_len = v; }
EXPORT int shim_get_heap_len(void) { return g_state.heap_len; }
EXPORT void shim_set_heap_max(int v) { g_state.heap_max = v; }
EXPORT int shim_get_heap_max(void) { return g_state.heap_max; }

EXPORT void shim_set_depth(const unsigned char *src, unsigned n) {
    deflate_state *s = &g_state;
    unsigned max = n < 2 * L_CODES + 1 ? n : 2 * L_CODES + 1;
    for (unsigned i = 0; i < max; i++) s->depth[i] = (uch)src[i];
}
EXPORT void shim_get_depth(unsigned char *out, unsigned n) {
    deflate_state *s = &g_state;
    unsigned max = n < 2 * L_CODES + 1 ? n : 2 * L_CODES + 1;
    for (unsigned i = 0; i < max; i++) out[i] = (unsigned char)s->depth[i];
}

/* pqdownheap sifts s->heap[k] down using tree[].Freq (dyn_ltree) + depth. */
EXPORT void shim_run_pqdownheap(int k) {
    deflate_state *s = &g_state;
    pqdownheap(s, s->dyn_ltree, k);
}

/* ---------- Generic tree accessors (union-slot aware) ----------
   ct_data is { union {ush freq; ush code;} fc; union {ush dad; ush len;} dl; }.
   fc holds Freq before gen_codes / Code after; dl holds Dad before gen_bitlen
   / Len after. The shim exposes the raw fc/dl slots so the Python fuzzer can
   set inputs (Freq via fc, Len via dl) and read outputs (Code via fc, Len via
   dl) matching whichever phase the function operates in. which: 0=dyn_ltree,
   1=dyn_dtree, 2=bl_tree. */
static ct_data *tree_of(int which) {
    deflate_state *s = &g_state;
    if (which == 1) return s->dyn_dtree;
    if (which == 2) return s->bl_tree;
    return s->dyn_ltree;
}
static unsigned tree_cap(int which) {
    if (which == 1) return 2 * D_CODES + 1;
    if (which == 2) return 2 * BL_CODES + 1;
    return HEAP_SIZE;
}
EXPORT void shim_set_tree_fc(int which, const unsigned short *v, unsigned n) {
    ct_data *t = tree_of(which); unsigned m = tree_cap(which); if (n < m) m = n;
    for (unsigned i = 0; i < m; i++) t[i].fc.freq = v[i];
}
EXPORT void shim_get_tree_fc(int which, unsigned short *o, unsigned n) {
    ct_data *t = tree_of(which); unsigned m = tree_cap(which); if (n < m) m = n;
    for (unsigned i = 0; i < m; i++) o[i] = t[i].fc.freq;
}
EXPORT void shim_set_tree_dl(int which, const unsigned short *v, unsigned n) {
    ct_data *t = tree_of(which); unsigned m = tree_cap(which); if (n < m) m = n;
    for (unsigned i = 0; i < m; i++) t[i].dl.len = (ush)v[i];
}
EXPORT void shim_get_tree_dl(int which, unsigned short *o, unsigned n) {
    ct_data *t = tree_of(which); unsigned m = tree_cap(which); if (n < m) m = n;
    for (unsigned i = 0; i < m; i++) o[i] = t[i].dl.len;
}

/* bl_count[0..MAX_BITS] — used by gen_codes and written by gen_bitlen. */
EXPORT void shim_set_bl_count(const unsigned short *v, unsigned n) {
    deflate_state *s = &g_state; unsigned m = MAX_BITS + 1; if (n < m) m = n;
    for (unsigned i = 0; i < m; i++) s->bl_count[i] = v[i];
}
EXPORT void shim_get_bl_count(unsigned short *o, unsigned n) {
    deflate_state *s = &g_state; unsigned m = MAX_BITS + 1; if (n < m) m = n;
    for (unsigned i = 0; i < m; i++) o[i] = s->bl_count[i];
}

/* gen_codes(tree, max_code, s->bl_count): reads tree.Len (dl) + bl_count,
   writes tree.Code (fc). No deflate_state mutation. */
EXPORT void shim_run_gen_codes(int which, int max_code) {
    deflate_state *s = &g_state;
    gen_codes(tree_of(which), max_code, s->bl_count);
}

/* Wire the three tree descriptors like _tr_init but WITHOUT zeroing the
   frequencies (so the caller's fuzzed Freq survive into build_tree). */
static void shim_desc_setup(void) {
    deflate_state *s = &g_state;
    tr_static_init();
    s->l_desc.dyn_tree = s->dyn_ltree; s->l_desc.stat_desc = &static_l_desc;
    s->d_desc.dyn_tree = s->dyn_dtree; s->d_desc.stat_desc = &static_d_desc;
    s->bl_desc.dyn_tree = s->bl_tree;  s->bl_desc.stat_desc = &static_bl_desc;
}

/* build_tree(s, desc): from fuzzed Freq (fc) builds the whole tree — heap,
   Len (dl), Code (fc), opt_len, static_len, max_code. which selects the
   descriptor/tree (0=l,1=d,2=bl). */
EXPORT void shim_run_build_tree(int which) {
    deflate_state *s = &g_state;
    shim_desc_setup();
    tree_desc *d = which == 1 ? &s->d_desc : (which == 2 ? &s->bl_desc : &s->l_desc);
    build_tree(s, d);
}
EXPORT int shim_get_desc_max_code(int which) {
    deflate_state *s = &g_state;
    return which == 1 ? s->d_desc.max_code : (which == 2 ? s->bl_desc.max_code : s->l_desc.max_code);
}
EXPORT void shim_set_desc_max_code(int which, int v) {
    deflate_state *s = &g_state;
    if (which == 1) s->d_desc.max_code = v;
    else if (which == 2) s->bl_desc.max_code = v;
    else s->l_desc.max_code = v;
}

/* build_bl_tree(s): scans dyn_ltree/dyn_dtree Len, builds bl_tree, returns
   max_blindex. Needs l_desc/d_desc.max_code + the two trees' Len set. */
EXPORT int shim_run_build_bl_tree(void) {
    deflate_state *s = &g_state;
    shim_desc_setup();
    return build_bl_tree(s);
}

/* ---------- Static Huffman tables (computed by tr_static_init) ----------
   These are zlib's fixed reference tables; the Rust workspace needs them as
   consts so build_tree/gen_bitlen can compute static_len and so descriptors
   can be constructed. which: 0=static_ltree (L_CODES+2), 1=static_dtree
   (D_CODES). */
EXPORT void shim_static_tree(int which, unsigned short *code_out,
                             unsigned short *len_out, unsigned n) {
    tr_static_init();
    const ct_data *t = which == 1 ? static_dtree : static_ltree;
    unsigned cap = which == 1 ? D_CODES : (L_CODES + 2);
    if (n < cap) cap = n;
    for (unsigned i = 0; i < cap; i++) {
        code_out[i] = t[i].fc.code;
        len_out[i] = t[i].dl.len;
    }
}
/* Small fixed const tables. which: 0=extra_lbits(29) 1=extra_dbits(30)
   2=extra_blbits(19) 3=base_length(29) 4=base_dist(30) 5=bl_order(19). */
EXPORT unsigned shim_const_table(int which, int *out, unsigned n) {
    tr_static_init();
    const int *src_i = 0; const uch *src_u = 0; unsigned cap = 0;
    switch (which) {
        case 0: src_i = extra_lbits; cap = LENGTH_CODES; break;
        case 1: src_i = extra_dbits; cap = D_CODES; break;
        case 2: src_i = extra_blbits; cap = BL_CODES; break;
        case 3: src_i = (const int *)0; cap = LENGTH_CODES; break; /* base_length: int[] */
        case 4: src_i = (const int *)0; cap = D_CODES; break;      /* base_dist */
        case 5: src_u = bl_order; cap = BL_CODES; break;
        default: return 0;
    }
    if (n < cap) cap = n;
    for (unsigned i = 0; i < cap; i++) {
        if (which == 3) out[i] = base_length[i];
        else if (which == 4) out[i] = base_dist[i];
        else if (src_u) out[i] = (int)src_u[i];
        else out[i] = src_i[i];
    }
    return cap;
}
/* gen_bitlen(s, desc): from a merged heap (heap[heap_max..HEAP_SIZE] in
   ascending-frequency order, tree.Dad set, tree.Freq set, desc.max_code)
   assigns bit lengths (tree.Len via dl), fills bl_count, and accumulates
   opt_len/static_len. The Python fuzzer supplies the pre-merge state (heap,
   heap_max, Dad, Freq, max_code) validated against the full build_tree. */
EXPORT void shim_run_gen_bitlen(int which) {
    deflate_state *s = &g_state;
    shim_desc_setup();
    tree_desc *d = which == 1 ? &s->d_desc : (which == 2 ? &s->bl_desc : &s->l_desc);
    gen_bitlen(s, d);
}

/* ---------- Bitstream emission layer (compress_block / send_all_trees) ----
   compress_block replays the LZ77 symbol buffer (3 bytes/symbol: dist_lo,
   dist_hi, lc) through the literal/distance Huffman trees, emitting to
   pending. send_all_trees serializes the three trees' bit lengths. Both need
   tr_static_init (populates the length/dist code tables). */
#define SYM_BUF_SIZE 8192
static unsigned char g_sym_buf[SYM_BUF_SIZE];

EXPORT void shim_set_sym_buf(const unsigned char *buf, unsigned n) {
    deflate_state *s = &g_state;
    if (n > SYM_BUF_SIZE) n = SYM_BUF_SIZE;
    memcpy(g_sym_buf, buf, n);
    s->sym_buf = (uchf *)g_sym_buf;
    s->sym_next = n;
}
/* _length_code[0..255], _dist_code[0..511] — populated by tr_static_init. */
EXPORT void shim_length_code(unsigned char *out, unsigned n) {
    tr_static_init();
    for (unsigned i = 0; i < n && i < 256; i++) out[i] = _length_code[i];
}
EXPORT void shim_dist_code(unsigned char *out, unsigned n) {
    tr_static_init();
    for (unsigned i = 0; i < n && i < 512; i++) out[i] = _dist_code[i];
}
EXPORT void shim_run_compress_block(void) {
    deflate_state *s = &g_state;
    tr_static_init();
    compress_block(s, s->dyn_ltree, s->dyn_dtree);
}
EXPORT void shim_run_send_all_trees(int lcodes, int dcodes, int blcodes) {
    deflate_state *s = &g_state;
    tr_static_init();
    send_all_trees(s, lcodes, dcodes, blcodes);
}

/* Static descriptor scalars: extra_base, max_length, elems for l/d/bl. */
EXPORT void shim_static_desc(int which, int *extra_base, int *max_length, int *elems) {
    tr_static_init();
    const static_tree_desc *d = which == 1 ? &static_d_desc
                              : (which == 2 ? &static_bl_desc : &static_l_desc);
    *extra_base = d->extra_base; *max_length = d->max_length; *elems = d->elems;
}

/* detect_data_type returns Z_BINARY, Z_TEXT, or Z_UNKNOWN */
EXPORT int shim_run_detect_data_type_ret(void) {
    deflate_state *s = &g_state;
    return detect_data_type(s);
}
