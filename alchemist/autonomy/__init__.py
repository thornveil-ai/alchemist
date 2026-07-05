"""Autonomy tooling — measuring the path to fully-automatic translation.

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
]
