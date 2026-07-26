"""_filter_to_project keeps only project content (drops system headers) using
gcc -E line markers — the piece that makes multi-variant #ifdef C preprocess
cleanly without flooding the analyzer with <stdint.h> etc."""
from pathlib import Path
from alchemist.analyzer.preprocessor import _filter_to_project


def test_keeps_project_drops_system():
    # a simulated `gcc -E` stream with markers for a project file + a system one
    text = "\n".join([
        '# 1 "myproj/foo.c"',
        "int project_fn(int a) { return a + 1; }",
        '# 1 "/usr/include/stdint.h" 1 3 4',
        "typedef long system_type_should_be_dropped;",
        '# 5 "myproj/foo.c" 2',
        "int another_project_fn(void) { return 0; }",
        '# 1 "<built-in>"',
        "int builtin_dropped(void);",
    ])
    out = _filter_to_project(text, [Path("myproj")])
    assert "project_fn" in out and "another_project_fn" in out
    assert "system_type_should_be_dropped" not in out
    assert "builtin_dropped" not in out
    # standard int types are re-provided
    assert "#include <stdint.h>" in out


def test_no_markers_yields_just_includes():
    out = _filter_to_project("int x;", [Path("myproj")])
    # nothing was attributed to a project file -> only the prepended includes
    assert "#include <stdint.h>" in out and "int x;" not in out
