"""Verify the canonical gate-grade datasets against MANIFEST.sha256 (Article II).
Run from the repo root or backtest/: python backtest/verify_data.py
Exit 0 = all files present and byte-identical; nonzero = report and STOP."""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MAN = os.path.join(HERE, "data", "MANIFEST.sha256")

def main():
    if not os.path.isfile(MAN):
        print("FAIL: MANIFEST.sha256 missing"); sys.exit(2)
    bad = missing = ok = 0
    # The manifest's comment header is cp1252 (authored on Windows); hash lines
    # are pure ASCII. Tolerant decode keeps verification byte-exact everywhere.
    for line in open(MAN, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        h, rel = line.split(None, 1)
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            print(f"MISSING: {rel}"); missing += 1; continue
        actual = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if actual != h:
            print(f"HASH MISMATCH: {rel}"); bad += 1
        else:
            ok += 1
    print(f"verified {ok} OK, {missing} missing, {bad} mismatched")
    sys.exit(0 if (missing == 0 and bad == 0) else 1)

if __name__ == "__main__":
    main()
