# Contributing

Thanks for looking. This is a small, opinionated project — the constraints
below are deliberate, not arbitrary, and PRs that violate them will be
declined with an explanation rather than a merge.

## The three constraints

### 1. The free tier ships **zero** runtime dependencies

`pip install meshctx-ctxkit` must pull nothing. No vector DB, no embedding
model, no SDK, no `mcp` package. Pure standard library.

This is the whole product thesis: it has to work on a locked-down laptop, a
plane, and a corporate proxy that blocks PyPI. If your change needs a
dependency, it goes in an extra that the user opts into, and the free path
must keep working without it.

**Check before you open a PR:**

```bash
python -m pip install --target /tmp/t --no-deps dist/*.whl
PYTHONPATH=/tmp/t PYTHONNOUSERSITE=1 python -S -c "import meshctx_ctxkit"
```

`python -S` is not optional. Without it your system `site-packages` quietly
satisfies the import and you will not notice you added a dependency. This is
exactly how a previous "74 tests green" release shipped a paid tier that did
not activate on a clean install.

### 2. Claims must match code

If the README, a docstring, or a tool description says something happens,
there must be a test whose failure message is that sentence.

Things this project has already had to walk back, and will not repeat:

- claiming hallucination detection when we only detect *suspicion*
- advertising a Team tier whose seat management did not exist
- stating "zero API spend" while shipping a feature that spends API budget

**Write the limitation next to the claim.** Every bold claim in this repo is
followed by what it does not cover. That is not hedging; it is the reason
anyone can trust the parts that are true.

### 3. Never commit a credential

See `SECURITY.md`. The parent project leaked a Redis password and a GitHub
token through git history. `.gitignore` blocks the obvious vectors; do not
work around it.

## Good first contributions

- **CJK tokenisation** — currently per-character. A proper segmenter behind an
  *optional* extra, with the zero-dependency path unchanged, would be welcome.
- **More offline checks** — unit/currency consistency, self-contradiction
  detection. Each needs a test with a real model-output example.
- **Client config snippets** for MCP clients not yet documented.
- **Bug reports with a failing test.** A test that reproduces the bug is worth
  more than a description of it.

## What will be declined

- Adding a dependency to the free path.
- Vector embeddings in the default install (offer it as an extra if you must).
- Telemetry, analytics, or phone-home of any kind.
- Features that require a hosted service to work.
- Marketing copy that overclaims.
- "Just add an LLM call here" — this thing is deliberately offline.

## Workflow

```bash
git clone https://github.com/LucyAndLuna2023/meshctx-ctxkit
cd meshctx-ctxkit
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# tests
PYTHONPATH=src python -m pytest tests/ -q

# what CI additionally checks (run it locally before pushing)
./publish.sh          # dry run: tests + build + clean-install matrix
```

`./publish.sh` without `--upload` touches nothing outside your machine.

## Commit messages

Conventional-ish, one line, imperative, and say *why* when it is not obvious:

```
fix(memory): index every idempotency key, not just the primary

Two different Stripe events about the same checkout session each minted a
licence because _load() keyed records by their primary key only.
```

## Code style

- Type hints on public functions.
- Docstrings explain *why*, not *what*. The `what` is the code.
- Comments where a reader would otherwise assume the wrong thing.
- No bare `except:`; catch the exception you mean and fail loudly otherwise.
- Fail closed on anything security-adjacent.

## Licence

Contributions are accepted under AGPL-3.0-or-later. By opening a PR you
confirm you have the right to license your contribution that way.
