"""Live wiring for WS4: run the diagnose-and-repair loop against a real crate.

This connects `make_repair_loop` to the real world with the lightest possible
oracle: a crate's own differential-vector `cargo test` run. A divergence surfaces
as an `assert_eq!` panic, which `parse_rust_diff_failures` already reads.

The refill is a focused single-function model call — give the model the C
reference, the current (buggy) Rust body, and the byte/field-precise repair
guidance, and ask for the corrected function — then splice it back with a
brace-matched Rust replacer. No full spec/arch context needed, which is what
makes this drivable standalone.

Acceptance goal (docs/PATH_TO_AUTONOMY.md, WS4): inject a bug into a verified
function, and have the loop localize + repair it with the tests going green,
zero human diagnosis.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from alchemist.autonomy.repair import (
    RepairResult,
    make_repair_loop,
    parse_rust_diff_failures,
)
from alchemist.implementer.reference_probe import extract_c_function_body


def _blank_rust(text: str) -> str:
    """Same-length copy with comment/string contents blanked, RUST-aware.

    Unlike the C blanker, this does NOT treat `'` as a char-literal opener
    unless it's actually a char literal (`'a'` / `'\\n'`). A lone `'ident`
    (a lifetime like `'static` / `'a`) is left intact, so brace matching over
    signatures with lifetimes works.
    """
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        two = text[i : i + 2]
        if two == "//":
            j = text.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif two == "/*":
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif text[i] == '"':
            out[i] = " "
            i += 1
            while i < n:
                if text[i] == "\\":
                    out[i] = " "
                    if i + 1 < n:
                        out[i + 1] = " "
                    i += 2
                    continue
                if text[i] == '"':
                    out[i] = " "
                    i += 1
                    break
                out[i] = " "
                i += 1
        elif text[i] == "'":
            # char literal only in the 'x' or '\x' shapes; else it's a lifetime.
            if i + 1 < n and text[i + 1] == "\\":
                j = i + 2
                while j < n and text[j] != "'":
                    j += 1
                for k in range(i, min(j + 1, n)):
                    out[k] = " "
                i = j + 1
            elif i + 2 < n and text[i + 2] == "'":
                out[i] = out[i + 1] = out[i + 2] = " "
                i += 3
            else:
                i += 1  # lifetime — leave intact
        else:
            i += 1
    return "".join(out)


# --- brace-matched Rust function extract / replace -------------------------
def _rust_fn_span(source: str, name: str) -> tuple[int, int] | None:
    """Return (start, end) byte span of `fn name (...) ... { body }` or None.

    Scans a comment/string-blanked copy so literals can't fool the matcher;
    handles generics/where-clauses by taking the first top-level `{` after the
    `fn name` token as the body opener.
    """
    clean = _blank_rust(source)
    n = len(clean)
    for m in re.finditer(r"\bfn\s+" + re.escape(name) + r"\b", clean):
        # find the body-opening brace at angle/paren depth 0
        i = m.end()
        angle = paren = 0
        brace_open = -1
        while i < n:
            c = clean[i]
            if c == "<":
                angle += 1
            elif c == ">":
                if angle:
                    angle -= 1
            elif c == "(":
                paren += 1
            elif c == ")":
                if paren:
                    paren -= 1
            elif c == ";" and angle == 0 and paren == 0:
                break  # a declaration/trait method, not a definition
            elif c == "{" and angle == 0 and paren == 0:
                brace_open = i
                break
            i += 1
        if brace_open < 0:
            continue
        depth = 0
        j = brace_open
        while j < n:
            if clean[j] == "{":
                depth += 1
            elif clean[j] == "}":
                depth -= 1
                if depth == 0:
                    # start at the beginning of the signature line (incl. pub/attrs
                    # is unnecessary — we replace the fn item body-and-sig only)
                    start = m.start()
                    # include a leading `pub ` if present
                    lead = source.rfind("\n", 0, start)
                    prefix = source[lead + 1 : start]
                    if prefix.strip() in ("pub", "pub(crate)"):
                        start = lead + 1
                    return start, j + 1
            j += 1
    return None


def extract_rust_fn(source: str, name: str) -> str | None:
    span = _rust_fn_span(source, name)
    return source[span[0] : span[1]] if span else None


def replace_rust_fn(source: str, name: str, new_fn: str) -> str | None:
    span = _rust_fn_span(source, name)
    if not span:
        return None
    return source[: span[0]] + new_fn.strip() + source[span[1] :]


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*|```$", "", t, flags=re.MULTILINE).strip()
    return t


# --- failing-test -> function localization ---------------------------------
def functions_from_failing_tests(
    cargo_output: str, candidates: Sequence[str]
) -> list[str]:
    """Order candidates by which appear in the names of failing tests.

    The strongest live localization signal: a failing `test_adler32_z_3` implies
    `adler32_z`. Falls back to all candidates if no name matches.
    """
    def _tokens(fn: str) -> list[str]:
        toks = [fn.lower()]
        if "_" in fn:
            toks.append(fn.rsplit("_", 1)[0].lower())  # adler32_z -> adler32
        return toks

    fails = parse_rust_diff_failures(cargo_output)
    hit: list[str] = []
    for f in fails:
        tname = f.test.lower()
        for c in candidates:
            if c not in hit and any(t in tname for t in _tokens(c)):
                hit.append(c)
    for c in candidates:
        if c not in hit:
            hit.append(c)
    return hit


# --- the live oracle + refill ---------------------------------------------
def run_crate_tests(crate_dir: Path, crate_name: str, env: dict | None = None,
                    timeout: int = 600) -> tuple[bool, str]:
    r = subprocess.run(
        ["cargo", "test", "-p", crate_name, "--", "--nocapture"],
        cwd=str(crate_dir), capture_output=True, text=True, timeout=timeout, env=env,
    )
    return r.returncode == 0, r.stdout + "\n" + r.stderr


def make_refill(
    module_path: Path,
    c_source_path: Path,
    llm,
    struct_context: str = "",
    on_event: Callable[[str], None] | None = None,
) -> Callable[[str, str], bool]:
    """Build a `refill(fn, guidance)` that re-fills one Rust function via the model."""

    def refill(fn: str, guidance: str) -> bool:
        source = module_path.read_text(encoding="utf-8")
        current = extract_rust_fn(source, fn)
        if current is None:
            return False
        c_body = extract_c_function_body(c_source_path, fn) or "(C source not found)"
        # relevant idiom patterns for this function
        try:
            from alchemist.catalog import match_idioms, render_prompt_hints
            idiom_block = render_prompt_hints(match_idioms(c_body)[:5])
        except Exception:
            idiom_block = ""
        prompt = (
            f"Fix this Rust function so its output matches the C reference EXACTLY. "
            f"A differential oracle caught a divergence:\n\n{guidance}\n\n"
            f"## C reference (authoritative)\n```c\n{c_body}\n```\n\n"
            f"## Current (incorrect) Rust\n```rust\n{current}\n```\n\n"
            f"{struct_context}\n{idiom_block}\n"
            f"Re-derive from the C semantics. Do NOT hard-code the expected bytes or "
            f"special-case the failing input. Return ONLY the corrected `fn {fn}` "
            f"definition (signature + body), no markdown, no other items."
        )
        resp = llm.call_structured(
            messages=[{"role": "user", "content": prompt}],
            tool_name="fix",
            tool_schema={"type": "object", "properties": {"function": {"type": "string"}},
                         "required": ["function"]},
            max_tokens=2600,
            temperature=0.0,
        )
        new_fn = _strip_fences((resp.structured or {}).get("function", ""))
        if not new_fn or f"fn {fn}" not in new_fn:
            if on_event:
                on_event(f"refill({fn}): model returned no usable function")
            return False
        replaced = replace_rust_fn(source, fn, new_fn)
        if replaced is None or replaced == source:
            return False
        module_path.write_text(replaced, encoding="utf-8")
        if on_event:
            on_event(f"refill({fn}): body rewritten ({len(new_fn)} chars)")
        return True

    return refill


def repair_crate(
    *,
    workspace_dir: Path,
    crate_name: str,
    module_path: Path,
    c_source_path: Path,
    candidates: Sequence[str],
    llm,
    env: dict | None = None,
    struct_context: str = "",
    max_attempts: int = 4,
    on_event: Callable[[str], None] | None = None,
) -> RepairResult:
    """Drive the WS4 loop against a real crate until its differential tests pass."""

    def run_differential() -> tuple[bool, str]:
        return run_crate_tests(workspace_dir, crate_name, env=env)

    # Order candidates by the initial failure's test names (strong localization).
    passed0, out0 = run_differential()
    ordered = list(candidates) if passed0 else functions_from_failing_tests(out0, candidates)

    refill = make_refill(module_path, c_source_path, llm,
                         struct_context=struct_context, on_event=on_event)

    loop = make_repair_loop(
        run_differential=run_differential,
        refill=refill,
        workspace_files={fn: module_path for fn in candidates},
        candidates=ordered,
        # every candidate "has write effects" so byte-diff localization keeps them
        # in play; the test-name ordering above is the real signal.
        effect_footprints={fn: {"output"} for fn in candidates},
        max_attempts=max_attempts,
        on_event=on_event,
    )
    return loop.run()
