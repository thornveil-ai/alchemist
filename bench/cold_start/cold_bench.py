#!/usr/bin/env python3
"""Alchemist cold-start benchmark harness (Phase 0).

Creates a suite of never-seen C functions across classes, runs the SHIPPING pipeline
on each COLD (no per-subject config, zero human touches), and scores how far each gets:
triaged-in? analyze/extract/architect/implement/verify pass? -- with the honest numbers.

Run on the box:  .venv/bin/python cold_bench.py
Writes:  bench/cold_start/<name>/<name>.c   (suite)
         bench/cold_start/RESULTS.md + results.json   (scorecard)
"""
import os, re, json, shutil, subprocess, sys, time

ROOT = os.environ.get("ALCHEMIST_ROOT", os.getcwd())
BENCH = os.path.join(ROOT, "bench", "cold_start")
_venv = os.path.join(ROOT, ".venv", "bin", "python")
VENV = _venv if os.path.exists(_venv) else sys.executable
ENDPOINT = os.environ.get("ALCHEMIST_ENDPOINT", "http://127.0.0.1:8086/v1")
STAGES = ["analyze", "extract", "architect", "implement", "verify", "report"]

# --- the suite: (name, class, C source) ------------------------------------------
SUITE = [
 ("isqrt", "math-scalar", """
unsigned isqrt(unsigned n) {
    unsigned x, y;
    if (n == 0) return 0;
    x = n; y = (x + 1) / 2;
    while (y < x) { x = y; y = (x + n / x) / 2; }
    return x;
}
"""),
 ("popcount", "bits-scalar", """
int popcount(unsigned long x) {
    int c = 0;
    while (x) { c += (int)(x & 1UL); x >>= 1; }
    return c;
}
"""),
 ("fletcher16", "checksum-buffer", """
unsigned short fletcher16(const unsigned char *data, int len) {
    unsigned s1 = 0, s2 = 0;
    int i;
    for (i = 0; i < len; i++) { s1 = (s1 + data[i]) % 255; s2 = (s2 + s1) % 255; }
    return (unsigned short)((s2 << 8) | s1);
}
"""),
 ("str_reverse", "string-inplace", """
void str_reverse(char *s, int len) {
    int i = 0, j = len - 1;
    while (i < j) { char t = s[i]; s[i] = s[j]; s[j] = t; i++; j--; }
}
"""),
 ("parse_int", "parser-buffer", """
long parse_int(const char *s, int len) {
    long v = 0; int i = 0, neg = 0;
    if (i < len && s[i] == '-') { neg = 1; i++; }
    for (; i < len; i++) {
        if (s[i] < '0' || s[i] > '9') break;
        v = v * 10 + (s[i] - '0');
    }
    return neg ? -v : v;
}
"""),
 ("xorshift", "stateful-prng", """
typedef struct { unsigned long state; } xorshift_state;
void xorshift_seed(xorshift_state *st, unsigned long seed) { st->state = seed ? seed : 1UL; }
unsigned long xorshift_next(xorshift_state *st) {
    unsigned long x = st->state;
    x ^= x << 13; x ^= x >> 7; x ^= x << 17;
    st->state = x;
    return x;
}
"""),
 ("rc4", "stateful-cipher", """
#include <stdint.h>
typedef struct { uint8_t s[256]; int i; int j; } rc4_state;
void rc4_init(rc4_state *st, const uint8_t *key, int keylen) {
    int i, j = 0;
    for (i = 0; i < 256; i++) st->s[i] = (uint8_t)i;
    for (i = 0; i < 256; i++) {
        j = (j + st->s[i] + key[i % keylen]) & 0xff;
        uint8_t t = st->s[i]; st->s[i] = st->s[j]; st->s[j] = t;
    }
    st->i = 0; st->j = 0;
}
void rc4_keystream(rc4_state *st, uint8_t *out, int len) {
    int i = st->i, j = st->j, k;
    for (k = 0; k < len; k++) {
        i = (i + 1) & 0xff;
        j = (j + st->s[i]) & 0xff;
        uint8_t t = st->s[i]; st->s[i] = st->s[j]; st->s[j] = t;
        out[k] = st->s[(st->s[i] + st->s[j]) & 0xff];
    }
    st->i = i; st->j = j;
}
"""),
 ("bump_alloc", "stateful-allocator", """
typedef struct { unsigned char *buf; int cap; int off; } bump_alloc;
void bump_init(bump_alloc *a, unsigned char *buf, int cap) { a->buf = buf; a->cap = cap; a->off = 0; }
int bump_alloc_n(bump_alloc *a, int n) {
    if (n < 0 || a->off + n > a->cap) return -1;
    { int p = a->off; a->off += n; return p; }
}
"""),
 # Clean (UB-free) versions of the sqrt / parser classes. The original `isqrt`
 # and `parse_int` above have genuine integer-overflow UB (isqrt: x+1 wraps to 0
 # at UINT_MAX -> n/0; parse_int: v*10 overflows) which the differential CORRECTLY
 # refuses. These are the well-formed equivalents, differentially verifiable.
 ("bitsqrt", "math-scalar-clean", """
unsigned bitsqrt(unsigned n) {
    unsigned res = 0;
    unsigned bit = 1u << 30;
    while (bit > n) bit >>= 2;
    while (bit != 0) {
        if (n >= res + bit) { n -= res + bit; res = (res >> 1) + bit; }
        else { res >>= 1; }
        bit >>= 2;
    }
    return res;
}
"""),
 ("atoib", "parser-buffer-clean", """
long atoib(const unsigned char *s, int len) {
    long v = 0; int i = 0, neg = 0;
    if (i < len && s[i] == 45) { neg = 1; i++; }
    for (; i < len && i < 18; i++) {
        if (s[i] < 48 || s[i] > 57) break;
        v = v * 10 + (long)(s[i] - 48);
    }
    return neg ? -v : v;
}
"""),
]

ANSI = re.compile(r"\x1b\[[0-9;]*[mK]")
def strip(s): return ANSI.sub("", s)

def score(out):
    r = {"triaged_in": None, "llm_calls": 0, "overall": None}
    for s in STAGES:
        r[s] = None
    # triage: did any module get classified algorithm (attempted) vs skipped as glue?
    m = re.search(r"Extracting specs for (\d+) algorithm modules \(skipping (\d+) glue", out)
    if m:
        r["triaged_in"] = int(m.group(1)) > 0
    m = re.search(r"Calls:\s*(\d+)", out)
    if m: r["llm_calls"] = int(m.group(1))
    for s in STAGES:
        m = re.search(r"\[(PASS|FAIL)\]\s+" + s + r"\b", out)
        if m: r[s] = (m.group(1) == "PASS")
    m = re.search(r"OVERALL:\s*(PASS|FAIL)", out)
    if m: r["overall"] = (m.group(1) == "PASS")
    return r

def run_one(name, csrc):
    d = os.path.join(BENCH, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name + ".c"), "w") as f:
        f.write(csrc.lstrip("\n"))
    shutil.rmtree(os.path.join(d, ".alchemist"), ignore_errors=True)
    env = dict(os.environ); env["ALCHEMIST_ENDPOINT"] = ENDPOINT
    t0 = time.monotonic()
    try:
        p = subprocess.run([VENV, "-m", "alchemist.cli", "translate", d, "--name", name + "-rs"],
                           capture_output=True, text=True, env=env, cwd=ROOT, timeout=900)
        out = strip(p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        out = "TIMEOUT"
    dt = time.monotonic() - t0
    r = score(out)
    r["seconds"] = round(dt, 1)
    return r

def main():
    os.makedirs(BENCH, exist_ok=True)
    results = {}
    for name, cls, csrc in SUITE:
        print("running", name, "(" + cls + ") ...", flush=True)
        r = run_one(name, csrc)
        r["class"] = cls
        results[name] = r
        reached = [s for s in STAGES if r.get(s)]
        print("   ", name, "triaged_in=" + str(r["triaged_in"]),
              "reached:", ",".join(reached) or "NONE", "overall=" + str(r["overall"]),
              "(" + str(r["seconds"]) + "s, " + str(r["llm_calls"]) + " calls)", flush=True)
    # scorecard
    def cell(v): return "PASS" if v is True else ("FAIL" if v is False else "-")
    lines = ["# Alchemist Cold-Start Baseline (Phase 0)", "",
             "Each function run through the SHIPPING pipeline COLD (no per-subject config, "
             "zero human touches). `triage` = did the classifier attempt it (vs skip as glue).", "",
             "| function | class | triage | analyze | extract | architect | implement | verify | overall | s | calls |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, cls, _ in SUITE:
        r = results[name]
        tri = "ATTEMPT" if r["triaged_in"] else ("SKIP" if r["triaged_in"] is False else "-")
        lines.append("| `%s` | %s | %s | %s | %s | %s | %s | %s | **%s** | %s | %s |" % (
            name, cls, tri, cell(r.get("analyze")), cell(r.get("extract")),
            cell(r.get("architect")), cell(r.get("implement")), cell(r.get("verify")),
            cell(r.get("overall")), r["seconds"], r["llm_calls"]))
    n = len(SUITE)
    def pct(key, val=True): return round(100.0 * sum(1 for x in results.values() if x.get(key) is val) / n)
    lines += ["",
        "## Honest numbers (n=%d)" % n,
        "- **Triaged in (attempted, not skipped as glue): %d%%**" % pct("triaged_in"),
        "- Reached extract (spec recovered): %d%%" % pct("extract"),
        "- Reached architect: %d%%" % pct("architect"),
        "- Passed implement (compiles + tests): %d%%" % pct("implement"),
        "- Passed verify (differential): %d%%" % pct("verify"),
        "- **OVERALL PASS cold, zero human touches: %d%%**" % pct("overall"),
    ]
    with open(os.path.join(BENCH, "RESULTS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(BENCH, "results.json"), "w") as f:
        json.dump(results, f, indent=2)
    print("\n" + "\n".join(lines[-8:]), flush=True)
    print("\nwrote bench/cold_start/RESULTS.md + results.json", flush=True)

if __name__ == "__main__":
    main()
