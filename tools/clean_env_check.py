#!/usr/bin/env python3
"""clean_env_check.py — verify the *real* install experience per extras tier.

Audit finding 3.2: "74 tests green" coexisted with "a paying customer on a
clean install gets tier: free". The cause: the test suite ran against a
system Python that already had PyJWT, so the missing dependency was
invisible.

This script installs the built wheel into throwaway target dirs and then
runs the CLI with ``python -S`` (no site-packages), asserting that:

    free tier   : works with ZERO dependencies
    license tier: verifies a licence when pyjwt[crypto] is present
    license tier: fails LOUDLY and actionably when it is absent

Exit code 1 on any violation — suitable for CI.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WHEEL_DIR = ROOT / "dist"
SRC = ROOT / "src"

GREEN, RED, YELLOW, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
failures: list[str] = []


def log(ok: bool, msg: str) -> None:
    print(f"{GREEN if ok else RED}{'PASS' if ok else 'FAIL'}{RESET} {msg}")
    if not ok:
        failures.append(msg)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def isolated_python(target: Path, code: str, env_extra: dict[str, str] | None = None):
    """Run python -S with ONLY `target` on sys.path (no system site-packages)."""
    env = {**os.environ, "PYTHONPATH": str(target), "PYTHONNOUSERSITE": "1"}
    if env_extra:
        env.update(env_extra)
    return run([sys.executable, "-S", "-c", code], env=env)


def main() -> int:
    wheels = sorted(WHEEL_DIR.glob("*.whl"))
    if not wheels:
        print(f"{RED}no wheel in {WHEEL_DIR} — run ./publish.sh first{RESET}")
        return 1
    wheel = wheels[-1]
    print(f"testing wheel: {wheel.name}\n")

    # ── tier 1: free, zero dependencies ────────────────────────────────
    t_free = Path(tempfile.mkdtemp(prefix="ctxfree-"))
    home_free = Path(tempfile.mkdtemp(prefix="ctxhome-"))
    r = run([sys.executable, "-m", "pip", "install", "--target", str(t_free),
             "--no-deps", "-q", str(wheel)])
    log(r.returncode == 0, "free tier: wheel installs with --no-deps")

    r = isolated_python(t_free, """
from meshctx_ctxkit.memory import MemoryStore
from meshctx_ctxkit.consensus import run_offline_checks
import tempfile
s = MemoryStore(root=tempfile.mkdtemp())
s.remember("clean env memory probe")
assert s.recall("probe"), "recall failed"
assert run_offline_checks("2 * 3 = 7")["verdict"] == "suspicious"
print("OK")
""")
    log(r.returncode == 0 and "OK" in r.stdout,
        "free tier: memory + verify work with zero dependencies"
        + ("" if r.returncode == 0 else f"  [{r.stderr.strip()[:200]}]"))

    # ── tier 2: licence WITHOUT pyjwt → must fail loudly ───────────────
    r = isolated_python(t_free, """
from meshctx_ctxkit.license import verify_license
lic = verify_license("some.token.here")
print(lic.tier)
print(lic.reason)
""", {"CTXKIT_HOME": str(home_free)})
    got_actionable = ("meshctx-ctxkit[license]" in r.stdout)
    log(got_actionable,
        "license tier: missing PyJWT reports the correct install command"
        + ("" if got_actionable else f"  [stdout={r.stdout.strip()[:160]}]"))

    # ── tier 3: licence WITH pyjwt[crypto] → must activate ─────────────
    t_paid = Path(tempfile.mkdtemp(prefix="ctxpaid-"))
    r = run([sys.executable, "-m", "pip", "install", "--target", str(t_paid),
             "-q", "--no-deps", str(wheel)])
    log(r.returncode == 0, "license tier: wheel installs")
    r = run([sys.executable, "-m", "pip", "install", "--target", str(t_paid),
             "-q", "pyjwt[crypto]"])
    log(r.returncode == 0, "license tier: pyjwt[crypto] installs")

    # sign a real token with the billing key, if present
    priv_path = Path(os.environ.get("CTXKIT_BILLING_KEYS", ROOT.parent / "billing" / "keys")) / "license_private.pem"
    if not priv_path.exists():
        print(f"{YELLOW}SKIP{RESET} license activation: no billing keypair to sign with")
        print("      (run billing/billing.py once to generate)")
    else:
        r = run([sys.executable, "-c", f"""
import sys; sys.path.insert(0, {str(SRC)!r})
from pathlib import Path
from meshctx_ctxkit.license import sign_license
print(sign_license(Path({str(priv_path)!r}).read_text(),
                   tier="pro", email="clean@ci", days=31))
"""])
        token = r.stdout.strip()
        if not token:
            log(False, f"could not sign token: {r.stderr[:200]}")
        else:
            home_paid = Path(tempfile.mkdtemp(prefix="ctxpaidhome-"))
            (home_paid / "license.key").write_text(token)
            r = isolated_python(t_paid, """
from meshctx_ctxkit.license import load_license_from_env
lic = load_license_from_env()
print(lic.tier)
print(lic.active)
""", {"CTXKIT_HOME": str(home_paid)})
            lines = r.stdout.strip().splitlines()
            ok = len(lines) >= 2 and lines[0] == "pro" and lines[1] == "True"
            log(ok, "license tier: a real paid licence activates on a clean install"
                + ("" if ok else f"  [out={r.stdout.strip()[:160]} err={r.stderr.strip()[:160]}]"))

    # ── tier 4: no collision with the unrelated `ctxkit` package ───────
    r = isolated_python(t_free, "import meshctx_ctxkit; print(meshctx_ctxkit.__version__)")
    log(r.returncode == 0, "package: import name `meshctx_ctxkit` is unique")
    r = isolated_python(t_free, """
import importlib.util as u
assert u.find_spec("ctxkit") is None, "we must not ship a top-level ctxkit module"
print("OK")
""")
    log(r.returncode == 0 and "OK" in r.stdout,
        "package: does not shadow the unrelated PyPI `ctxkit` package")

    # ── tier 5: console script exists and is uniquely named ────────────
    scripts = list(t_free.glob("bin/meshctx-ctxkit")) + list(t_free.glob("Scripts/meshctx-ctxkit*"))
    log(bool(scripts), "package: console script `meshctx-ctxkit` is installed")
    clashing = list(t_free.glob("bin/ctxkit")) + list(t_free.glob("Scripts/ctxkit*"))
    log(not clashing, "package: no `ctxkit` script that would collide on install")

    for d in (t_free, t_paid, home_free):
        shutil.rmtree(d, ignore_errors=True)
    for p in ROOT.glob("ctxpaidhome-*"):
        shutil.rmtree(p, ignore_errors=True)

    print()
    if failures:
        print(f"{RED}{len(failures)} check(s) failed:{RESET}")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{GREEN}all clean-environment checks passed{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
