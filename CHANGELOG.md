# Changelog

All notable changes to this project. Format based on
[Keep a Changelog](https://keepachangelog.com/); versioning follows
[SemVer](https://semver.org/).

---

## [Unreleased]

### Not yet done — blocks any paid launch

- **Billing service is not deployed.** Code exists in a separate private repo.
  No public sale, no pricing page, no Stripe live verification.
- **No public source tag or sdist for a paid tier yet.** A paid tier requires
  source availability matching the published wheel.
- **Stripe test-clock coverage** for renewal / cancel / failure / recovery is
  not written. Until it is, `invoice.paid` handling is unverified against
  Stripe's live schema (see `AUDIT_REMEDIATION.md` §3.4).
- **Deployment hardening** (systemd, TLS termination, monitoring, backups)
  is not provided.

### Security — read this before anything else

An external audit found that the *parent* project (`meshctx`) leaked
credentials through its git history:

- a Redis password was hardcoded in `cluster/hub_client.py` and
  `cluster/cluster_comm_v6.py` in older commits
- a GitHub token was embedded in the git remote URL

**Neither affected this repository**, but both are the reason this repo ships
a strict `.gitignore` and no credentials of any kind. If you fork the parent
project, rotate those credentials — do not assume a history rewrite is enough.

---

## [0.1.0] — 2026-11-02

First release. Pre-launch: free tools are usable, the paid tier is code-complete
but not for sale.

### Added

**Memory**
- `ctx_remember` / `ctx_recall` / `ctx_forget` / `ctx_stats` — local,
  append-only JSONL store with fsync, a BM25 index, and CJK per-character
  tokenisation. Zero runtime dependencies; pure stdlib.
- Crash safety: a torn trailing line never breaks startup (tested).
- Compaction when deletions dominate the log.
- Human-readable storage — `cat ~/.ctxkit/memory.jsonl` is the whole story.

**Verification (offline, free)**
- `ctx_verify_text` recomputes stated arithmetic, checks percentages,
  validates dates (including impossible ones like "February 30"), flags
  unqualified absolutes, and sanity-checks URL shape. Pure stdlib.
- Explicitly *not* a correctness prover. It flags suspicion; it does not
  establish truth. Documented in README and in the tool description.

**Consensus (paid tier)**
- `ctx_consensus` asks several models the same question and scores agreement
  of extracted claims. Requires `pyjwt[crypto]` and `httpx`, plus a licence.
- Honest limitation, stated everywhere it is sold: agreement is not
  correctness.

**Licensing**
- `ctx_license` shows tier, expiry and monthly usage.
- Ed25519 (JWT `EdDSA`) licences verify **offline** — a paying customer is
  never locked out because a licence server is down.
- `algorithms=["EdDSA"]` is pinned, defeating `alg:none` and the
  public-key-as-HMAC-secret confusion attack. Tampering, expiry and key
  mismatch are all tested to fail closed.
- Use the `[license]` extra. Without it, licence verification fails loudly
  with an actionable message rather than silently downgrading.

**Packaging**
- Distribution `meshctx-ctxkit`; import package `meshctx_ctxkit`; console
  scripts `meshctx-ctxkit` and `mctxkit`.
  These names are deliberately unique: the unrelated PyPI package `ctxkit`
  also ships a top-level `ctxkit/` module and a `ctxkit` command, so the two
  cannot coexist in one environment. This package does not shadow it, and CI
  asserts that.
- Extras: none (free, zero deps) / `[license]` / `[api]` / `[all]` / `[dev]`.
- MCP protocol `2024-11-05` over stdio, implemented without the `mcp` SDK so
  that `pip install` genuinely pulls nothing.

### Testing

- 60 unit and protocol tests, including a real subprocess end-to-end session
  and validation against the official MCP Python SDK client.
- CI runs the suite on Linux, macOS and Windows across Python 3.10 and 3.12.
- A dedicated clean-install job proves, on every push, that (a) the free tier
  works with zero dependencies, (b) a missing `pyjwt` fails with the right
  install hint, (c) a real paid licence activates on a clean install, and
  (d) nothing collides with the `ctxkit` package.

### Fixed during audit

Bugs found by an external audit of the pre-release build, all now regression-tested:

- BM25 ranked a long document above a short one for a whole-phrase query.
- The word-form arithmetic regex never matched (bad f-string build).
- `server.main` lost EOF when reading stdin via iteration, hanging the
  process after the client closed the pipe.
- The licence error message named the wrong extra (`[api]` instead of
  `[license]`).
- `ensure_keys()` regenerated the keypair when only the public key was
  missing, silently invalidating every licence ever sold. Now derives the
  public key from the private one, and fails closed on corruption or mismatch.
- Webhook deduplication indexed only the primary key, so two different
  events about the same checkout session both issued a licence.
- The order log stored the customer email and the full licence token in
  plaintext. Now stores only hashes plus the token's last six characters,
  with `0600` permissions.

### Known limitations

- Retrieval is lexical (BM25). "car" will not find "automobile." This is the
  deliberate cost of zero dependencies and zero downloads.
- `ctx_consensus` measures model agreement, not truth. Three models can agree
  and all be wrong.
- The usage counter is a local JSON file and can be deleted. It exists to
  prevent runaway API bills, not to enforce billing.
- Single-node idempotency store; not suitable behind multiple app servers.
