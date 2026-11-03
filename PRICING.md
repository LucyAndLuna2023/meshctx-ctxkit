# meshctx-ctxkit — Pricing

> **Everything is free.** Since 2026-11-03, no feature is behind a paywall.

## Why it is free

`ctx_consensus` spends **the user's** API budget — you supply `CTXKIT_API_KEY`,
and the calls happen on your machine. Our marginal cost per user is **$0**.

Charging for it would have meant selling a local JSON counter that any user
could delete. That is not a subscription; it is a toll booth on a road we did
not build.

So: free. All of it.

## What you get

| Tool | What it does | Cost |
|---|---|---|
| `ctx_remember` | Store a durable local memory | free |
| `ctx_recall` | BM25 retrieval (CJK-aware, offline) | free |
| `ctx_forget` | Delete a memory | free |
| `ctx_stats` | Store statistics | free |
| `ctx_verify_text` | Offline arithmetic / date / absolute-claim checks | free |
| `ctx_consensus` | Multi-model agreement scoring | free (you pay your model provider) |
| `ctx_license` | Show usage and limits | free |

## The one limit, and why it exists

`ctx_consensus` counts calls locally and stops at **2,000/month by default**.

This is **not a paywall**. It is an abuse guard: a runaway loop should not
silently burn through someone's API budget overnight. It is:

- local only (no server, no phone-home, no account)
- resettable by you
- removable: set `CTXKIT_CONSENSUS_FREE_QUOTA=0` to disable it entirely

If you hit it, the error message tells you exactly how to raise it.

## If we ever charge for something

It will be for something we actually pay for:

- hosted consensus (we supply the model keys)
- server-side team memory sharing
- compliance/audit reports delivered as documents

Each of those costs us real money per use, which is what makes a price
defensible. A local feature that costs us nothing will stay free.

## Licence

AGPL-3.0-or-later. Commercial licensing is available for closed-source use —
see `COMMERCIAL_TERMS.md`. That is about **legal usage rights**, not feature
access. You never need to pay to unlock a capability.
