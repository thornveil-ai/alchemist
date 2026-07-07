"""Item C — ingestion front-door + scope triage (the honesty layer)."""

from alchemist.autonomy.onboard import discover_functions
from alchemist.autonomy.ingest import scope_triage, triage_report

SRC = (
    "unsigned char *make(unsigned long n) {\n    unsigned char *p = malloc(n);\n    return p;\n}\n"
    "void log_line(const char *m) {\n    printf(\"%s\", m);\n}\n"
    "void run_cb(int (*cb)(int), int x) {\n    cb(x);\n}\n"
    "unsigned checksum(const unsigned char *d, unsigned long n) {\n"
    "    unsigned h = 0;\n    for (unsigned long i = 0; i < n; i++) h = h * 31u + d[i];\n    return h;\n}\n"
)


def _scopes():
    return {s.name: s for s in scope_triage(discover_functions(SRC))}


def test_heap_allocator_is_heap_scope():
    assert _scopes()["make"].scope == "heap"


def test_io_function_is_out_of_scope():
    s = _scopes()["log_line"]
    assert s.scope == "oos" and ("I/O" in s.reason or "syscall" in s.reason)


def test_function_pointer_param_is_out_of_scope():
    s = _scopes()["run_cb"]
    assert s.scope == "oos" and "function-pointer" in s.reason


def test_buffer_len_function_is_in_scope():
    assert _scopes()["checksum"].scope in ("scalar", "buffer")


def test_triage_report_counts_in_scope():
    rep = triage_report(scope_triage(discover_functions(SRC)))
    assert rep["total"] == 4
    assert rep["in_scope"] == 2          # make (heap) + checksum; log_line & run_cb are oos
    assert rep["by_scope"]["oos"] == 2


def test_complex_multibuffer_function_classified_complex():
    # AES-style: two buffers + a key + a size -> complex, not mislabelled scalar
    src = ("void aes_encrypt(const unsigned char in[], unsigned char out[], "
           "const unsigned int key[], int keysize) {\n    out[0] = in[0];\n}\n")
    s = {x.name: x for x in scope_triage(discover_functions(src))}["aes_encrypt"]
    assert s.scope == "complex"


def test_route_maps_scope_to_builder():
    from alchemist.autonomy.ingest import route
    assert route("heap") == "build_ownership_crate"
    assert route("stateful") == "build_stateful_crate"
    assert route("effectful") == "build_effectful_crate"
    assert route("oos") is None and route("complex") is None   # not auto-translatable
