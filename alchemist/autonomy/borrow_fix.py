"""Mechanical borrow-restructuring (Tier 3) — close the frontier without the model.

Borrow-checker conflicts (E0502/E0503) are the wall the model kept hitting
(deflate_fast, SHA-256): C aliases freely, safe Rust can't. But these errors are
DETERMINISTIC — rustc points at the exact line and the borrowed variable — so the
fix is mechanical, not a reasoning task. Two rewrites cover the vast majority:

  A. `f(ctx, &ctx.field)`      -> `let t = ctx.field; f(ctx, &t);`   (hoist the borrow)
  B. `x.a = f(&mut x, ..)`     -> `let t = f(&mut x, ..); x.a = t;`  (hoist the RHS)

Applied one error at a time, recompiling between (line numbers shift), until the
borrow errors are gone. This makes the diagnoser's job logic-only, and turns the
"borrow restructuring" wall into a reliable pass.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

_ERR = re.compile(r"error\[(E050[23])\]: cannot (?:borrow|use) `\*?([\w.]+)")
_LOC = re.compile(r"-->\s+\S+:(\d+):\d+")


def parse_borrow_errors(output: str) -> list[tuple[str, int, str]]:
    """(code, line, base_var) for each E0502/E0503, in report order."""
    errs: list[tuple[str, int, str]] = []
    lines = output.splitlines()
    for i, l in enumerate(lines):
        m = _ERR.search(l)
        if not m:
            continue
        var = m.group(2).lstrip("*").split(".")[0]
        for j in range(i, min(i + 6, len(lines))):
            lm = _LOC.search(lines[j])
            if lm:
                errs.append((m.group(1), int(lm.group(1)), var))
                break
    return errs


def apply_borrow_fix(source: str, line_no: int, var: str, counter: int) -> str | None:
    """Rewrite the one offending line; return new source or None if no pattern fits."""
    lines = source.split("\n")
    if not (1 <= line_no <= len(lines)):
        return None
    idx = line_no - 1
    line = lines[idx]
    indent = re.match(r"\s*", line).group(0)
    tmp = "__brw%d" % counter
    v = re.escape(var)

    # Pattern A: an immutable `&var.field` argument while `var` is also passed
    # (bare or `&mut`) on the same line -> hoist the field to a local copy.
    m = re.search(r"&(?!mut\b)(" + v + r"\.[\w.]+(?:\[[^\]]+\])?)", line)
    if m and re.search(r"(?<![\w.])" + v + r"\b(?!\s*\.)", line):
        expr = m.group(1)
        newline = line[:m.start()] + "&" + tmp + line[m.end():]
        lines[idx:idx + 1] = [indent + "let %s = %s;" % (tmp, expr), newline]
        return "\n".join(lines)

    # Pattern B: `lhs <op>= rhs;` where both sides reference var (self-borrowing
    # assignment) -> hoist the RHS into a local.
    am = re.match(r"(\s*)([\w.\[\]]+)\s*([-+^|&*/]?=)\s*(.+);\s*$", line)
    if am and re.search(r"\b" + v + r"\b", am.group(4)) and re.search(r"\b" + v + r"\b", am.group(2)):
        lhs, op, rhs = am.group(2), am.group(3), am.group(4)
        lines[idx:idx + 1] = [indent + "let %s = %s;" % (tmp, rhs),
                              indent + "%s %s %s;" % (lhs, op, tmp)]
        return "\n".join(lines)
    return None


def fix_borrows(module_path: Path, run_build: Callable[[], str], max_iters: int = 16) -> bool:
    """Resolve E0502/E0503 in `module_path` mechanically. `run_build()` returns the
    compiler output. True if all borrow errors were cleared."""
    module_path = Path(module_path)
    counter = 0
    for _ in range(max_iters):
        errs = parse_borrow_errors(run_build())
        if not errs:
            return True
        code, line, var = errs[0]
        new = apply_borrow_fix(module_path.read_text(encoding="utf-8"), line, var, counter)
        if new is None:
            return False  # no mechanical pattern -> hand back to the diagnoser
        module_path.write_text(new, encoding="utf-8")
        counter += 1
    return False
