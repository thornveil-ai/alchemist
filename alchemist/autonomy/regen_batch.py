"""Batch autonomous regeneration — retire human-ported functions for real.

For each implementation function in a verified crate:

    1. snapshot the module, then STUB the target function (`{ unimplemented!() }`)
       so the workspace is correct except for that one hole;
    2. run the WS4 loop: the differential tests fail -> localize -> the model
       refills the function from the C reference + guidance -> re-verify;
    3. if the crate goes differential-green, the function is *proven*
       autonomously reproducible -> record it in the retirement ledger;
    4. restore the pristine verified body either way (we're proving the model
       CAN produce it, not replacing the human-verified canon).

The ledger is saved after every function, so a long run is resumable and every
retirement is backed by a real green differential run (never a fake-green).

See docs/PATH_TO_AUTONOMY.md (WS4) and the M1 scorecard.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Sequence

from alchemist.autonomy.ledger import Ledger
from alchemist.autonomy.live_repair import (
    _blank_rust,
    _rust_fn_span,
    make_refill,
    run_crate_tests,
)


_FAILED_RE = re.compile(r"^test\s+(\S+)\s+\.\.\.\s+FAILED", re.MULTILINE)


def failing_tests(output: str) -> frozenset[str]:
    """Names of tests that FAILED in a cargo run (order-independent set)."""
    return frozenset(_FAILED_RE.findall(output))


def _extract_cargo_errors(output: str, limit: int = 24) -> str:
    """Pull the actionable failure lines from a cargo run: compile errors (with
    their message + note lines) and assert_eq diffs. This is what gets fed back
    to the model so it fixes the CAUSE (e.g. 'cannot find function put_short' ->
    inline the C macro) instead of guessing again."""
    keep: list[str] = []
    lines = output.splitlines()
    for i, l in enumerate(lines):
        s = l.strip()
        if s.startswith(("error[", "error:", "warning: unused")) or "cannot find" in s \
           or "no method named" in s or "mismatched types" in s \
           or s.startswith(("left:", "right:", "assertion")) or "panicked at" in s:
            keep.append(l.rstrip())
            # include the immediately-following help/note line for compile errors
            if i + 1 < len(lines) and lines[i + 1].strip().startswith(("-->", "help:", "note:", "=")):
                keep.append(lines[i + 1].rstrip())
        if len(keep) >= limit:
            break
    return "\n".join(keep)

_IMPL_FN_RE = re.compile(r"^\s*(?:pub(?:\(crate\))?\s+)?(?:unsafe\s+)?fn\s+(\w+)\s*[<(]",
                         re.MULTILINE)


def list_impl_functions(module_source: str) -> list[str]:
    """Implementation functions in a module, in file order, excluding test fns."""
    cut = len(module_source)
    m = re.search(r"#\[cfg\(test\)\]|\nmod tests\b", module_source)
    if m:
        cut = m.start()
    body = module_source[:cut]
    seen: list[str] = []
    for name in _IMPL_FN_RE.findall(body):
        if not name.startswith("test_") and name not in seen:
            seen.append(name)
    return seen


def stub_fn(source: str, name: str) -> str | None:
    """Replace `name`'s body with `{ unimplemented!() }`, keeping the signature."""
    span = _rust_fn_span(source, name)
    if not span:
        return None
    fn_text = source[span[0] : span[1]]
    clean = _blank_rust(fn_text)
    angle = paren = 0
    brace_open = -1
    for i, c in enumerate(clean):
        if c == "<":
            angle += 1
        elif c == ">":
            angle = max(0, angle - 1)
        elif c == "(":
            paren += 1
        elif c == ")":
            paren = max(0, paren - 1)
        elif c == "{" and angle == 0 and paren == 0:
            brace_open = i
            break
    if brace_open < 0:
        return None
    sig = fn_text[:brace_open].rstrip()
    stub = sig + " { unimplemented!() }"
    return source[: span[0]] + stub + source[span[1] :]


def regen_function(
    *,
    workspace_dir: Path,
    crate_name: str,
    module_path: Path,
    c_source_path: Path,
    fn: str,
    llm,
    env: dict | None = None,
    max_attempts: int = 3,
    isolate: bool = True,
    on_event: Callable[[str], None] | None = None,
) -> tuple[str, int]:
    """Prove `fn` autonomously reproducible. Returns (outcome, attempts).

    outcome in {"retired", "resisted", "no-stub", "already-broken",
    "untestable-baseline"}. Always restores the pristine verified module.

    `isolate=True` runs only the fn's own tests (right when a crate has
    per-function differential vectors + unrelated pre-existing failures).
    `isolate=False` runs the whole crate (right for a baseline-green crate whose
    coverage is integration/e2e, e.g. inflate's round-trip tests).
    """
    original = module_path.read_text(encoding="utf-8")
    test_filter = (fn.lstrip("_") or fn) if isolate else ""

    def run() -> tuple[bool, frozenset[str], str]:
        ok, out = run_crate_tests(workspace_dir, crate_name, env=env, test_filter=test_filter)
        compiled = ok or ("test result:" in out)  # tests actually ran (not a compile error)
        return compiled, failing_tests(out), out

    # Baseline failing set on the verified canon. We prove reproduction by
    # RETURNING TO this set (not "all green"), so a crate with unrelated stale
    # failures (deflate has 21, trees 16) is still a valid target.
    base_compiled, baseline_fails, _ = run()
    if not base_compiled:
        return "untestable-baseline", 0
    stubbed = stub_fn(original, fn)
    if stubbed is None:
        return "no-stub", 0
    module_path.write_text(stubbed, encoding="utf-8")
    try:
        # The stub must ADD failures (this fn's tests) beyond baseline, else no
        # test in scope exercises it and reproducing it proves nothing.
        stub_compiled, stub_fails, _ = run()
        if not (stub_compiled and stub_fails > baseline_fails):
            return "already-broken", 0
        # Iterative refill with compile/test-error feedback — the model sees its
        # own last attempt plus the exact error and fixes the CAUSE.
        refill = make_refill(module_path, c_source_path, llm, on_event=on_event)
        base_msg = ("The differential oracle rejects this function's output. Match the "
                    "C reference exactly.")
        prev_err = ""
        for attempt in range(1, max_attempts + 1):
            guidance = base_msg
            if prev_err:
                guidance += (
                    "\n\n## Your previous attempt FAILED with this compiler/test output "
                    "— fix the CAUSE:\n```\n" + prev_err + "\n```\n"
                    "Reminder: C macros (put_byte, put_short, Assert, Tracev) are NOT "
                    "functions here — inline them. The pending output buffer is the Vec "
                    "`state.pending`: put_byte(s,b) => state.pending.push(b as u8); "
                    "put_short(s,w) => state.pending.push((w & 0xff) as u8); "
                    "state.pending.push((w >> 8) as u8). Only call functions listed as "
                    "in scope above; never invent a helper."
                )
            changed = refill(fn, guidance)
            if not changed:
                break
            compiled, cur_fails, out = run()
            if compiled and cur_fails == baseline_fails:
                return "retired", attempt  # back to baseline -> reproduced
            prev_err = _extract_cargo_errors(out) or "(non-compiling or new failures)"
        return "resisted", max_attempts
    finally:
        module_path.write_text(original, encoding="utf-8")  # restore canon


def regen_module(
    *,
    workspace_dir: Path,
    crate_name: str,
    module_path: Path,
    c_source_path: Path,
    llm,
    ledger: Ledger,
    functions: Sequence[str] | None = None,
    env: dict | None = None,
    max_attempts: int = 3,
    isolate: bool = True,
    on_event: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """Regenerate every impl function in a module, updating the ledger as it goes."""
    src = module_path.read_text(encoding="utf-8")
    fns = list(functions) if functions is not None else list_impl_functions(src)
    results: dict[str, str] = {}
    for fn in fns:
        if ledger.is_retired(crate_name, fn):
            results[fn] = "already-retired"
            continue
        if on_event:
            on_event(f"--- regen {crate_name}::{fn} ---")
        outcome, attempts = regen_function(
            workspace_dir=workspace_dir, crate_name=crate_name, module_path=module_path,
            c_source_path=c_source_path, fn=fn, llm=llm, env=env,
            max_attempts=max_attempts, isolate=isolate, on_event=on_event,
        )
        results[fn] = outcome
        if outcome == "retired":
            ledger.retire(crate_name, fn, attempts=attempts)
            ledger.save()
        if on_event:
            on_event(f"    {crate_name}::{fn}: {outcome} (attempts={attempts})")
    return results
