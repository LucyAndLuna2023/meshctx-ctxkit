# ctxkit

**Local-first memory + verification for AI agents.**
Runs fully offline. Zero login. Zero API spend. Zero dependencies.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)
[![MCP](https://img.shields.io/badge/MCP-compatible-purple)](https://modelcontextprotocol.io)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0%20%2B%20Commercial-orange)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-60%20passed-brightgreen)]()

---

## The two problems every agent user hits

**1. Your agent forgets everything.**
You tell Claude or Cursor something on Monday. On Tuesday it has no idea. The
usual fix is a cloud memory service — which means shipping your project notes,
client names, and internal decisions to someone else's server, behind a login,
for a monthly fee.

**2. Your agent lies with total confidence.**
A single model will state `3 × 7 = 25`, invent a URL, and tell you a deadline is
"100% guaranteed." It never hesitates. You find out later.

`ctxkit` fixes both — **on your own machine, with no network at all.**

---

## What you get

### 🧠 `ctx_remember` / `ctx_recall` — memory that survives restarts

Append-only JSONL on local disk, indexed with BM25 for instant retrieval.
No embeddings, no vector database, no model download, no GPU, no account.

- Works in a clean venv with **zero pip dependencies**
- Handles Chinese/Japanese/Korean text (per-character tokenisation)
- Crash-safe: a torn write never corrupts the store
- You can `cat ~/.ctxkit/memory.jsonl` and read your own memory — it's just text
- Deleting is real deleting: `ctx_forget` tombstones and compacts

### 🔍 `ctx_verify_text` — catch bad output before it ships

Free, offline, pure stdlib. Recomputes everything a model asserted:

| Check | Catches |
|---|---|
| `arithmetic` | `250 * 4 = 900` → reports computed `1000` |
| `percent` | `20% of 150 is 45` → reports computed `30` |
| `date` | "February 30, 2025", years >2 ahead |
| `absolute_claims` | `100% guaranteed`, `never`, `risk-free`, `all users` |
| `url_format` | malformed or suspicious links |

Verdict is `clean` or `suspicious`, with every failure itemised.

### 🔑 `ctx_license` — tier, expiry and usage

Shows what you're on, when it expires, and how many consensus calls you've
used this month. Everything verifies **offline** — paying customers are never
locked out because a licence server is down.

### 🎯 `ctx_consensus` — multi-model cross-check *(paid tier)*

Ask the same question to several models, extract each one's key claims, and
score their agreement. Disagreements are listed per model, so you see *exactly*
where the models disagree instead of a vague "the AI might be wrong."

**This measures agreement, not correctness.** Three models can agree and all
be wrong. It narrows where to look; it does not establish truth.

Requires `CTXKIT_API_KEY` + `CTXKIT_API_BASE`. Nowhere near as scary as it
sounds — it's an OpenAI-compatible endpoint and works with any provider.

## Tiers

| | **Free** | **Pro $9/mo** |
|---|---|---|
| `ctx_remember` / `ctx_recall` / `ctx_forget` | ✅ unlimited | ✅ |
| `ctx_verify_text` | ✅ unlimited | ✅ |
| `ctx_stats` / `ctx_license` | ✅ | ✅ |
| `ctx_consensus` | — | 300/mo |
| Bring your own model API key | — | ✅ |
| Runtime dependencies | **zero** | `pyjwt[crypto]`, `httpx` |
| Support | community | best-effort, no SLA |

**Not yet on sale.** The paid tier exists in code but billing is not deployed
and has not passed its deployment checklist. See `../AUDIT_REMEDIATION.md`.

**Memory and verification are free forever and unlimited.** They cost nothing
to run — no server, no model calls — so charging for them would be charging
for nothing. The paid tier is the only part that spends real money on model
API calls, which is exactly what it's priced against.

---

## Install

```bash
pip install meshctx-ctxkit
```

That's it. **No extras needed for memory and verification** — zero dependencies.

Only if you want the paid `ctx_consensus` feature:

```bash
pip install 'meshctx-ctxkit[license]'   # licence verification
pip install 'meshctx-ctxkit[api]'       # consensus (also pulls httpx)
```

Verify it works:

```bash
meshctx-ctxkit add "Stripe key rotated 3 May; old key revoked" --tag ops
meshctx-ctxkit search "stripe"
meshctx-ctxkit verify "Cost is 250 * 4 = 900 hours and it is 100% guaranteed"
```

---

## Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "ctxkit": {
      "command": "meshctx-ctxkit",
      "args": ["serve"]
    }
  }
}
```

Restart Claude Desktop. You'll see seven tools appear.

## Add to Cursor / Cline / Windsurf / Zed

Same idea — point the MCP server config at:

```
command: ctxkit
args: ["serve"]
```

Any MCP-capable client works. The server speaks protocol `2024-11-05` over stdio.

---

## Try it in 60 seconds

```
You:    Remember that this client's invoice must go to billing@acme.example,
        never to the sales rep.

Claude: [calls ctx_remember] ✓ stored locally

--- restart Claude Desktop, new conversation ---

You:    Where does the Acme invoice go?

Claude: [calls ctx_recall "acme invoice"]
        → "invoice must go to billing@acme.example, never to the sales rep"
        It goes to billing@acme.example — not the sales rep.
```

No cloud. No login. No subscription. It just remembered.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CTXKIT_HOME` | `~/.ctxkit` | Where `memory.jsonl` lives |
| `CTXKIT_API_KEY` | *(unset)* | Enables `ctx_consensus` |
| `CTXKIT_API_BASE` | *(unset)* | OpenAI-compatible base URL |
| `CTXKIT_MODELS` | 3 defaults | Comma-separated model list for consensus |
| `CTXKIT_LICENSE` | `~/.ctxkit/license.key` | Pro/Team licence token |

---

## CLI reference

```
meshctx-ctxkit add "text" [--tag t1 --tag t2]   store a memory
meshctx-ctxkit search "query" [--limit 5]        retrieve
meshctx-ctxkit stats                             count, tags, disk path
meshctx-ctxkit verify "text"                     offline sanity checks
meshctx-ctxkit license [--key TOKEN]             show tier, expiry, usage
meshctx-ctxkit serve                             run the MCP server

Short alias: `mctxkit` is identical.
```

---

## How it compares

| | Cloud memory services | Vector-DB memory libs | **ctxkit** |
|---|---|---|---|
| Data stays on your disk | ❌ | ✅ | ✅ |
| Works with no network | ❌ | depends | ✅ |
| Needs an account/login | ❌ usually yes | ❌ | ✅ **no** |
| pip dependencies | SDK required | heavy | **0** |
| Human-readable storage | ❌ | ❌ | ✅ JSONL |
| Built-in output verification | ❌ | ❌ | ✅ |
| Monthly cost | $10–30 | free | **free forever** |

---

## Development

```bash
git clone https://github.com/LucyAndLuna2023/meshctx
cd meshctx
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -q
```

60 tests: memory semantics, BM25 ranking, crash recovery, every verifier,
consensus scoring, the full MCP protocol surface, and a real subprocess
end-to-end session.

---

## License

AGPL-3.0-or-later for open-source use. Commercial/enterprise licensing
available — see `LICENSE`.

The commercial tiers are what fund the free one. Pricing, and a plain-English
explanation of exactly what you get and don't, is in `PRICING.md`.

---

## Honest limitations

- Retrieval is **lexical (BM25)**, not semantic. "car" won't find "automobile."
  This is the deliberate price of needing zero dependencies and zero downloads.
- `ctx_verify_text` **flags suspicion, it does not prove truth.** Clean output
  can still be wrong; it just contains no machine-checkable arithmetic, date,
  or absolute-claim errors.
- `ctx_consensus` measures **agreement, not correctness.** Three models can agree
  and all be wrong — especially on niche or recent facts. It's a smoke detector,
  not a fireproof wall.
- Memory is local by design. There is no sync between machines. That's the point.
