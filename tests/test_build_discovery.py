"""Build discovery: include resolution + stubbing logic (gcc-free unit tests).

The end-to-end compile loop is validated against real ArduPilot crc.cpp on the
box (needs a compiler); here we lock the resolution logic.
"""

import tempfile
from pathlib import Path

from alchemist.autonomy.build_discovery import (
    _resolve_in_tree, BuildPlan, discover_build, BuildError,
)


def _tree(files: dict) -> Path:
    root = Path(tempfile.mkdtemp())
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return root


def test_resolve_finds_header_include_root():
    root = _tree({"src/lib/foo.h": "", "src/main.c": ""})
    # a source that does `#include "lib/foo.h"` — the include ROOT is src/
    got = _resolve_in_tree("lib/foo.h", [root])
    assert got is not None
    assert (got / "lib" / "foo.h").exists()


def test_resolve_returns_none_when_absent():
    root = _tree({"src/main.c": ""})
    assert _resolve_in_tree("AP_HAL/Boards.h", [root]) is None


def test_build_plan_compile_cmd():
    plan = BuildPlan([Path("crc.cpp")], [Path("inc")], Path("stubs"), [], "g++")
    cmd = plan.compile_cmd([Path("_oracle.cpp")], Path("out"))
    assert "-Iinc" in cmd and "crc.cpp" in cmd and "_oracle.cpp" in cmd
    assert cmd[0] == "g++"


def test_discover_stubs_missing_out_of_tree_header():
    # a self-contained C that includes a header not in the tree -> must be stubbed
    root = _tree({"thing.c": '#include <Missing/dep.h>\nint f(void){return 0;}\n'})
    try:
        plan = discover_build([root / "thing.c"], [root], root, gcc="cc")
    except (FileNotFoundError, BuildError):
        # no compiler available in this environment -> skip (box validates e2e)
        import pytest
        pytest.skip("no C compiler available")
    assert "Missing/dep.h" in plan.stubbed
    assert (plan.stub_dir / "Missing" / "dep.h").exists()
