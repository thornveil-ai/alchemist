"""Mechanical integer-width coercion (like borrow_fix, for types).

C converts integer widths implicitly; Rust does not, so translated code hits
`u8 ^= u32` (E0277) and `expected u8, found u32` (E0308). These are DETERMINISTIC:
rustc names the line AND the exact types, so the fix is mechanical — insert an
`as <target>` cast — not a reasoning task the model must win. Applied one error at
a time, recompiling between (like fix_borrows). This turns the single most common
C->Rust type friction into a reliable pass.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

_E0277 = re.compile(r"error\[E0277\]: no implementation for `(\w+)\s*([-+*/^|&%]+)=\s*(\w+)`")
_E0308 = re.compile(r"error\[E0308\]: mismatched types")
_EXPECTED = re.compile(r"expected `?(\w+)`?, found `?(\w+)`?")
_LOC = re.compile(r"-->\s+\S+:(\d+):\d+")
_INT_TYPES = {"u8", "u16", "u32", "u64", "u128", "usize",
              "i8", "i16", "i32", "i64", "i128", "isize"}


def parse_type_errors(output: str) -> list[tuple[str, int, str]]:
    """(kind, line, target_type) for E0277 compound-assign and E0308 int mismatches."""
    errs: list[tuple[str, int, str]] = []
    lines = output.splitlines()
    for i, l in enumerate(lines):
        m = _E0277.search(l)
        if m and m.group(1) in _INT_TYPES:
            for j in range(i, min(i + 6, len(lines))):
                lm = _LOC.search(lines[j])
                if lm:
                    errs.append(("compound", int(lm.group(1)), m.group(1)))
                    break
            continue
        if _E0308.search(l):
            tgt, line_no = None, None
            for j in range(i, min(i + 10, len(lines))):
                em = _EXPECTED.search(lines[j])
                lm = _LOC.search(lines[j])
                if lm and line_no is None:
                    line_no = int(lm.group(1))
                if em and tgt is None and em.group(1) in _INT_TYPES and em.group(2) in _INT_TYPES:
                    tgt = em.group(1)
            if tgt and line_no:
                errs.append(("assign", line_no, tgt))
    return errs


def apply_type_fix(source: str, line_no: int, target: str) -> str | None:
    """Wrap the RHS of the offending assignment in `(RHS) as <target>`."""
    lines = source.split("\n")
    if not (1 <= line_no <= len(lines)):
        return None
    idx = line_no - 1
    line = lines[idx]
    if "as " + target in line:
        return None  # already cast here -> avoid a fix loop
    # compound assign: LHS OP= RHS;  ->  LHS OP= (RHS) as target;
    m = re.match(r"(\s*)(.+?)\s*([-+*/^|&%]+=)\s*(.+);\s*$", line)
    if m:
        lines[idx] = "%s%s %s (%s) as %s;" % (m.group(1), m.group(2), m.group(3), m.group(4), target)
        return "\n".join(lines)
    # plain assign: LHS = RHS;  ->  LHS = (RHS) as target;   (not ==, not let-with-type)
    m = re.match(r"(\s*)([\w.\[\]() ]+?)\s*=\s*(.+);\s*$", line)
    if m and "==" not in line and ": " not in m.group(2):
        lines[idx] = "%s%s = (%s) as %s;" % (m.group(1), m.group(2), m.group(3), target)
        return "\n".join(lines)
    return None


def fix_types(module_path: Path, run_build: Callable[[], str], max_iters: int = 24) -> bool:
    """Resolve E0277/E0308 integer-width mismatches mechanically. True if cleared."""
    module_path = Path(module_path)
    last = None
    for _ in range(max_iters):
        errs = parse_type_errors(run_build())
        if not errs:
            return True
        kind, line, target = errs[0]
        if (line, target) == last:  # no progress on the same error -> give up
            return False
        new = apply_type_fix(module_path.read_text(encoding="utf-8"), line, target)
        if new is None:
            return False
        module_path.write_text(new, encoding="utf-8")
        last = (line, target)
    return False
