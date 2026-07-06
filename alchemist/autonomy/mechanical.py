"""One entry point for the DETERMINISTIC (no-model) repair fixers.

Across the breadth sweeps, most compile failures turned out to be mechanical —
rustc names the line and the exact problem, so the fix is a text transform, not a
reasoning task. Running these BEFORE the model diagnoser means the model only ever
has to handle genuine logic gaps:

  - borrow_fix      : E0502/E0503 aliasing (hoist the conflicting borrow)
  - fix_types       : E0277/E0308 integer-width coercion (insert `as` casts)
  - fix_method_names: E0599 hallucinated methods (rename to the real one)

They're looped because each can expose the other (a type cast can reveal a borrow,
a borrow hoist can reveal a width mismatch).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from alchemist.autonomy.borrow_fix import fix_borrows
from alchemist.autonomy.type_fix import fix_types, fix_method_names


def mechanical_repair(module_path: Path, run_build: Callable[[], str],
                      rounds: int = 4) -> bool:
    """Loop the deterministic fixers until the classes they handle are gone.
    `run_build()` returns compiler output. True if all three report clean."""
    module_path = Path(module_path)
    for _ in range(rounds):
        b = fix_borrows(module_path, run_build)
        t = fix_types(module_path, run_build)
        m = fix_method_names(module_path, run_build)
        if b and t and m:  # none of our classes left to fix -> stop looping
            break
    # honest return: whether the BUILD is now clean (an unhandled class -> False,
    # so the caller knows to hand it to the model diagnoser)
    return "error[" not in run_build()
