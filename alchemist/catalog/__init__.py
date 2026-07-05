"""C-idiom pattern catalog (WS6 of the autonomy roadmap).

A versioned, machine-consumable catalog of `C-idiom -> Rust-model` transforms,
seeded from the zlib translation. The pipeline uses it two ways:

  * `match_idioms(c_source)` detects which idioms a C function likely uses
    (cheap regex signals) so only relevant patterns are surfaced.
  * `render_prompt_hints(idioms)` renders those patterns into a concise block
    injected into the model's context before it writes the Rust body.

Each idiom encodes something a human recognized by hand during the zlib
translation. The catalog is the "learning layer": every new library contributes
patterns, and regressions guard them.

See docs/PATH_TO_AUTONOMY.md (WS6).
"""

from .idioms import (
    Idiom,
    IDIOMS,
    CATALOG_VERSION,
    match_idioms,
    render_prompt_hints,
    idiom_by_id,
)

__all__ = [
    "Idiom",
    "IDIOMS",
    "CATALOG_VERSION",
    "match_idioms",
    "render_prompt_hints",
    "idiom_by_id",
]
