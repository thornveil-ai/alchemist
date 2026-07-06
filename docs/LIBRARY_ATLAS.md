# The C Library Atlas — charting humanity's C for translation

Master chart of C libraries to push through the Alchemist pipeline
(`translate ./lib` → onboard → oracle → fill → borrow-fix → differential verify).
Organized by **push-through priority** (how well it fits the pipeline *today*),
then by domain. Compiled from the curated ecosystem catalogs (awesome-c,
awesome-cryptography, single-file libs, clib) + direct knowledge.

**Class taxonomy** (what the pipeline supports):
- `scalar` — buffer(+len) → scalar (checksums, non-crypto hashes) ✅ handled
- `buffer` — bytes → bytes (codecs, transforms) ✅ handled
- `stateful` — init/update/final over a ctx struct (crypto hashes, streaming) ✅ handled
- `oneshot-crypto` — key-setup + block/stream (ciphers) ⚠️ mostly stateful-shaped, some multi-array state
- `complex` — big multi-file, control-flow-heavy (compression, regex, protobuf) ⚠️ frontier
- `oos` — out of scope now (C++, needs HAL/syscalls, nondeterministic/iteration-order)

**Verification:** every "run" is byte-exact-or-refused vs the compiled C reference.

## Mapped universe (as of this sweep)
Compiled from four parallel catalog sweeps — **~600+ distinct C libraries** charted:
- **awesome-c** (kozross/oz123, ~350 entries across 40 categories) + **uhub** supplement (~35 library-grade).
- **single-file / header-only** libs (nothings/single_file_libs, cute_headers, clib) — ~200+ pure-C, the highest-value tier.
- **crypto/hashing/compression/codecs** deep sweep (~100 with per-algorithm URLs + API style).
- **parsing/serialization/data-structures/string/math** (~100).

The vast majority are **out of the differential sweet spot** (networking, GUI, databases,
OS/HAL, build tools, test frameworks, applications). The **push-through universe** —
pure-C, deterministic, single-file, fits a supported class — is on the order of
**150–200 libraries**, catalogued into the tiers below. That's the real target count
for "chart humanity's C and push it through."

---

## Tier A — push through NOW (pure C · single-file · deterministic · fits a supported class)

### Crypto hashes (stateful init/update/final) — the SHA-256 lane
| Library | Repo | Class | Status |
|---|---|---|---|
| SHA-256 (B-Con) | B-Con/crypto-algorithms | stateful | ✅ 300 vectors |
| SHA-1 (B-Con) | B-Con/crypto-algorithms | stateful | 🔄 in batch |
| MD5 (B-Con) | B-Con/crypto-algorithms | stateful | 🔄 in batch |
| MD2 (B-Con) | B-Con/crypto-algorithms | stateful | 🔄 in batch |
| SHA-3/Keccak | mjosaarinen/tiny_sha3 · brainhub/SHA3IUF | stateful | ⬜ |
| BLAKE2s/2b (ref) | BLAKE2/BLAKE2 (blake2-ref.c) | stateful | ⬜ has Rust ref to cross-check |
| BLAKE3 (portable) | BLAKE3-team/BLAKE3 (c/) | stateful | ⬜ official C **and** Rust |
| SHA-512 | amosnier/sha-2 · WjCryptLib | stateful | ⬜ |
| MD4 (RFC 1320) | Zunawe/md5-c lineage | stateful | ⬜ |
| RIPEMD-160 | Bosselaers reference | stateful | ⬜ |
| Streebog (GOST) | adegtyarev/streebog | stateful | ⬜ |
| Whirlpool / Tiger | rhash/RHash (sphlib) | stateful | ⬜ |

### Non-crypto hashes (scalar / one-shot) — the CRC lane
| Library | Repo | Class | Status |
|---|---|---|---|
| ArduPilot crc.cpp | ArduPilot/AP_Math | scalar | ✅ 180–240 |
| xxHash (XXH32/64) | Cyan4973/xxHash | scalar (+stateful variant) | ⬜ huge official KATs; Rust ref |
| MurmurHash3 | PeterScott/murmur3 | scalar | ⬜ pure-C extraction |
| SipHash-2-4 | veorq/SipHash | scalar | ⬜ std `SipHasher` ref |
| FNV-1/1a | lcn2/fnv (Landon Noll ref) | scalar | ⬜ trivial |
| djb2 / sdbm | oz/hash writeup | scalar | ⬜ tiny |
| Jenkins lookup3 / one-at-a-time | burtleburtle lookup3.c | scalar | ⬜ |
| t1ha | erthink/t1ha | scalar | ⬜ self-tests |
| wyhash | wangyi-fudan/wyhash | scalar | ⬜ single-header |
| Pearson | Logan007/pearson | scalar | ⬜ 256-byte table |
| CRC catalogue (100+) | pycrc generator · reveng | scalar | ⬜ corpus generator: emit every CRC variant |
| Adler-32 / Fletcher | madler/zlib · RFC 1146 | scalar | ✅(adler in zlib) / ⬜ |
| Luhn / Verhoeff / Damm | check-digit refs | scalar | ⬜ tiny |

### Codecs (buffer → buffer)
| Library | Repo | Class | Status |
|---|---|---|---|
| base64 (zhicheng) | zhicheng/base64 | buffer | ✅ 24+32 |
| libb64 | libb64/libb64 | stateful/buffer | ⬜ streaming |
| base64 (aklomp scalar) | aklomp/base64 | buffer | ⬜ |
| base32 (RFC 4648) | google-authenticator base32.c | buffer | ⬜ |
| base16/hex | trivial refs | buffer | ⬜ smallest codec |
| base58 / base58check | bitcoin/libbase58 · trezor | buffer | ⬜ bignum mod |
| Z85 / ascii85 | zeromq spec · dhalf/ascii85 | buffer | ⬜ |
| base45 (RFC 9285) | ehn-dcc base45-c | buffer | ⬜ |
| URL percent-encode | curl escape · yuriks/urlencode | buffer | ⬜ table codec |
| quoted-printable / uuencode | MIME refs · sharutils | buffer | ⬜ |
| ROT13 | B-Con/crypto-algorithms | buffer | ⬜ trivial |
| varint / LEB128 | SQLite varint.c | scalar/buffer | ⬜ tiny golden unit |

### Stream ciphers & MACs (small stateful machines)
| Library | Repo | Class | Status |
|---|---|---|---|
| RC4 / ARCFOUR | B-Con · WjCryptLib | stateful | ⬜ KSA+PRGA state machine |
| ChaCha20 | Ginurx/chacha20-c (RFC 8439) | stateful/oneshot | ⬜ RFC vectors |
| Salsa20 | alexwebr/salsa20 | stateful | ⬜ |
| Poly1305 | floodyberry/poly1305-donna | stateful | ⬜ RFC 8439; Rust ref |
| TEA / XTEA / XXTEA | Wheeler-Needham refs | oneshot block | ⬜ textbook-small |
| SipHash (MAC use) | veorq/SipHash | scalar | ⬜ |

---

## Tier B — needs a frontier piece (bigger, control-flow-heavy, or a shape gap)

| Library | Repo | Class | Blocker |
|---|---|---|---|
| zlib deflate/inflate | madler/zlib | complex | ✅ done hand-driven; auto path = big state machines (deflate_fast logic) |
| puff.c (ref inflate) | zlib/contrib/puff | complex | small enough to translate wholesale — good next moonshot |
| miniz | richgel999/miniz | complex | single-file zlib clone; whole-codec differential |
| LZ4 / FastLZ | lz4/lz4 · ariya/FastLZ | complex | LZ match emission (deflate_fast-class logic) |
| heatshrink | atomicobject/heatshrink | stateful | poll/sink state machine — tractable |
| tiny-AES-c | kokke/tiny-AES-c | oneshot-crypto | key schedule = multi-array state; modes |
| jsmn | zserge/jsmn | parser | ✅ done (1 diagnosis) |
| cJSON / parson / tiny-json | DaveGamble/cJSON · kgabis/parson | parser | DOM alloc + pointer graph |
| tomlc99 / inih | cktan/tomlc99 · benhoyt/inih | parser | callback/streaming shape |
| tiny-regex-c / slre | kokke · cesanta | regex | NFA control flow |
| protobuf-c / nanopb | protobuf-c · nanopb | serialize | varint/zigzag = tiny units (Tier A); full codec = Tier B |
| tiny-bignum-c | kokke/tiny-bignum-c | complex | big-int arithmetic, no I/O — strong differential target |
| SoftFloat | ucb-bar/berkeley-softfloat-3 | complex | IEEE-754 emulation, exact bit output |
| TweetNaCl | tweetnacl.cr.yp.to | multi | ~100 lines, full crypto — whole-file stretch goal |

---

## Tier C — out of scope now (records the honest edge)
C++ (RapidJSON, simdjson, RE2, Eigen, Botan, Crypto++, metrohash, SpookyHash);
anything needing a real HAL/syscalls or TLS state machines (OpenSSL/mbedTLS/wolfSSL
as *whole* libraries — mine them for KATs instead); iteration-order-dependent
outputs (uthash/khash *order*); allocator-address-leaking (`%p`, tpl).

---

## Aggregators = golden-vector sources (not translation targets)
libtomcrypt · nettle · OpenSSL · mbedTLS · libsodium · WjCryptLib · XKCP · RHash ·
CRC RevEng catalogue · RFC appendices (1319/1320/1321, 1071, 1950–52, 4648, 8439,
8949, 7693) · NESSIE/eSTREAM/CAESAR KATs. Mine these for known-answer tests to seed
the differential corpora; harness the single-file libs above for the actual runs.

---

*Live results scoreboard: [BREADTH_TRACKER.md](BREADTH_TRACKER.md). This atlas is
the map; the tracker is how far we've gotten.*
