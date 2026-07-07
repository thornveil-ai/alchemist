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

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
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

    def retrieve(self, c_snippet: str, k: int = 2, min_sim: float = 0.5) -> list[tuple[str, str]]:
        """Closest verified examples by Jaccard idiom-similarity, above `min_sim`.

        The threshold matters: SHA-1 and SHA-256 share loose tags (for, ^=, <<) but
        are NOT the same idiom -- injecting a SHA-256 example into a SHA-1 fill misled
        the model. Requiring majority-shared tags means only genuinely-similar code is
        offered, so retrieval helps instead of hurts."""
        q = _tags(c_snippet)
        if not q:
            return []

        def sim(tags):
            union = q | tags
            return len(q & tags) / len(union) if union else 0.0
        scored = sorted(self.examples, key=lambda e: sim(e[0]), reverse=True)
        return [(c, r) for tags, c, r in scored[:k] if sim(tags) >= min_sim]

    def as_context(self, c_snippet: str, k: int = 2) -> str:
        ex = self.retrieve(c_snippet, k)
        if not ex:
            return ""
        blocks = ["// verified translation of a similar C idiom:\n// C:\n%s\n// Rust:\n%s" % (c, r)
                  for c, r in ex]
        return "## Worked examples (already verified byte-exact)\n" + "\n\n".join(blocks)


def harvest_to_store(store: "VerifiedExampleStore", cfile, lib_rs_path, fn_names) -> int:
    """Extract verified (C body -> Rust) pairs from a verified crate into the store.
    Run over every green crate to bootstrap the corpus, so a fresh library starts warm
    with hundreds of worked examples instead of translating from scratch."""
    from alchemist.implementer.reference_probe import extract_c_function_body
    from alchemist.autonomy.live_repair import extract_rust_fn
    rust_src = Path(lib_rs_path).read_text(errors="replace")
    added = 0
    for fn in fn_names:
        cbody = extract_c_function_body(Path(cfile), fn) or ""
        rust = extract_rust_fn(rust_src, fn) or ""
        if cbody.strip() and rust.strip():
            store.add(cbody, rust)
            added += 1
    return added


class PersistentExampleStore(VerifiedExampleStore):
    """A VerifiedExampleStore backed by a JSON file, so what the tool learns on one
    library carries into the next run. Every green fill feeds it; every new fill
    retrieves from it. The pass rate compounds as the corpus grows."""

    def __init__(self, path):
        super().__init__()
        self.path = Path(path)
        if self.path.exists():
            for c, r in json.loads(self.path.read_text() or "[]"):
                super().add(c, r)

    def add(self, c_snippet: str, rust: str) -> None:
        super().add(c_snippet, rust)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([[c, r] for _, c, r in self.examples]))
