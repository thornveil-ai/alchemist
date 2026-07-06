"""The C-idiom pattern catalog itself.

Seeded from the zlib byte-exact translation (docs/zlib_case_study.md). Every
entry is a pattern a human recognized by hand; encoding it here is what turns
that recognition into an automated capability (WS6).

Detection is deliberately cheap: each idiom carries `c_signals`, a tuple of
regexes matched against the C source. A hit means "this pattern is *likely*
present, surface its guidance" — false positives are fine (an extra hint costs
little); the model still decides. Precision can grow later (semantic/CFG-based
detection) without changing the consumer interface.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

# Bump when entries change in a way that could alter model output, so caches /
# receipts can record which catalog produced a given translation.
CATALOG_VERSION = "0.1.0-zlib-seed"


@dataclass(frozen=True)
class Idiom:
    """One C-idiom -> Rust-model transform.

    id           stable kebab-case identifier
    name         short human title
    tags         categories (buffer / ownership / control-flow / arithmetic / ...)
    c_signals    regex strings; any match flags the idiom as likely-present
    rust_model   the transform, stated as guidance the model can apply
    rationale    *why* — the semantic gap being bridged
    example      concrete zlib site the pattern came from
    caution      optional gotcha that bit us on zlib (the bug this prevents)
    """

    id: str
    name: str
    tags: tuple[str, ...]
    c_signals: tuple[str, ...]
    rust_model: str
    rationale: str
    example: str
    caution: str = ""
    _compiled: tuple[Pattern[str], ...] = field(default=(), repr=False, compare=False)

    def compiled(self) -> tuple[Pattern[str], ...]:
        # Lazily compile signals (frozen dataclass -> cache on the class-level dict).
        cache = _SIGNAL_CACHE.get(self.id)
        if cache is None:
            cache = tuple(re.compile(s) for s in self.c_signals)
            _SIGNAL_CACHE[self.id] = cache
        return cache

    def matches(self, c_source: str) -> bool:
        return any(p.search(c_source) for p in self.compiled())

    def prompt_block(self) -> str:
        lines = [f"### {self.name}  [{self.id}]", f"- **When:** {self.rationale}",
                 f"- **Do:** {self.rust_model}", f"- **e.g. (zlib):** {self.example}"]
        if self.caution:
            lines.append(f"- **Watch out:** {self.caution}")
        return "\n".join(lines)


_SIGNAL_CACHE: dict[str, tuple[Pattern[str], ...]] = {}


# --------------------------------------------------------------------------
# The catalog. Ordered roughly by how often each bit us / how load-bearing it
# is for correctness.
# --------------------------------------------------------------------------
IDIOMS: tuple[Idiom, ...] = (
    Idiom(
        id="advancing-input-pointer",
        name="Advancing input pointer -> drained Vec (or offset)",
        tags=("buffer", "ownership"),
        c_signals=(r"\*\s*\w*next\w*\s*\+\+", r"next_in\s*\+=", r"\bavail_in\b",
                   r"\bread_buf\b"),
        rust_model=(
            "Model a consumed input buffer as an owned `Vec<u8>` drained from the "
            "front (`drain(0..n)`) OR as `(Vec<u8>, offset: usize)` when the C reaches "
            "backward into already-consumed bytes. Track `avail_in` as the remaining "
            "count. Never keep a raw pointer."
        ),
        rationale="C consumes input by advancing a pointer; Rust owns the buffer.",
        example="`next_in`/`avail_in`, `read_buf(strm, ...)` draining input into the window.",
        caution=("If the function later reads bytes it already consumed (e.g. "
                 "`next_in - w_size`), a plain drained Vec loses them — use the offset "
                 "model. This is exactly why `deflate_stored` needs a design decision."),
    ),
    Idiom(
        id="appending-output-pointer",
        name="Appending output pointer -> pushed Vec",
        tags=("buffer",),
        c_signals=(r"\*\s*\w*put\w*\s*\+\+", r"next_out\s*\+=", r"\bavail_out\b"),
        rust_model=(
            "Model output as an owned `Vec<u8>` you `push`/`extend_from_slice` onto; "
            "track `avail_out` as remaining space (`left`) and decrement as you emit. "
            "`put - out` in C (start of this call's output) becomes a saved index into "
            "the output Vec."
        ),
        rationale="C writes output through an advancing pointer; Rust appends to a Vec.",
        example="`next_out`/`put`/`left` in the inflate driver and `flush_pending`.",
    ),
    Idiom(
        id="pointer-into-shared-array",
        name="Pointer into a shared array -> offset index",
        tags=("buffer", "tables"),
        c_signals=(r"=\s*\w+\s*;\s*/\*.*table", r"\+\+\s*\)\s*&\s*\(", r"code\s+FAR\s*\*"),
        rust_model=(
            "When several C pointers index into one backing array (and advance within "
            "it), keep ONE `Vec<T>` and represent each pointer as a `usize` offset "
            "(`lencode_off`, `distcode_off`, `next_off`). Index as `arr[off + i]`. If a "
            "builder returns how many entries it used, thread that as the next offset."
        ),
        rationale="C aliases sub-tables as pointers into a shared buffer; Rust uses offsets.",
        example=("`lencode`/`distcode`/`next` all point into `state->codes[ENOUGH]`; "
                 "`inflate_table` advances the pointer by its `used` count."),
    ),
    Idiom(
        id="pointer-aliasing-same-memory",
        name="Two names for the same memory -> mem::take bridge",
        tags=("ownership", "aliasing"),
        c_signals=(r"\.dyn_tree", r"->\s*dyn_\wtree", r"stat_desc", r"tree_desc"),
        rust_model=(
            "If the coherent types split what C treats as one buffer under two names, "
            "bridge them with `core::mem::take`: move the Vec into the field the callee "
            "reads, call, then move it back. Do NOT clone (breaks the shared-mutation "
            "semantics) and do NOT keep both live (borrow conflict)."
        ),
        rationale="C lets `desc.dyn_tree` and `s.dyn_ltree` be the same array; safe Rust can't.",
        example="`_tr_flush_block` syncs `l_desc.dyn_tree` <-> `dyn_ltree` around `build_tree`.",
        caution=("Miss this and freqs/lengths silently desync — the bug shows up as the "
                 "wrong *block type* chosen (static vs dynamic), not a crash."),
    ),
    Idiom(
        id="union-fields",
        name="union -> separate fields (or enum)",
        tags=("types",),
        c_signals=(r"\bunion\b", r"\.fc\b", r"\.dl\b", r"Freq\b.*Code\b"),
        rust_model=(
            "Translate a C `union` used as two named views of the same slot into "
            "SEPARATE Rust fields when the two views are never live at once for the same "
            "logical value (e.g. freq-then-code), or a tagged `enum` when they genuinely "
            "vary. Prefer separate fields for the frequency/code and dad/len pairs."
        ),
        rationale="C unions overlap storage; safe Rust models the two uses explicitly.",
        example="`ct_data { union { fc {freq;code}; dl {dad;len} } }` -> freq/code/dad/len fields.",
    ),
    Idiom(
        id="owner-holds-substate",
        name="strm->state pointer -> owner holds sub-state by value",
        tags=("ownership",),
        c_signals=(r"->\s*state\b", r"internal_state", r"z_streamp"),
        rust_model=(
            "Model the stream/handle as OWNING its internal state by value "
            "(`struct DeflateStream { state: DeflateState, next_in: Vec<u8>, ... }`). "
            "Functions that touch stream buffers take `&mut Stream`; pure state "
            "transforms take `&mut State`. This keeps a single, coherent ownership tree."
        ),
        rationale="C threads a `state*` off the stream; Rust makes ownership explicit and total.",
        example="`DeflateStream` owns `DeflateState`; `InflateStream` owns `InflateState`.",
    ),
    Idiom(
        id="goto-to-labeled-loop",
        name="goto-based control flow -> labeled loop + break",
        tags=("control-flow",),
        c_signals=(r"\bgoto\s+\w+", r"^\s*\w+:\s*$", r"for\s*\(\s*;\s*;\s*\)\s*switch"),
        rust_model=(
            "Render a `for(;;) switch(state->mode)` machine as "
            "`'label: loop { match state.mode { ... } }`. A `goto exit_label` (e.g. on "
            "input underflow) becomes `break 'label`. State transitions set `mode` and "
            "`continue`. Fall-through cases become explicit `mode = NEXT; continue;`. Put "
            "the post-loop cleanup (C's label body) after the loop."
        ),
        rationale="C state machines lean on goto; safe Rust structures them with labeled loops.",
        example="`inflate()`'s `goto inf_leave` on every `NEEDBITS` underflow -> `break 'inf_leave`.",
        caution=("Every C `case` fall-through must be made explicit — a missing "
                 "`mode = TYPE` arm silently drops into the wrong state."),
    ),
    Idiom(
        id="bit-accumulator-macros",
        name="Bit-accumulator macros -> inlined bit ops",
        tags=("control-flow", "bits"),
        c_signals=(r"\bNEEDBITS\b", r"\bDROPBITS\b", r"\bPULLBYTE\b", r"\bBITS\s*\("),
        rust_model=(
            "Inline the LSB-first bit accumulator: `hold: u64`, `bits: u32`. "
            "NEEDBITS(n) -> `while bits < n { if have==0 { break 'exit } hold |= "
            "(next_in[nin] as u64) << bits; nin+=1; have-=1; bits+=8; }`. "
            "BITS(n) -> `hold & ((1<<n)-1)`. DROPBITS(n) -> `hold >>= n; bits -= n;`."
        ),
        rationale="C hides the bit buffer in macros with embedded gotos; Rust inlines them.",
        example="inflate `TYPEDO`/`STORED`/`LEN` states; deflate `send_bits`.",
    ),
    Idiom(
        id="reset-only-intended-fields",
        name="Struct reset must zero only the intended fields",
        tags=("gotcha", "state"),
        c_signals=(r"init_block", r"=\s*\{\s*0\s*\}", r"zmemzero"),
        rust_model=(
            "When C zeroes a SUBSET of a struct (a few counters/arrays), translate that "
            "literally — zero exactly those fields. Do NOT `*s = Default::default()` the "
            "whole struct; that wipes status/config the caller still needs."
        ),
        rationale="A partial C reset is easy to over-translate into a total reset.",
        example="`init_block` zeroes the tree frequencies only, not the whole `DeflateState`.",
        caution="The whole-struct-wipe version passes any test that only checks the zeroed fields.",
    ),
    Idiom(
        id="shift-width-overflow",
        name="1 << i for wide i -> guard the shift width",
        tags=("arithmetic", "gotcha"),
        c_signals=(r"1\s*<<\s*\w+", r"1L\s*<<", r"1U\s*<<"),
        rust_model=(
            "A C `1 << i` where `i` can reach or exceed the type width is UB in C but "
            "PANICS in Rust. Use a wider type, or a shifting mask advanced each iteration "
            "(`mask <<= 1`) instead of recomputing `1 << i`, or mask `i` explicitly."
        ),
        rationale="Rust shift-overflow panics where C silently produced garbage.",
        example="`detect_data_type` scanning bits 0..32 — `1 << i` overflowed at i>=32.",
    ),
    Idiom(
        id="unsigned-wrap-sentinel",
        name="Unsigned-wrap / sentinel values -> explicit signed handling",
        tags=("arithmetic",),
        c_signals=(r"0xffffffff", r"0xffff\b", r"\(unsigned\s+long\)", r"combine"),
        rust_model=(
            "Where C relies on unsigned wraparound or a max-value sentinel, make it "
            "explicit: cast to the signed type to test a negative encoding, return the "
            "sentinel deliberately, and use `wrapping_add`/`wrapping_mul` for intended "
            "overflow. Match the C width exactly (`as u32` truncation included)."
        ),
        rationale="Implicit C wrap/sentinels become explicit, width-exact Rust.",
        example="`adler32_combine` negative-length sentinel: read len2 as signed, return 0xFFFFFFFF.",
    ),
    Idiom(
        id="stale-local-after-callback",
        name="Locals go stale after a call that mutates shared state",
        tags=("gotcha", "state"),
        c_signals=(r"fill_window", r"lookahead", r"strstart"),
        rust_model=(
            "If a helper mutates fields you cached in locals, DON'T keep local copies "
            "across the call — read `strm.state.*` directly afterward, and pass only "
            "`&mut` temporaries as call arguments. Re-load anything the callee can touch."
        ),
        rationale="C code often re-reads struct fields; a naive port caches them and desyncs.",
        example="`deflate_slow` cached `strstart`/`lookahead` that `fill_window` had moved.",
        caution="Symptom is an underflow/`- 1` panic several statements later, far from the cause.",
    ),
    Idiom(
        id="const-config-table",
        name="Static config/lookup tables -> const arrays",
        tags=("tables",),
        c_signals=(r"static\s+const\s+\w+\s+\w+\s*\[", r"configuration_table", r"_tree\s*\["),
        rust_model=(
            "Emit C `static const` tables as Rust `const` arrays with the exact same "
            "values and order. For per-level parameter tables use a tuple/struct array; "
            "for Huffman trees emit the precomputed entries verbatim."
        ),
        rationale="Lookup tables must be reproduced byte-identical, not regenerated approximately.",
        example="`configuration_table[10]` (good/lazy/nice/chain per level); static Huffman trees.",
    ),
    Idiom(
        id="rust-integer-width-coercion",
        name="C mixes integer widths freely -> Rust needs explicit `as` + masking",
        tags=("gotcha", "types"),
        c_signals=(r"unsigned char\s+\w+\s*\^=", r"\bBYTE\b.*[\^|&]=", r"\w+\s*\^=\s*\w+",
                   r"uint8_t.*=.*uint32_t", r">>\s*\d+\s*&\s*0xff"),
        rust_model=(
            "C silently converts between integer widths; Rust does not. When a "
            "narrow variable is combined with a wider one (`u8 ^= u32`, `state[i] = "
            "word`), you MUST cast explicitly and mask to the target width: "
            "`x ^= (y & 0xff) as u8;` or `x = ((x as u32) ^ y) as u8;`. When packing "
            "bytes into a word or unpacking, cast each byte `as u32` before shifting. "
            "Never rely on implicit truncation — it is a compile error (E0277)."
        ),
        rationale="C's implicit integer conversions become explicit `as` casts + masks in Rust.",
        example="md2 `c ^= s[k]` where c:u8, s[k]:u32 -> `c ^= (s[k] & 0xff) as u8;`.",
        caution="Manifests as E0277 'no implementation for `u8 ^= u32`' or E0308 mismatched types.",
    ),
    Idiom(
        id="rust-type-annotation-needed",
        name="ambiguous integer literal/let -> annotate the type (E0282)",
        tags=("gotcha", "types"),
        c_signals=(r"unsigned\s+\w+\s*=\s*0x", r"for\s*\(\s*(?:unsigned\s+)?int"),
        rust_model=(
            "When a `let`, accumulator, or literal has no inferable type (common "
            "translating C where the type is implicit), Rust reports E0282 'type "
            "annotations needed'. Annotate explicitly: `let mut acc: u32 = 0;`, "
            "`let i = 0usize;`, or suffix the literal (`1u64`). Match the C variable's "
            "declared width."
        ),
        rationale="C variable types are declared; a naked Rust `let 0` can be ambiguous — annotate to the C width.",
        example="`unsigned a = 0` accumulating u32 words -> `let mut a: u32 = 0;`.",
        caution="Manifests as E0282 'type annotations needed'.",
    ),
    Idiom(
        id="rust-borrow-split-self-call",
        name="s->field = f(s, ..) -> split into let tmp = f(&mut s); s.field = tmp",
        tags=("ownership", "gotcha"),
        c_signals=(r"->\w+\s*=\s*\w+\s*\([^)]*\bs\b", r"=\s*longest_match\s*\(",
                   r"\w+\(\s*&?s\s*,", r"->\w+\s*=\s*\w+\([^)]*strm"),
        rust_model=(
            "C aliases freely; Rust forbids using a value that is simultaneously "
            "mutably borrowed (E0502/E0503). Two rules: (1) split self-borrowing "
            "assignments — `s.field = f(&mut s, ..)` becomes `let tmp = f(&mut s, ..); "
            "s.field = tmp;`. (2) Before a call that takes `&mut s` (or `&mut s.state`), "
            "COPY any `s.field` you also pass/read into a local first: "
            "`let cur = s.strstart; g(&mut s, cur);`. Extract-then-call; never read a "
            "field of the same struct you are mutably borrowing in one expression."
        ),
        rationale="C's free aliasing becomes Rust borrow-checker conflicts; extract locals to break them.",
        example="deflate_fast: `s.match_length = longest_match(&mut s, head)` -> "
                "`let ml = longest_match(&mut s, head); s.match_length = ml;`.",
        caution="Manifests as E0502/E0503 'cannot borrow/use ... because it is/was mutably borrowed'.",
    ),
    Idiom(
        id="c-debug-macros-are-noops",
        name="C debug/assert macros -> omit (no-ops in release)",
        tags=("gotcha", "control-flow"),
        c_signals=(r"\bcheck_match\s*\(", r"\bAssert\s*\(", r"\bTracev+\s*\(",
                   r"\bTrace\s*\(", r"\bsend_debug\b", r"zmemzero\s*\("),
        rust_model=(
            "C debug-only macros compile to nothing in release builds — `check_match`, "
            "`Assert`, `Tracev`/`Tracevv`/`Tracecv`, `Trace`, `send_debug` are guarded by "
            "ZLIB_DEBUG and expand to `do {} while (0)`. DELETE these calls entirely in "
            "Rust; they have no runtime effect. Do NOT translate them into function calls "
            "(they are not functions) — that is an undefined-symbol compile error."
        ),
        rationale="Debug macros are no-ops in release C; translating them as calls fails to compile.",
        example="deflate_fast: `check_match(s, start, match, len);` -> omitted entirely.",
    ),
    Idiom(
        id="c-manual-output-index-is-the-length",
        name="C out[j++] with a manually-advanced index -> return length is j, not the buffer",
        tags=("buffer", "gotcha"),
        c_signals=(r"out\[j\+\+\]", r"out\[j\]\s*=", r"return\s+j\s*;", r"\bj\s*=\s*0"),
        rust_model=(
            "When C writes into `out[j]` and advances `j` MANUALLY (not once per "
            "loop iteration), the returned length is `j` — and any final `out[j] = "
            "...` that does NOT do `j++` is a PARTIAL byte that is only kept if a "
            "later `out[j++] |= ...` commits it (e.g. base64 decode drops the "
            "trailing partial on padding/end). Do NOT model this with Vec::push: use "
            "a pre-sized buffer + an explicit `j` index, mirror `out[j]` / `out[j++]` "
            "exactly, and return `out[..j].to_vec()`. Pushing every write keeps bytes "
            "the C never counted."
        ),
        rationale="A hand-managed write index decouples buffer contents from the reported length; push-based Vecs over-count.",
        example="base64_decode: case 1/2 write `out[j]=..` without j++, then break on '=' -> that byte is NOT in the j-length result.",
        caution="Manifests as output one byte too long on padded/truncated input, or an index panic.",
    ),
    Idiom(
        id="c-fixed-array-field-to-vec-sizing",
        name="C fixed-size array field -> Rust Vec must be sized before indexed write",
        tags=("buffer", "gotcha", "state"),
        c_signals=(r"->\s*\w+\s*\[[^\]]+\]\s*[+\-^|&]?=", r"s->\w+\[", r"for\s*\([^)]*\)\s*\w*->\w+\["),
        rust_model=(
            "A C fixed-size array field (`ush bl_count[MAX_BITS+1]`, `int heap[..]`) "
            "is ALWAYS allocated; the coherent Rust models it as `Vec<T>`, which may "
            "be EMPTY on a default/fresh state. Before writing OR reading it by index, "
            "ensure it is sized: `if s.field.len() < N { s.field.resize(N, 0); }` where "
            "N is the C array length (inline the value). Do NOT assume the Vec is "
            "pre-sized like the C array — indexing an empty Vec panics."
        ),
        rationale="C arrays are always allocated; the coherent-model Vec is not, so indexed writes panic on empty.",
        example="gen_bitlen: `if s.bl_count.len() < 16 { s.bl_count.resize(16, 0); }` before `s.bl_count[bits] = 0`.",
        caution="Panics as 'index out of bounds: the len is 0' at the first indexed write — logic looks correct.",
    ),
    Idiom(
        id="for-loop-post-increment-cursor",
        name="C for(;;cursor++) with helper calls -> increment at loop END",
        tags=("control-flow", "gotcha"),
        c_signals=(r"for\s*\([^;]*;[^;]*;\s*\w*(?:pos|cursor|i|p)\w*\s*\+\+\s*\)",
                   r"for\s*\(\s*;", r"parser->pos\+\+", r"->pos\b"),
        rust_model=(
            "A C `for (init; cond; cursor++)` advances the cursor at the END of each "
            "iteration, so inside the body the cursor still points AT the current "
            "element. Translate as `while cond { let c = seq[cursor]; match c { .. }; "
            "cursor += 1; }` — increment at the END, NOT right after reading. This "
            "matters when the body calls a sub-function that itself reads/advances the "
            "cursor (e.g. a sub-parser that expects the cursor AT the opening "
            "delimiter): pre-incrementing hands it the wrong position and every such "
            "element is off by one."
        ),
        rationale="Post-increment for-loops keep the cursor on the current element during the body; eager increment breaks helper calls.",
        example="jsmn_parse `for(; pos<len; pos++)`: calling jsmn_parse_string with pos AT the opening quote. "
                "Eager `pos+=1` before dispatch made every string/primitive off by one (2/13); end-of-loop increment -> 13/13.",
        caution="The single most common cause of off-by-one token bounds when porting a hand-written parser loop.",
    ),
    Idiom(
        id="pointer-return-into-array-to-index",
        name="Pointer-into-array return -> index (pool allocation)",
        tags=("ownership", "buffer"),
        c_signals=(r"return\s+&\w+\s*\[", r"return\s+NULL\s*;", r"\)\s*;\s*\n[^;]*->",
                   r"=\s*\w+_alloc\w*\("),
        rust_model=(
            "A C function that returns a POINTER into an array (e.g. "
            "`return &tokens[i++];`, `return NULL;` when full) and whose callers "
            "mutate through it (`tok->field = ...`) must, in Rust, return the "
            "INDEX (i32, with -1 for the null/full case). Callers become: "
            "`let i = alloc(...); if i < 0 { return ERR; } tokens[i as usize].field = ...`. "
            "NEVER return a `&mut` you keep using across further calls that also "
            "borrow the array — index into the array each time instead. Keep the "
            "'current container/parent' as a stored INDEX too (e.g. `toksuper: i32`, "
            "-1 = none), and update it exactly where the C reassigns the pointer."
        ),
        rationale="C pool-allocators hand back a pointer to mutate; safe Rust can't alias, so it indexes.",
        example="jsmn `jsmn_alloc_token` returns `jsmntok_t*`; the Rust returns the token index; "
                "`parser.toksuper` is the current-container index (-1=none), reassigned on `:` and reset on `,`.",
        caution="If callers mutate through a kept pointer AND the array is re-borrowed, container size "
                "counts double — reassign the index at the exact points C reassigns the pointer.",
    ),
    Idiom(
        id="rust-byte-literal-escaping",
        name="C char literals -> Rust byte literals (escaping)",
        tags=("gotcha", "syntax"),
        c_signals=(r"'\\\\'", r"'\\\"'", r"'\\[nrt0]'", r"==\s*'[^']", r"case\s+'"),
        rust_model=(
            "When comparing bytes of a `&[u8]`, use byte literals: `b'{'`, `b'\"'`, "
            "`b'0'..=b'9'`. Escaping is the trap — a BACKSLASH byte is `b'\\\\'` "
            "(writing `b'\\'` is a syntax error: unterminated char literal). Tab/"
            "newline/CR are `b'\\t'`/`b'\\n'`/`b'\\r'`. Match C's `'\\\\'`, `'\"'`, "
            "`'\\n'` to the corresponding `b'..'`."
        ),
        rationale="C char constants become Rust byte literals; the backslash escape is a common syntax error.",
        example="jsmn string parsing compares `js[pos]` to `'\\\\'`, `'\"'`, `'/'` -> `b'\\\\'`, `b'\"'`, `b'/'`.",
        caution="The model deterministically writes `b'\\'` for a backslash byte — an unterminated char literal.",
    ),
    Idiom(
        id="complete-huffman-code",
        name="Fixed Huffman tables must form a *complete* code",
        tags=("tables", "gotcha", "bits"),
        c_signals=(r"inflate_fixed", r"fixedtables", r"lenfix", r"distfix"),
        rust_model=(
            "When building fixed/static Huffman tables at runtime, supply the FULL symbol "
            "count the code was defined over, including reserved symbols, so the code is "
            "complete (Kraft sum == 1). Under-counting yields an 'incomplete code' error."
        ),
        rationale="An incomplete code table is rejected by the table builder.",
        example="Fixed distance table needs 32 length-5 codes (not 30) to be complete.",
    ),
)


def idiom_by_id(idiom_id: str) -> Idiom | None:
    return next((i for i in IDIOMS if i.id == idiom_id), None)


def match_idioms(c_source: str) -> list[Idiom]:
    """Return the idioms whose C-signals fire on this source, catalog order."""
    return [i for i in IDIOMS if i.matches(c_source)]


def render_prompt_hints(idioms: "list[Idiom] | tuple[Idiom, ...] | None" = None) -> str:
    """Render a concise, injectable guidance block for the given idioms.

    Pass the result of `match_idioms(c_source)` to surface only relevant patterns;
    pass None to render the whole catalog.
    """
    items = list(IDIOMS if idioms is None else idioms)
    if not items:
        return ""
    header = (
        "## C->safe-Rust idiom patterns (apply where they fit)\n"
        f"<!-- catalog {CATALOG_VERSION} -->\n"
        "These recurring C constructs have known safe-Rust models. Follow them "
        "unless the specific code demands otherwise:\n"
    )
    return header + "\n\n".join(i.prompt_block() for i in items) + "\n"
