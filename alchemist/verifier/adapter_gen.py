"""Emit the differential-adapter crate: safe c_*/rust_* wrappers.

The harnesses proptest_gen emits compare `rust_<algo>(&input)` against
`c_<algo>(&input)`. Those wrapper functions have to exist somewhere, and
they have to call the REAL generated Rust API — not an assumed one. This
module generates them:

  - `c_<algo>` wrappers wrap the raw `extern "C"` declarations the FFI
    crate (auto_ffi) exposes, with the standard seed for the algorithm.
  - `rust_<algo>` wrappers call the generated crates directly. The actual
    function and signature are DISCOVERED by scanning the generated
    workspace's sources for `pub fn` declarations, then adapting the
    harness shape (`&[u8]` in, checksum out) onto the discovered shape.

Fail-closed contract: a harness whose symbols can't be found, or whose
discovered signature has no known adapter, is reported as unresolved. The
caller (differential_tester) emits a FAILING test for it — the gate can go
red for that algorithm, but it can never silently skip it.

Wrappers return the FULL effect footprint of a call, not just the return
value: for pure checksums that is the return value; for out-param shapes
(compress/uncompress) the wrapper returns `(status, bytes)` so a status
mismatch or a buffer mismatch both fail the comparison.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from alchemist.verifier.proptest_gen import AlgorithmHarness


class AdapterError(Exception):
    """A harness symbol could not be adapted to the discovered API."""


# ---------------------------------------------------------------------------
# Generated-API discovery
# ---------------------------------------------------------------------------

@dataclass
class RustFn:
    name: str
    params: list[tuple[str, str]]      # (param_name, rust_type)
    ret: str                           # return type, "" for unit
    crate: str                         # Cargo package name (hyphens allowed)
    file: Path | None = None

    @property
    def crate_ident(self) -> str:
        return self.crate.replace("-", "_")


_PUB_FN = re.compile(
    r"^\s*pub\s+fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)\s*(?:->\s*([^{;]+))?\s*\{",
    re.MULTILINE,
)


def _parse_params(params: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    depth = 0
    buf: list[str] = []
    parts: list[str] = []
    for ch in params:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if ":" not in p:
            # `self` receivers etc. — record as-is with empty type
            out.append((p, ""))
            continue
        name, ty = p.split(":", 1)
        name = re.sub(r"^mut\s+", "", name.strip())
        out.append((name, _norm_type(ty)))
    return out


def _norm_type(ty: str) -> str:
    return re.sub(r"\s+", "", ty.strip())


def discover_rust_api(
    workspace: Path,
    *,
    packages: list[str] | None = None,
) -> dict[str, list[RustFn]]:
    """Scan member crates' sources for public function signatures.

    Returns EVERY definition per name (one entry per defining crate) — the
    resolver refuses ambiguous names instead of silently binding to whichever
    crate sorts first, which would let a shadowing crate produce a green
    differential run for code that was never exercised.

    `packages` restricts the scan to those crate dirs (matching the
    compile/test gate scoping). Test modules are skipped (everything
    at/after the first `#[cfg(test)]` in a file, matching how the test
    emitter appends test blocks).
    """
    api: dict[str, list[RustFn]] = {}
    workspace = Path(workspace)
    for cargo_toml in sorted(workspace.glob("*/Cargo.toml")):
        crate_dir = cargo_toml.parent
        if packages and crate_dir.name not in packages:
            continue
        m = re.search(r'^name\s*=\s*"([^"]+)"', cargo_toml.read_text(encoding="utf-8"),
                      re.MULTILINE)
        if not m:
            continue
        crate_name = m.group(1)
        for rs in sorted((crate_dir / "src").rglob("*.rs")):
            text = rs.read_text(encoding="utf-8", errors="replace")
            cut = text.find("#[cfg(test)]")
            if cut != -1:
                text = text[:cut]
            for fm in _PUB_FN.finditer(text):
                name = fm.group(1)
                defs = api.setdefault(name, [])
                if any(d.crate == crate_name for d in defs):
                    continue  # first definition per crate wins within a crate
                defs.append(RustFn(
                    name=name,
                    params=_parse_params(fm.group(2) or ""),
                    ret=_norm_type(fm.group(3) or ""),
                    crate=crate_name,
                    file=rs,
                ))
    return api


# ---------------------------------------------------------------------------
# Wrapper emission
# ---------------------------------------------------------------------------

@dataclass
class ResolvedAdapter:
    harness: AlgorithmHarness
    rust_wrapper: str
    c_wrapper: str
    rust_crates: set[str] = field(default_factory=set)   # package names used
    # Human-readable binding, e.g. "adler32 -> zlib_checksum::adler32_z".
    # Surfaced in the gate summary so a reviewer can see WHAT was compared.
    resolution: str = ""


@dataclass
class AdapterPlan:
    resolved: list[ResolvedAdapter] = field(default_factory=list)
    unresolved: list[tuple[AlgorithmHarness, str]] = field(default_factory=list)

    @property
    def rust_crates(self) -> set[str]:
        out: set[str] = set()
        for r in self.resolved:
            out |= r.rust_crates
        return out


_BYTESLICE = "&[u8]"
_INT32 = {"u32", "i32"}
_LEN_TYPES = {"usize", "u32", "u64", "uInt", "c_uint"}

# Candidate generated-fn names per compression side. The harness algorithm
# name ("deflate") names the ALGORITHM; the API functions carry zlib's
# public names.
_COMPRESS_CANDIDATES = ["compress", "compress_z"]
_DECOMPRESS_CANDIDATES = ["uncompress", "uncompress_z", "decompress"]

_CALL_IDENT = re.compile(r"^\s*(\w+)\s*\(")


def _call_ident(expr: str, what: str) -> str:
    """Leading identifier of a harness call expression (the wrapper name)."""
    m = _CALL_IDENT.match(expr or "")
    if not m:
        raise AdapterError(f"cannot parse wrapper name from {what} expression {expr!r}")
    return m.group(1)


def _resolve_checksum_rust(
    h: AlgorithmHarness, api: dict[str, list[RustFn]],
) -> tuple[str, RustFn]:
    """Build the body of `rust_<algo>(data: &[u8]) -> u32` from the real API."""
    seed = h.seed or 0
    candidates = [h.algorithm, f"{h.algorithm}_z"]
    tried: list[str] = []
    for cand in candidates:
        fn = _pick_unambiguous(cand, api)
        if fn is None:
            tried.append(f"{cand}: not found")
            continue
        tys = [t for _, t in fn.params]
        path = f"{fn.crate_ident}::{fn.name}"
        if fn.ret not in _INT32:
            tried.append(f"{cand}: returns {fn.ret or '()'}, need u32")
            continue
        if len(tys) == 3 and tys[0] in _INT32 and tys[1] == _BYTESLICE and tys[2] == "usize":
            return f"{path}({seed}u32, data, data.len())", fn
        if len(tys) == 2 and tys[0] in _INT32 and tys[1] == _BYTESLICE:
            return f"{path}({seed}u32, data)", fn
        if len(tys) == 1 and tys[0] == _BYTESLICE:
            return f"{path}(data)", fn
        tried.append(f"{cand}: no adapter for signature ({', '.join(tys)}) -> {fn.ret}")
    raise AdapterError(
        f"cannot adapt rust side of '{h.algorithm}' (category {h.category}): "
        + "; ".join(tried)
    )


def _resolve_checksum_c(h: AlgorithmHarness, ffi_crate: str, c_fn_names: set[str]) -> str:
    seed = h.seed or 0
    if h.algorithm not in c_fn_names:
        raise AdapterError(
            f"C reference does not export '{h.algorithm}' "
            f"(available: {', '.join(sorted(c_fn_names)) or 'none'})"
        )
    # Raw extern shape (auto_ffi): fn <name>(seed: c_ulong, buf: *const c_uchar,
    # len: c_uint) -> c_ulong. `as _` casts infer from the extern declaration.
    return (
        f"unsafe {{ {ffi_crate}::{h.algorithm}({seed} as _, data.as_ptr(), "
        f"data.len() as _) as u32 }}"
    )


def _pick_unambiguous(name: str, api: dict[str, list[RustFn]]) -> RustFn | None:
    defs = api.get(name) or []
    if len(defs) > 1:
        crates = ", ".join(sorted(d.crate for d in defs))
        raise AdapterError(
            f"'{name}' is defined in multiple crates ({crates}) — ambiguous "
            f"binding refused; scope the run with packages=[...] or rename"
        )
    return defs[0] if defs else None


def _resolve_compression_side(
    candidates: list[str],
    api: dict[str, list[RustFn]],
    *,
    wrapper_name: str,
    is_compress: bool,
) -> tuple[str, RustFn]:
    """Emit a full-footprint wrapper `(i32, Vec<u8>)` for one compression side.

    Status mapping: Ok → 0; Err → -1000, a sentinel meaning "generated error
    enum not yet code-mapped". The harness asserts SUCCESS parity (status==0
    vs status==0), so the sentinel never masquerades as a specific zlib code.
    """
    tried: list[str] = []
    for cand in candidates:
        fn = _pick_unambiguous(cand, api)
        if fn is None:
            tried.append(f"{cand}: not found")
            continue
        tys = [t for _, t in fn.params]
        path = f"{fn.crate_ident}::{fn.name}"
        # zlib out-param shape: (dest, dest_len, source, source_len) -> Result<(), E>
        if (len(tys) == 4 and tys[0] == "&mut[u8]" and tys[1] == "&mutusize"
                and tys[2] == _BYTESLICE and tys[3] == "usize"
                and fn.ret.startswith("Result<()")):
            if is_compress:
                alloc = "vec![0u8; data.len() + data.len() / 1000 + 64]"
                sig = f"pub fn {wrapper_name}(data: &[u8]) -> (i32, Vec<u8>)"
            else:
                alloc = "vec![0u8; cap]"
                sig = f"pub fn {wrapper_name}(data: &[u8], cap: usize) -> (i32, Vec<u8>)"
            body = (
                f"/// Full effect footprint of {fn.crate}::{fn.name}: status + output\n"
                f"/// buffer as written (truncated to the reported length).\n"
                f"{sig} {{\n"
                f"    let mut dest = {alloc};\n"
                f"    let mut dest_len = dest.len();\n"
                f"    let status = match {path}(&mut dest, &mut dest_len, data, data.len()) {{\n"
                f"        Ok(()) => 0,\n"
                f"        Err(_) => -1000, // generated error enum not yet code-mapped\n"
                f"    }};\n"
                f"    dest.truncate(dest_len);\n"
                f"    (status, dest)\n"
                f"}}\n"
            )
            return body, fn
        # Owning shape: (&[u8]) -> Result<Vec<u8>, E>
        if (len(tys) == 1 and tys[0] == _BYTESLICE
                and fn.ret.startswith("Result<Vec<u8>")):
            sig = (f"pub fn {wrapper_name}(data: &[u8]) -> (i32, Vec<u8>)"
                   if is_compress else
                   f"pub fn {wrapper_name}(data: &[u8], cap: usize) -> (i32, Vec<u8>)")
            extra = "" if is_compress else "    let _ = cap;\n"
            body = (
                f"/// Full effect footprint of {fn.crate}::{fn.name}.\n"
                f"{sig} {{\n"
                f"{extra}"
                f"    match {path}(data) {{\n"
                f"        Ok(v) => (0, v),\n"
                f"        Err(_) => (-1000, Vec::new()), // error enum not yet code-mapped\n"
                f"    }}\n"
                f"}}\n"
            )
            return body, fn
        tried.append(f"{cand}: no adapter for signature ({', '.join(tys)}) -> {fn.ret}")
    raise AdapterError(
        f"cannot adapt {'compress' if is_compress else 'decompress'} side: "
        + "; ".join(tried)
    )


def _c_compression_wrapper(
    wrapper_name: str,
    c_fn: str,
    ffi_ident: str,
    c_fn_names: set[str],
    *,
    is_compress: bool,
) -> str:
    if c_fn not in c_fn_names:
        raise AdapterError(
            f"C reference does not export '{c_fn}' "
            f"(available: {', '.join(sorted(c_fn_names)) or 'none'})"
        )
    if is_compress:
        return (
            f"pub fn {wrapper_name}(data: &[u8]) -> (i32, Vec<u8>) {{\n"
            f"    let mut dest = vec![0u8; data.len() + data.len() / 1000 + 64];\n"
            f"    let mut dest_len = dest.len() as std::os::raw::c_ulong;\n"
            f"    let rc = unsafe {{\n"
            f"        {ffi_ident}::{c_fn}(dest.as_mut_ptr(), &mut dest_len,\n"
            f"                            data.as_ptr(), data.len() as _)\n"
            f"    }};\n"
            f"    dest.truncate(dest_len as usize);\n"
            f"    (rc as i32, dest)\n"
            f"}}\n"
        )
    return (
        f"pub fn {wrapper_name}(data: &[u8], cap: usize) -> (i32, Vec<u8>) {{\n"
        f"    let mut dest = vec![0u8; cap];\n"
        f"    let mut dest_len = cap as std::os::raw::c_ulong;\n"
        f"    let rc = unsafe {{\n"
        f"        {ffi_ident}::{c_fn}(dest.as_mut_ptr(), &mut dest_len,\n"
        f"                            data.as_ptr(), data.len() as _)\n"
        f"    }};\n"
        f"    dest.truncate(dest_len as usize);\n"
        f"    (rc as i32, dest)\n"
        f"}}\n"
    )


def plan_adapters(
    harnesses: list[AlgorithmHarness],
    *,
    rust_workspace: Path,
    ffi_crate_name: str,
    c_fn_names: set[str],
    packages: list[str] | None = None,
) -> AdapterPlan:
    """Resolve every harness against the discovered Rust API and C exports.

    Unresolvable harnesses are collected, not raised: the caller emits
    failing tests for them so the gate stays red without hiding the ones
    that CAN be verified. `packages` restricts API discovery to the same
    crates the compile/test gates are scoped to.
    """
    api = discover_rust_api(rust_workspace, packages=packages)
    ffi_ident = ffi_crate_name.replace("-", "_")
    plan = AdapterPlan()
    for h in harnesses:
        try:
            if h.category in ("checksum", "hash"):
                rust_body, fn = _resolve_checksum_rust(h, api)
                c_body = _resolve_checksum_c(h, ffi_ident, c_fn_names)
                rust_wrapper = (
                    f"/// Full effect footprint of {fn.crate}::{fn.name}: pure fn, "
                    f"footprint == return value.\n"
                    f"pub fn rust_{h.algorithm}(data: &[u8]) -> u32 {{\n"
                    f"    {rust_body}\n"
                    f"}}\n"
                )
                c_wrapper = (
                    f"pub fn c_{h.algorithm}(data: &[u8]) -> u32 {{\n"
                    f"    {c_body}\n"
                    f"}}\n"
                )
                plan.resolved.append(ResolvedAdapter(
                    harness=h,
                    rust_wrapper=rust_wrapper,
                    c_wrapper=c_wrapper,
                    rust_crates={fn.crate},
                    resolution=f"{h.algorithm} -> {fn.crate_ident}::{fn.name}",
                ))
            elif h.category in ("compression", "decompression"):
                rust_c_name = _call_ident(h.rust_call, "rust_call")
                rust_d_name = _call_ident(h.rust_decompress_call or "",
                                          "rust_decompress_call")
                c_c_name = _call_ident(h.c_call, "c_call")
                c_d_name = _call_ident(h.c_decompress_call or "",
                                       "c_decompress_call")
                comp_body, comp_fn = _resolve_compression_side(
                    _COMPRESS_CANDIDATES, api,
                    wrapper_name=rust_c_name, is_compress=True,
                )
                decomp_body, decomp_fn = _resolve_compression_side(
                    _DECOMPRESS_CANDIDATES, api,
                    wrapper_name=rust_d_name, is_compress=False,
                )
                c_comp = _c_compression_wrapper(
                    c_c_name, c_c_name.removeprefix("c_"), ffi_ident,
                    c_fn_names, is_compress=True,
                )
                c_decomp = _c_compression_wrapper(
                    c_d_name, c_d_name.removeprefix("c_"), ffi_ident,
                    c_fn_names, is_compress=False,
                )
                plan.resolved.append(ResolvedAdapter(
                    harness=h,
                    rust_wrapper=comp_body + "\n" + decomp_body,
                    c_wrapper=c_comp + "\n" + c_decomp,
                    rust_crates={comp_fn.crate, decomp_fn.crate},
                    resolution=(
                        f"{h.algorithm} -> {comp_fn.crate_ident}::{comp_fn.name} "
                        f"+ {decomp_fn.crate_ident}::{decomp_fn.name}"
                    ),
                ))
            else:
                raise AdapterError(
                    f"no adapter template for category '{h.category}' yet — "
                    f"refusing to fake one"
                )
        except AdapterError as e:
            plan.unresolved.append((h, str(e)))
    return plan


def emit_adapter_lib(
    plan: AdapterPlan,
    *,
    ffi_crate_name: str,
) -> str:
    """Emit the diff crate's src/lib.rs with all resolved wrappers."""
    ffi_ident = ffi_crate_name.replace("-", "_")
    lines: list[str] = [
        "//! Auto-generated differential adapter (alchemist.verifier.adapter_gen).",
        "//!",
        "//! Bridges the generated Rust workspace and the compiled C reference so",
        "//! proptest harnesses compare the same shapes. Regenerated on every",
        "//! verify run — do not hand-edit.",
        "",
        "#![allow(dead_code)]",
        "",
        "// -------- C reference wrappers --------",
        "",
    ]
    for r in plan.resolved:
        lines.append(r.c_wrapper)
    lines.append("// -------- Generated-Rust wrappers --------")
    lines.append("")
    for r in plan.resolved:
        lines.append(r.rust_wrapper)
    return "\n".join(lines)


def _rust_string_safe(s: str) -> str:
    """Escape a message for interpolation into a panic!() format literal."""
    return (
        s.replace("\\", "\\\\")
        .replace('"', "'")
        .replace("{", "{{")
        .replace("}", "}}")
    )


def emit_unresolved_tests(plan: AdapterPlan) -> str:
    """Emit a failing #[test] per unresolved harness (fail-closed)."""
    blocks: list[str] = []
    for h, reason in plan.unresolved:
        safe = _rust_string_safe(reason)
        blocks.append(
            f"#[test]\n"
            f"fn {h.algorithm}_adapter_unresolved() {{\n"
            f"    panic!(\"ADAPTER UNRESOLVED for '{h.algorithm}': {safe} — this "
            f"algorithm was NOT differentially verified. Refusing to pass.\");\n"
            f"}}\n"
        )
    return "\n".join(blocks)
