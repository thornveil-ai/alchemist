"""Pillar 2 — the whole-program type model + bottom-up translation order.

Per-function translation uses a LOCAL view of types, so two functions can disagree
on how the same C type maps to Rust at their shared call boundary. To scale from a
function to a codebase you need ONE type model the whole program shares: every C
typedef/struct/pointer resolved to its coherent Rust form ONCE, consistently, so a
function that returns `SHA256_CTX*` and a function that consumes it use the exact
same Rust type.

Paired with the call graph topo-sorted leaves-first, this turns per-function wins
into codebase throughput: by the time you fill `f`, everything `f` calls is already
translated, typed, and verified — so `f`'s signature and its calls line up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from alchemist.autonomy.onboard import c_to_rust_scalar
from alchemist.autonomy.stateful import rust_struct_name, resolve_typedefs


@dataclass
class ProgramTypeModel:
    typedefs: dict[str, str] = field(default_factory=dict)   # name -> underlying C type
    structs: set[str] = field(default_factory=set)           # struct/typedef'd struct names
    enums: set[str] = field(default_factory=set)

    @classmethod
    def from_sources(cls, srcs: list[str]) -> "ProgramTypeModel":
        m = cls()
        for src in srcs:
            m.typedefs.update(resolve_typedefs(src))
            for sm in re.finditer(r"\bstruct\s+(\w+)\s*\{", src):
                m.structs.add(sm.group(1))
            for tm in re.finditer(r"\}\s*(\w+)\s*;", src):   # typedef struct {...} Name;
                m.structs.add(tm.group(1))
            for em in re.finditer(r"\benum\s+(\w+)", src):
                m.enums.add(em.group(1))
        return m

    def _base(self, c_type: str) -> str:
        """Chase typedef chains to a base C type (bounded)."""
        t = c_type.replace("const", "").replace("struct", "").strip()
        seen = set()
        while t in self.typedefs and t not in seen:
            seen.add(t)
            t = self.typedefs[t].replace("const", "").replace("struct", "").strip()
        return t

    def is_struct(self, c_type: str) -> bool:
        t = c_type.replace("const", "").replace("struct", "").strip().rstrip("*").strip()
        return t in self.structs or self._base(t) in self.structs

    def rust_type(self, c_type: str, role: str | None = None) -> str:
        """Coherent Rust type for a C type in a given role. Roles carry the model's
        core rewrites: a (ptr,len) pair -> &[u8], an out-buffer -> Vec<u8> return, a
        ctx pointer -> &mut Ctx. Consistent across the whole program."""
        c_type = c_type.strip()
        is_ptr = "*" in c_type or "[" in c_type
        base = self._base(re.sub(r"[\*\[\]0-9\s]+$", "", c_type)).strip() or c_type
        is_const = "const" in c_type

        if role == "buffer":      # (ptr, len) input pair
            return "&[u8]"
        if role == "out_buffer":  # written output -> owned return
            return "Vec<u8>"
        if role == "out_return":
            return "Vec<u8>"
        if is_ptr and (base in self.structs or self._base(base) in self.structs):
            name = rust_struct_name(base)
            return ("&%s" if is_const else "&mut %s") % name   # ctx pointer
        if base in self.structs:
            return rust_struct_name(base)
        if base in self.enums:
            return "u32"
        return c_to_rust_scalar(base)

    def topo_order(self, funcs: dict) -> list[str]:
        """Leaves-first: a function appears after everything it calls. Cycles are
        broken deterministically (by name) so recursion never deadlocks."""
        for f in funcs.values():
            if not hasattr(f, "calls") or f.calls is None:
                f.calls = {c for c in re.findall(r"\b(\w+)\s*\(", getattr(f, "body", ""))
                           if c in funcs and c != f.name}
        order, seen, temp = [], set(), set()

        def visit(n: str):
            if n in seen or n not in funcs:
                return
            if n in temp:            # cycle -> stop; deterministic tie-break
                return
            temp.add(n)
            for c in sorted(funcs[n].calls):
                visit(c)
            temp.discard(n)
            seen.add(n)
            order.append(n)
        for name in sorted(funcs):
            visit(name)
        return order
