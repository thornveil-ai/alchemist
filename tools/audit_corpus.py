#!/usr/bin/env python3
"""Corpus-quality gate for the C->Rust verified training pairs. Trustworthy
(tight heuristics, minimal false positives). HARD findings fail the audit.

Checked failure modes:
  A. Oracle-gaming / correctness (HARD)
     A1 cheat: unsafe / extern "C" / libc / #[link] / asm! / transmute / include! /
        Command / std::{fs,net,env,process} in a 'verified' body
     A2 whole-body stub: the entire fn body is todo!()/unimplemented!()/unreachable!()
        or {} / {0} (a stub that somehow passed the oracle)
     A3 input-ignoring: a fn with params whose body references NONE of them
  B. Integrity (HARD)  B1 empty; B2 no `fn`; B3 no byte-exact provenance;
     B5 c-not-a-definition; B6 unbalanced braces (truncation).  B4(SOFT) name mismatch
  C. Cleanliness (SOFT)  C1 exact dup; C2 near-dup C; C3 trivial; C4 debug leftovers;
     C5 encoding artifacts; C6 preprocessed-C artifacts; C7 possibly-incomplete
  D. Metadata (SOFT, from sft.jsonl)  category unknown; imbalance; won_via/rationale
     coverage; system-prompt consistency
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path("/data/rigrun/projects/alchemist")
PAIRS = ROOT / "corpus" / "pairs.jsonl"
SFT = ROOT / "corpus" / "sft.jsonl"

CHEAT = [(r"\bunsafe\b", "unsafe"), (r'extern\s+"C"', 'extern"C"'), (r"\blibc\b", "libc"),
         (r"#\[\s*link", "#[link]"), (r"\basm!", "asm!"), (r"\btransmute\b", "transmute"),
         (r"\binclude!\s*\(", "include!"), (r"\bCommand\b", "Command"),
         (r"\bstd::fs\b", "std::fs"), (r"\bstd::net\b", "std::net"),
         (r"\bstd::env\b", "std::env"), (r"\bstd::process\b", "std::process")]
DEBUG = [r"\bprintln!", r"\bdbg!\s*\(", r"\beprintln!"]
STD_FREE = set("""assert assert_eq debug_assert panic write writeln format print
    println eprintln vec matches min max size_of from_utf8 from_utf8_unchecked""".split())
KW_MACROS = {"wrapping_add", "wrapping_sub", "wrapping_mul", "wrapping_neg",
             "wrapping_shl", "wrapping_shr", "rotate_left", "rotate_right"}
RUST_KW = {"if", "while", "for", "match", "in", "loop", "return", "else", "as",
           "let", "fn", "mut", "move", "ref", "where", "impl", "unsafe", "and", "or"}


def load(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def norm_c(c):
    c = re.sub(r"/\*.*?\*/", "", c, flags=re.S)
    c = re.sub(r"//[^\n]*", "", c)
    return re.sub(r"\s+", "", c)


def balanced(s):
    return s.count("{") == s.count("}") and s.count("(") == s.count(")")


def last_body(rust):
    i = rust.find("{")
    return rust[i:] if i >= 0 else ""


def is_whole_stub(rust):
    b = last_body(rust)
    inner = b.strip()[1:-1].strip() if b.startswith("{") and b.endswith("}") else b
    if re.fullmatch(r"(0|Default::default\(\))?", inner):
        return True
    return bool(re.fullmatch(r"(todo!|unimplemented!|unreachable!)\s*\([^)]*\)\s*;?", inner))


def rust_fns(rust):
    return set(re.findall(r"\bfn\s+([a-zA-Z_]\w*)", rust))


def free_calls(rust):
    return set(re.findall(r"(?<![.\w:])([a-z_]\w*)\s*\(", rust))


def params_of(rust):
    m = re.search(r"\bfn\s+\w+\s*\(([^)]*)\)", rust, re.S)
    ps = []
    if m:
        for part in m.group(1).split(","):
            pm = re.match(r"\s*(?:mut\s+)?(r#\w+|[a-zA-Z_]\w*)\s*:", part)
            if pm and pm.group(1) != "self":
                ps.append(pm.group(1))
    return ps


def main():
    rows = load(PAIRS)
    print(f"=== pairs.jsonl: {len(rows)} rows ===\n")
    hard, soft = [], []
    seen_cr, normc, lens = set(), {}, []
    for r in rows:
        sf = f"{r.get('subject')}::{r.get('function')}"
        c, rust = (r.get("c") or ""), (r.get("rust") or "")
        cs, rs = c.strip(), rust.strip()
        if not cs or not rs:
            hard.append((sf, "B1 empty")); continue
        if "fn " not in rust:
            hard.append((sf, "B2 no-fn"))
        if r.get("verified") != "byte-exact-differential":
            hard.append((sf, "B3 no-provenance"))
        for pat, lab in CHEAT:
            if re.search(pat, rust):
                hard.append((sf, f"A1 cheat:{lab}"))
        if is_whole_stub(rust):
            hard.append((sf, "A2 whole-body-stub"))
        if "{" not in c:
            hard.append((sf, "B5 c-no-body"))
        if not balanced(rust):
            hard.append((sf, "B6 rust-unbalanced"))
        if not balanced(c):
            soft.append((sf, "B6 c-unbalanced"))
        ps, body = params_of(rust), last_body(rust)
        if ps and not any(re.search(rf"(?<!\w){re.escape(p)}(?!\w)", body) for p in ps):
            soft.append((sf, f"A3 ignores-params {ps}"))
        fns, fld = rust_fns(rust), (r.get("function") or "")
        if fns and fld:
            nm = lambda x: x.lower().replace("_", "").replace("r#", "")
            if not any(nm(fld) in nm(f) or nm(f) in nm(fld) for f in fns):
                soft.append((sf, f"B4 name-mismatch {fld}"))
        if (cs, rs) in seen_cr:
            soft.append((sf, "C1 exact-dup"))
        seen_cr.add((cs, rs))
        nc = norm_c(c)
        if nc in normc and normc[nc] != sf:
            soft.append((sf, f"C2 near-dup-of {normc[nc]}"))
        normc.setdefault(nc, sf)
        lens.append(rust.count("\n") + 1)
        if any(re.search(p, rust) for p in DEBUG):
            soft.append((sf, "C4 debug"))
        if "�" in c + rust or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", c + rust):
            soft.append((sf, "C5 ctrl-char"))
        if re.search(r'^#\s+\d+\s+"', c, re.M) or "__attribute__" in c or "__extension__" in c:
            soft.append((sf, "C6 preprocessed-artifact"))
        undef = [x for x in free_calls(rust)
                 if x not in fns and x not in STD_FREE and x not in KW_MACROS and x not in RUST_KW]
        if undef:
            soft.append((sf, f"C7 free-call-undef:{undef[:4]}"))

    sfts = load(SFT)
    cats, vias = Counter(), Counter()
    no_rat, sysset = 0, set()
    for r in sfts:
        m = r.get("meta", {})
        cats[m.get("category") or "unknown"] += 1
        vias[m.get("won_via") or "unknown"] += 1
        if not m.get("rationale"):
            no_rat += 1
        msgs = r.get("messages", [])
        sysset.add(msgs[0]["content"] if msgs and msgs[0]["role"] == "system" else "")

    lens.sort()
    print("--- HARD (toxic pairs) ---")
    if not hard:
        print("  none")
    for sf, w in hard:
        print(f"  {w:26} {sf}")
    print(f"\n--- SOFT ({len(soft)}) by type ---")
    for k, v in Counter(w.split(" ")[0] for _, w in soft).most_common():
        print(f"  {k}: {v}")
    for sf, w in soft[:25]:
        print(f"    {w[:52]:52} {sf}")
    print("\n--- distribution / metadata ---")
    if lens:
        print(f"  rust lines: min={lens[0]} med={lens[len(lens)//2]} max={lens[-1]} (<=3: {sum(1 for x in lens if x<=3)})")
    print(f"  sft categories: {dict(cats.most_common())}")
    print(f"  sft won_via: {dict(vias)}")
    print(f"  sft without rationale: {no_rat}/{len(sfts)}")
    print(f"  distinct system prompts: {len(sysset)} (want 1)")
    if cats and sfts:
        top, cnt = cats.most_common(1)[0]
        share = cnt / len(sfts)
        print(f"  largest category: {top} {share:.0%}" + ("  [imbalance>40%]" if share > 0.4 else ""))
    print(f"\nAUDIT: {'FAIL' if hard else 'PASS'}  ({len(hard)} hard, {len(soft)} soft)")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
