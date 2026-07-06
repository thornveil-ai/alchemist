"""Auto-oracle generation (WS5) — turn a discovered C function into (a) a coherent
Rust signature and (b) a call in a differential harness, without a hand-written
setup script.

The intellectual core is **signature classification**: given C params like
`(const uint8_t *buf, uint32_t len, uint16_t crc)`, decide which is the input
BUFFER, which is its LENGTH, and which are scalar SEEDs. That mapping is what the
hand-written `setup_*.py` encoded by eye; here it's derived from the signature.

Scope: the byte-processing function class (buffer + length + optional scalars ->
scalar), which covers checksums, hashes, and codecs — the bulk of leaf C. Structs
and output-pointer params are future work (flagged, not guessed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from alchemist.autonomy.onboard import c_to_rust_scalar, CFunc

_LEN_NAMES = {"len", "length", "size", "count", "n", "num", "nbytes", "buf_len",
              "buflen", "datalen", "num_words", "numwords", "sz", "cnt"}


@dataclass
class Param:
    role: str      # "buffer" | "len" | "scalar" | "unknown"
    c_type: str
    name: str
    rust_type: str  # meaningful for scalar/len


@dataclass
class CallSpec:
    func: str
    params: list[Param]
    ret_rust: str

    @property
    def supported(self) -> bool:
        """True iff every param classified cleanly (no structs / out-pointers)."""
        return all(p.role != "unknown" for p in self.params) and \
            any(p.role == "buffer" for p in self.params)


def _split_params(params: str) -> list[str]:
    params = params.strip()
    if not params or params == "void":
        return []
    return [p.strip() for p in params.split(",") if p.strip()]


def _name_and_type(param: str) -> tuple[str, str]:
    """`const uint8_t *buf` -> (type='const uint8_t *', name='buf'). Strips a
    default-argument (`= 0`) if present."""
    param = param.split("=")[0].strip()
    m = re.search(r"([A-Za-z_]\w*)\s*$", param)
    name = m.group(1) if m else ""
    c_type = param[: m.start()].strip() if m else param
    return name, c_type


def classify_signature(cfunc: CFunc) -> CallSpec:
    parts = _split_params(cfunc.params)
    out: list[Param] = []
    for p in parts:
        name, c_type = _name_and_type(p)
        is_ptr = "*" in p
        if is_ptr:
            # A byte input buffer is a CONST pointer to a byte-width type
            # (uint8_t/char/void). A wider pointer (uint32_t*), a mutable byte
            # pointer (out-param), or a struct pointer is NOT — flag unknown.
            byte_ptr = bool(re.search(r"\b(char|uint8_t|u8|void)\b", c_type))
            if byte_ptr and "const" in c_type:
                out.append(Param("buffer", c_type, name, "u8"))
            else:
                out.append(Param("unknown", c_type, name, "u8"))
        elif name.lower() in _LEN_NAMES and any(q.role == "buffer" for q in out):
            out.append(Param("len", c_type, name, c_to_rust_scalar(c_type)))
        else:
            out.append(Param("scalar", c_type, name, c_to_rust_scalar(c_type)))
    return CallSpec(cfunc.name, out, c_to_rust_scalar(cfunc.ret))


def rust_signature(spec: CallSpec) -> str:
    """Coherent Rust signature: buffer+len collapse to one `&[u8]`; scalars stay."""
    args: list[str] = []
    buffer_done = False
    for p in spec.params:
        if p.role == "buffer":
            if not buffer_done:
                args.append("data: &[u8]")
                buffer_done = True
        elif p.role == "len":
            continue  # folded into data.len()
        elif p.role == "scalar":
            args.append("%s: %s" % (p.name, p.rust_type))
    return "pub fn %s(%s) -> %s" % (spec.func, ", ".join(args), spec.ret_rust)


def c_call_args(spec: CallSpec, buf_expr: str = "in", len_expr: str = "l",
                scalar_expr: str = "0") -> str:
    """The C argument list to invoke the function in the harness."""
    out = []
    for p in spec.params:
        if p.role == "buffer":
            out.append(buf_expr)
        elif p.role == "len":
            out.append(len_expr)
        else:
            out.append(scalar_expr)
    return ", ".join(out)


def rust_call(spec: CallSpec, input_bytes: bytes, scalar: str = "0") -> str:
    """A Rust call expression for a differential test: buffer -> byte-slice
    literal, len folded away, scalars default to `scalar`."""
    slice_lit = "&[" + ", ".join(str(b) for b in input_bytes) + "]"
    args = []
    for p in spec.params:
        if p.role == "buffer":
            args.append(slice_lit)
        elif p.role == "len":
            continue
        elif p.role == "scalar":
            args.append(scalar)
    return "%s(%s)" % (spec.func, ", ".join(args))


def generate_c_harness(specs: list[CallSpec], header: str) -> str:
    """A dispatch `main()` — argv[1] names the function, stdin is the byte buffer,
    scalars default to 0, result printed as an unsigned integer."""
    calls = "\n".join(
        '    if(!strcmp(n,"%s")) { printf("%%llu",(unsigned long long)%s(%s)); return 0; }'
        % (s.func, s.func, c_call_args(s))
        for s in specs if s.supported
    )
    return (
        '#include <cstdio>\n#include <cstring>\n#include <cstdint>\n#include "%s"\n'
        "int main(int argc, char** argv){\n"
        "  const char* n = argv[1]; static uint8_t in[65536];\n"
        "  uint32_t l = (uint32_t)fread(in, 1, sizeof(in), stdin);\n"
        "%s\n  return 1;\n}\n" % (header, calls)
    )
