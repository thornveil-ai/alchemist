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
    repair_crate,
    run_crate_tests,
)

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
    on_event: Callable[[str], None] | None = None,
) -> tuple[str, int]:
    """Prove `fn` autonomously reproducible. Returns (outcome, attempts).

    outcome in {"retired", "resisted", "no-stub", "already-broken"}.
    Always restores the pristine verified module afterward.
    """
    original = module_path.read_text(encoding="utf-8")
    stubbed = stub_fn(original, fn)
    if stubbed is None:
        return "no-stub", 0
    module_path.write_text(stubbed, encoding="utf-8")
    try:
        # Sanity: the stub must actually break the crate (else the test doesn't
        # cover this fn and "reproducing" it proves nothing).
        passed_stub, _ = run_crate_tests(workspace_dir, crate_name, env=env)
        if passed_stub:
            return "already-broken", 0  # no test exercises this fn — can't prove
        result = repair_crate(
            workspace_dir=workspace_dir, crate_name=crate_name, module_path=module_path,
            c_source_path=c_source_path, candidates=[fn], llm=llm, env=env,
            max_attempts=max_attempts, on_event=on_event,
        )
        return ("retired" if result.status == "fixed" else "resisted", result.attempts)
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
            max_attempts=max_attempts, on_event=on_event,
        )
        results[fn] = outcome
        if outcome == "retired":
            ledger.retire(crate_name, fn, attempts=attempts)
            ledger.save()
        if on_event:
            on_event(f"    {crate_name}::{fn}: {outcome} (attempts={attempts})")
    return results
