"""Verification receipts — the claim as an artifact.

Every verify run that reaches the differential gate emits a machine-readable
receipt recording exactly WHAT was verified against WHICH oracle: gate
results, harness bindings (which generated fn was compared to which C
export), case counts, boundary lengths, and the oracle's identity — compiler
version, flags, and content hashes of the C sources and the built DLL. A
consumer can check the claim without re-running anything, and a claim that
can't name its oracle can't be made at all.

Integrity: the receipt embeds a SHA-256 over its own canonical JSON (with
the integrity block excluded), so any edit is detectable. If
ALCHEMIST_RECEIPT_KEY is set, an HMAC-SHA256 over the same bytes is added.
Chaining receipts through signet's HMAC audit chain (the planned substrate)
is deliberately deferred until key custody for this repo is decided —
an unsigned-but-content-addressed receipt is honest; a badly-keyed
signature is theater.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

RECEIPT_SCHEMA = "alchemist-verification-receipt/v1"


def _sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _tool_version(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        first = (r.stdout or r.stderr).strip().splitlines()
        return first[0] if first else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def build_receipt(
    *,
    report,
    rust_workspace: Path,
    diff_config=None,
    diff_evidence: dict | None = None,
    specs=None,
) -> dict:
    """Assemble the receipt dict from a VerificationReport + run evidence."""
    gates = []
    for name in ("compile", "anti_stub", "no_unsafe", "semantic", "test",
                 "differential", "e2e"):
        g = getattr(report, name, None)
        if g is None:
            continue
        gates.append({"gate": g.name, "passed": g.passed, "summary": g.summary})

    harnesses = []
    oracle = None
    if diff_config is not None:
        for h in diff_config.harnesses:
            harnesses.append({
                "algorithm": h.algorithm,
                "category": h.category,
                "cases": h.cases,
                "seed": h.seed,
                "boundary_lengths": list(h.boundary_lengths or []),
            })
        c_sources = [
            {"path": str(p), "sha256": _sha256_file(Path(p))}
            for p in diff_config.c_sources
        ]
        oracle = {
            "ffi_crate": diff_config.ffi_crate_name,
            "compiler": {
                "command": "gcc -shared -O2 -fPIC",
                "version": _tool_version(["gcc", "--version"]),
            },
            "c_sources": c_sources,
        }
    if diff_evidence:
        if oracle is not None:
            dll = diff_evidence.get("dll_path")
            oracle["dll"] = {
                "path": str(dll) if dll else None,
                "sha256": _sha256_file(Path(dll)) if dll else None,
            }
        bindings = diff_evidence.get("bindings") or []
        unresolved = diff_evidence.get("unresolved") or []
        by_alg = {b.split(" -> ")[0]: b for b in bindings}
        un_by_alg = dict(unresolved)
        for h in harnesses:
            if h["algorithm"] in by_alg:
                h["binding"] = by_alg[h["algorithm"]]
            elif h["algorithm"] in un_by_alg:
                h["unresolved"] = un_by_alg[h["algorithm"]]

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "workspace": str(rust_workspace),
        "packages": list(diff_config.packages) if diff_config else [],
        "overall_passed": report.passed,
        "gates": gates,
        "differential": {
            "harnesses": harnesses,
            "cargo_summary": (diff_evidence or {}).get("cargo_summary"),
        },
        "oracle": oracle,
        "specs": {
            "modules": len(specs) if specs is not None else None,
            "algorithms": (
                sum(len(getattr(m, "algorithms", None) or []) for m in specs)
                if specs is not None else None
            ),
        },
        "environment": {
            "rustc": _tool_version(["rustc", "-V"]),
            "cargo": _tool_version(["cargo", "-V"]),
            "platform": platform.platform(),
        },
    }
    return _seal(receipt)


def _canonical_bytes(receipt: dict) -> bytes:
    body = {k: v for k, v in receipt.items() if k != "integrity"}
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _seal(receipt: dict) -> dict:
    payload = _canonical_bytes(receipt)
    integrity: dict = {"content_sha256": hashlib.sha256(payload).hexdigest()}
    key = os.environ.get("ALCHEMIST_RECEIPT_KEY", "")
    if key:
        integrity["hmac_sha256"] = _hmac.new(
            key.encode("utf-8"), payload, hashlib.sha256
        ).hexdigest()
    else:
        integrity["hmac_sha256"] = None
        integrity["note"] = (
            "unsigned — set ALCHEMIST_RECEIPT_KEY to add an HMAC; "
            "signet chain integration pending key-custody decision"
        )
    receipt["integrity"] = integrity
    return receipt


def verify_receipt_integrity(receipt: dict, *, key: str | None = None) -> bool:
    """Recompute the content hash (and HMAC when a key is given)."""
    integrity = receipt.get("integrity") or {}
    payload = _canonical_bytes(receipt)
    if integrity.get("content_sha256") != hashlib.sha256(payload).hexdigest():
        return False
    if key is not None:
        expected = _hmac.new(key.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        if integrity.get("hmac_sha256") != expected:
            return False
    return True


def write_receipt(receipt: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return path
