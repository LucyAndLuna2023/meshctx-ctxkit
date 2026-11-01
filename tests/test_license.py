"""License + quota tests. Uses a real Ed25519 keypair so the crypto path
being shipped is the path being tested."""
import json
import time

import pytest

# Audit finding 3.2: paid-tier tests must FAIL when the paid dependencies are
# missing, not silently skip. A skipped license suite is how "74 tests green"
# coexisted with "paying customers get tier: free on a clean install".
try:
    import jwt  # noqa: F401
except ImportError as e:  # pragma: no cover
    pytest.fail(
        "PyJWT is required to test the paid licence tier and must not be "
        "skipped. Install it with: pip install 'meshctx-ctxkit[license]'. "
        f"Original error: {e}", pytrace=False)
try:
    import cryptography  # noqa: F401
except ImportError as e:  # pragma: no cover
    pytest.fail(
        "cryptography is required to test the paid licence tier and must not "
        "be skipped. Install it with: pip install 'meshctx-ctxkit[license]'. "
        f"Original error: {e}", pytrace=False)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from meshctx_ctxkit.license import (
    License, QUOTAS, sign_license, verify_license, load_license_from_env,
)
from meshctx_ctxkit.usage import UsageMeter
from meshctx_ctxkit.server import CtxKitServer
from meshctx_ctxkit.memory import MemoryStore


@pytest.fixture(scope="module")
def keys():
    priv = Ed25519PrivateKey.generate()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()).decode()
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return priv_pem, pub_pem


class TestSignVerify:
    def test_roundtrip_pro(self, keys):
        priv, pub = keys
        tok = sign_license(priv, tier="pro", email="a@b.co", days=30)
        lic = verify_license(tok, pub)
        assert lic.tier == "pro" and lic.active
        assert lic.email == "a@b.co"
        assert lic.consensus_quota == QUOTAS["pro"]["consensus_per_month"]

    def test_team_managed_keys(self, keys):
        priv, pub = keys
        tok = sign_license(priv, tier="team", email="t@co", days=30)
        lic = verify_license(tok, pub)
        assert lic.tier == "team" and lic.managed_keys is True and lic.seats == 5

    def test_no_token_is_free(self):
        lic = verify_license(None, "irrelevant")
        assert lic.tier == "free" and not lic.active and "no token" in lic.reason

    def test_placeholder_key_refused(self, keys):
        priv, _ = keys
        tok = sign_license(priv, tier="pro", email="x@y.z")
        lic = verify_license(tok, "-----BEGIN PUBLIC KEY-----\nPLACEHOLDER_REPLACE_ME\n-----END PUBLIC KEY-----")
        assert lic.tier == "free"
        assert "not configured" in lic.reason

    def test_wrong_pubkey_rejected(self, keys):
        priv, _ = keys
        other = Ed25519PrivateKey.generate().public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        lic = verify_license(sign_license(priv, tier="pro", email="x@y.z"), other)
        assert lic.tier == "free" and "invalid license" in lic.reason

    def test_expired_token_rejected(self, keys):
        priv, pub = keys
        tok = sign_license(priv, tier="pro", email="x@y.z", days=1)
        future = time.time() + 3 * 86400
        lic = verify_license(tok, pub, now=future)
        assert lic.tier == "free" and "expired" in lic.reason

    def test_tampered_token_rejected(self, keys):
        priv, pub = keys
        tok = sign_license(priv, tier="pro", email="x@y.z")
        head, payload, sig = tok.split(".")
        bad = f"{head}.{payload}.{'A' * len(sig)}"
        assert verify_license(bad, pub).tier == "free"

    def test_hs256_downgrade_rejected(self, keys):
        """alg-confusion attack: forge an HS256 token using the public key as
        the HMAC secret. Our verifier pins algorithms=["EdDSA"], so this must
        be rejected even though a naive lib would accept it."""
        import base64
        import hashlib
        import hmac
        _, pub = keys

        def b64(b: bytes) -> str:
            return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

        header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = b64(json.dumps({
            "tier": "team", "email": "attacker@evil.test",
            "exp": int(time.time()) + 9999}).encode())
        signing_input = f"{header}.{payload}".encode()
        sig = hmac.new(pub.encode(), signing_input, hashlib.sha256).digest()
        forged = f"{header}.{payload}.{b64(sig)}"
        lic = verify_license(forged, pub)
        assert lic.tier == "free", "HS256 forgery must not grant a tier"
        assert "invalid license" in lic.reason

    def test_alg_none_rejected(self, keys):
        _, pub = keys
        unsigned = jwt.encode({"tier": "team", "exp": int(time.time()) + 9999},
                              None, algorithm="none")
        assert verify_license(unsigned, pub).tier == "free"

    def test_unknown_tier_rejected(self, keys):
        priv, pub = keys
        tok = sign_license(priv, tier="free", email="x@y.z")
        # "free" is a valid tier name but not a sellable one; signed free token
        # must not grant consensus either way.
        lic = verify_license(tok, pub)
        assert lic.consensus_quota == 0

    def test_load_from_env(self, keys, monkeypatch):
        priv, _ = keys
        monkeypatch.setenv("CTXKIT_LICENSE", sign_license(priv, tier="pro", email="e@f.g"))
        lic = load_license_from_env()
        # without the real baked-in key, it must fail closed
        assert lic.tier == "free"


class TestUsageMeter:
    def test_counts_and_blocks_at_quota(self, tmp_path):
        m = UsageMeter(tmp_path)
        assert m.used() == 0
        for i in range(3):
            ok, used = m.check_and_consume(3)
            assert ok and used == i + 1
        ok, used = m.check_and_consume(3)
        assert not ok and used == 3

    def test_persists_across_instances(self, tmp_path):
        UsageMeter(tmp_path).check_and_consume(100)
        assert UsageMeter(tmp_path).used() == 1

    def test_quota_is_per_month(self, tmp_path):
        m = UsageMeter(tmp_path)
        m.check_and_consume(1, now=1_700_000_000)   # Nov 2023
        ok, _ = m.check_and_consume(1, now=1_700_000_000)
        assert not ok
        # a fresh month gets a fresh budget
        ok, used = m.check_and_consume(1, now=1_710_000_000)
        assert ok and used == 1


class TestGatedServer:
    def _srv(self, tmp_path, lic):
        return CtxKitServer(store=MemoryStore(root=tmp_path / "h"),
                            license_=lic, meter=UsageMeter(tmp_path / "h"))

    def _call(self, srv, name, args):
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": name, "arguments": args}})
        return json.loads(r["result"]["content"][0]["text"])

    def test_free_tier_consensus_denied(self, tmp_path):
        srv = self._srv(tmp_path, License(tier="free", reason="no token"))
        out = self._call(srv, "ctx_consensus", {"question": "x", "models": ["a", "b"]})
        assert out["ok"] is False
        assert "paid license" in out["error"]
        assert out["tier"] == "free"

    def test_free_tier_memory_still_works(self, tmp_path):
        srv = self._srv(tmp_path, License(tier="free"))
        out = self._call(srv, "ctx_remember", {"text": "free tier note"})
        assert out["ok"] is True
        out = self._call(srv, "ctx_recall", {"query": "free tier"})
        assert out["hits"]

    def test_pro_tier_consumes_quota(self, tmp_path):
        lic = License(tier="pro", email="p@q.r", exp=int(time.time()) + 999)
        srv = self._srv(tmp_path, lic)
        self._call(srv, "ctx_consensus", {"question": "q", "models": ["only-one"]})
        # only 1 model → consensus reports error, but the call was counted
        assert srv.meter.used() == 1

    def test_quota_exhausted_message(self, tmp_path):
        lic = License(tier="pro", email="p@q.r", exp=int(time.time()) + 999)
        srv = self._srv(tmp_path, lic)
        for _ in range(lic.consensus_quota):
            srv.meter.check_and_consume(lic.consensus_quota)
        out = self._call(srv, "ctx_consensus", {"question": "q", "models": ["a"]})
        assert out["ok"] is False and "quota" in out["error"]

    def test_license_tool_reports_tier(self, tmp_path):
        lic = License(tier="team", email="t@co", exp=int(time.time()) + 999)
        srv = self._srv(tmp_path, lic)
        out = self._call(srv, "ctx_license", {})
        assert out["tier"] == "team" and out["consensus_quota"] == 3000
        assert "ctx_verify_text" in out["free_tools"]

    def test_tools_list_has_seven_tools(self, tmp_path):
        srv = self._srv(tmp_path, License(tier="free"))
        r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert len(r["result"]["tools"]) == 7
