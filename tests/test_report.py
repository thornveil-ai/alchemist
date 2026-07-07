"""Item 4 — the report artifact renderer."""

from alchemist.autonomy.report import render_markdown

ATT = {
    "project": "mylib",
    "sha256": "abc123def456" * 5 + "1234",
    "summary": {"total": 3, "by_verdict": {"verified": 1, "refused": 2}, "verified_fraction": 0.333},
    "functions": [
        {"function": "hash", "verdict": "verified", "memory_safe": True, "miri": True, "cwes": ["CWE-416"]},
        {"function": "logit", "verdict": "refused", "reason": "oos: uses I/O", "cwes": []},
        {"function": "cbc", "verdict": "refused", "reason": "complex: multi-buffer", "cwes": []},
    ],
}


def test_report_header_and_score():
    md = render_markdown(ATT)
    assert "# Alchemist translation report: mylib" in md
    assert "1/3 functions verified" in md
    assert "sha256:abc123def456" in md          # signed digest surfaced


def test_report_rows_and_reasons():
    md = render_markdown(ATT)
    assert "`hash`" in md and "CWE-416" in md    # verified row shows eliminated CWEs
    assert "oos: uses I/O" in md                 # refused row shows the reason


def test_report_orders_verified_first():
    md = render_markdown(ATT)
    assert md.index("`hash`") < md.index("`logit`")   # verified before refused
