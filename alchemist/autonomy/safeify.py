"""The c2rust-baseline route: refine unsafe-correct Rust into SAFE Rust, oracle-gated.

The model translating C→Rust from scratch is the unreliable step. A better pipeline:

    C --(c2rust, deterministic)--> unsafe Rust (byte-exact by construction)
      --(model, ONE pass, oracle-gated)--> safe idiomatic Rust

This flips the hard problem into an easy one. The unsafe baseline is ALWAYS correct
(c2rust preserves C semantics), so:
  - coverage expands to ANY C: you always have a correct starting point,
  - the model's job shrinks from "translate" to "make this safe" (far more reliable),
  - it's single-shot latency (one refine pass, not from-scratch generation),
  - and the floor is unsafe-but-correct: if the model can't safe-ify a piece, you keep
    the correct unsafe version and label it. Correctness is never traded for safety.

`c2rust` is the pluggable deterministic front-end; the value here is the gated refine
loop, which works on any correct baseline (c2rust output OR a first model fill).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from alchemist.autonomy.idiomaticity import verified_refactor


def c2rust_available() -> bool:
    return shutil.which("c2rust") is not None


def transpile_with_c2rust(c_file: Path, work: Path) -> Path | None:
    """Deterministically transpile C to unsafe Rust (byte-exact by construction).
    Returns the .rs path, or None if c2rust isn't available."""
    if not c2rust_available():
        return None
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    # c2rust needs a compile_commands.json; for a single TU we synthesize one
    cc = work / "compile_commands.json"
    cc.write_text('[{"directory":"%s","command":"cc -c %s","file":"%s"}]'
                  % (c_file.parent, c_file.name, c_file))
    r = subprocess.run(["c2rust", "transpile", str(cc)], capture_output=True, cwd=str(work))
    out = c_file.with_suffix(".rs")
    return out if out.exists() and r.returncode == 0 else None


SAFEIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "safe_function": {"type": "string",
                          "description": "the function rewritten with NO unsafe and NO raw "
                                         "pointers (slices/iterators), IDENTICAL behavior"}},
    "required": ["safe_function"],
}


def _safeify_candidate(unsafe_fn: str, llm, temperature: float = 0.0) -> str | None:
    prompt = (
        "This Rust function is correct but uses `unsafe` and/or raw pointers. Rewrite it "
        "with NO `unsafe` block and NO raw pointers -- use slices, iterators, and safe "
        "indexing -- keeping EXACTLY identical behavior (same wrapping arithmetic, same "
        "result). Return only the complete `pub fn`.\n\n```rust\n%s\n```" % unsafe_fn)
    try:
        resp = llm.call_structured(messages=[{"role": "user", "content": prompt}],
                                   tool_name="safeify", tool_schema=SAFEIFY_SCHEMA,
                                   max_tokens=1400, temperature=temperature)
        cand = (getattr(resp, "structured", None) or {}).get("safe_function", "")
        return re.sub(r"^```\w*\n|\n```$", "", cand.strip()) or None
    except Exception:
        return None


def safeify(module_path: Path, verify: Callable[[], bool], llm) -> str:
    """Refine an unsafe-but-correct module toward safe Rust, gated by the oracle.
    Returns 'safe' (fully safe-ified + verified), 'partial' (some unsafe remains but
    still correct), or 'already-safe'. Correctness is guaranteed throughout: any
    candidate that diverges is reverted, so the worst case is the correct unsafe floor.
    """
    module_path = Path(module_path)
    src = module_path.read_text(encoding="utf-8")
    if "unsafe" not in src and not re.search(r"\*\s*(?:const|mut)\b", src):
        return "already-safe"
    cand = _safeify_candidate(src, llm)
    if cand and verified_refactor(module_path, cand, verify):
        after = module_path.read_text()
        return "safe" if ("unsafe" not in after and not re.search(r"\*\s*(?:const|mut)\b", after)) \
            else "partial"
    return "partial"   # unsafe-but-correct floor preserved
