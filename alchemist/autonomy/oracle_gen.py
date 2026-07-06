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
# names that mark a MUTABLE byte pointer as the OUTPUT buffer (vs an in/out we
# won't guess). Conservative on purpose: mis-reading an input as output is worse
# than skipping.
_OUT_NAMES = {"out", "dst", "dest", "output", "result", "obuf", "outbuf",
              "out_buf", "dest_buf", "o", "encoded", "decoded", "digest", "hash"}


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
    ret_void: bool = False

    @property
    def supported(self) -> bool:
        """True iff every param classified cleanly and there's a byte buffer to
        drive (input or output). An output buffer with a VOID return and no
        out-length pointer is NOT supported — we can't size the output, so we'd
        have no honest oracle (murmur3's `f(key,len,seed,out)` writes a fixed but
        undeclared N bytes)."""
        if not (all(p.role != "unknown" for p in self.params)
                and any(p.role in ("buffer", "out_buffer") for p in self.params)):
            return False
        if self.buffer_output and self.ret_void and not self.has_out_len:
            return False
        return True

    @property
    def buffer_output(self) -> bool:
        """The function writes its result into a caller-provided byte buffer;
        the coherent Rust returns a `Vec<u8>` and the C length-return is dropped."""
        return any(p.role == "out_buffer" for p in self.params)

    @property
    def has_out_len(self) -> bool:
        return any(p.role == "out_length_ptr" for p in self.params)

    @property
    def rust_ret(self) -> str:
        return "Vec<u8>" if self.buffer_output else self.ret_rust


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


def _resolve_typedefs_in(text: str, typedefs: dict) -> str:
    if not typedefs:
        return text

    def rep(m):
        w = m.group(0)
        seen: set = set()
        while w in typedefs and w not in seen:
            seen.add(w)
            w = typedefs[w]
        return w
    return re.sub(r"\b[A-Za-z_]\w*\b", rep, text)


def classify_signature(cfunc: CFunc, typedefs: dict | None = None) -> CallSpec:
    parts = _split_params(cfunc.params)
    out: list[Param] = []
    for p in parts:
        # array-syntax params decay to pointers: `const BYTE data[]` -> `const BYTE * data`
        p = re.sub(r"([A-Za-z_]\w*)\s*\[\s*\w*\s*\]", r"* \1", p)
        name, c_type = _name_and_type(p)
        # resolve typedef'd byte types (BYTE -> unsigned char) for detection
        c_type = _resolve_typedefs_in(c_type, typedefs or {})
        is_ptr = "*" in p
        if is_ptr:
            # A byte INPUT buffer is a CONST pointer to a byte-width type
            # (uint8_t/char/void). A MUTABLE byte pointer named like an output
            # (out/dst/digest/...) is the OUTPUT buffer. Wider pointers
            # (uint32_t*), unnamed-as-output mutable pointers, and struct
            # pointers we don't guess -> unknown.
            byte_ptr = bool(re.search(r"\b(char|uint8_t|u8|void)\b", c_type))
            if byte_ptr and "const" in c_type:
                out.append(Param("buffer", c_type, name, "u8"))
            elif byte_ptr and name.lower() in _OUT_NAMES:
                out.append(Param("out_buffer", c_type, name, "u8"))
            elif (re.search(r"\b(int|size_t|unsigned|uint\d+_t|long|size)\b", c_type)
                  and (name.lower() in _LEN_NAMES
                       or re.search(r"(len|size|count)$", name.lower()))):
                # pointer to an integer named like a length = OUTPUT length pointer
                out.append(Param("out_length_ptr", c_type, name, "usize"))
            else:
                out.append(Param("unknown", c_type, name, "u8"))
        elif (name.lower() in _LEN_NAMES
              or re.search(r"(len|size|count|bytes|words)$", name.lower())) \
                and any(q.role in ("buffer", "out_buffer") for q in out):
            out.append(Param("len", c_type, name, c_to_rust_scalar(c_type)))
        else:
            out.append(Param("scalar", c_type, name, c_to_rust_scalar(c_type)))
    return CallSpec(cfunc.name, out, c_to_rust_scalar(cfunc.ret),
                    ret_void=bool(re.match(r"^\s*(static\s+|inline\s+)*void\b", cfunc.ret or "")))


def rust_signature(spec: CallSpec) -> str:
    """Coherent Rust signature: buffer+len collapse to one `&[u8]`; scalars stay;
    an output buffer becomes a `Vec<u8>` RETURN (the C length-return is dropped)."""
    args: list[str] = []
    buffer_done = False
    for p in spec.params:
        if p.role == "buffer":
            if not buffer_done:
                args.append("data: &[u8]")
                buffer_done = True
        elif p.role in ("len", "out_buffer", "out_length_ptr"):
            continue  # len -> data.len(); out_buffer -> return; out-length -> Vec len
        elif p.role == "scalar":
            args.append("%s: %s" % (p.name, p.rust_type))
    return "pub fn %s(%s) -> %s" % (spec.func, ", ".join(args), spec.rust_ret)


def c_call_args(spec: CallSpec, buf_expr: str = "in", len_expr: str = "l",
                scalar_expr: str = "0", out_expr: str = "outbuf") -> str:
    """The C argument list to invoke the function in the harness."""
    out = []
    for p in spec.params:
        if p.role == "buffer":
            out.append("(%s)%s" % (p.c_type.strip(), buf_expr))  # cast: char* vs uint8_t*
        elif p.role == "len":
            out.append(len_expr)
        elif p.role == "out_buffer":
            out.append("(%s)%s" % (p.c_type.strip(), out_expr))
        elif p.role == "out_length_ptr":
            out.append("(%s)&__ol" % p.c_type.strip())
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


def generate_c_harness(specs: list[CallSpec], header) -> str:
    """A dispatch `main()` — argv[1] names the function, stdin is the input byte
    buffer, scalars default to 0. A scalar-return function prints its value; an
    output-buffer function writes the produced bytes (length = the C return).

    `header` is a header name or a list of header names to `#include`."""
    headers = [header] if isinstance(header, str) else list(header)
    includes = "".join('#include "%s"\n' % h for h in headers)
    lines = []
    for s in specs:
        if not s.supported:
            continue
        if s.buffer_output and s.has_out_len:
            # output length is written through a pointer arg, not the return value
            call = ("    if(!strcmp(n,\"%s\")) { unsigned long __ol=0; %s(%s); "
                    "fwrite(outbuf,1,(size_t)__ol,stdout); return 0; }"
                    % (s.func, s.func, c_call_args(s)))
        elif s.buffer_output:
            call = ("    if(!strcmp(n,\"%s\")) { unsigned long long m=(unsigned long long)%s(%s); "
                    "fwrite(outbuf,1,(size_t)m,stdout); return 0; }"
                    % (s.func, s.func, c_call_args(s)))
        else:
            call = ('    if(!strcmp(n,"%s")) { printf("%%llu",(unsigned long long)%s(%s)); return 0; }'
                    % (s.func, s.func, c_call_args(s)))
        lines.append(call)
    return (
        '#include <cstdio>\n#include <cstring>\n#include <cstdint>\n%s'
        "int main(int argc, char** argv){\n"
        "  const char* n = argv[1]; static uint8_t in[65536]; static uint8_t outbuf[262144];\n"
        "  uint32_t l = (uint32_t)fread(in, 1, sizeof(in), stdin);\n"
        "%s\n  return 1;\n}\n" % (includes, "\n".join(lines))
    )
