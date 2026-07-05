"""WS4 — autonomous diagnose-and-repair.

The single biggest slice of autonomy debt (see the scorecard: 382/523 open items
are human-ported/-repaired Rust bodies). Almost all of that human labor was the
same loop, run by hand ~9 times on zlib:

    run the differential oracle -> read the EXACT discrepancy -> figure out which
    function is responsible -> re-inject that function with the discrepancy as
    guidance -> re-verify -> keep it if fixed, revert if not.

This module automates that loop. It has four parts, each independently testable:

  1. `describe_*`  — turn a raw differential failure (bytes, or a state-effect
     footprint) into a precise, minimal `Discrepancy` (first divergence, context,
     kind). This is what made the manual fixes fast: not "it's wrong" but
     "byte 47: expected 0x1a, got 0x00; lengths match".
  2. `localize`    — rank which candidate function is responsible, using effect
     footprints (a function is a suspect if it writes the state/region that
     diverged) and the call graph.
  3. `render_repair_guidance` — render the discrepancy (+ suspicion) into a prompt
     block the model can act on.
  4. `RepairLoop`  — orchestrate: oracle -> localize -> re-inject -> verify-or-
     revert, bounded retries, refuse (never fake-green) on non-convergence.

The orchestrator takes plain callables so it wires onto the real pipeline (the
differential runner + the TDD re-fill) and is unit-testable with fakes.

See docs/PATH_TO_AUTONOMY.md (WS4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence


# --------------------------------------------------------------------------
# 1. Discrepancy extraction
# --------------------------------------------------------------------------
@dataclass
class Discrepancy:
    kind: str          # "equal" | "length" | "value" | "field" | "missing"
    location: str      # "byte 47" | "field 'strstart'" | "length"
    expected: str
    actual: str
    context: str = ""  # side-by-side hex / field context
    summary: str = ""

    @property
    def is_equal(self) -> bool:
        return self.kind == "equal"


def _hex(b: bytes) -> str:
    return " ".join(f"{x:02x}" for x in b)


def describe_bytes(expected: bytes, actual: bytes, window: int = 8) -> Discrepancy:
    """Precise diff of two byte streams (e.g. compressed output vs the C reference)."""
    if expected == actual:
        return Discrepancy("equal", "-", "", "", summary="byte-identical")

    n = min(len(expected), len(actual))
    first = next((i for i in range(n) if expected[i] != actual[i]), n)

    lo = max(0, first - window)
    hi_e = min(len(expected), first + window + 1)
    hi_a = min(len(actual), first + window + 1)
    ctx = (
        f"        offset {lo}..\n"
        f"  expected: {_hex(expected[lo:hi_e])}\n"
        f"  actual  : {_hex(actual[lo:hi_a])}\n"
        f"            {'   ' * (first - lo)}^^ first divergence at byte {first}"
    )

    if first < n:
        return Discrepancy(
            kind="value",
            location=f"byte {first}",
            expected=f"0x{expected[first]:02x}",
            actual=f"0x{actual[first]:02x}",
            context=ctx,
            summary=(
                f"outputs diverge at byte {first}: expected 0x{expected[first]:02x}, "
                f"got 0x{actual[first]:02x}"
                + ("" if len(expected) == len(actual)
                   else f" (and lengths differ: expected {len(expected)}, got {len(actual)})")
            ),
        )
    # Common prefix, one is longer.
    return Discrepancy(
        kind="length",
        location=f"byte {first} (end of shorter stream)",
        expected=f"len {len(expected)}",
        actual=f"len {len(actual)}",
        context=ctx,
        summary=(
            f"outputs share the first {first} bytes but lengths differ: "
            f"expected {len(expected)}, got {len(actual)} "
            f"({'output truncated' if len(actual) < len(expected) else 'output too long'})"
        ),
    )


def describe_state(expected: dict, actual: dict, max_fields: int = 6) -> Discrepancy:
    """Field-level diff of two state-effect footprints (stateful-fn oracle)."""
    diffs: list[tuple[str, object, object]] = []
    for k in expected:
        if k not in actual:
            diffs.append((k, expected[k], "<missing>"))
        elif actual[k] != expected[k]:
            diffs.append((k, expected[k], actual[k]))
    extra = [k for k in actual if k not in expected]

    if not diffs and not extra:
        return Discrepancy("equal", "-", "", "", summary="all effect fields match")

    if not diffs and extra:
        return Discrepancy(
            "missing", f"unexpected field(s): {', '.join(extra[:max_fields])}",
            "-", ", ".join(extra[:max_fields]),
            summary=f"implementation wrote fields the reference did not: {', '.join(extra[:max_fields])}",
        )

    field_ctx = "\n".join(
        f"  {k}: expected={_short(e)}  actual={_short(a)}" for k, e, a in diffs[:max_fields]
    )
    first_k, first_e, first_a = diffs[0]
    return Discrepancy(
        kind="field",
        location=f"field '{first_k}'"
        + (f" (+{len(diffs) - 1} more)" if len(diffs) > 1 else ""),
        expected=_short(first_e),
        actual=_short(first_a),
        context=field_ctx,
        summary=(
            f"{len(diffs)} effect field(s) diverge; first: '{first_k}' "
            f"expected {_short(first_e)}, got {_short(first_a)}"
        ),
    )


def _short(v: object, limit: int = 48) -> str:
    s = repr(v)
    return s if len(s) <= limit else s[: limit - 1] + "…"


# --- bridge: real cargo failures -> structured discrepancies ---------------
@dataclass
class DiffFailure:
    test: str
    discrepancy: Discrepancy
    message: str = ""   # the assert_eq! custom message, if any (often the case id)


_ARR_RE = re.compile(r"\[([0-9,\s]*)\]")
_LEFT_RE = re.compile(r"^\s*left:\s*(.+?),?\s*$")
_RIGHT_RE = re.compile(r"^\s*right:\s*(.+?),?\s*$")
_BLOCK_RE = re.compile(r"----\s+(\S+)\s+stdout\s+----")
_MSG_RE = re.compile(r"panicked at [^\n]*:\s*\n(?:assertion.*\n(?:\s*(?:left|right):.*\n)*)?\s*(.+)")


def _parse_byte_array(text: str) -> bytes | None:
    m = _ARR_RE.search(text)
    if not m:
        return None
    body = m.group(1).strip()
    if not body:
        return b""
    try:
        vals = [int(x) for x in body.split(",") if x.strip() != ""]
    except ValueError:
        return None
    if all(0 <= v <= 255 for v in vals):
        return bytes(vals)
    return None


def parse_rust_diff_failures(cargo_output: str) -> list[DiffFailure]:
    """Extract structured discrepancies from a failing `cargo test` run.

    Rust's differential harness compares Rust-vs-C with `assert_eq!` inside the
    test binary, so a divergence surfaces as a panic in the captured output:

        ---- test_deflate_l6_3 stdout ----
        thread '...' panicked at tests/differential.rs:42:5:
        assertion `left == right` failed: deflate L6 case 3
          left: [26, 43, 60, 77]
         right: [26, 43, 0, 77]

    We recover (test name, expected/actual bytes, message) per failing test and
    turn each into a `Discrepancy` via `describe_bytes` — the same precision the
    repair loop consumes. When left/right aren't byte arrays we still capture a
    value-level discrepancy from their reprs. Handles the `left ==`/`(left ==`
    format variants and the reference being on either side of the assert.
    """
    failures: list[DiffFailure] = []
    # Split into per-test blocks; the leading chunk (before any ---- block ----)
    # is ignored (it's the summary/compile output).
    parts = _BLOCK_RE.split(cargo_output)
    # parts = [pre, name1, body1, name2, body2, ...]
    for i in range(1, len(parts) - 1, 2):
        name = parts[i]
        body = parts[i + 1]
        left_m = next((_LEFT_RE.match(l) for l in body.splitlines() if _LEFT_RE.match(l)), None)
        right_m = next((_RIGHT_RE.match(l) for l in body.splitlines() if _RIGHT_RE.match(l)), None)
        if not left_m or not right_m:
            continue
        left_txt, right_txt = left_m.group(1), right_m.group(1)
        # custom assert message (after "failed:" — often the case identifier)
        msg = ""
        fm = re.search(r"assertion.*failed:\s*(.+)", body)
        if fm:
            msg = fm.group(1).strip()
        lb, rb = _parse_byte_array(left_txt), _parse_byte_array(right_txt)
        if lb is not None and rb is not None:
            # Convention: reference/expected is the C side. Harnesses vary on
            # which side that is; describe_bytes is symmetric on location, and
            # we label C-as-expected. If unknown, treat `right` as expected only
            # when `left` looks like the Rust output — default: right=expected.
            disc = describe_bytes(rb, lb)
        else:
            disc = Discrepancy(
                "value", "assert_eq operands",
                left_txt.strip().strip("`"), right_txt.strip().strip("`"),
                summary=f"differential mismatch in {name}",
            )
        failures.append(DiffFailure(test=name, discrepancy=disc, message=msg))
    return failures


# --------------------------------------------------------------------------
# 2. Fault localization
# --------------------------------------------------------------------------
@dataclass
class Suspect:
    function: str
    score: float
    reason: str


def localize(
    discrepancy: Discrepancy,
    candidates: Sequence[str],
    effect_footprints: dict[str, set[str]] | None = None,
    call_graph: dict[str, set[str]] | None = None,
    recently_changed: Sequence[str] = (),
) -> list[Suspect]:
    """Rank candidate functions most likely responsible for `discrepancy`.

    Heuristics, strongest first:
      * a function whose effect footprint includes the diverged field is a prime
        suspect (field-kind discrepancies);
      * functions changed most recently are likelier (we just touched them);
      * callers of a suspect inherit reduced suspicion (propagation).

    Effect footprints are exactly the WS1 metadata the oracle already needs, so
    this gets sharper as WS1 lands. Absent footprints, falls back to recency.
    """
    footprints = effect_footprints or {}
    changed = {f: (len(recently_changed) - i) for i, f in enumerate(recently_changed)}
    scored: list[Suspect] = []

    diverged_field = None
    if discrepancy.kind == "field":
        diverged_field = discrepancy.location.split("'")[1] if "'" in discrepancy.location else None

    for fn in candidates:
        score = 0.0
        reasons: list[str] = []
        fp = footprints.get(fn, set())
        if diverged_field and diverged_field in fp:
            score += 10.0
            reasons.append(f"writes diverged field '{diverged_field}'")
        if fn in changed:
            score += 2.0 + 0.1 * changed[fn]
            reasons.append("recently changed")
        # a function that writes *any* state is a mild suspect for value/length diffs
        if discrepancy.kind in ("value", "length") and fp:
            score += 0.5
            reasons.append("has write effects")
        if score > 0:
            scored.append(Suspect(fn, score, "; ".join(reasons)))

    # Propagate a fraction of suspicion to callers of strong suspects.
    if call_graph:
        strong = {s.function for s in scored if s.score >= 10.0}
        callers = {
            caller for caller, callees in call_graph.items()
            if callees & strong and caller in set(candidates)
        }
        existing = {s.function for s in scored}
        for c in callers - existing:
            scored.append(Suspect(c, 1.0, "calls a prime suspect"))

    scored.sort(key=lambda s: s.score, reverse=True)
    return scored


# --------------------------------------------------------------------------
# 3. Repair guidance rendering
# --------------------------------------------------------------------------
def render_repair_guidance(
    discrepancy: Discrepancy, suspect: Suspect | None = None
) -> str:
    """Render the discrepancy (+ optional suspicion) as a model-facing repair block."""
    if discrepancy.is_equal:
        return ""
    lines = [
        "## Differential-oracle failure (fix the CAUSE, do not special-case the symptom)",
        f"- **What diverged:** {discrepancy.summary}",
        f"- **Where:** {discrepancy.location}",
        f"- **Reference (correct):** {discrepancy.expected}",
        f"- **This implementation (wrong):** {discrepancy.actual}",
    ]
    if discrepancy.context:
        lines.append("```\n" + discrepancy.context + "\n```")
    if suspect is not None:
        lines.append(f"- **Most likely culprit:** `{suspect.function}` — {suspect.reason}")
    lines.append(
        "Re-derive this from the C semantics so the bytes/effects match exactly. "
        "Do NOT hard-code the expected value or add a special case for this input."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 4. The repair loop
# --------------------------------------------------------------------------
@dataclass
class RepairResult:
    status: str                 # "fixed" | "refused" | "unchanged"
    function: str | None
    attempts: int
    history: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "fixed"


@dataclass
class RepairLoop:
    """Bounded, byte-exact-or-refused repair orchestrator.

    Plug in the real pipeline via three callables:
      * run_oracle()            -> (passed: bool, expected: bytes|dict, actual: bytes|dict)
      * reinject(fn, guidance)  -> bool   (re-fill `fn` with the guidance; True if it changed)
      * revert(fn)              -> None   (restore the previous body)

    The loop never claims success without the oracle passing; on non-convergence
    it *refuses* (status="refused"), preserving byte-exact-or-refused.
    """

    run_oracle: Callable[[], tuple[bool, object, object]]
    reinject: Callable[[str, str], bool]
    revert: Callable[[str], None]
    candidates: Sequence[str]
    effect_footprints: dict[str, set[str]] | None = None
    call_graph: dict[str, set[str]] | None = None
    max_attempts: int = 4
    on_event: Callable[[str], None] | None = None

    def _log(self, msg: str, history: list[str]) -> None:
        history.append(msg)
        if self.on_event:
            self.on_event(msg)

    def _oracle(self) -> tuple[bool, Discrepancy | None]:
        """Normalize run_oracle() to (passed, Discrepancy|None).

        Accepts either shape so the loop wires onto both oracle styles:
          * (passed, expected, actual)     -> byte/state diff computed here
          * (passed, Discrepancy | None)   -> discrepancy already extracted
                                              (e.g. via parse_rust_diff_failures)
        """
        res = self.run_oracle()
        passed = bool(res[0])
        if passed:
            return True, None
        if len(res) == 2:
            disc = res[1]
            if not isinstance(disc, Discrepancy):
                disc = Discrepancy("value", "unknown", "", "", summary="oracle failed")
            return False, disc
        return False, self._describe(res[1], res[2])

    def run(self) -> RepairResult:
        history: list[str] = []
        passed, disc0 = self._oracle()
        if passed:
            return RepairResult("fixed", None, 0, history)

        tried: set[str] = set()
        last_fn: str | None = None
        disc = disc0
        for attempt in range(1, self.max_attempts + 1):
            assert disc is not None
            suspects = [
                s for s in localize(
                    disc, self.candidates, self.effect_footprints,
                    self.call_graph, recently_changed=list(tried),
                )
                if s.function not in tried
            ]
            if not suspects:
                self._log("no remaining suspect to try — refusing", history)
                return RepairResult("refused", last_fn, attempt - 1, history)

            suspect = suspects[0]
            last_fn = suspect.function
            tried.add(suspect.function)
            guidance = render_repair_guidance(disc, suspect)
            self._log(
                f"attempt {attempt}: {disc.summary} -> repairing `{suspect.function}` "
                f"(score {suspect.score:.1f}: {suspect.reason})",
                history,
            )
            changed = self.reinject(suspect.function, guidance)
            if not changed:
                self._log(f"`{suspect.function}` unchanged by re-inject; next suspect", history)
                continue

            passed, next_disc = self._oracle()
            if passed:
                self._log(f"oracle PASSED after repairing `{suspect.function}`", history)
                return RepairResult("fixed", suspect.function, attempt, history)
            # regression check: revert if it didn't help, so we never drift worse.
            self._log(f"still failing after `{suspect.function}`; reverting it", history)
            self.revert(suspect.function)
            passed, reverted_disc = self._oracle()
            # carry the freshest discrepancy into the next attempt
            disc = reverted_disc or next_disc or disc

        self._log("exhausted attempts — refusing (never fake-green)", history)
        return RepairResult("refused", last_fn, self.max_attempts, history)

    @staticmethod
    def _describe(expected: object, actual: object) -> Discrepancy:
        if isinstance(expected, (bytes, bytearray)) and isinstance(actual, (bytes, bytearray)):
            return describe_bytes(bytes(expected), bytes(actual))
        if isinstance(expected, dict) and isinstance(actual, dict):
            return describe_state(expected, actual)
        # Fallback: stringify.
        eq = expected == actual
        return Discrepancy(
            "equal" if eq else "value", "value", _short(expected), _short(actual),
            summary="values match" if eq else f"expected {_short(expected)}, got {_short(actual)}",
        )


# --------------------------------------------------------------------------
# 5. Pipeline wiring adapter
# --------------------------------------------------------------------------
def make_repair_loop(
    *,
    run_differential: Callable[[], tuple[bool, str]],
    refill: Callable[[str, str], bool],
    workspace_files: dict[str, Path],
    candidates: Sequence[str],
    effect_footprints: dict[str, set[str]] | None = None,
    call_graph: dict[str, set[str]] | None = None,
    max_attempts: int = 4,
    on_event: Callable[[str], None] | None = None,
) -> RepairLoop:
    """Wire a `RepairLoop` onto the real pipeline.

    Parameters (dependency-injected so this stays unit-testable and doesn't drag
    in the heavy DifferentialTester / TDDGenerator at import time):

      run_differential() -> (passed, cargo_output)
          Run the differential gate; on failure return its captured cargo text
          (stdout+stderr) so we can extract the byte-level discrepancy.
      refill(fn, guidance) -> changed
          Re-fill one Rust function with the repair guidance appended to its
          prompt (thin wrapper over TDDGenerator._fill_in_function). Return
          whether the body actually changed.
      workspace_files: fn -> the .rs file it lives in.
          Used to snapshot the file before a re-inject and restore it on revert,
          so a non-helping repair can't drift the workspace worse.

    The differential discrepancy is recovered via `parse_rust_diff_failures`, so
    the loop sees "byte 47: expected 0x1a got 0x00" — not just "it failed".
    """
    snapshots: dict[str, str] = {}

    def run_oracle() -> tuple[bool, Discrepancy | None]:
        passed, output = run_differential()
        if passed:
            return True, None
        fails = parse_rust_diff_failures(output)
        disc = (
            fails[0].discrepancy
            if fails
            else Discrepancy("value", "differential", "", "",
                             summary="differential gate failed (no parseable assert)")
        )
        return False, disc

    def reinject(fn: str, guidance: str) -> bool:
        f = workspace_files.get(fn)
        if f is not None:
            try:
                snapshots[fn] = Path(f).read_text(encoding="utf-8")
            except OSError:
                snapshots.pop(fn, None)
        return refill(fn, guidance)

    def revert(fn: str) -> None:
        snap = snapshots.get(fn)
        f = workspace_files.get(fn)
        if snap is not None and f is not None:
            try:
                Path(f).write_text(snap, encoding="utf-8")
            except OSError:
                pass

    return RepairLoop(
        run_oracle=run_oracle,
        reinject=reinject,
        revert=revert,
        candidates=candidates,
        effect_footprints=effect_footprints,
        call_graph=call_graph,
        max_attempts=max_attempts,
        on_event=on_event,
    )
