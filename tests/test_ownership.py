"""Pillar 6 — memory-ownership translation: heap detection + ownership-typed sigs.

The end-to-end (malloc-return C -> owned Vec<u8>, contents byte-exact across 40
vectors, zero unsafe, Miri: zero UB) is proven on the box; here we lock the
detection and the ownership-typed signature inference.
"""

from alchemist.autonomy.onboard import discover_functions
from alchemist.autonomy.ownership import detect_heap_api, owned_signatures

HEAP = ("unsigned char *make(unsigned long n, unsigned char f) {\n"
        "    unsigned char *p = malloc(n);\n"
        "    for (unsigned long i = 0; i < n; i++) p[i] = f;\n"
        "    return p;\n}\n"
        "void freeit(unsigned char *p) { free(p); }\n")


def test_detect_allocate_return_and_free():
    api = detect_heap_api(discover_functions(HEAP))
    assert api is not None
    assert api.alloc.name == "make" and api.alloc.size_param == "n"
    assert api.alloc.elem_rust == "u8"
    assert api.free_fn == "freeit"


def test_ownership_typed_signatures():
    api = detect_heap_api(discover_functions(HEAP))
    sigs = owned_signatures(api)
    # allocator RETURNS an owned Vec (ownership out); size param -> usize
    assert sigs["make"] == "pub fn make(n: usize, f: u8) -> Vec<u8>"
    # free fn TAKES the Vec by value (ownership in -> dropped; C free becomes implicit)
    assert "(_buf: Vec<u8>)" in sigs["freeit"]


def test_no_heap_api_for_pure_function():
    assert detect_heap_api(discover_functions("int add(int a, int b) { return a + b; }")) is None


def test_classify_pointer_borrow_out_owned():
    from alchemist.autonomy.ownership import classify_pointer_param
    assert classify_pointer_param("h ^= in[i];", "in", is_const=True) == "borrow"   # const view
    assert classify_pointer_param("out[i] = x;", "out") == "out"                    # written buffer
    assert classify_pointer_param("free(p);", "p") == "owned"                       # freed -> owned


def test_infer_param_ownership_mixed_signature():
    from alchemist.autonomy.ownership import infer_param_ownership
    src = ("void proc(const unsigned char *in, unsigned long n, unsigned char *out) {\n"
           "    for (unsigned long i = 0; i < n; i++) out[i] = in[i] ^ 0xff;\n}\n")
    fn = discover_functions(src)["proc"]
    roles = {nm: (role, rty) for nm, role, rty in infer_param_ownership(fn)}
    assert roles["in"] == ("borrow", "&[u8]")     # const input -> borrowed view
    assert roles["out"] == ("out", "Vec<u8>")     # written output -> owned Vec
    assert roles["n"][0] == "scalar"


def test_detect_box_alloc_vs_buffer():
    from alchemist.autonomy.ownership import detect_box_alloc
    assert detect_box_alloc("struct Node *p = malloc(sizeof(struct Node));") == "Node"
    assert detect_box_alloc("Item *it = malloc(sizeof(Item));") == "Item"
    assert detect_box_alloc("char *buf = malloc(n);") is None      # buffer -> Vec, not Box


def test_struct_field_ownership_types():
    from alchemist.autonomy.ownership import struct_field_rust_type
    assert struct_field_rust_type("char *") == "String"            # owned C string
    assert struct_field_rust_type("unsigned char *") == "Vec<u8>"  # owned byte buffer
    assert struct_field_rust_type("struct Node *") == "Box<Node>"  # owned sub-object
    assert struct_field_rust_type("int") == "i32"                  # scalar unchanged


def test_multibuffer_signature_cipher_shape():
    from alchemist.autonomy.ownership import multibuffer_signature
    src = ("void xcrypt(const unsigned char *in, unsigned long n, "
           "const unsigned char *key, unsigned char *out) {\n"
           "    for (unsigned long i = 0; i < n; i++) out[i] = in[i] ^ key[i % 16];\n}\n")
    fn = discover_functions(src)["xcrypt"]
    sig = multibuffer_signature(fn)
    assert "in_: &[u8]" in sig and "key: &[u8]" in sig   # inputs borrowed; `in` keyword-escaped
    assert "-> Vec<u8>" in sig                           # output buffer returned
    assert " n:" not in sig                              # length dropped (implicit in slice)


def test_mode_cipher_element_aware_signature():
    from alchemist.autonomy.ownership import multibuffer_signature, detect_mode_cipher
    src = ("int aes_encrypt_cbc(const BYTE in[], size_t in_len, BYTE out[], "
           "const WORD key[], int keysize, const BYTE iv[]) {\n    out[0] = in[0] ^ iv[0];\n}\n")
    funcs = discover_functions(src)
    assert detect_mode_cipher(funcs) == "aes_encrypt_cbc"      # mode + 2+ buffers + key
    sig = multibuffer_signature(funcs["aes_encrypt_cbc"])
    assert "in_: &[u8]" in sig and "iv: &[u8]" in sig          # byte buffers -> &[u8]
    assert "key: &[u32]" in sig                                # WORD key -> &[u32] (element-aware)
    assert "-> Vec<u8>" in sig                                 # output buffer returned


def test_detect_mode_cipher_rejects_plain_hash():
    from alchemist.autonomy.ownership import detect_mode_cipher
    src = "void sha_update(struct Ctx *c, const BYTE d[], size_t n) {\n    c->x = d[0];\n}\n"
    assert detect_mode_cipher(discover_functions(src)) is None
