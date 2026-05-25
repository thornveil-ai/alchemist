# Alchemist — Roadmap

**Status:** Research prototype with proven methodology. NOT production-ready (per [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md)).
**Visibility:** Public. Apache-2.0.
**Owner:** Thornveil LLC.
**Last reviewed:** 2026-05-22

This roadmap is the source-of-truth narrative for where Alchemist is, and what
gets it to "contract-ready" status. Live tracking lives on the
[Thornveil Roadmap project](https://github.com/orgs/thornveil-ai/projects/1)
with `Repository = alchemist` filter.

---

## What "contract-ready" means for Alchemist

Alchemist sits in the **CISA / DoD CIO / ONCD memory-safe regulatory tide**.
The 2026-2028 federal regulatory cycle will produce procurement requirements
that mandate or strongly prefer memory-safe replacements for legacy C in
security-critical systems. Alchemist's contract-ready state is: **in a
position where a federal program office can confidently use it (or sponsor
its use) to translate a real production C library and receive verified-correct
Rust output.**

Concretely, that requires:

1. **Trustworthy output, not just compilable output.** Pipeline must refuse to
   produce wrong-looking code rather than silently shipping stubs. Verified
   by differential testing against the C reference on every translation.
2. **Demonstrated success on standard libraries.** At minimum: mbedTLS,
   lwIP, possibly tinycrypt or libsodium. One of these translated end-to-end
   with verified correctness.
3. **Published methodology.** Algorithm-aware translation paper at arXiv
   minimum, peer-reviewed venue ideally (PLDI workshop, USENIX Security
   adjacent, ACM CCS).
4. **DARPA TRACTOR or equivalent adjacency.** Documented engagement with
   the federal memory-safety program ecosystem.
5. **External users.** Production users beyond the founder; at least one
   federal-adjacent organization translating real code with it.

Cross-references the broader portfolio: Alchemist's regulatory tailwind is
independent of [Mycelium / RigRun / Auspex] but feeds the same
"sovereign AI for federal" narrative — memory-safe code generation that
runs entirely locally on operator-controlled hardware.

---

## Now — what's actually shipped (as of 2026-05-22)

The baseline. These are facts on the ground, including the honest gaps.

### What works (the moat)

- **Methodology proven.** Algorithm-first translation produces 9.2× LOC compression with 0 unsafe blocks. zlib translated from 23,139 lines C → 2,512 lines Rust, all 7 generated crates compile.
- **Adler-32 bit-exact match** against C zlib across 30,000+ random byte arrays (after fixing the wrong-constant bug — proves the verification step works).
- **11-module pipeline architecture** (analyzer, extractor, architect, implementer, verifier, reporter, plus llm, plugins, references, standards, verifier/templates). Six stages with named gates.
- **21,181 LOC source, 6,944 LOC tests.** 47 test files, 436 test functions. README claims 543/543 tests passing (test count has grown since file enumeration).
- **3 translation subjects** in `subjects/`: tinychk (small), zlib (full, with bugs documented), zlib-dll (DLL variant scaffolded).
- **Reference binaries** in `verify/`: libz.dll.a + zlib1.dll for differential testing on Windows.
- **6 docs files**: api_reference, architecture, phase_d_playbook (the verification playbook), plugins, troubleshooting, tutorial.
- **Local-only inference** at Gemma 4 31B Dense on operator hardware. Zero cloud cost, no data egress.
- **Apache-2.0**, NOTICE present, org transfer to `thornveil-ai` complete.

### What's honestly broken (per PRODUCTION_READINESS.md)

The verification step caught what would have shipped as silent failures:

- **Cryptographically wrong constants** — Adler-32 base 255 vs RFC-required 65521. (Fixed.)
- **Stub functions that compile but don't work** — `compress()` returns zero-filled buffers. `unimplemented!()` calls in core paths.
- **Missing functions claimed by architecture** — CRC-32 module contains only table-writers, no actual `crc32()` function.
- **Type mismatches** — `z_stream` vs `inflate_state` confusion across module boundaries.
- **Reliability today on real code:** ~30-50% of generated functions actually work for stateful libraries like zlib. Single-function stateless algorithms: high success rate. Kernel / driver / OS code: near-zero.

The full taxonomy is in PRODUCTION_READINESS.md. This roadmap inherits its
priority ordering.

---

## Next 90 days (target: 2026-08-20)

Tier 1 hardening per PRODUCTION_READINESS.md — the work that converts
"compiles but broken" to "fails loudly when wrong."

### M01. PyPI first publication (`thornveil-alchemist`)
**Target: 2026-06-05.** Currently registered as `thornveil-alchemist` in pyproject.toml but PyPI returns 404 (not yet published). Set up Trusted Publisher binding for `thornveil-ai/alchemist`. Publish v0.1.0.
**Success:** `pip install thornveil-alchemist` works.

### M02. Add `docs.yml` and `publish.yml` CI workflows
**Target: 2026-06-05.** Currently have ci.yml + label-sync.yml only. Need docs.yml (build & deploy mkdocs to GH Pages) and publish.yml (tag → PyPI release via Trusted Publisher).
**Success:** Tag a v0.1.1 → docs site auto-publishes; PyPI release auto-publishes.

### M03. Tier 1.1 — Test-driven generation (Stage 4 must be TDD)
**Target: 2026-07-15.** Per PRODUCTION_READINESS Bug Class 2: Stage 4 currently generates code that compiles even when the model doesn't know how to implement the algorithm. TDD-Stage-4 = generate tests from the spec FIRST, then generate impl, then require tests pass before stage marked complete. Biggest single bug-class prevention.
**Success:** Stage 4 refuses to mark a function complete unless its spec-derived tests pass.

### M04. Tier 1.2 — Anti-stub detection scrubber
**Target: 2026-07-15.** Per PRODUCTION_READINESS Bug Class 2: detect and reject generated code containing patterns like `// we don't have`, `// simulate`, `// for this spec`, `unimplemented!()`, `todo!()`, zero-fill returns. Scrubber rule additions; rejection in the validator stage.
**Success:** Adversarial test where the LLM is fed an algorithm it cannot implement produces a hard pipeline failure (not a silent stub).

### M05. Tier 1.3 — Public API completeness check
**Target: 2026-07-22.** Per PRODUCTION_READINESS Bug Class 3: verify every function declared in C headers exists in generated Rust with matching signature. Catches the "CRC-32 module is missing the actual crc32 function" failure mode.
**Success:** Pipeline fails if any public C symbol is missing from generated crates.

### M06. Tier 1.4 — Mandatory differential testing in Stage 5
**Target: 2026-07-22.** Per PRODUCTION_READINESS Tier 1.4: every translation must include a differential test config (e.g., `mylib_config.py` for the subject) that diffs generated Rust output against C reference output on randomized inputs. Stage 5 fails if config is missing or tests don't pass.
**Success:** zlib translation includes a differential test passing on 10,000+ random inputs.

### M07. Tier 1.5 — Spec test-vector requirement
**Target: 2026-07-29.** Per PRODUCTION_READINESS Tier 1.5: for any algorithm with an RFC / spec test vector (Adler-32, CRC-32, AES, SHA-2, etc.), spec extractor must surface the test vectors and verifier must run them. Catches "model invented constants" failures.
**Success:** Adler-32, CRC-32, and at least one cryptographic primitive each carry RFC test vectors in their spec.

### M08. v0.2.0 release — Tier 1 complete
**Target: 2026-08-10.** Tag + release after M03-M07 land. CHANGELOG entry documents the Tier 1 hardening cycle. First versioned release on PyPI under thornveil-alchemist.
**Success:** v0.2.0 tagged, PyPI live, GitHub release with notes.

### M09. tinychk end-to-end verified-correct
**Target: 2026-08-20.** tinychk is the small subject (2 C files, 2 Rust files). After Tier 1 work, full Stage 1-6 pipeline on tinychk should produce Rust that passes differential test against C reference. This is the proof-of-life for "TDD + differential testing actually works end-to-end."
**Success:** `alchemist translate ./subjects/tinychk` produces Rust that passes the differential test gate. Run reproducible on a fresh checkout.

---

## Next 6 months (target: 2027-02-22)

Tier 2 + Tier 3 work from PRODUCTION_READINESS.md, plus multi-codebase
validation and the methodology paper.

### M10. Tier 2.6 — Compile-driven skeleton (Phase 2 plan)
**Target: 2026-10-15.** Generate skeleton Rust that compiles first, then iteratively fill in implementations with TDD. Per PRODUCTION_READINESS Phase 2 estimated 4-6 weeks.
**Success:** Skeleton stage produces compiling Rust scaffold; iteratively filled by Stage 4.

### M11. Tier 2.7 — Field schema pre-scan
**Target: 2026-10-31.** Catches the "z_stream vs inflate_state" type-mismatch bug class. Pre-scan all struct fields across the C codebase; ensure Rust generation respects type identity across module boundaries.
**Success:** Pipeline detects and reports any cross-module type confusion before generation.

### M12. Tier 2.8 — Spec validation by second model
**Target: 2026-11-15.** Adversarial spec verification — a different LLM re-derives the spec from the C source and diffs against the first model's extracted spec. Disagreements escalate to user. Catches "model invented constants" earlier in the pipeline.
**Success:** Two-model spec agreement step exists; disagreements logged for review.

### M13. zlib end-to-end verified-correct
**Target: 2026-12-15.** The harder subject. After Tier 1 + Tier 2 work, zlib full pipeline produces Rust that passes the C reference differential test. Replaces the current "compiles but compress() returns zeros" state with verified correctness.
**Success:** `alchemist translate ./subjects/zlib` produces Rust passing differential tests on compress/decompress roundtrip across diverse input shapes.

### M14. mbedTLS partial translation attempt
**Target: 2027-01-15.** Tier 3.11 begins. mbedTLS is the next subject above zlib — crypto with NIST CAVP test vectors. Even partial success (translating selected modules: SHA-2, AES-CBC) proves generalization.
**Success:** ≥1 mbedTLS crypto primitive translated end-to-end with NIST CAVP test vectors passing.

### M15. v0.3.0 release — Tier 2 complete
**Target: 2027-01-31.** Tag + release after M10-M14 land. Reliability claim updates: ~85% on standard codebases (per PRODUCTION_READINESS Phase 3 estimate).
**Success:** v0.3.0 tagged, PyPI live, CHANGELOG entry, README reliability table updated.

### M16. Methodology paper draft (arXiv submission ready)
**Target: 2027-02-15.** Algorithm-aware C-to-Rust translation methodology paper. Sections: motivation (CISA memory-safety mandate), algorithm-first approach, refuses-success gate discipline, verification methodology, empirical evaluation on zlib + mbedTLS subjects.
**Success:** Paper draft complete, internal review pass, arXiv submission queued.

### M17. First external user adoption
**Target: 2027-02-22.** Someone outside Thornveil successfully runs alchemist on their own C library and gets working Rust output. Could be from awesome-list discovery, conference talk, or direct outreach.
**Success:** Public GitHub issue or social media post from an external user reporting a successful translation; PR or issue thread documenting the run.

---

## Contract-ready (target: 2027-12-31)

The state where federal memory-safe procurement programs can engage
with Alchemist as a credible tool, not a research artifact.

### M18. arXiv paper published + conference talk delivered
**Target: 2027-06-30.** M16 arXiv submission lands. Conference talk delivered at one of: PLDI 2027 workshop, USENIX Security AISec, ACM CCS, BSidesDC. Recording publicly available.
**Success:** arXiv paper has DOI; conference recording links from docs site.

### M19. Tier 3.10 + 3.12 — Productionize CLI + plugin architecture
**Target: 2027-08-31.** Wire all validators / scrubbers / fixers into the main `alchemist translate` command (currently some are standalone scripts). Implement domain plugin system (crypto plugin auto-imports NIST CAVP test vectors; RTOS plugin handles interrupt contexts).
**Success:** `alchemist translate ./mbedTLS --plugin crypto` works end-to-end; plugin contract documented in docs/plugins.md.

### M20. Multi-codebase validation pass
**Target: 2027-09-30.** Per PRODUCTION_READINESS Tier 3.11: run on mbedTLS (crypto), lwIP (TCP/IP), and either FreeRTOS or tinycrypt. Each surfaces new failure classes; each becomes a generic fix.
**Success:** 3+ standard libraries with verified-correct partial or full translations; failure modes documented.

### M21. DARPA TRACTOR / federal memory-safety adjacency
**Target: 2027-10-31.** Establish engagement with the federal memory-safety program ecosystem. This may be: a DARPA TRACTOR program reference, a CISA memory-safe roadmap citation, an ONCD memory-safety report mention, or sponsorship for an AFRL/AvMC pilot translation.
**Success:** Public federal-adjacent document references Alchemist by name OR by capability pattern.

### M22. 100+ stars, 25+ external users
**Target: 2027-11-30.** Quantitative social-proof floor for a research-grade tool in a regulated space. Below these, federal program managers dismiss as "academic." Above them, the tool reads as community-validated.
**Success:** Sustained ≥100 stars; ≥25 external successful-translation reports (GitHub issues, blog posts, conference mentions).

### M23. v1.0.0 stable
**Target: 2027-12-15.** Feature lock, semver commitment, breaking-change deadline. Includes:
  - Stable CLI surface documented
  - Plugin contract versioned
  - Reliability table in README based on empirical multi-codebase data
**Success:** v1.0.0 tagged + PyPI; migration guide for 0.x → 1.0; LTS commitment for v1.x line (12 months minimum).

### M24. Production translation of a security-relevant real-world C library
**Target: 2027-12-31.** The "anyone can use it" proof. A real production C library (security-relevant, third-party-maintained) translated to Rust by an external organization using Alchemist, with the result accepted upstream or used in production by that organization.
**Success:** Documented case study of external organization shipping Rust generated by Alchemist in production.

---

## Dependencies + cross-system flow

```
   ┌──────────────────────────┐
   │  Alchemist (public OSS)  │  ← THIS ROADMAP
   │  C-to-Rust translation   │
   │  Memory-safe-by-default  │
   └──────────────────────────┘
              │ (no direct internal dependency)
              ▼
   ┌──────────────────────────┐
   │  Federal memory-safety   │
   │  procurement tide:       │
   │  CISA / DoD CIO / ONCD   │
   │  DARPA TRACTOR adjacent  │
   └──────────────────────────┘
```

**Critical path:** M03-M07 (Tier 1 hardening) before M09 (tinychk e2e
verified) before M13 (zlib e2e verified) before M14 (mbedTLS partial). The
methodology paper (M16) sits in parallel with the multi-codebase work and
can draft as M09/M13 surface findings.

**Decoupled from:** All 9 other Thornveil systems. Alchemist has no
internal-product dependency. Its leverage is regulatory tailwind, not
portfolio-integration.

---

## Owner notes

- **Don't ship v1.0 before mbedTLS works.** The "anyone with normal C code"
  threshold per PRODUCTION_READINESS requires the Tier 1+2+3 work AND
  validation on at least one cryptographic library. v1.0 before that is
  premature; v0.x is the honest framing.
- **The PRODUCTION_READINESS.md document IS the development plan.**
  Treat it as the design doc; this roadmap is its execution schedule.
- **Federal adjacency timing matters.** DARPA TRACTOR-style programs run on
  18-24 month cycles. Engagement (M21) must start by Q2 2027 to land in
  the FY28 program cycle.
- **`subjects/zlib-dll` is currently 0 Rust files.** Decide whether
  zlib-dll is a separate subject worth pursuing or just a platform variant
  of zlib. Defer decision until M13.
- **PyPI name is `thornveil-alchemist`** (not `alchemist`). The `alchemist`
  package on PyPI is squatted; we won the namespace question via prefix.
  Document this prominently to avoid wrong-package installs.
