"""Oracle provenance tags for fuzz-generated test vectors.

Every machine-generated vector records WHICH oracle produced its expected
value — a content hash of the compiled shim/DLL or of the pure-Python
reference's source. The tag rides in TestVector.source (the only free-text
field that survives the pydantic round-trip), e.g.:

    "pure Python reference: crc_word_big [oracle:pyref:_crc_word_big_pure_ref:1a2b3c4d5e6f7081]"

Two consumers:
  * `_backfill_fuzz_vectors` treats tagged vectors as regenerable — they are
    ALWAYS re-derived on the next run so a persisted vector can never
    outlive a fix to its oracle — while untagged (extractor- or
    hand-authored) vectors are never touched.
  * Humans reading a spec checkpoint can see exactly what blessed a value.
"""

from __future__ import annotations

import hashlib
import inspect
import re
from pathlib import Path

_ORACLE_TAG_RE = re.compile(r"\s*\[oracle:[^\]]+\]\s*$")


class OracleDisputeError(RuntimeError):
    """Two oracles disagree about ground truth.

    This is a stop-the-line event: no caller may downgrade it to a warning
    and continue with vectors minted by either disputant. Entry points must
    let it propagate (or re-raise it) — the crc_word_big chimera shipped
    precisely because a disputed reference kept blessing vectors.
    """


def is_tagged(vector) -> bool:
    """True when the vector's source carries an oracle provenance tag."""
    return bool(_ORACLE_TAG_RE.search(getattr(vector, "source", "") or ""))


def strip_tag(source: str) -> str:
    return _ORACLE_TAG_RE.sub("", source or "").rstrip()


def _short_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()[:16]


def oracle_tag_for_file(kind: str, path) -> str:
    """Tag identifying a compiled oracle artifact (shim DLL, reference DLL)."""
    p = Path(path) if path else None
    if p is None or not p.exists():
        return f"{kind}:unknown:0000000000000000"
    return f"{kind}:{p.name}:{_short_hash(p.read_bytes())}"


def oracle_tag_for_callable(kind: str, obj) -> str:
    """Tag identifying a Python reference oracle by its source content."""
    name = getattr(obj, "__name__", None) or type(obj).__name__
    try:
        payload = inspect.getsource(
            obj if inspect.isfunction(obj) or inspect.ismethod(obj) else type(obj)
        ).encode("utf-8")
    except (OSError, TypeError):
        payload = repr(obj).encode("utf-8")
    return f"{kind}:{name}:{_short_hash(payload)}"


def tag_vectors(vectors, tag: str):
    """Stamp every vector's source with the oracle tag (idempotent)."""
    for v in vectors:
        base = strip_tag(getattr(v, "source", "") or "")
        v.source = f"{base} [oracle:{tag}]".strip()
    return vectors
