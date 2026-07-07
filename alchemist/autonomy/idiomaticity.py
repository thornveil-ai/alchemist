"""Pillar 5 — verified-preserving idiomaticity pass.

TRACTOR's explicit bar is *idiomatic* safe Rust, not just correct Rust. Our fills
are coherent but mechanical (raw indexing, sentinel returns, C-shaped loops). This
raises idiomaticity — but every candidate rewrite must stay BYTE-EXACT on the
differential or it is reverted. Idiomaticity is never traded for the guarantee.

The gate is the whole point: propose (rule- or model-driven) -> verify -> keep or
revert. A refactor that changes observable behavior by one byte is thrown away, so
the output is both more idiomatic AND still provably equivalent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable


def verified_refactor(module_path: Path, refactored_module: str,
                      verify: Callable[[], bool]) -> bool:
    """Swap in a refactored module; keep it iff `verify()` still passes (byte-exact),
    else restore the original. Returns True if the refactor was kept."""
    module_path = Path(module_path)
    original = module_path.read_text(encoding="utf-8")
    module_path.write_text(refactored_module, encoding="utf-8")
    if verify():
        return True
    module_path.write_text(original, encoding="utf-8")   # never keep a divergence
    return False


def idiomaticity_score(rust: str) -> int:
    """Heuristic: higher = more idiomatic. Penalizes C-shaped Rust (unsafe, while-
    index loops, raw indexing, `as` casts, C-style `mut i` cursors); rewards
    iterators/adapters and `for &x` binding. Used to rank refactor candidates."""
    penalty = (rust.count("unsafe") * 6
               + len(re.findall(r"\bwhile\b", rust)) * 3
               + len(re.findall(r"\[\s*\w+\s*\]", rust)) * 1      # raw indexing
               + len(re.findall(r"\blet\s+mut\s+\w+\s*(?::[^=]+)?=\s*0", rust)) * 2  # index cursors
               + rust.count(" as ") * 1)
    reward = (rust.count(".iter()") * 2 + rust.count(".fold(") * 3 + rust.count(".map(") * 2
              + rust.count(".sum()") * 3 + len(re.findall(r"\bfor\s+&", rust)) * 2
              + rust.count(".windows(") * 2 + rust.count(".chunks(") * 2)
    return reward - penalty


IDIOM_SCHEMA = {
    "type": "object",
    "properties": {
        "idiomatic_function": {"type": "string",
                               "description": "the same function rewritten in idiomatic safe Rust "
                                              "(iterators/adapters over raw indexing), IDENTICAL behavior"},
    },
    "required": ["idiomatic_function"],
}


def model_idiomatic_candidate(rust_fn: str, llm, temperature: float = 0.2) -> str | None:
    """Ask the model for an idiomatic rewrite of one function. Behavior-preservation
    is NOT trusted — the caller must gate it through `verified_refactor`."""
    prompt = (
        "Rewrite this Rust function to be maximally IDIOMATIC and safe while keeping "
        "EXACTLY identical behavior: prefer iterators/adapters (`.iter()`, `.fold()`, "
        "`.map()`, `.sum()`, `for &x in`) over raw indexing and `while` cursors; keep "
        "wrapping arithmetic exactly. Return only the complete `pub fn`.\n\n"
        "```rust\n%s\n```" % rust_fn)
    try:
        resp = llm.call_structured(messages=[{"role": "user", "content": prompt}],
                                   tool_name="idiomatic", tool_schema=IDIOM_SCHEMA,
                                   max_tokens=1400, temperature=temperature)
        cand = (getattr(resp, "structured", None) or {}).get("idiomatic_function", "")
        cand = re.sub(r"^```\w*\n|\n```$", "", cand.strip())
        return cand or None
    except Exception:
        return None


def idiomatic_pass(module_path: Path, candidates: list[str],
                   verify: Callable[[], bool]) -> int:
    """Apply candidate refactorings in order, keeping each only if it verifies. Each
    kept candidate becomes the new baseline (candidates may build on each other).
    Returns how many were accepted."""
    module_path = Path(module_path)
    kept = 0
    for cand in candidates:
        if verified_refactor(module_path, cand, verify):
            kept += 1
    return kept
