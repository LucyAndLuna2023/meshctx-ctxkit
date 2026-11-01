# Commercial Terms — meshctx-ctxkit Pro

> **Effective upon first sale. Not yet in effect: no paid tier is on sale.**
> This document exists so that when money *does* change hands, both sides
> know exactly what was bought. Written plainly on purpose — a licence you
> cannot read is not a licence, it is a trap.

---

## 1. What you are buying

A **commercial licence to use the software without the AGPL's copyleft
obligations.** That is the entire product.

Specifically, Pro grants:

- The right to use `meshctx-ctxkit` inside proprietary/closed-source works
  without releasing your source under AGPL-3.0.
- Access to the `ctx_consensus` tool, capped at 300 calls per calendar month.
- Best-effort email support (see §4 — **there is no SLA**).

## 2. What you are NOT buying

Stated explicitly, because vague promises are how people get hurt:

| Not included | Reality |
|---|---|
| Hosted API | There is none. You supply your own model API key. |
| Model API costs | Yours. We never bill for model inference. |
| Managed API keys | Not implemented. |
| Team seats | Not implemented. One licence = one developer. |
| Uptime guarantee | None. |
| Support SLA / response time | None. Best effort only. |
| Any promise of correctness | See §5. This software flags suspicion; it does not prove truth. |

## 3. Price, billing, refunds

- **Price:** $9 USD per month, per developer.
- **Billing:** monthly, via Stripe. Cancel anytime; access continues to the
  end of the paid period.
- **Refunds:** if the software does not do what this document and the README
  say it does, tell us within 30 days and it is refunded in full, no
  questions, no exit interview.
- **Price changes:** existing subscribers are grandfathered for 12 months.
  We will not raise your price and hope you do not notice.

## 4. Support

Email, best effort, **no response-time commitment.** If something is broken
in a way that makes the product unusable for you, it gets fixed or you get
a refund under §3. We will not pretend to staff an on-call rotation that
does not exist.

## 5. No warranty of correctness

This is the most important paragraph in this document.

`ctx_verify_text` and `ctx_consensus` are **heuristics**. They:

- flag arithmetic and date errors they can parse
- measure agreement between models

They do **not**:

- prove any statement true or false
- catch every error
- replace review by a human

**Do not rely on this software for medical, legal, financial, safety-critical,
or otherwise consequential decisions.** Output marked `clean` can still be
wrong. If you need a guarantee of correctness, you need a different product.

## 6. Privacy and data handling

The free and Pro tiers are **local-first by design**:

| Data | Where it lives | Do we see it? |
|---|---|---|
| Your memories (`memory.jsonl`) | Your disk | **No** |
| Verification inputs | Never leaves your machine | **No** |
| Multi-model consensus prompts | Sent to the model provider **you** configured, with **your** key | **No** |
| Licence verification | Local signature check | **No** |
| Licence purchase (email, payment) | Stripe + our minimal order log | **Yes, see below** |

### What the billing service stores

When you subscribe, we store:

- your email **address hash** and domain only (sufficient for support, not
  for sending you marketing)
- the licence token's SHA-256 hash and last six characters
- purchase timestamp, tier, plan ID
- the licence token itself is emailed to you and **is not retained in the
  order log**

We never receive your model API keys, your memories, or your prompts.

### Deletion

Email us and the order record is deleted. The licence stops verifying at
expiry. Nothing to purge from a service we do not run on your data.

### Third parties

- **Stripe** processes payment. Their privacy policy governs card data. We
  never see your card number.
- Any model provider you configure is between you and them.

## 7. AGPL and this licence together

`meshctx-ctxkit` is AGPL-3.0-or-later **or** these commercial terms, at your
option. The full AGPL text ships in `LICENSE`.

If you comply with AGPL-3.0, you do not need this licence. This exists for
people who cannot or will not publish their source. Choosing it does not
change anything about the software you already have.

## 8. Trademarks

"MeshCtx" and "meshctx-ctxkit" are the project's names. Do not use them to
endorse or promote derived products without written permission. Forking and
redistributing under AGPL is fine; implying your fork is official is not.

## 9. Limitation of liability

To the maximum extent permitted by law, total liability is limited to the
amount you paid us in the 12 months before the claim. The software is
provided **"as is"**, without warranty of any kind, express or implied,
including merchantability, fitness for a particular purpose, and
non-infringement.

## 10. Changes to these terms

Material changes are emailed to active subscribers at least 30 days before
taking effect. You may cancel before then and receive a pro-rata refund.
Terms are versioned in the public repository; no silent edits.

---

*Last updated: 2026-11-02. Version 0.1-draft. **Not in force** — no paid tier
is currently offered. This draft exists so the terms can be reviewed before
money is accepted, not after.*
