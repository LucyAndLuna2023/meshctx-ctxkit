#!/usr/bin/env bash
# publish.sh — one-shot release: test, build, verify, upload to PyPI.
#
# Usage:
#   ./publish.sh              # test + build + verify (no upload)
#   ./publish.sh --upload     # also upload to PyPI (needs ~/.pypirc or TWINE_*)
#
# Safe by default: without --upload nothing leaves this machine.
set -euo pipefail

cd "$(dirname "$0")"
UPLOAD=0
[[ "${1:-}" == "--upload" ]] && UPLOAD=1

PKG=meshctx-ctxkit
echo "==> 0/5 checking license keypair sync"
python3 tools/embed_pubkey.py || {
  echo
  echo "FAIL: the client's embedded public key does not match the billing"
  echo "      server's private key. Any license we sell would fail to verify."
  echo "      Fix: python3 tools/embed_pubkey.py --fix"
  exit 1
}

echo "==> 1/5 running test suite"
export PYTHONPATH=src
export CTXKIT_HOME="$(mktemp -d)"
python3 -m pytest tests/ -q

echo "==> 2/5 building wheel + sdist"
rm -rf dist build src/*.egg-info
python3 -m pip wheel . -w dist --no-deps -q
python3 setup_sdist.py 2>/dev/null || python3 -m build --sdist -o dist 2>/dev/null || \
  echo "    (sdist skipped — wheel is enough for our use)"

echo "==> 3/5 verifying clean install in isolation"
TGT="$(mktemp -d)"
python3 -m pip install --target "$TGT" --no-deps -q dist/*.whl
CTXKIT_HOME="$TGT/home" PYTHONPATH="$TGT" python3 -m meshctx_ctxkit add "install probe" >/dev/null
CTXKIT_HOME="$TGT/home" PYTHONPATH="$TGT" python3 -m meshctx_ctxkit search "probe" | grep -q "install probe"
echo "    clean install OK"

echo "==> 4/5 verifying MCP handshake"
PYTHONPATH=src CTXKIT_HOME="$TGT/h2" python3 - "$TGT" <<'PY'
import json, os, subprocess, sys
tgt = sys.argv[1]
env = dict(os.environ, PYTHONPATH=tgt, CTXKIT_HOME=os.path.join(tgt, "h2"))
p = subprocess.Popen([sys.executable, "-m", "meshctx_ctxkit", "serve"],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL, env=env, text=True)
p.stdin.write(json.dumps({"jsonrpc":"2.0","id":1,"method":"initialize",
                          "params":{"protocolVersion":"2024-11-05"}})+"\n")
p.stdin.flush()
r = json.loads(p.stdout.readline())
assert r["result"]["serverInfo"]["name"] == "ctxkit", r
p.stdin.close(); p.wait(timeout=10)
print("    MCP handshake OK:", r["result"]["serverInfo"])
PY

echo "==> 4b/5 clean-environment matrix (free / license / collision)"
python3 tools/clean_env_check.py || {
  echo "FAIL: clean-environment install does not behave as documented."
  exit 1
}

echo "==> 5/5 release artifact"
ls -lh dist/

if [[ $UPLOAD -eq 1 ]]; then
  # Delegates to tools/publish_pypi.sh, which reads the token from an env var
  # only — never from argv, never from a file. A token on the command line
  # shows up in `ps` and in shell history; that is how the parent project's
  # credentials ended up in a public git log.
  ./tools/publish_pypi.sh
else
  echo
  echo "Dry run complete. To publish:"
  echo "  ./publish.sh --upload"
  echo
  echo "First time only — create a PyPI API token at https://pypi.org/manage/account/token/"
  echo "and export:  TWINE_USERNAME=__token__  TWINE_PASSWORD=pypi-AgEI..."
fi
