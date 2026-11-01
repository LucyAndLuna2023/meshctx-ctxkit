# Security Policy

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Email the maintainer (see the GitHub profile for a current address) with:

- what you found and where
- the impact you believe it has
- reproduction steps, if you have them

You will get an acknowledgement within a few days. This is a small project
run by one person — there is no bug bounty and no 24/7 response, and claiming
otherwise would be dishonest.

## Supported versions

Only the latest release receives fixes. This project is pre-1.0 and the API
may change.

## Design decisions that affect your threat model

Read these before assuming what this software does or does not protect.

### Local-first by design

Memories live in `~/.ctxkit/memory.jsonl` on your disk. Prompts and verification
input never leave your machine unless *you* configure a model provider for
`ctx_consensus`, in which case they go to that provider with *your* key.

There is no telemetry and no phone-home.

### Licences verify offline

Licence tokens are Ed25519-signed JWTs. The public key ships in the package;
the private key never leaves the billing server. This means:

- ✅ A paying customer works offline, forever, even if we vanish.
- ⚠️ **A licensed client cannot be remotely revoked.** A leaked licence stays
  valid until it expires. That is the deliberate trade: no phone-home.
- ⚠️ If the private key is compromised, an attacker can mint valid licences.
  Detection is the only remedy; see key handling below.

### Key handling

The server refuses to start rather than risk destroying the signing key:

| State | Behaviour |
|---|---|
| private present, public missing | derive public from private |
| private unparseable | **refuse to start**, preserve the file |
| private / public mismatched | **refuse to start** |
| public without private | **refuse to start** |

Regenerating the private key invalidates every licence ever issued, so it is
never done automatically. Back it up.

### Attack surface we test against

`tests/test_license.py` asserts these are rejected:

- `alg: none`
- `HS256` forged with the public key as the HMAC secret (algorithm confusion)
- tampered signature
- expired token
- token signed by a different key
- unknown tier

### Webhook handling

- Signature verified with `hmac.compare_digest` (constant time) and a
  ±300 s timestamp window (replay resistance).
- Idempotent on both event ID and business object (session / invoice /
  subscription). Stripe retries at-least-once; one payment must mint exactly
  one licence.
- Order logs store a SHA-256 of the email and of the licence token, plus the
  token's last six characters — never the raw token — with `0600` permissions.

### The usage counter is not a security control

`usage.json` is a local file the user can delete. It stops runaway API spend.
It does not and cannot enforce billing. Do not build anything that depends on
it being tamper-proof.

## What this software does NOT protect against

Stated plainly so nobody relies on it for the wrong thing:

- **It does not make model output correct.** `ctx_verify_text` catches bad
  arithmetic, impossible dates and unqualified absolutes. It cannot catch a
  confidently wrong claim that is internally consistent.
- **It does not detect prompt injection.** Memories are text; if you store
  hostile text it will be retrieved like any other text.
- **It does not encrypt the memory file at rest.** It is plain JSONL. Use
  full-disk encryption if your notes are sensitive.
- **It does not sandbox tools.** It is a memory store and a text verifier.
