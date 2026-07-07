"""Fill quality — raise the pass rate WITHOUT a stronger base model.

Two model-agnostic multipliers:

  best_of_n  — the model is stochastic, so sample N candidate translations, gate
               EVERY one on the differential oracle, and keep the first that is
               byte-exact. A function the model gets right 40% of the time becomes
               ~92% at N=4 (1 - 0.6^4). The oracle makes this free of risk: a wrong
               sample can never be kept.

  VerifiedExampleStore — retrieval-augmented fill. Keep a growing library of
               VERIFIED (C-idiom -> Rust) pairs; pull the closest ones into the
               fill/diagnose prompt so the model translates by analogy to code that
               already passed, instead of from scratch. Every green fill feeds it,
               so the tool gets better at the idioms it has already conquered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


def best_of_n(generate: Callable[[int], str | None], verify: Callable[[str], bool],
              n: int = 4) -> tuple[str | None, int]:
    """Generate up to `n` candidates; return (candidate, attempts) for the FIRST that
    verifies, else (None, n). `generate(i)` yields candidate i (vary temperature/seed
    by i); `verify(cand)` runs the oracle. Nothing unverified is ever returned."""
    for i in range(n):
        cand = generate(i)
        if cand and verify(cand):
            return cand, i + 1
    return None, n


_TAG = re.compile(r"malloc|free|calloc|realloc|memcpy|memset|rotate|"
                  r"<<|>>|\^=|\|=|&=|\+=|->|\[|for\b|while\b|struct\b|union\b|return\b")


def _tags(c: str) -> set[str]:
    return set(m.group(0) for m in _TAG.finditer(c))


@dataclass
class VerifiedExampleStore:
    """Retrieval store of verified C->Rust translations, ranked by idiom overlap."""
    examples: list = field(default_factory=list)   # (tags, c_snippet, rust)

    def add(self, c_snippet: str, rust: str) -> None:
        self.examples.append((_tags(c_snippet), c_snippet.strip(), rust.strip()))

    def retrieve(self, c_snippet: str, k: int = 2) -> list[tuple[str, str]]:
        q = _tags(c_snippet)
        if not q:
            return []
        scored = sorted(self.examples, key=lambda e: len(q & e[0]), reverse=True)
        return [(c, r) for tags, c, r in scored[:k] if q & tags]

    def as_context(self, c_snippet: str, k: int = 2) -> str:
        ex = self.retrieve(c_snippet, k)
        if not ex:
            return ""
        blocks = ["// verified translation of a similar C idiom:\n// C:\n%s\n// Rust:\n%s" % (c, r)
                  for c, r in ex]
        return "## Worked examples (already verified byte-exact)\n" + "\n\n".join(blocks)
