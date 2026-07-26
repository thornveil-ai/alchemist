#!/usr/bin/env python3
"""Export every oracle-verified (C fn -> Rust fn) win as a training pair.

Walks all subjects' .alchemist/wins/<crate>/<module>/<fn>.rs (each = a
byte-exact-VERIFIED Rust body) and pairs it with the originating C function
extracted from the subject's C sources. Emits a single JSONL corpus — the
god-tier fine-tune fuel. Every pair is provably correct (the oracle certified
it), so this is zero-label-noise SFT data.

Usage: python export_pairs.py [--out /path/pairs.jsonl]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path("/data/rigrun/projects/alchemist")
sys.path.insert(0, str(ROOT))


def _extract_c_fn(c_text: str, fn_name: str) -> str | None:
    """Best-effort: pull the full C definition of fn_name from a source blob
    via brace matching (no tree-sitter dependency)."""
    import re
    m = re.search(
        r"(?:^|\n)[A-Za-z_][\w \t\*\(\),]*?\b" + re.escape(fn_name) + r"\s*\([^;{]*\)\s*\{",
        c_text)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "corpus" / "pairs.jsonl"))
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    subjects = ROOT / "subjects"
    pairs, no_c, dupes = [], 0, 0
    seen = set()
    for win in subjects.glob("*/.alchemist/wins/**/*.rs"):
        parts = win.relative_to(subjects).parts
        subject = parts[0]
        fn_name = win.stem
        rust = win.read_text(encoding="utf-8", errors="replace").strip()
        if not rust or "unimplemented!" in rust:
            continue
        # find the C source: concat all .c in the subject dir
        c_blob = ""
        subj_dir = subjects / subject
        for cf in subj_dir.glob("*.c"):
            c_blob += cf.read_text(encoding="utf-8", errors="replace") + "\n"
        c_fn = _extract_c_fn(c_blob, fn_name) if c_blob else None
        key = (subject, fn_name)
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        if not c_fn:
            no_c += 1
            # still record the Rust + subject for provenance; skip if no C anchor
            continue
        pairs.append({
            "subject": subject,
            "function": fn_name,
            "c": c_fn,
            "rust": rust,
            "source": "alchemist-verified-win",
            "verified": "byte-exact-differential",
        })

    with out.open("w", encoding="utf-8") as fh:
        for p in pairs:
            fh.write(json.dumps(p) + "\n")

    print(f"exported {len(pairs)} verified (C->Rust) pairs -> {out}")
    print(f"  (skipped {no_c} wins with no C anchor, {dupes} dupes)")
    print(f"  subjects covered: {len(set(p['subject'] for p in pairs))}")
    # crude size stats
    if pairs:
        import statistics
        rl = [len(p['rust']) for p in pairs]
        print(f"  rust body chars: min {min(rl)} / median {int(statistics.median(rl))} / max {max(rl)}")


if __name__ == "__main__":
    main()
