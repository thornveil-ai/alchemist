#!/usr/bin/env python3
"""Bulk real-library ingester -> Alchemist subjects (the volume accelerant).

Manifest-driven: each entry fetches a self-contained, permissively-licensed C
library's files (raw from GitHub), drops them in subjects/ingest/<name>/, and
compile-checks. Anything that compiles is a ready batch_run subject. Fetching
real libs beats hand-seeding: each carries many oracle-classifiable functions
(digest/ctx_transform cores, checksums, scalar math).

Add entries to MANIFEST; re-run; then:
  python tools/batch_run.py --subjects subjects/ingest/<names...>
"""
import subprocess
import urllib.request
from pathlib import Path

BASE = Path("/data/rigrun/projects/alchemist/subjects/ingest")

# name -> (raw_base_url, [files], license)
MANIFEST = {
    # B-Con/crypto-algorithms — PUBLIC DOMAIN, each .c+.h self-contained.
    "bcon_sha256":   ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["sha256.c", "sha256.h"], "public-domain"),
    "bcon_sha1":     ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["sha1.c", "sha1.h"], "public-domain"),
    "bcon_md5":      ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["md5.c", "md5.h"], "public-domain"),
    "bcon_md2":      ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["md2.c", "md2.h"], "public-domain"),
    "bcon_base64":   ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["base64.c", "base64.h"], "public-domain"),
    "bcon_arcfour":  ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["arcfour.c", "arcfour.h"], "public-domain"),
    "bcon_rot13":    ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["rot-13.c", "rot-13.h"], "public-domain"),
    "bcon_des":      ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["des.c", "des.h"], "public-domain"),
    "bcon_blowfish": ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["blowfish.c", "blowfish.h"], "public-domain"),
    "bcon_aes":      ("https://raw.githubusercontent.com/B-Con/crypto-algorithms/master/", ["aes.c", "aes.h"], "public-domain"),
}


def fetch(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "verano-ingest"})
        data = urllib.request.urlopen(req, timeout=25).read()
        dest.write_bytes(data)
        return len(data) > 20
    except Exception as e:  # noqa: BLE001
        print("   fetch fail:", e)
        return False


def main():
    BASE.mkdir(parents=True, exist_ok=True)
    ready, failed = [], []
    for name, (base_url, files, lic) in MANIFEST.items():
        d = BASE / name
        d.mkdir(parents=True, exist_ok=True)
        ok = all(fetch(base_url + f, d / f) for f in files)
        if not ok:
            failed.append((name, "fetch")); continue
        cfiles = [str(d / f) for f in files if f.endswith(".c")]
        r = subprocess.run(["gcc", "-c", "-w"] + cfiles + ["-I", str(d)],
                           capture_output=True, text=True, cwd=str(d))
        # write a LICENSE marker for provenance
        (d / "LICENSE.txt").write_text(f"upstream: {base_url}\nlicense: {lic}\n")
        if r.returncode == 0:
            ready.append(name)
            print(f"  {name}: READY ({lic})")
        else:
            failed.append((name, "compile"))
            print(f"  {name}: compile FAIL: {r.stderr[:150]}")
    print(f"\ningested {len(ready)} ready / {len(failed)} failed")
    print("READY:", " ".join("subjects/ingest/" + n for n in ready))


if __name__ == "__main__":
    main()
