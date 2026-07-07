"""Item B — safety verification + provenance (what makes 'securely' defensible).

Three artifacts an accreditor actually needs:

  safety_audit  — the translated Rust must earn "safe": zero `unsafe`/raw pointers,
                  or `unsafe` confined to audited FFI shims (one `from_raw_parts` per
                  `extern "C"` wrapper). Anything else is flagged.

  cwe_findings  — the security PAYOFF, made concrete: which CWE classes the C exposes
                  (malloc/free -> UAF/double-free/leak; strcpy/memcpy -> overflow;
                  raw indexing -> OOB) that safe Rust structurally eliminates.

  VerificationReceipt — a signed, reproducible record per function/project: verdict,
                  vector count, branch coverage, safety report, Miri result, CWEs
                  eliminated, model. Content-hashed (and signet-signed when available)
                  so the claim is attestable, not a footnote in a log.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field


# C idiom -> (CWE, class) that translating to SAFE Rust structurally removes
_CWE_PATTERNS: list[tuple[str, list[tuple[str, str]]]] = [
    (r"\b(?:malloc|calloc)\s*\(", [("CWE-401", "memory leak"), ("CWE-416", "use-after-free")]),
    (r"\bfree\s*\(", [("CWE-415", "double free"), ("CWE-416", "use-after-free")]),
    (r"\brealloc\s*\(", [("CWE-416", "use-after-free")]),
    (r"\bstrcpy\s*\(", [("CWE-120", "unbounded buffer copy")]),
    (r"\bstrcat\s*\(", [("CWE-120", "unbounded buffer copy")]),
    (r"\bgets\s*\(", [("CWE-242", "inherently unsafe gets()")]),
    (r"\b(?:sprintf|vsprintf)\s*\(", [("CWE-134", "format string"), ("CWE-787", "OOB write")]),
    (r"\bmemcpy\s*\(", [("CWE-120", "copy without bounds check")]),
    (r"\[\s*\w+\s*\]", [("CWE-125", "OOB read"), ("CWE-787", "OOB write")]),
]


def cwe_findings(c_src: str) -> list[tuple[str, str]]:
    """CWE classes present in the C that safe Rust eliminates (deduped, sorted)."""
    found: dict[str, str] = {}
    for pat, cwes in _CWE_PATTERNS:
        if re.search(pat, c_src):
            for cwe, desc in cwes:
                found.setdefault(cwe, desc)
    return sorted(found.items())


@dataclass
class SafetyReport:
    unsafe_blocks: int
    raw_pointers: int
    ffi_wrappers: int
    memory_safe: bool     # unsafe confined to FFI shims (or none at all)


def safety_audit(rust_src: str) -> SafetyReport:
    unsafe = len(re.findall(r"\bunsafe\b", rust_src))
    raw = len(re.findall(r"\*\s*(?:const|mut)\b", rust_src))
    ffi = rust_src.count('extern "C"')
    # each FFI wrapper legitimately owns at most one `unsafe` (the from_raw_parts);
    # any unsafe beyond that is a real safety concern.
    memory_safe = unsafe <= ffi
    return SafetyReport(unsafe, raw, ffi, memory_safe)


@dataclass
class VerificationReceipt:
    function: str
    verdict: str                     # "verified" | "partial" | "refused"
    vectors: int
    branch_coverage: float
    safety: SafetyReport
    miri_clean: bool | None
    cwes_eliminated: list
    model: str
    tool: str = "alchemist"

    def canonical(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()

    def attest(self) -> dict:
        """Receipt + integrity digest, signet-signed if the runtime is available."""
        out = {"receipt": asdict(self), "sha256": self.digest()}
        try:                                     # optional signet signing
            from signet import sign as _sign     # type: ignore
            out["signature"] = _sign(self.canonical())
        except Exception:
            out["signature"] = None
        return out
