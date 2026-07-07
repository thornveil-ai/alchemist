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
