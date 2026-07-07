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
