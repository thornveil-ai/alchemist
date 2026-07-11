"""Regression guard for SpecExtractor's live helpers.

CI never runs the real extract path with a model, so a live helper can be
deleted without any unit test failing while the actual `translate` pipeline
breaks at stage 2. This happened to `_build_project_context` (wrongly removed
with the dead _extract_module_OLD_BULK cluster). These tests exercise the
helper directly — no model, no network — so the method's absence fails loudly.
"""

from __future__ import annotations

from alchemist.extractor.spec_extractor import SpecExtractor


def _extractor() -> SpecExtractor:
    # __init__ builds an LLM client but makes no network call; the helper under
    # test doesn't touch the LLM.
    return SpecExtractor()


def test_build_project_context_exists_and_is_callable():
    ex = _extractor()
    assert hasattr(ex, "_build_project_context"), (
        "_build_project_context is called by extract_all() every run — it must "
        "exist on SpecExtractor"
    )
    analysis = {
        "source": "subjects/tinychk",
        "summary": {"total_files": 2, "total_lines": 113, "total_functions": 4},
        "modules": [
            {"name": "tinychk", "category": "algorithm",
             "functions": ["a", "b", "c", "d"], "total_lines": 51},
        ],
    }
    ctx = ex._build_project_context(analysis)
    assert isinstance(ctx, str) and ctx
    assert "tinychk" in ctx
    assert "Files: 2" in ctx
    assert "Functions: 4" in ctx
    assert "1 function" not in ctx  # sanity: renders the 4-function module


def test_build_project_context_handles_empty_analysis():
    ex = _extractor()
    ctx = ex._build_project_context({})
    assert isinstance(ctx, str)
    assert "Project Analysis Summary" in ctx
