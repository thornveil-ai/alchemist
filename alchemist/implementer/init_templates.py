"""Deterministic templates for init/reset functions.

Init functions like `deflateInit_`, `inflateReset`, `_tr_init`, and
`tr_static_init` fail LLM generation consistently — they allocate and
configure 30+ struct fields, which the model either stubs or mis-fills.

This module generates these functions from the struct's Default impl
plus explicit field overrides. The output is always valid Rust, always
compiles, and always matches the declared struct schema.

Invocation path: TDDGenerator._prompt_for_impl detects init/reset patterns
in the function name and returns pre-baked code instead of calling LLM.
"""

from __future__ import annotations

import re

from alchemist.extractor.schemas import AlgorithmSpec


# Only truly empty/reset functions get the blanket-default template.
# Init functions that take real parameters (e.g., deflateInit2_ with level,
# windowBits, memLevel, strategy) set specific fields and CANNOT be served
# by `*state = Default::default()` — those now go through the reference
# probe instead. Narrowing this list is a P1 compliance fix.
_RESET_ONLY_PATTERNS = [
    r"^\w*[Rr]eset\d*$",        # inflateReset, deflateReset, inflateReset2
    r"^\w*[Rr]esetKeep$",       # inflateResetKeep
    r"^_tr_init$",              # zlib: local; zeroes internal counts
    r"^tr_static_init$",        # zlib: no-op after static init table cached
    r"^init_block$",            # zlib: zeros a handful of counts
]

# Lazy static-table initializers (e.g. crc32_init_table): in C they fill a
# file-scope static table on first use; the safe-Rust translation has no
# mutable global, so every caller computes/holds its own table and the
# initializer's entire observable effect disappears. A no-op is the correct
# and COMPLETE translation — not a stub — provided the function takes no
# inputs and returns nothing observable.
_TABLE_INIT_PATTERNS = [
    r".*init.*table.*",
    r".*table.*init.*",
    r".*make_?crc_?table.*",
]


def is_noop_table_init(alg) -> bool:
    """True iff `alg` is a zero-input, void-return static-table initializer
    whose only C effect was populating a file-scope static."""
    name = alg.name
    if alg.inputs:
        return False
    ret = (alg.return_type or "()").strip()
    if ret not in ("", "()"):
        return False
    lowered = name.lower()
    return any(re.match(p, lowered) for p in _TABLE_INIT_PATTERNS)


def noop_table_init_template(alg) -> str | None:
    """Emit the no-op translation for a static-table initializer."""
    if not is_noop_table_init(alg):
        return None
    return (
        f"pub fn {alg.name}() {{\n"
        f"    // The C original populated a file-scope static lookup table on\n"
        f"    // first use. This safe-Rust translation has no mutable global;\n"
        f"    // each consumer computes the table it needs, so initialization\n"
        f"    // is a no-op here.\n"
        f"}}"
    )


_FREE_CALL_RE = re.compile(
    r"^(free|cfree|kfree|vfree|xfree|g_free|\w+_(free|destroy|release|dispose|cleanup))"
    r"\s*\(.*\)$", re.IGNORECASE)


def free_noop_template(alg, source_root) -> str | None:
    """A `void free_X(ptr)` whose C body is ONLY deallocation calls is a no-op in
    safe Rust — an owned buffer (Vec/Box) drops automatically. Accept it as an
    empty body ONLY when the C body CONFIRMS pure deallocation (fail-closed: any
    other statement and we defer to the model). This clears the "no test vectors"
    refusal for a genuine free/destroy wrapper (heap:free_buffer), which the model
    itself recognises should be removed under Rust ownership.
    """
    if source_root is None:
        return None
    ret = (alg.return_type or "()").strip()
    if ret not in ("()", "void", ""):
        return None
    if len(alg.inputs or []) != 1:
        return None
    pt = (alg.inputs[0].rust_type or "").strip()
    if not (pt.startswith("&") or pt.startswith("Vec<") or pt.startswith("Box<")
            or "[u8" in pt or pt.startswith("*")):
        return None
    from pathlib import Path
    from alchemist.implementer.reference_probe import extract_c_function_body
    body = None
    root = Path(source_root)
    for cf in list(root.rglob("*.c")) + list(root.rglob("*.h")):
        try:
            b = extract_c_function_body(cf, alg.name)
        except Exception:  # noqa: BLE001
            b = None
        if b:
            body = b
            break
    if not body:
        return None
    # extract_c_function_body returns the WHOLE function; take the { ... } body.
    open_i, close_i = body.find("{"), body.rfind("}")
    if open_i == -1 or close_i <= open_i:
        return None
    b = body[open_i + 1:close_i]
    b = re.sub(r"/\*.*?\*/", " ", b, flags=re.DOTALL)
    b = re.sub(r"//[^\n]*", " ", b)
    stmts = [s.strip() for s in b.split(";") if s.strip()]
    if not stmts or not all(_FREE_CALL_RE.match(s) for s in stmts):
        return None
    from alchemist.implementer.skeleton import _fn_signature
    return (f"{_fn_signature(alg)} {{\n"
            f"    // The C original freed the buffer. In safe Rust an owned buffer\n"
            f"    // (Vec/Box) is dropped automatically, so this deallocation is a\n"
            f"    // no-op — there is nothing to verify.\n"
            f"}}")


def is_init_function(name: str) -> bool:
    """True iff a deterministic reset-to-default template is applicable.

    Returns False for parameterized init functions (`*Init*`), which
    actually configure state from their arguments — those go through
    the LLM with a reference-probe transliteration, not this template.
    """
    for pat in _RESET_ONLY_PATTERNS:
        if re.match(pat, name):
            return True
    return False


def generate_init_template(alg: AlgorithmSpec) -> str | None:
    """Produce a deterministic implementation for init/reset functions.

    Strategy:
      1. If the function takes `&mut X` where X is a known struct, emit
         `*x = X::default();` — reset to all-default.
      2. If the function returns `Result<(), E>`, wrap in `Ok(())`.
      3. If the function takes no params, just return `()` or Default.
      4. Otherwise, return None (let the LLM try).
    """
    if not is_init_function(alg.name):
        return None

    params = alg.inputs or []
    ret = (alg.return_type or "()").strip()

    # Find the first &mut param — that's our state to reset
    state_param = None
    for p in params:
        t = (p.rust_type or "").strip()
        if t.startswith("&mut ") or "Option<&mut" in t:
            state_param = p
            break

    lines: list[str] = []
    # Parameter name sanitization — match the skeleton's logic
    param_names = []
    for i, p in enumerate(params):
        name = p.name.strip() or f"arg{i}"
        if name in ("type", "match", "in", "fn", "let", "if", "else", "for",
                    "while", "return", "loop", "move", "ref", "mut", "self",
                    "const", "static", "unsafe", "use", "mod", "pub"):
            name = f"r#{name}"
        param_names.append(name)

    state_idx = params.index(state_param) if state_param is not None else -1

    # Silence unused-variable warnings for every param EXCEPT the state one,
    # which we're about to use via dereference-assignment.
    for i, n in enumerate(param_names):
        if i == state_idx:
            continue
        lines.append(f"    let _ = {n};")

    if state_param is not None:
        state_name = param_names[state_idx]
        # Dereference and assign default. We name the struct type explicitly
        # so `Default::default()` resolves without type-inference ambiguity.
        stype = (state_param.rust_type or "").strip()
        # Strip a leading `&mut ` or `&` to get the owned type name.
        owned = re.sub(r"^&\s*mut\s+", "", stype).strip()
        owned = re.sub(r"^&\s*", "", owned).strip()
        # If it's `Option<&mut T>` or similar, fall back to Default::default().
        if "<" in owned:
            lines.append(f"    *{state_name} = Default::default();")
        else:
            lines.append(f"    *{state_name} = {owned}::default();")

    # Build return value based on return type
    if ret in ("", "()"):
        lines.append("")
    elif ret.startswith("Result<"):
        lines.append("    Ok(Default::default())" if not re.search(r"Result<\s*\(\s*\)", ret)
                     else "    Ok(())")
    elif ret in ("u32", "i32", "usize", "u64", "i64", "u8", "i8", "u16", "i16", "bool"):
        lines.append(f"    Default::default()")
    else:
        lines.append(f"    Default::default()")

    # Build signature
    sig_params = ", ".join(
        f"{param_names[i]}: {p.rust_type}" for i, p in enumerate(params)
    )
    ret_annot = "" if ret in ("", "()") else f" -> {ret}"
    signature = f"pub fn {alg.name}({sig_params}){ret_annot}"

    return f"{signature} {{\n" + "\n".join(lines) + "\n}"


def try_init_template(alg: AlgorithmSpec) -> str | None:
    """Public API — returns a deterministic impl if applicable, else None."""
    return generate_init_template(alg)
