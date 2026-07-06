"""Crash-safe recovery for the regen loop.

A regen killed by a timeout (SIGKILL) skips the `finally` restore and leaves the
module stubbed — which then poisons every later run (the corrupted file is read
as the "original"). This is exactly what happened once by hand. The fix: a
crash-safe `.regenbak` sidecar written before any modification, recovered at the
start of the next run.
"""

import tempfile
from pathlib import Path

from alchemist.autonomy.regen_batch import recover_pending, _bak_path


def _tmp_module(text: str) -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / "trees.rs"
    p.write_text(text, encoding="utf-8")
    return p


def test_recover_restores_from_sidecar():
    mod = _tmp_module("STUBBED unimplemented!()")     # killed mid-run state
    _bak_path(mod).write_text("pub fn gen_bitlen() {}", encoding="utf-8")  # pristine snapshot
    assert recover_pending(mod) is True
    assert mod.read_text(encoding="utf-8") == "pub fn gen_bitlen() {}"
    assert not _bak_path(mod).exists()               # sidecar consumed


def test_recover_is_noop_when_no_sidecar():
    mod = _tmp_module("pub fn ok() {}")
    assert recover_pending(mod) is False
    assert mod.read_text(encoding="utf-8") == "pub fn ok() {}"


def test_recover_idempotent():
    mod = _tmp_module("corrupt")
    _bak_path(mod).write_text("pristine", encoding="utf-8")
    assert recover_pending(mod) is True
    # second call has nothing to do and must not clobber the recovered file
    assert recover_pending(mod) is False
    assert mod.read_text(encoding="utf-8") == "pristine"
