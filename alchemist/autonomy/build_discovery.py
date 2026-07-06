"""Build/compile discovery (Tier 1 #1) — figure out how to compile a C target
into something the oracle can link against, WITHOUT a hand-written recipe.

Real C doesn't come with `gcc -I. foo.c` spelled out: it has an `#include` graph
across internal headers, and platform/HAL headers that aren't present in a
leaf-translation context. This iteratively compiles (`-fsyntax-only`), reads the
first *missing header* error, and resolves it either by FINDING the header in the
source tree (add its dir to the include path) or STUBBING it (empty header) when
it's an out-of-tree dependency — exactly what was hand-done for ArduPilot's
`AP_HAL/AP_HAL_Boards.h`. Reports what it stubbed, because a stub is an honesty
boundary (we compiled past a dependency we didn't have).
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


class BuildError(Exception):
    pass


@dataclass
class BuildPlan:
    sources: list[Path]
    include_dirs: list[Path]
    stub_dir: Path
    stubbed: list[str] = field(default_factory=list)
    gcc: str = "g++"

    def include_flags(self) -> list[str]:
        return ["-I" + str(d) for d in self.include_dirs]

    def compile_cmd(self, extra_sources: list[Path], out_bin: Path,
                    opt: str = "-O2") -> list[str]:
        return [self.gcc, opt, *self.include_flags(), "-o", str(out_bin),
                *[str(s) for s in extra_sources], *[str(s) for s in self.sources]]


_MISSING = re.compile(r"fatal error:\s*(.+?):\s*No such file", re.I)


def _resolve_in_tree(header: str, search_roots: list[Path]) -> Path | None:
    """Find a header whose path ends with `header` (e.g. 'AP_HAL/Boards.h'); return
    the include ROOT to add (the dir such that `header` resolves)."""
    tail = header.replace("\\", "/")
    name = Path(tail).name
    for root in search_roots:
        for cand in root.rglob(name):
            cp = str(cand).replace("\\", "/")
            if cp.endswith(tail):
                # strip the header-relative suffix to get the include root
                root_str = cp[: -len(tail)].rstrip("/")
                return Path(root_str) if root_str else cand.parent
    return None


def discover_build(sources: list[Path], search_roots: list[Path], work_dir: Path,
                   gcc: str = "g++", max_iters: int = 60) -> BuildPlan:
    """Return a BuildPlan that compiles `sources` cleanly (syntax/headers), by
    iteratively resolving missing includes (find-in-tree, else stub)."""
    sources = [Path(s) for s in sources]
    search_roots = [Path(r) for r in search_roots]
    stub_dir = Path(work_dir) / "_stubs"
    stub_dir.mkdir(parents=True, exist_ok=True)
    # seed include dirs: each source's own dir + the search roots
    include_dirs: list[Path] = []
    for d in [s.parent for s in sources] + search_roots + [stub_dir]:
        if d not in include_dirs:
            include_dirs.append(d)
    stubbed: list[str] = []

    for _ in range(max_iters):
        cmd = [gcc, "-fsyntax-only", *["-I" + str(d) for d in include_dirs],
               *[str(s) for s in sources]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            return BuildPlan(sources, include_dirs, stub_dir, stubbed, gcc)
        m = _MISSING.search(r.stderr)
        if not m:
            raise BuildError(
                "compile error is not a missing header (can't auto-resolve):\n"
                + "\n".join(r.stderr.splitlines()[:6]))
        header = m.group(1).strip()
        found = _resolve_in_tree(header, search_roots)
        if found is not None:
            if found not in include_dirs:
                include_dirs.append(found)
        else:
            stub = stub_dir / header
            stub.parent.mkdir(parents=True, exist_ok=True)
            if not stub.exists():
                stub.write_text("")
            if header not in stubbed:
                stubbed.append(header)
        # loop retries with the new include dir / stub
    raise BuildError("did not converge to a clean compile within %d iters" % max_iters)
