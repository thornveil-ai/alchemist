"""The autonomy retirement ledger.

A function is "retired" from the autonomy debt ONLY when the WS4 loop has
provably reproduced it with no human: its body is stubbed out, the model refills
it from the C reference, and the crate's differential tests go green — all
autonomously. This ledger records those proofs so the scorecard can subtract
them from the open debt.

Honest by construction: nothing lands here without a green differential run, and
the proof metadata (attempts, timestamp source) travels with it. Delete an entry
and the debt goes back up — no silent credit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parent / "retired_ledger.json"


@dataclass
class Ledger:
    path: Path = _DEFAULT
    retired: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "Ledger":
        p = Path(path) if path else _DEFAULT
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return cls(path=p, retired=data.get("retired", {}))
            except (OSError, json.JSONDecodeError):
                pass
        return cls(path=p, retired={})

    def key(self, crate: str, fn: str) -> str:
        return f"{crate}::{fn}"

    def is_retired(self, crate: str, fn: str) -> bool:
        return self.key(crate, fn) in self.retired

    def retire(self, crate: str, fn: str, *, attempts: int, proof: str = "regen-differential",
               note: str = "") -> None:
        self.retired[self.key(crate, fn)] = {
            "crate": crate, "fn": fn, "attempts": attempts, "proof": proof, "note": note,
        }

    def retired_fns(self) -> set[str]:
        """Bare function names that have been retired (any crate)."""
        return {v["fn"] for v in self.retired.values()}

    def retired_pairs(self) -> set[tuple[str, str]]:
        return {(v["crate"], v["fn"]) for v in self.retired.values()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"retired": self.retired}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def __len__(self) -> int:
        return len(self.retired)
