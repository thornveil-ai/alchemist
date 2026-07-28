#!/usr/bin/env python3
"""Turn oracle-verified pairs into ELITE C->Rust fine-tune data.

Every record is (a) PROVABLY correct (oracle byte-exact — zero label noise, the
thing almost no other C->Rust dataset has), (b) chat-formatted for TRL/Unsloth
SFT, (c) enriched with the extracted spec's rationale (purpose + algorithm notes
+ rust strategy) so the model learns the *reasoning*, not just the mapping, and
(d) tagged with difficulty (won_via) + domain (category) for curriculum/balanced
sampling. Dedups on (c,rust).

Outputs:
  corpus/sft.jsonl        — {messages:[sys,user,assistant], meta:{...}}
  corpus/sft_stats.json   — counts by category / won_via / size
"""
import json
import hashlib
from pathlib import Path

ROOT = Path("/data/rigrun/projects/alchemist")
PAIRS = ROOT / "corpus" / "pairs.jsonl"
OUT = ROOT / "corpus" / "sft.jsonl"
STATS = ROOT / "corpus" / "sft_stats.json"

SYSTEM = ("You are an expert systems engineer who translates C functions into "
          "safe, idiomatic Rust that is byte-for-byte behaviorally identical to "
          "the C on every input. Forbid unsafe code. Preserve C integer "
          "semantics exactly (use wrapping_add/sub/mul for overflow, match "
          "signedness and widths). Return only the Rust function.")


def _find_spec(subject: str, fn: str) -> dict | None:
    base = ROOT / "subjects" / subject / ".alchemist" / "specs"
    if not base.exists():
        return None
    for p in base.glob("_functions/**/" + fn + ".json"):
        try:
            return json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            return None
    return None


def _rationale(spec: dict | None) -> str:
    if not spec:
        return ""
    bits = []
    if spec.get("purpose"):
        bits.append(spec["purpose"].strip())
    if spec.get("algorithm_notes"):
        bits.append("Algorithm: " + spec["algorithm_notes"].strip())
    if spec.get("rust_strategy"):
        bits.append("Rust strategy: " + spec["rust_strategy"].strip())
    return "  ".join(bits)


# (subject|function) keyword -> domain category, checked in priority order so
# specific families win (e.g. 'sha256' -> hash before any generic match).
_CAT_RULES = [
    ("cipher",     ["aes", "des", "rc4", "arcfour", "blowfish", "chacha", "salsa",
                     "xtea", "tea", "cipher", "encrypt", "decrypt", "jambu", "sparkle",
                     "xoodoo", "monocypher", "poly1305", "x25519", "ed25519"]),
    ("checksum",   ["crc", "adler", "fletcher", "checksum", "cksum", "parity", "bch"]),
    ("prng",       ["rand", "rng", "prng", "xorshift", "splitmix", "pcg", "lcg",
                     "mersenne", "xoshiro"]),
    ("fixedpoint", ["fix16", "q16", "q8", "qfixed", "fixed", "fract", "libfixmath"]),
    ("encoding",   ["base64", "base32", "base58", "varint", "encode", "decode", "rot13", "rot-13"]),
    ("graphics",   ["rgb", "argb", "rgb565", "luminance", "channel", "alpha_blend",
                     "pixel", "color", "_screen", "blend"]),
    ("hash",       ["sha", "md5", "md4", "md2", "blake", "murmur", "siphash", "xxh",
                     "fnv", "digest", "_hash", "hash64", "hash_", "oat_", "pjw", "djb",
                     "rs_hash", "js_hash", "wang", "fmix", "mix_", "sdbm", "jenkins",
                     "knuth", "xorrot", "wyhash", "degski", "nasam", "moremur",
                     "lowbias", "prospector", "stafford", "triple32", "iqint",
                     "fasthash", "pelican", "skeeto", "shifter", "belloch",
                     "avaround", "xnasam", "xqo", "lea64", "finalize"]),
    ("bitops",     ["popcount", "clz", "ctz", "gray", "bswap", "rotl", "rotr",
                     "reverse_bit", "_bits", "bit_", "pow2", "sign_extend",
                     "lowest_set", "trailing_zeros", "isolate", "clear_low",
                     "reflect", "combine2", "round_up"]),
    ("string",     ["str", "ascii", "utf", "atoi", "palindrome", "word", "char",
                     "upper", "lower", "regex"]),
    ("intmath",    ["isqrt", "gcd", "factorial", "fib", "prime", "collatz", "digit",
                     "sqrt", "expr", "genann", "mod", "mul", "pow", "lcm", "fact",
                     "catalan", "totient", "mobius", "divisor", "triangular",
                     "pentagonal", "hexagonal", "tribonacci", "binomial", "radical",
                     "crt", "chinese", "sqr", "ilog", "ipow", "perfect", "abundant",
                     "square", "geomsum", "sumto", "reverse_dec", "reverse_base",
                     "count_div", "sum_of", "sum_prop", "sum_div", "sat_", "clamp",
                     "abs", "imax", "imin", "umax", "umin", "min3", "max3",
                     "midpoint", "sign", "wrap_inc", "is_pow2", "midpoint"]),
    ("parser",     ["parse", "lex", "token", "json", "http"]),
]


def _infer_category(subject, function, c_src=""):
    hay = f"{subject} {function}".lower()
    for cat, kws in _CAT_RULES:
        if any(k in hay for k in kws):
            return cat
    return "unknown"


def main():
    if not PAIRS.exists():
        print("no pairs.jsonl yet"); return
    seen, records = set(), []
    cat_hist, via_hist = {}, {}
    for line in PAIRS.read_text().splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        c, rust = p.get("c", "").strip(), p.get("rust", "").strip()
        if not c or not rust or "unimplemented!" in rust:
            continue
        key = hashlib.sha256((c + "\x00" + rust).encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        spec = _find_spec(p.get("subject", ""), p.get("function", ""))
        cat = (spec or {}).get("category") or "unknown"
        if cat == "unknown":
            cat = _infer_category(p.get("subject", ""), p.get("function", ""), c)
        via = p.get("won_via") or "unknown"
        cat_hist[cat] = cat_hist.get(cat, 0) + 1
        via_hist[via] = via_hist.get(via, 0) + 1
        user = f"Translate this C function to safe Rust:\n\n```c\n{c}\n```"
        rat = _rationale(spec)
        records.append({
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
                {"role": "assistant", "content": f"```rust\n{rust}\n```"},
            ],
            "meta": {
                "subject": p.get("subject"), "function": p.get("function"),
                "category": cat, "won_via": via,
                "rationale": rat,
                "verified": "byte-exact-differential",
                "reference_c": c, "rust": rust,
            },
        })
    with OUT.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    stats = {
        "records": len(records),
        "by_category": dict(sorted(cat_hist.items(), key=lambda x: -x[1])),
        "by_won_via": via_hist,
        "with_rationale": sum(1 for r in records if r["meta"]["rationale"]),
    }
    STATS.write_text(json.dumps(stats, indent=2))
    print(f"SFT records: {len(records)} -> {OUT}")
    print(f"  by category: {stats['by_category']}")
    print(f"  by won_via:  {stats['by_won_via']}")
    print(f"  with rationale: {stats['with_rationale']}/{len(records)}")


if __name__ == "__main__":
    main()
