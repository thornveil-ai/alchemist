"""Keystone #1 validation: after struct-carry, jsmn's C `jsmn_parser` must map to
ONE canonical Rust type across every function (was ParserState in jsmn_parse vs
Parser in jsmn_init). Runs stages 1-2 to build specs, then invokes struct-carry
and reports the Rust type each function uses for the parser struct."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from alchemist.config import AlchemistConfig
from alchemist.pipeline import run_translate_all
from alchemist.extractor.schemas import ModuleSpec
from alchemist.verifier.struct_lift import (
    inject_state_shared_types,
    _bare_struct_name,
)

SRC = Path("subjects/jsmn").resolve()


def build_specs() -> list:
    # Stages 1-2 only: analyze + extract -> .alchemist/specs/*.json
    run_translate_all(SRC, "jsmn", config=AlchemistConfig(), stages=(1, 2),
                      refuse_without_diff=False, enforce_validator=False)
    specs_dir = SRC / ".alchemist" / "specs"
    return [ModuleSpec.model_validate(json.loads(f.read_text(encoding="utf-8")))
            for f in sorted(specs_dir.glob("*.json"))]


def main() -> int:
    specs = build_specs()
    n = inject_state_shared_types(str(SRC), specs)
    print(f"struct-carry emitted {n} shared type(s)\n")

    parser_types: Counter[str] = Counter()
    emitted: set[str] = set()
    for m in specs:
        for st in (getattr(m, "shared_types", None) or []):
            emitted.add(st.name)
        for alg in (getattr(m, "algorithms", None) or []):
            for inp in (alg.inputs or []):
                bare = _bare_struct_name(inp.rust_type)
                if bare and ("parser" in bare.lower()):
                    parser_types[bare] += 1
                    print(f"  {alg.name:24s} {inp.name:12s} -> {inp.rust_type}")

    print(f"\nEmitted shared struct names: {sorted(emitted)}")
    print(f"Distinct parser-struct Rust names in signatures: {dict(parser_types)}")

    distinct = set(parser_types)
    ok = len(distinct) <= 1
    print(f"\nKEYSTONE#1 {'PASS' if ok else 'FAIL'}: "
          f"{'one canonical parser type' if ok else 'MULTIPLE parser types — incoherent'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
