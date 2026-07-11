"""Stage 2: Extract algorithm specifications from C code via LLM.

Takes analysis output (parsed files, call graph, modules) and produces
AlgorithmSpec / ModuleSpec for each detected module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from alchemist.config import AlchemistConfig
from alchemist.extractor.schemas import (
    AlgorithmSpec,
    FunctionSpec,
    ModuleSpec,
    SharedType,
    TypeField,
)
from alchemist.extractor.prompts.extract_algorithm import (
    SYSTEM_PROMPT,
    MODULE_EXTRACTION_PROMPT,
)
from alchemist.llm.client import AlchemistLLM, CachedContext
from alchemist.llm.structured import pydantic_to_tool_schema

console = Console(force_terminal=True, legacy_windows=False)


class SpecExtractor:
    """Extract algorithm specifications from analyzed C code."""

    def __init__(self, config: AlchemistConfig | None = None):
        self.config = config or AlchemistConfig()
        self.llm = AlchemistLLM(self.config)
        self._cached_context: CachedContext | None = None
        self._output_dir: Path | None = None

    def extract_all(
        self,
        analysis: dict,
        output_dir: Path | None = None,
    ) -> list[ModuleSpec]:
        """Extract specs for all detected modules.

        Args:
            analysis: Output from Stage 1 (analysis.json)
            output_dir: Where to write spec JSON files
        """
        self._output_dir = output_dir
        modules = analysis.get("modules", [])
        if not modules:
            console.print("[red]No modules found in analysis.[/red]")
            return []

        # Filter to algorithm modules only
        algo_modules = [m for m in modules if m["category"] == "algorithm"]
        glue_modules = [m for m in modules if m["category"] != "algorithm"]

        console.print(
            f"[cyan]Extracting specs for {len(algo_modules)} algorithm modules "
            f"(skipping {len(glue_modules)} glue modules)[/cyan]"
        )

        # Build cached context (system prompt + project overview)
        self._cached_context = self.llm.create_cached_context(
            system_text=SYSTEM_PROMPT,
            project_context=self._build_project_context(analysis),
        )

        specs = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Extracting specs...", total=len(algo_modules))

            for mod in algo_modules:
                progress.update(task, description=f"Extracting {mod['name']}...")
                # Skip if module spec already exists
                if output_dir:
                    existing = output_dir / f"{mod['name']}.json"
                    if existing.exists():
                        try:
                            cached = ModuleSpec.model_validate(
                                json.loads(existing.read_text())
                            )
                            specs.append(cached)
                            console.print(f"  [dim]Skipping {mod['name']} (already done)[/dim]")
                            progress.update(task, advance=1)
                            continue
                        except Exception:
                            pass
                spec = self._extract_module(mod, analysis)
                if spec:
                    specs.append(spec)

                    # Save incrementally
                    if output_dir:
                        out_file = output_dir / f"{mod['name']}.json"
                        out_file.write_text(spec.model_dump_json(indent=2))
                        console.print(f"  [green]Wrote {out_file}[/green]")

                progress.update(task, advance=1)

        # Print cost summary
        stats = self.llm.stats
        console.print(f"\n[cyan]LLM Stats:[/cyan]")
        console.print(f"  Calls: {stats['call_count']}")
        console.print(f"  Input tokens: {stats['total_input_tokens']:,}")
        console.print(f"  Output tokens: {stats['total_output_tokens']:,}")
        console.print(f"  Total cost: ${stats['total_cost_usd']:.4f}")

        return specs

    def _extract_module(self, module: dict, analysis: dict) -> ModuleSpec | None:
        """Extract spec for a single module via per-function extraction.

        Strategy: extract lightweight FunctionSpec for each significant function
        individually (small, reliable LLM calls), then aggregate into a ModuleSpec.
        """
        # Find all functions belonging to this module
        module_funcs = set(module.get("functions", []))
        files_dict = analysis.get("files", {})

        # Gather (function_name, file_path, source_code) tuples
        func_data = []
        for filepath, file_data in files_dict.items():
            if not filepath.endswith(".c"):
                continue
            try:
                source = Path(filepath).read_text(errors="replace")
            except FileNotFoundError:
                continue
            lines = source.split("\n")
            for func in file_data.get("functions", []):
                if func["name"] not in module_funcs:
                    continue
                start = func.get("start_line", 1) - 1
                end = func.get("end_line", start + 1)
                # Include a few lines before for comments
                ctx_start = max(0, start - 3)
                func_source = "\n".join(lines[ctx_start:end])
                func_data.append({
                    "name": func["name"],
                    "file": filepath,
                    "source": func_source,
                    "lines": func.get("line_count", 0),
                })

        if not func_data:
            console.print(f"  [yellow]No functions found for {module['name']}[/yellow]")
            return None

        # Skip very large (>500 lines). Skip tiny (<5-line) functions ONLY when they are
        # `static` (internal helpers the model can inline). Keep tiny PUBLIC functions — they
        # are part of the library's surface (thin API wrappers, small exported ops) and
        # dropping them silently loses coverage for whole-library translation.
        def _is_static_fn(f: dict) -> bool:
            return bool(re.search(
                r"(?:^|\n)[ \t]*static\b[^\n;{]*\b" + re.escape(f["name"]) + r"\s*\(",
                f.get("source", "")))

        def _is_uncalled_void_noarg(f: dict) -> bool:
            # `void NAME(void)` with NO caller in the module — a pure side-effect routine that
            # nothing depends on (an EXTERNAL table generator like crc32_table, called only by
            # a build-time `precalc` main). Skip it: no I/O to verify and no dependent code.
            # BUT keep void-noarg initializers that ARE called (a lazy runtime-table builder
            # like init_crcdnp_tab that crc_dnp invokes) — dropping those breaks the caller.
            is_void_noarg = bool(re.search(
                r"(?:^|\n)[ \t]*(?:static\s+)?void\s+" + re.escape(f["name"])
                + r"\s*\(\s*(?:void)?\s*\)",
                f.get("source", "")))
            if not is_void_noarg:
                return False
            called = any(
                other is not f and re.search(r"\b" + re.escape(f["name"]) + r"\s*\(",
                                              other.get("source", ""))
                for other in func_data
            )
            return not called

        def _called_by_other(f: dict) -> bool:
            return any(
                other is not f and re.search(r"\b" + re.escape(f["name"]) + r"\s*\(",
                                              other.get("source", ""))
                for other in func_data)

        def _is_inlinable_static(f: dict) -> bool:
            # A `static` (internal-linkage) helper is NEVER public API. Drop it so the model
            # INLINES it into its callers (whose fill prompt is fed the helper body via
            # collect_callee_context). Two cases: (1) a static table INITIALIZER like
            # init_crc16_tab (void — no fuzzable I/O, always stubs); (2) a static worker like
            # crc_ccitt_generic that the public wrappers (crc_xmodem/1d0f/ffff) call with a
            # fixed start value. Drop when the static is void OR is called by another module
            # function (the inline target). A static that is uncalled AND returns a value is
            # left alone (rare leaf). The byte-exact differential catches any caller that
            # mis-inlines it, so this can never launder a wrong translation to green.
            if not _is_static_fn(f):
                return False
            is_void = bool(re.search(
                r"(?:^|\n)[ \t]*static\s+void\b[^\n;{]*\b" + re.escape(f["name"]) + r"\s*\(",
                f.get("source", "")))
            return is_void or _called_by_other(f)
        significant = [
            f for f in func_data
            if ((5 <= f["lines"] <= 500) or (0 < f["lines"] < 5 and not _is_static_fn(f)))
            and not _is_uncalled_void_noarg(f)
            and not _is_inlinable_static(f)
        ]
        if not significant:
            significant = func_data[:5]

        # Checkpoint directory for per-function specs
        func_ckpt_dir = self._output_dir / "_functions" / module["name"] if self._output_dir else None
        if func_ckpt_dir:
            func_ckpt_dir.mkdir(parents=True, exist_ok=True)

        # Load any previously-extracted function specs
        func_specs: list[FunctionSpec] = []
        already_done: set[str] = set()
        if func_ckpt_dir:
            for fpath in func_ckpt_dir.glob("*.json"):
                try:
                    fs = FunctionSpec.model_validate(json.loads(fpath.read_text()))
                    func_specs.append(fs)
                    already_done.add(fs.name)
                except Exception:
                    pass

        remaining = [f for f in significant if f["name"] not in already_done]
        console.print(
            f"  [cyan]{module['name']}: {len(already_done)} already done, "
            f"extracting {len(remaining)} more (of {len(func_data)} total)[/cyan]"
        )

        # Extract FunctionSpec for each remaining function
        schema = pydantic_to_tool_schema(FunctionSpec)
        server_failures = 0
        for i, f in enumerate(remaining):
            # Check server before each call; wait if down
            if not self.llm.wait_for_server(max_wait=90, check_interval=10):
                console.print(
                    f"  [red]Server unavailable after waiting 90s — "
                    f"pausing module {module['name']}[/red]"
                )
                break

            prompt = (
                f"Analyze this C function and extract its specification.\n\n"
                f"Function: {f['name']} (file: {Path(f['file']).name})\n\n"
                f"```c\n{f['source']}\n```\n\n"
                f"Return a FunctionSpec describing what the algorithm does, "
                f"its inputs/outputs in idiomatic Rust types, and implementation notes. "
                f"Focus on the ALGORITHM, not the C syntax."
            )

            resp = self.llm.call_structured(
                messages=[{"role": "user", "content": prompt}],
                tool_name="function_spec",
                tool_schema=schema,
                cached_context=self._cached_context,
                max_tokens=1500,
            )

            if resp.structured:
                try:
                    spec = FunctionSpec.model_validate(resp.structured)
                    func_specs.append(spec)
                    # CHECKPOINT: save immediately
                    if func_ckpt_dir:
                        (func_ckpt_dir / f"{spec.name}.json").write_text(
                            spec.model_dump_json(indent=2)
                        )
                    console.print(
                        f"    [green]{spec.name}[/green] ({spec.category}) [{resp.duration_ms}ms]"
                    )
                    server_failures = 0
                except Exception as e:
                    console.print(f"    [yellow]{f['name']}: validation failed[/yellow]")
            else:
                content = (resp.content or "")[:80]
                console.print(f"    [red]{f['name']}: no JSON[/red]")
                if "ERROR" in (resp.content or "") or "Unavailable" in (resp.content or ""):
                    server_failures += 1
                    if server_failures >= 3:
                        console.print(
                            f"  [red]3 consecutive server failures — "
                            f"pausing module {module['name']}[/red]"
                        )
                        break

        if not func_specs:
            return None

        return self._aggregate_to_module_spec(module["name"], func_specs)

    def _aggregate_to_module_spec(
        self, name: str, func_specs: list[FunctionSpec]
    ) -> ModuleSpec:
        """Convert a list of FunctionSpecs into a ModuleSpec.

        One AlgorithmSpec per FunctionSpec. The earlier "group by category"
        strategy silently merged independent algorithms (e.g. adler32 + crc32
        + fletcher16) into a single spec with concatenated parameter lists,
        which broke skeleton generation downstream.
        """
        VALID_CATEGORIES = {
            "compression", "decompression", "checksum", "hash",
            "cipher", "filter", "controller", "data_structure",
            "protocol", "utility", "other",
        }

        algorithms: list[AlgorithmSpec] = []
        seen_names: set[str] = set()
        for fs in func_specs:
            # Dedupe: the extractor can write two FunctionSpec with the same
            # name when the LLM re-extracts a checkpoint that is then merged
            # by the spec completer. Skip repeats so the skeleton doesn't
            # emit `pub fn X` twice (Rust rejects duplicate fn definitions).
            if fs.name in seen_names:
                continue
            seen_names.add(fs.name)
            cat = fs.category if fs.category in VALID_CATEGORIES else "other"
            algo = AlgorithmSpec(
                name=fs.name,
                display_name=fs.name.replace("_", " ").title(),
                category=cat,
                description=(fs.purpose or fs.name)[:500],
                mathematical_description=fs.algorithm_notes or "",
                inputs=fs.inputs,
                return_type=fs.return_type or "()",
                no_std_compatible=True,
                unsafe_required=bool(fs.unsafe_required),
                referenced_standards=sorted(fs.referenced_standards or []),
                source_functions=[fs.name],
            )
            algorithms.append(algo)

        algo_names = ", ".join(a.name for a in algorithms) or "(none)"
        return ModuleSpec(
            name=name,
            display_name=name.replace("_", " ").title(),
            description=(
                f"Module containing {len(func_specs)} function"
                f"{'' if len(func_specs) == 1 else 's'}: {algo_names}"
            ),
            algorithms=algorithms,
        )
