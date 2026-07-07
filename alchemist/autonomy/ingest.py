"""Item C — the ingestion front-door + scope triage (what makes it a 'shop').

A one-stop shop starts by pointing at a real project, not a curated file. This:

  ingest_project — git URL / tarball / local dir -> a normalized Project (the .c
                   translation units, headers, include dirs).

  scope_triage   — classify every function by the shape Alchemist can translate
                   (scalar / buffer / stateful / heap / effectful) OR mark it
                   out-of-scope with a REASON (I/O, syscalls, varargs, asm, function
                   pointers). This is the honesty layer: the pipeline can only promise
                   what it can verify, and triage says up front what that is.
"""

from __future__ import annotations

import re
import subprocess
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

from alchemist.autonomy.onboard import discover_functions


@dataclass
class Project:
    root: Path
    c_files: list[Path]
    headers: list[Path]
    include_dirs: list[Path]


def ingest_project(source: str, work: Path) -> Project:
    """Normalize a git URL, tarball, or local directory into a Project."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    src = str(source)
    if src.endswith(".git") or src.startswith(("http://", "https://", "git@")) and src.endswith(".git"):
        root = work / "clone"
        if not root.exists():
            subprocess.run(["git", "clone", "--depth", "1", src, str(root)], check=True,
                           capture_output=True)
    elif src.endswith((".tar.gz", ".tgz", ".tar")):
        root = work / "extracted"
        root.mkdir(exist_ok=True)
        with tarfile.open(src) as t:
            t.extractall(root)
    else:
        root = Path(src)
    c_files = sorted(root.rglob("*.c"))
    headers = sorted(root.rglob("*.h"))
    include_dirs = sorted({h.parent for h in headers} | {c.parent for c in c_files})
    return Project(root, c_files, headers, include_dirs)


@dataclass
class FnScope:
    name: str
    scope: str      # scalar | buffer | stateful | heap | effectful | oos
    reason: str


# patterns that put a function beyond verified-or-refused (for now)
_OOS = re.compile(
    r"\b(fopen|fclose|fread|fwrite|fprintf|fscanf|printf|scanf|puts|getchar|"
    r"socket|connect|send|recv|bind|listen|accept|"
    r"pthread\w*|mtx_\w*|thrd_\w*|atomic_\w*|"
    r"system|exec\w*|fork|popen|"
    r"va_start|va_arg|va_end|"
    r"setjmp|longjmp|"
    r"__asm__|__asm|asm\s*\()\b")


def scope_triage(funcs: dict, globals_names: set[str] | None = None) -> list[FnScope]:
    """Classify each function by the shape we can translate, or mark oos with why."""
    g = globals_names or set()
    out: list[FnScope] = []
    for n, f in funcs.items():
        body = getattr(f, "body", "")
        params = getattr(f, "params", "")
        ret = getattr(f, "ret", "")
        if _OOS.search(body):
            out.append(FnScope(n, "oos", "uses I/O / syscall / varargs / asm"))
        elif "(*" in params:
            out.append(FnScope(n, "oos", "function-pointer parameter (callback)"))
        elif re.search(r"\b(?:malloc|calloc)\b", body) and re.search(r"\breturn\b", body) \
                and "*" not in ret and ret.strip() not in ("void", ""):
            out.append(FnScope(n, "heap", "allocates a buffer and returns ownership"))
        elif g & set(re.findall(r"\b\w+\b", body)):
            out.append(FnScope(n, "effectful", "reads/writes file-static global state"))
        elif re.search(r"(?:_CTX|_ctx|_state|_context)\s*\*|\bstruct\s+\w+\s*\*", params):
            out.append(FnScope(n, "stateful", "carries a context/state struct"))
        elif re.search(r"\b(?:const\s+)?(?:unsigned\s+)?char\s*\*|\bBYTE\s*\*|\buint8_t\s*\*|\[\s*\]",
                       params) and re.search(r"\b(len|n|size|count)\b", params):
            kind = "buffer" if ("*" in ret or "void" not in ret and re.search(r"out|dst|dest", params)) \
                else "scalar"
            out.append(FnScope(n, kind, "byte buffer + length"))
        else:
            out.append(FnScope(n, "scalar", "scalar/simple signature"))
    return out


def triage_report(scopes: list[FnScope]) -> dict:
    """Honest summary: counts by scope + the in-scope fraction."""
    by: dict[str, int] = {}
    for s in scopes:
        by[s.scope] = by.get(s.scope, 0) + 1
    in_scope = sum(v for k, v in by.items() if k != "oos")
    return {"total": len(scopes), "in_scope": in_scope, "by_scope": dict(sorted(by.items()))}
