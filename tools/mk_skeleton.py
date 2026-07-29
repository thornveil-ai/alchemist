#!/usr/bin/env python3
"""Deterministically scaffold a minimal, compiling free-fn skeleton workspace for a
single-function stream-cipher subject, so `solo` can fill the body (no reliance on
`implement`'s nondeterministic struct/Result output). Layout matches what solo +
generate_tests_for_workspace expect: <output>/<crate>/src/<module>.rs holding the
free fn (+ the appended #[cfg(test)] mod tests)."""
import sys
from pathlib import Path

subj = Path(sys.argv[1])      # subjects/ingest/chacha20
crate = sys.argv[2]           # chacha20-cipher
module = sys.argv[3]          # chacha20
sig = sys.argv[4]             # full Rust fn signature, e.g. "pub fn chacha20_xor(key: &[u8], ...)"

out = subj / ".alchemist" / "output"
(out / crate / "src").mkdir(parents=True, exist_ok=True)

(out / "Cargo.toml").write_text(
    "[workspace]\nresolver = \"2\"\nmembers = [\"%s\"]\n" % crate, encoding="utf-8")

(out / crate / "Cargo.toml").write_text(
    "[package]\nname = \"%s\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\n" % crate,
    encoding="utf-8")

(out / crate / "src" / "lib.rs").write_text(
    "#![forbid(unsafe_code)]\n#![no_std]\n#![allow(unused_imports)]\n"
    "#[macro_use]\nextern crate alloc;\n"
    "use alloc::vec::Vec;\n\npub mod %s;\npub use self::%s::*;\n" % (module, module),
    encoding="utf-8")

# Stub free fn — the exact signature the spec implies; solo replaces the whole fn.
body = (
    "#![allow(unused_variables, dead_code, clippy::too_many_arguments)]\n\n"
    "use crate::*;\n\n"
    "%s {\n    // stub — to be filled by the model\n}\n" % sig
)
(out / crate / "src" / ("%s.rs" % module)).write_text(body, encoding="utf-8")
print("scaffolded", out)
