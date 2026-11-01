# meshctx-ctxkit — Pricing

> **Status: NOT READY FOR SALE.** Team tier is withdrawn (audit 4.3).
> Pro is deferred until the billing service passes the deployment checklist.
> See `../AUDIT_REMEDIATION.md` for what must be true before money changes hands.

## What is actually built

| Capability | Status |
|---|---|
| Local memory (`ctx_remember` / `ctx_recall` / `ctx_forget`) | ✅ shipped |
| Offline output verification (`ctx_verify_text`) | ✅ shipped |
| Multi-model consensus (`ctx_consensus`) | ✅ code works, **gated behind a licence** |
| Licence verification | ✅ shipped (`[license]` extra) |
| Stripe billing service | ⚠️ code complete, **not deployed, not audited for live** |
| Team seat management | ❌ **does not exist** |
| Managed API keys | ❌ **does not exist** |
| Support SLA | ❌ **not offered** |

## Tiers (current, honest)

| | **Free** | **Pro** |
|---|---|---|
| Price | $0 forever | **$9/mo** (proposed — see below) |
| `ctx_remember` / `ctx_recall` / `ctx_forget` | ✅ unlimited | ✅ |
| `ctx_verify_text` | ✅ unlimited | ✅ |
| `ctx_stats` / `ctx_license` | ✅ | ✅ |
| `ctx_consensus` | — | ✅ 300/mo, **bring your own API key** |
| Runtime dependencies | **zero** | `pyjwt[crypto]` + `httpx` |
| Support | community | best-effort email, no SLA |

### Why $9 and not $19

The audit is right about this: **Pro does not spend our money.**

- The user supplies `CTXKIT_API_KEY`; model calls happen locally.
- Our marginal cost per Pro user is **$0**.
- The usage counter is a local JSON file the user can delete.

So $19/mo was priced against a cost we do not bear, and against a control
we cannot enforce. That is not a business model, it is a paywall.

**$9/mo is priced as what it actually is:** an unlock fee for a paid tool,
plus the funding that keeps the free tier maintained. If we ever build a
hosted API (where we *do* pay for model calls), the pricing changes and so
does the work required to justify it.

## Withdrawn

| Item | Why |
|---|---|
| **Team $79/mo** | Promised managed keys + 5 seats + 24h support. None of it exists. Selling it would be misrepresentation. |
| **Managed API keys** | No key storage, rotation, revocation, or per-seat accounting. |
| **24h support SLA** | No on-call. Never promise an SLA you are not staffed for. |
| **Hosted API pricing narrative** | The product is BYOK. There is no hosted tier. |

## If we later build a hosted tier, it requires

1. Server-side key custody (secrets manager, not env vars in a repo)
2. Server-side metering and rate limiting (the local counter cannot be the
   basis for billing)
3. Per-request audit trail
4. Real unit economics measured, not estimated
5. Support staffing

That is a different product with a different cost structure. Not a price change.

## Refunds

Month-to-month. If the tool does not do what this document says it does,
it is refunded in full, no questions. See `COMMERCIAL_TERMS.md`.

## Development funding

The free tier exists because the paid tier is honest about what it sells.
If Pro never sells, the free tier still ships — it is AGPL and the source
is public. Money buys convenience, not access.
