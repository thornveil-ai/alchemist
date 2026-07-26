#!/usr/bin/env python3
"""Build DPO preference data from near-miss negatives + verified wins.

For each function that both (a) produced a compiled-but-differential-failed
near-miss and (b) eventually verified byte-exact, emit a preference triple:
  prompt  = the C function + translate instruction
  chosen  = the oracle-verified Rust
  rejected= the near-miss Rust (with the divergence that killed it)
These are the most instructive C->Rust training signals: the exact wrong-vs-right
distinction the model must learn. Outputs corpus/dpo.jsonl + corpus/dpo_stats.json.
"""
import json
import hashlib
from pathlib import Path

ROOT = Path("/data/rigrun/projects/alchemist")
SUBJ = ROOT / "subjects"
OUT = ROOT / "corpus" / "dpo.jsonl"
STATS = ROOT / "corpus" / "dpo_stats.json"

SYSTEM = ("You are an expert systems engineer who translates C functions into "
          "safe, byte-exact Rust. Forbid unsafe code; preserve C integer "
          "semantics exactly.")


def _extract_c_fn(c_text: str, fn: str) -> str | None:
    import re
    m = re.search(r"(?:^|\n)[A-Za-z_][\w \t\*\(\),]*?\b" + re.escape(fn) + r"\s*\([^;{]*\)\s*\{", c_text)
    if not m:
        return None
    start = m.start() if c_text[m.start()] != "\n" else m.start() + 1
    brace = c_text.index("{", m.end() - 1)
    depth, i = 1, brace + 1
    while depth and i < len(c_text):
        if c_text[i] == "{":
            depth += 1
        elif c_text[i] == "}":
            depth -= 1
        i += 1
    return c_text[start:i]


def _wins(subj: Path) -> dict:
    out = {}
    w = subj / ".alchemist" / "wins"
    if w.exists():
        for rs in w.glob("**/*.rs"):
            b = rs.read_text(encoding="utf-8", errors="replace").strip()
            if b and "unimplemented!" not in b:
                out[rs.stem] = b
    return out


def main():
    triples, seen = [], set()
    subjects_with = 0
    for nm_file in SUBJ.glob("*/.alchemist/near_misses.jsonl"):
        subj = nm_file.parent.parent
        wins = _wins(subj)
        if not wins:
            continue
        c_blob = "\n".join(cf.read_text(encoding="utf-8", errors="replace")
                           for cf in sorted(subj.glob("*.c")))
        got = False
        for line in nm_file.read_text().splitlines():
            if not line.strip():
                continue
            nm = json.loads(line)
            fn = nm["function"]
            chosen = wins.get(fn)
            rejected = (nm.get("rust") or "").strip()
            if not chosen or not rejected or chosen == rejected:
                continue
            c_fn = _extract_c_fn(c_blob, fn)
            if not c_fn:
                continue
            key = hashlib.sha256((fn + rejected).encode()).hexdigest()
            if key in seen:
                continue
            seen.add(key); got = True
            triples.append({
                "subject": subj.name, "function": fn,
                "prompt": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"Translate this C function to safe Rust:\n\n```c\n{c_fn}\n```"},
                ],
                "chosen": f"```rust\n{chosen}\n```",
                "rejected": f"```rust\n{rejected}\n```",
                "divergence": nm.get("divergence", ""),
            })
        if got:
            subjects_with += 1
    with OUT.open("w", encoding="utf-8") as f:
        for t in triples:
            f.write(json.dumps(t) + "\n")
    stats = {"dpo_triples": len(triples), "subjects_contributing": subjects_with}
    STATS.write_text(json.dumps(stats, indent=2))
    print(f"DPO triples: {len(triples)} (from {subjects_with} subjects) -> {OUT}")


if __name__ == "__main__":
    main()
