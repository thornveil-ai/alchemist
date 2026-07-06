"""Stateful init/update/final onboarding — detection + struct/signature emission.

End-to-end (build + fill + deep fuzz) runs on the box; here we lock the logic.
"""

from alchemist.autonomy.onboard import discover_functions
from alchemist.autonomy.stateful import (
    resolve_typedefs, parse_ctx_fields, emit_ctx_struct, detect_stateful_api,
    stateful_signature, rust_struct_name, generate_sequence_harness,
)

SHA_LIKE = """
typedef unsigned char BYTE;
typedef unsigned int WORD;
#define SHA256_BLOCK_SIZE 32
typedef struct {
    BYTE data[64];
    WORD datalen;
    unsigned long long bitlen;
    WORD state[8];
} SHA256_CTX;
void sha256_transform(SHA256_CTX *ctx, const BYTE data[]) { }
void sha256_init(SHA256_CTX *ctx) { }
void sha256_update(SHA256_CTX *ctx, const BYTE data[], size_t len) { sha256_transform(ctx, data); }
void sha256_final(SHA256_CTX *ctx, BYTE hash[]) { sha256_transform(ctx, ctx->data); }
"""


def _api():
    funcs = discover_functions(SHA_LIKE)
    return funcs, detect_stateful_api(funcs, {"SHA256_BLOCK_SIZE": 32},
                                      resolve_typedefs(SHA_LIKE))


def test_resolve_typedefs():
    td = resolve_typedefs(SHA_LIKE)
    assert td["BYTE"] == "unsigned char" and td["WORD"] == "unsigned int"


def test_rust_struct_name():
    assert rust_struct_name("SHA256_CTX") == "Sha256Ctx"


def test_parse_ctx_fields_keeps_arrays():
    td = resolve_typedefs(SHA_LIKE)
    fields = parse_ctx_fields(SHA_LIKE, "SHA256_CTX", td, {})
    by = {f.name: f.rust_type for f in fields}
    assert by == {"data": "[u8; 64]", "datalen": "u32",
                  "bitlen": "u64", "state": "[u32; 8]"}


def test_emit_ctx_struct_has_default():
    td = resolve_typedefs(SHA_LIKE)
    fields = parse_ctx_fields(SHA_LIKE, "SHA256_CTX", td, {})
    rs = emit_ctx_struct("Sha256Ctx", fields)
    assert "pub struct Sha256Ctx" in rs
    assert "pub data: [u8; 64]," in rs
    assert "data: [0; 64]" in rs   # Default fills arrays > 32


def test_detect_stateful_api():
    funcs, api = _api()
    assert api is not None
    assert api.ctx_c == "SHA256_CTX" and api.ctx_rust == "Sha256Ctx"
    assert api.init == "sha256_init"
    assert api.update == "sha256_update"
    assert api.final == "sha256_final"
    assert "sha256_transform" in api.helpers
    assert api.digest_len == 32


def test_stateful_signatures():
    funcs, api = _api()
    assert stateful_signature("sha256_init", funcs, api) == "pub fn sha256_init(ctx: &mut Sha256Ctx)"
    assert stateful_signature("sha256_update", funcs, api) == "pub fn sha256_update(ctx: &mut Sha256Ctx, data: &[u8])"
    # final's `BYTE hash[]` out-buffer -> Vec return
    assert stateful_signature("sha256_final", funcs, api) == "pub fn sha256_final(ctx: &mut Sha256Ctx) -> Vec<u8>"


def test_macro_helpers_expression_vs_statement():
    from alchemist.autonomy.stateful import emit_macro_helpers
    src = (
        "#define F(x,y,z) (((x) & (y)) | (~(x) & (z)))\n"
        "#define ROTLEFT(a,b) (((a) << (b)) | ((a) >> (32-(b))))\n"
        "#define FF(a,b,c,d,m,s,t) { \\\n"
        "  (a) += F((b),(c),(d)) + (m) + (t); \\\n"
        "  (a) = ROTLEFT((a),(s)) + (b); }\n"
    )
    helpers, names = emit_macro_helpers(src)
    # expression macros become fns; the mutating block macro FF is skipped (inlined)
    assert "F" in names and "ROTLEFT" in names
    assert "FF" not in names
    assert "unclosed" not in helpers and "\\" not in helpers  # no continuation leak
    assert "rotate_left" in helpers


def test_sequence_harness_runs_the_trio():
    funcs, api = _api()
    h = generate_sequence_harness(api, funcs, ["sha256.h"])
    assert "sha256_init(&ctx)" in h
    assert "sha256_update(&ctx, in, n)" in h
    assert "sha256_final(&ctx, out)" in h
    assert "fwrite(out,1,32,stdout)" in h
