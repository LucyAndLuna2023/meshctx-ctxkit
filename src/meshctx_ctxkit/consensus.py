"""Verification & multi-model consensus for ctxkit.

Two layers:

``run_offline_checks(text)``
    Pure-stdlib sanity checks that catch the most common LLM failure
    modes without any network: broken arithmetic, impossible dates,
    unreachable-looking URLs, and unqualified absolute claims.

``multi_model_consensus(question, ...)``
    Ask the same question to N OpenAI-compatible endpoints, extract
    each model's key claims, and score cross-model agreement. This is
    the paid/hosted path (``ctxkit[api]`` + ``CTXKIT_API_KEY``); it is
    optional and the server never requires it.

The offline layer is the free product core; the consensus layer is the
commercial add-on. Both are honest about what they cannot do: they flag
suspicion, they do not prove truth.
"""
from __future__ import annotations

import json
import os
import re
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

# ── offline checks ─────────────────────────────────────────────────────

_NUM = r"\d[\d,]*(?:\.\d+)?"
_ARITH_RE = re.compile(
    rf"({_NUM})\s*([+\-*/×x÷])\s*({_NUM})\s*=\s*({_NUM})", re.IGNORECASE
)
_WORD_ARITH_RE = re.compile(
    r"({num})\s*(plus|minus|times|multiplied by|divided by)\s*({num})\s*"
    r"(?:is|equals|=)\s*({num})".format(num=_NUM),
    re.IGNORECASE,
)
_PCT_RE = re.compile(
    rf"({_NUM})\s*%\s*of\s*({_NUM})\s*(?:is|equals|=)\s*({_NUM})", re.IGNORECASE
)
_YEAR_RE = re.compile(r"\b((?:18|19|20|21)\d{2})\b")
_MD_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{1,2})(?:st|nd|rd|th)?\b,?\s*((?:18|19|20|21)\d{2})?",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_ABSOLUTE_RE = re.compile(
    r"\b(always|never|100%|guaranteed|impossible|everyone|nobody|"
    r"all users|zero risk|risk[- ]free|completely safe)\b",
    re.IGNORECASE,
)
_MONTH_DAYS = {
    "january": 31, "february": 29, "march": 31, "april": 30, "may": 31,
    "june": 30, "july": 31, "august": 31, "september": 30, "october": 31,
    "november": 30, "december": 31,
}
_OPS = {"+": 1, "-": 1, "*": 1, "/": 1, "×": 1, "x": 1, "÷": 1,
        "plus": 1, "minus": 1, "times": 1, "multiplied by": 1, "divided by": 1}


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def _fmt(x: float) -> str:
    return f"{x:.6f}".rstrip("0").rstrip(".")


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def arithmetic_check(text: str) -> list[CheckResult]:
    """Recompute every ``a op b = c`` pattern stated in the text."""
    out: list[CheckResult] = []
    for a, op, b, c in _ARITH_RE.findall(text):
        try:
            x, y, z = _num(a), _num(b), _num(c)
            got = {"+": x + y, "-": x - y, "*": x * y, "×": x * y, "x": x * y,
                   "/": x / y if y else float("inf"), "÷": x / y if y else float("inf")}[op.lower() if op.lower() in ("x",) else op]
        except Exception:
            continue
        ok = abs(got - z) < 1e-6 * max(1.0, abs(z))
        out.append(CheckResult(
            "arithmetic", ok,
            f'"{a} {op} {b} = {c}" — computed {_fmt(got)}'
            + ("" if ok else f", text says {c}")))
    for a, op, b, c in _WORD_ARITH_RE.findall(text):
        try:
            x, y, z = _num(a), _num(b), _num(c)
            got = {"plus": x + y, "minus": x - y, "times": x * y,
                   "multiplied by": x * y,
                   "divided by": x / y if y else float("inf")}[op.lower()]
        except Exception:
            continue
        ok = abs(got - z) < 1e-6 * max(1.0, abs(z))
        out.append(CheckResult(
            "arithmetic", ok,
            f'"{a} {op} {b} = {c}" — computed {_fmt(got)}'
            + ("" if ok else f", text says {c}")))
    return out


def percent_check(text: str) -> list[CheckResult]:
    out: list[CheckResult] = []
    for p, base, claimed in _PCT_RE.findall(text):
        try:
            got = _num(base) * _num(p) / 100.0
        except Exception:
            continue
        ok = abs(got - _num(claimed)) < 1e-6 * max(1.0, abs(got))
        out.append(CheckResult(
            "percent", ok,
            f'"{p}% of {base} = {claimed}" — computed {_fmt(got)}'
            + ("" if ok else f", text says {claimed}")))
    return out


def date_check(text: str, *, now_year: int | None = None) -> list[CheckResult]:
    import datetime
    this_year = now_year or datetime.date.today().year
    out: list[CheckResult] = []
    for year in _YEAR_RE.findall(text):
        y = int(year)
        if y > this_year + 2:
            out.append(CheckResult(
                "date", False,
                f"year {y} is more than 2 years in the future "
                f"(current {this_year}) — likely a hallucinated date"))
    for month, day, year in _MD_DATE_RE.findall(text):
        d = int(day)
        max_d = _MONTH_DAYS[month.lower()]
        if d > max_d:
            out.append(CheckResult(
                "date", False,
                f'"{month} {day}" does not exist ({month} has {max_d} days)'))
    return out


def absolute_claim_check(text: str) -> list[CheckResult]:
    hits = sorted({m.group(0).lower() for m in _ABSOLUTE_RE.finditer(text)})
    if not hits:
        return [CheckResult("absolute_claims", True, "no unqualified absolutes found")]
    return [CheckResult(
        "absolute_claims", False,
        "unqualified absolutes (verify or hedge these): " + ", ".join(hits))]


def url_check(text: str) -> list[CheckResult]:
    urls = _URL_RE.findall(text)
    if not urls:
        return []
    suspicious = [u for u in urls
                  if u.endswith((".png", ".jpg", ".pdf")) and "arxiv" not in u]
    ok = not suspicious
    return [CheckResult(
        "url_format", ok,
        f"{len(urls)} URL(s) found" + (f"; suspicious: {suspicious}" if suspicious else ""))]


def run_offline_checks(text: str) -> dict[str, Any]:
    checks = (arithmetic_check(text) + percent_check(text)
              + date_check(text) + absolute_claim_check(text) + url_check(text))
    failed = [c for c in checks if not c.passed]
    return {
        "verdict": "suspicious" if failed else "clean",
        "n_checks": len(checks),
        "failed": [asdict(c) for c in failed],
        "passed": [asdict(c) for c in checks if c.passed],
    }


# ── multi-model consensus (optional, hosted) ──────────────────────────

_STOP = {"the", "a", "an", "of", "is", "are", "was", "were", "to", "in",
         "on", "for", "and", "or", "that", "this", "it", "with", "as", "by"}


def _norm_claim(s: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9]+", s.lower())
    return frozenset(w for w in words if w not in _STOP)


def claim_similarity(a: str, b: str) -> float:
    sa, sb = _norm_claim(a), _norm_claim(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def extract_claims(answer: str) -> list[str]:
    """Ask-format helper: models are instructed to end with a JSON array of
    claims; pull it out, falling back to sentence split."""
    m = re.search(r"\[\s*\".*\"\s*\]", answer, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list) and arr and all(isinstance(x, str) for x in arr):
                return arr
        except json.JSONDecodeError:
            pass
    sents = re.split(r"(?<=[.!?])\s+", answer.strip())
    return [s for s in sents if len(s.split()) >= 4][:8]


@dataclass
class ConsensusReport:
    question: str
    models: list[str]
    verdict: str                      # high | medium | low | error
    agreement_score: float            # 0..1
    shared_claims: list[str] = field(default_factory=list)
    outlier_claims: dict[str, list[str]] = field(default_factory=dict)
    per_model: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_consensus(question: str, answers: dict[str, str],
                    threshold: float = 0.45) -> ConsensusReport:
    """Pure scoring — injectable and testable without any network."""
    models = list(answers)
    if len(models) < 2:
        return ConsensusReport(question, models, "error", 0.0, notes=[
            "consensus needs >= 2 model answers"])
    claim_sets = {m: extract_claims(a) for m, a in answers.items()}
    shared: list[str] = []
    outliers: dict[str, list[str]] = {m: [] for m in models}
    pair_scores: list[float] = []
    matched: set[tuple[int, int]] = set()
    for m in models:
        for claim in claim_sets[m]:
            hit = False
            for n in models:
                if n == m:
                    continue
                for i, c2 in enumerate(claim_sets[n]):
                    if claim_similarity(claim, c2) >= threshold:
                        pair_scores.append(claim_similarity(claim, c2))
                        matched.add((models.index(m), models.index(n)))
                        hit = True
                        break
                if hit:
                    break
            if hit and claim not in shared:
                shared.append(claim)
            elif not hit:
                outliers[m].append(claim)
    n_pairs = len(models) * (len(models) - 1)
    coverage = len({(i, j) for i, j in matched}) / n_pairs if n_pairs else 0.0
    avg_sim = statistics.mean(pair_scores) if pair_scores else 0.0
    score = round(0.6 * coverage + 0.4 * avg_sim, 3)
    verdict = "high" if score >= 0.7 else ("medium" if score >= 0.4 else "low")
    return ConsensusReport(question, models, verdict, score,
                           shared_claims=shared[:10],
                           outlier_claims={m: v[:5] for m, v in outliers.items() if v},
                           per_model={m: a[:400] for m, a in answers.items()},
                           notes=["lexical claim matching; threshold "
                                  f"{threshold} — flags suspicion, does not prove truth"])


CONSENSUS_PROMPT = (
    "Answer the question below. After your answer, append a line "
    "'CLAIMS:' followed by a JSON array of 3-7 short factual claims "
    "your answer depends on.\n\nQuestion: {q}"
)


def default_http_transport(model: str, prompt: str, timeout: float) -> str:
    """OpenAI-compatible chat completion. Requires httpx + env config:
    CTXKIT_API_BASE, CTXKIT_API_KEY. The model name is passed through."""
    import httpx  # optional extra
    base = os.environ.get("CTXKIT_API_BASE", "").rstrip("/")
    key = os.environ.get("CTXKIT_API_KEY", "")
    if not base or not key:
        raise RuntimeError("CTXKIT_API_BASE / CTXKIT_API_KEY not configured")
    r = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.2},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def multi_model_consensus(question: str, models: list[str],
                          transport: Callable[[str, str, float], str] | None = None,
                          timeout: float = 120.0) -> dict[str, Any]:
    transport = transport or default_http_transport
    prompt = CONSENSUS_PROMPT.format(q=question)
    answers: dict[str, str] = {}
    errors: dict[str, str] = {}
    for m in models:
        try:
            answers[m] = transport(m, prompt, timeout)
        except Exception as e:  # one model failing must not kill the report
            errors[m] = str(e)[:200]
    if len(answers) < 2:
        return {"verdict": "error", "question": question,
                "errors": errors,
                "notes": ["need >= 2 successful model calls for consensus"]}
    report = score_consensus(question, answers)
    report.notes.append(f"model errors: {errors}" if errors else "all models answered")
    return report.to_dict()
