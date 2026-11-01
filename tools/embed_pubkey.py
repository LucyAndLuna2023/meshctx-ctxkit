#!/usr/bin/env python3
"""embed_pubkey.py — sync the billing server's public key into the client.

THE most common licensing bug: regenerate keys on the server, forget to
rebuild the client, and every paying customer's license silently fails to
verify. Run this after ANY key change, then rebuild and republish.

Usage:
    python3 tools/embed_pubkey.py            # check only (exit 1 if mismatched)
    python3 tools/embed_pubkey.py --fix      # rewrite license.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUB_PATH = Path(os.environ.get("CTXKIT_BILLING_KEYS", ROOT.parent / "billing" / "keys")) / "license_public.pem"
CLIENT = ROOT / "src" / "meshctx_ctxkit" / "license.py"


def main() -> int:
    fix = "--fix" in sys.argv
    if not PUB_PATH.exists():
        # In the public repo there is no billing service, hence no key to
        # check against. That is expected for contributors and CI — the
        # embedded placeholder is fine because no licence is being sold.
        print(f"SKIP no billing public key at {PUB_PATH}")
        print("     (expected in the public repo — nothing to cross-check)")
        return 0
    pub = PUB_PATH.read_text().strip()
    src = CLIENT.read_text()

    m = re.search(r'PUBLIC_KEY_PEM = os\.environ\.get\("CTXKIT_LICENSE_PUBKEY"\) or """(.*?)"""',
                  src, re.DOTALL)
    if not m:
        print(f"❌ could not find PUBLIC_KEY_PEM block in {CLIENT}")
        print("   the file format changed — update this script's regex")
        return 1
    embedded = m.group(1).strip()

    if embedded == pub:
        print("✅ client public key matches billing server key")
        return 0

    print("⚠️  KEY MISMATCH")
    print(f"   server   : {pub.splitlines()[1] if len(pub.splitlines()) > 1 else pub}")
    print(f"   embedded : {embedded.splitlines()[1] if len(embedded.splitlines()) > 1 else embedded}")
    print()
    print("   Licenses signed by the server would NOT verify in the client.")
    if not fix:
        print("   Run with --fix to update, then rebuild + republish.")
        return 1

    new_block = ('PUBLIC_KEY_PEM = os.environ.get("CTXKIT_LICENSE_PUBKEY") or """'
                 + pub + '"""')
    CLIENT.write_text(src[:m.start()] + new_block + src[m.end():])
    print(f"✅ embedded updated in {CLIENT}")
    print("   NEXT: rebuild the wheel and republish to PyPI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
