#!/usr/bin/env python3
"""Generate a minimal-but-valid .alchemist/specs + architecture.json for a
single-function stream-cipher subject, validated against the real Pydantic
models before writing. Differential signatures come from
collect_subject_signatures, so the spec only needs to load + name the fn."""
import json, sys
from pathlib import Path
sys.path.insert(0, ".")

subj = Path(sys.argv[1])          # e.g. subjects/ingest/chacha20
mod = sys.argv[2]                 # module name, e.g. chacha20
fn = sys.argv[3]                  # function, e.g. chacha20_xor
disp = sys.argv[4]                # display, e.g. "ChaCha20"
desc = sys.argv[5]                # one-line description
std = sys.argv[6]                 # referenced standard

from alchemist.extractor.schemas import ModuleSpec
from alchemist.architect.schemas import CrateArchitecture

algo = {
    "name": fn,
    "display_name": disp,
    "category": "cipher",
    "description": desc,
    "mathematical_description": desc,
    "inputs": [
        {"name": "key", "rust_type": "&[u8]", "description": "Secret key.", "direction": "input", "constraints": ""},
        {"name": "nonce", "rust_type": "&[u8]", "description": "Nonce / IV.", "direction": "input", "constraints": ""},
        {"name": "counter", "rust_type": "u32", "description": "Initial block counter.", "direction": "input", "constraints": ""},
        {"name": "in_", "rust_type": "&[u8]", "description": "Plaintext input.", "direction": "input", "constraints": ""},
        {"name": "out", "rust_type": "&mut [u8]", "description": "Ciphertext output.", "direction": "output", "constraints": ""},
        {"name": "len", "rust_type": "usize", "description": "Byte length.", "direction": "input", "constraints": ""},
    ],
    "outputs": [],
    "return_type": "()",
    "state": [],
    "invariants": [],
    "error_conditions": [],
    "preconditions": [],
    "postconditions": [],
    "test_vectors": [],
    "referenced_standards": [std],
    "suggested_rust_traits": [],
    "no_std_compatible": True,
    "unsafe_required": False,
    "unsafe_justification": "",
    "time_complexity": "",
    "space_complexity": "",
    "source_functions": [fn],
    "source_files": [],
}
spec = {
    "name": mod,
    "display_name": disp,
    "description": f"Module containing 1 function: {fn}",
    "algorithms": [algo],
}
arch = {
    "workspace_name": f"translated-{mod}",
    "description": "Complete Rust workspace architecture.",
    "crates": [
        {"name": f"{mod}-cipher", "description": desc, "is_no_std": True,
         "dependencies": [], "external_deps": [], "modules": [mod], "public_api": [fn]},
    ],
    "dependency_graph": {f"{mod}-cipher": []},
    "traits": [], "error_types": [], "ownership_decisions": [],
    "features": [], "state_wrappers": [], "builders": [], "unsafe_boundaries": [],
}

# Validate against the real models.
ModuleSpec.model_validate(spec)
CrateArchitecture.model_validate(arch)

alch = subj / ".alchemist"
(alch / "specs").mkdir(parents=True, exist_ok=True)
(alch / "specs" / f"{mod}.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
(alch / "architecture.json").write_text(json.dumps(arch, indent=2), encoding="utf-8")
print("wrote specs + architecture for", mod, "(validated)")
