"""Build the C subject as a shared library for differential testing.

When the pipeline translates a fresh C codebase, Stage 5's differential
gate needs a pre-built C shared library to call via ctypes/FFI. This
module discovers toolchains (MinGW on Windows, gcc/clang on Linux/macOS),
compiles all .c files in the subject, and produces a DLL/so/dylib.

The build is cached per (source-hash, flags) tuple so re-runs skip
recompilation unless C sources changed.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Directory names that hold NON-library code (tests, examples, build artifacts,
# vendored deps). Excluded from oracle/differential compilation so a real library
# tree builds cleanly without hand-config (WALL 4).
_NONLIB_DIRS = {
    "test", "tests", "example", "examples", "bench", "benches", "demo", "demos",
    "fuzz", "fuzzing", "doc", "docs", "build", "cmake", "third_party", "vendor",
    ".git", "target", ".alchemist", "node_modules", "contrib",
    # Build-time tooling that GENERATES sources (e.g. table generators) — not the
    # library itself. Their .c files (libcrc's precalc/crc32_table.c) fill a global
    # table and have nothing to differentially fuzz; treating them as modules is wrong.
    "precalc", "precompute", "gen", "tools", "tool", "scripts", "bin", "util", "utils",
}
_MAIN_RE = re.compile(r"\bint\s+main\s*\(")
# An amalgamation/unity build: a .c that #includes other .c files (onelua.c,
# sqlite3.c). Linking it with the real .c files duplicates every symbol.
_AMALGAM_RE = re.compile(r'#\s*include\s+"[^"]+\.c"')


def prepare_native_build(root, *, timeout: int = 180) -> str | None:
    """Run a library's native build best-effort to materialize BUILD-TIME-GENERATED sources
    (lookup tables, config headers, `*.inc` files) before discovery/compilation.

    Detects a Makefile (make) or CMakeLists.txt (out-of-source cmake build). Best-effort:
    never raises and a failed/partial build is fine as long as `discover_c_build` still finds
    compilable sources afterwards. Returns a short status string, or None if no build system.

    SECURITY: this executes the library's own build, i.e. arbitrary code from the subject.
    That is inherent to "translate this library" (you must build what you translate), but it
    should only ever run on a library the operator chose to translate. Bounded by `timeout`,
    output captured, run in-tree as the current (non-root) user.
    """
    root = Path(root)
    if shutil.which("make") is not None:
        for mk in ("Makefile", "makefile", "GNUmakefile"):
            if (root / mk).exists():
                try:
                    r = subprocess.run(
                        ["make"], cwd=str(root), capture_output=True,
                        text=True, timeout=timeout,
                    )
                    return f"make: {'ok' if r.returncode == 0 else 'partial'}"
                except Exception:  # noqa: BLE001
                    return "make: failed"
    if (root / "CMakeLists.txt").exists() and shutil.which("cmake") is not None:
        try:
            bd = root / "_alch_cmake_build"
            bd.mkdir(exist_ok=True)
            subprocess.run(["cmake", str(root)], cwd=str(bd),
                           capture_output=True, text=True, timeout=timeout)
            r = subprocess.run(["cmake", "--build", "."], cwd=str(bd),
                               capture_output=True, text=True, timeout=timeout)
            return f"cmake: {'ok' if r.returncode == 0 else 'partial'}"
        except Exception:  # noqa: BLE001
            return "cmake: failed"
    return None


def discover_c_build(root, *, max_files: int = 300) -> tuple[list[Path], list[Path]]:
    """Discover a C library's compilable sources + include dirs from a directory tree.

    Handles a real library layout (not just a flat dir of `.c` files):
    - Recursively collects `.c` files, skipping NON-library trees (test/example/
      bench/fuzz/doc/build/vendor) and any file defining `int main(` (a driver or
      example — it would also clash at link time in a shared lib).
    - Include dirs = the root plus every directory that contains a `.h` file.

    Returns (sources, include_dirs). Falls back to a flat top-level `*.c` glob if the
    recursive walk finds nothing usable, so single-file subjects behave as before.
    """
    root = Path(root)
    sources: list[Path] = []
    include_dirs: set[Path] = {root}
    for cf in sorted(root.rglob("*.c")):
        rel = cf.relative_to(root).parts[:-1]
        if {p.lower() for p in rel} & _NONLIB_DIRS:
            continue
        try:
            txt = cf.read_text(errors="replace")
        except OSError:
            continue
        if _MAIN_RE.search(txt):
            continue
        # Skip amalgamation / unity-build files that #include OTHER .c files
        # (Lua's onelua.c, sqlite3.c-style). Compiling them alongside the real
        # .c files defines every symbol twice -> duplicate-symbol link failure,
        # which silently kills the differential oracle build.
        if _AMALGAM_RE.search(txt):
            continue
        sources.append(cf)
        if len(sources) >= max_files:
            break
    for hf in root.rglob("*.h"):
        rel = hf.relative_to(root).parts[:-1]
        if {p.lower() for p in rel} & _NONLIB_DIRS:
            continue
        include_dirs.add(hf.parent)
    if not sources:
        sources = sorted(root.glob("*.c"))
    return sources, sorted(include_dirs)


@dataclass
class BuildResult:
    """Outcome of a C shared-library build."""
    ok: bool
    dll_path: Path | None = None
    compile_log: str = ""
    error: str = ""
    # Cache-key fingerprint (hash of all source file contents + flags)
    fingerprint: str = ""


def _source_fingerprint(sources: list[Path], flags: tuple[str, ...]) -> str:
    h = hashlib.sha256()
    for p in sorted(sources):
        try:
            h.update(p.read_bytes())
            h.update(str(p).encode("utf-8"))
        except OSError:
            pass
    for f in flags:
        h.update(f.encode("utf-8"))
    return h.hexdigest()[:16]


def _detect_compiler() -> tuple[str, str] | None:
    """Find a C compiler. Returns (command, style) where style is 'gcc' or 'msvc'.

    Prefers MinGW on Windows (for consistency with pre-built zlib1.dll),
    falls back to MSVC cl.exe. On Linux/macOS uses gcc/clang.
    """
    if platform.system() == "Windows":
        for candidate in ("x86_64-w64-mingw32-gcc", "gcc", "cc"):
            if shutil.which(candidate):
                return (candidate, "gcc")
        if shutil.which("cl"):
            return ("cl", "msvc")
    else:
        for candidate in ("gcc", "clang", "cc"):
            if shutil.which(candidate):
                return (candidate, "gcc")
    return None


def _dll_extension() -> str:
    sys = platform.system()
    if sys == "Windows":
        return ".dll"
    if sys == "Darwin":
        return ".dylib"
    return ".so"


def build_shared_library(
    name: str,
    sources: list[Path],
    include_dirs: list[Path],
    output_dir: Path,
    *,
    extra_flags: tuple[str, ...] = (),
    defines: tuple[str, ...] = (),
) -> BuildResult:
    """Compile a C shared library from the given sources.

    Args:
      name: library base name (no extension). Result is output_dir / <name>.<ext>.
      sources: list of .c files to compile.
      include_dirs: include paths (will be -I'd).
      output_dir: where the shared library is written.
      extra_flags: additional compiler flags.
      defines: preprocessor defines (without leading -D).

    Returns BuildResult describing outcome.
    """
    sources = [Path(s) for s in sources if Path(s).exists()]
    if not sources:
        return BuildResult(ok=False, error="no source files provided")
    fingerprint = _source_fingerprint(sources, extra_flags + defines)
    output_dir.mkdir(parents=True, exist_ok=True)
    dll_path = output_dir / f"{name}{_dll_extension()}"
    # Cache hit: skip build if the DLL already matches the fingerprint.
    fp_path = dll_path.with_suffix(".fingerprint")
    if dll_path.exists() and fp_path.exists():
        try:
            if fp_path.read_text().strip() == fingerprint:
                return BuildResult(
                    ok=True, dll_path=dll_path,
                    compile_log="cache hit", fingerprint=fingerprint,
                )
        except OSError:
            pass
    compiler = _detect_compiler()
    if compiler is None:
        return BuildResult(
            ok=False,
            error="no C compiler found on PATH (tried gcc/clang/cl/mingw)",
            fingerprint=fingerprint,
        )
    cc, style = compiler
    # Build the command line.
    if style == "gcc":
        cmd = [cc, "-shared", "-fPIC", "-O2", "-o", str(dll_path)]
        for d in include_dirs:
            cmd.extend(["-I", str(d)])
        for define in defines:
            cmd.append(f"-D{define}")
        cmd.extend(extra_flags)
        cmd.extend(str(s) for s in sources)
    else:  # msvc
        cmd = [cc, "/LD", "/O2", f"/Fe:{dll_path}"]
        for d in include_dirs:
            cmd.append(f"/I{d}")
        for define in defines:
            cmd.append(f"/D{define}")
        cmd.extend(extra_flags)
        cmd.extend(str(s) for s in sources)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return BuildResult(
            ok=False, error="compile timed out after 600s",
            fingerprint=fingerprint,
        )
    log = result.stdout + "\n" + result.stderr
    if result.returncode != 0 or not dll_path.exists():
        return BuildResult(
            ok=False, compile_log=log,
            error=f"compile failed (exit {result.returncode})",
            fingerprint=fingerprint,
        )
    # Record fingerprint for future cache-hit checks.
    try:
        fp_path.write_text(fingerprint, encoding="utf-8")
    except OSError:
        pass
    return BuildResult(
        ok=True, dll_path=dll_path, compile_log=log, fingerprint=fingerprint,
    )


def build_subject_dll(
    c_source_dir: Path,
    output_dir: Path,
    *,
    lib_name: str | None = None,
    exclude_globs: tuple[str, ...] = ("*test*.c", "*example*.c", "*bench*.c"),
) -> BuildResult:
    """Convenience wrapper: compile all .c files in a subject directory.

    Excludes common test/example/benchmark files by default.
    """
    c_source_dir = Path(c_source_dir)
    all_sources: list[Path] = []
    for p in c_source_dir.rglob("*.c"):
        if any(p.match(g) for g in exclude_globs):
            continue
        all_sources.append(p)
    if not all_sources:
        return BuildResult(
            ok=False,
            error=f"no .c files found under {c_source_dir}",
        )
    return build_shared_library(
        name=lib_name or c_source_dir.name,
        sources=sorted(all_sources),
        include_dirs=[c_source_dir],
        output_dir=output_dir,
    )
