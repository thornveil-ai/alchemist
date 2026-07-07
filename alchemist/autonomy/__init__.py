"""Autonomy tooling — measuring the path to fully-automatic translation.

⚠️  SUPERSEDED / RESEARCH TRACK — READ docs/GROUNDING.md BEFORE ADDING CODE HERE.
The shipping product is `alchemist.cli` (analyzer→extractor→architect→implementer→
verifier→reporter); the CLI imports ZERO symbols from this package. Most modules here
re-implement more-mature shipping modules (see the duplication table in GROUNDING.md).
Only four additions are genuinely new and worth promoting into the shipping pipeline:
Miri gate, sanitizer-diff + divergence, perf parity, and shim_synth (auto stateful
shim). Do not grow this as a parallel pipeline — harden the shipping path instead.

The M1 scorecard (see docs/PATH_TO_AUTONOMY.md) quantifies the "autonomy debt"
for a subject: the human-supplied, subject-specific artifacts the pipeline
currently depends on to translate it. Every item is something M1 (push-button
zlib) must eliminate or auto-synthesize. You can't drive to zero what you don't
count.
"""

from .scorecard import (
    DebtCategory,
    Scorecard,
    build_scorecard,
    render_scorecard,
)
from .repair import (
    Discrepancy,
    Suspect,
    RepairLoop,
    RepairResult,
    DiffFailure,
    describe_bytes,
    describe_state,
    localize,
    render_repair_guidance,
    parse_rust_diff_failures,
    make_repair_loop,
)

__all__ = [
    "DebtCategory",
    "Scorecard",
    "build_scorecard",
    "render_scorecard",
    "Discrepancy",
    "Suspect",
    "RepairLoop",
    "RepairResult",
    "DiffFailure",
    "describe_bytes",
    "describe_state",
    "localize",
    "render_repair_guidance",
    "parse_rust_diff_failures",
    "make_repair_loop",
]
