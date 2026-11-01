"""Local-first memory store for ctxkit.

Design goals, in priority order:
  1. Never lose data. Every write is fsync'd into a JSONL append log.
  2. Never need a network. Zero dependencies; pure stdlib.
  3. Never be slow on read. An in-process index over the JSONL.

Storage layout (all under ``~/.ctxkit`` by default)::

    memory.jsonl        append-only log of {id, text, tags, ts, ...}
    .lock               advisory lock file

Retrieval is lexical (BM25-style) rather than vector-based on purpose:
it needs no embedding model, no downloads, and no GPU — which is what
"local-first, works on a plane" actually requires.
"""
from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

_WORD_RE = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    """Split into lowercase word tokens; CJK is split per character so that
    Chinese/Japanese notes still retrieve sensibly without a segmenter."""
    return [t.lower() for t in _WORD_RE.findall((text or "").lower())]


@dataclass
class Memory:
    id: str
    text: str
    tags: list[str] = field(default_factory=list)
    ts: float = field(default_factory=time.time)
    source: str = "manual"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class MemoryStore:
    """Append-only JSONL memory with an in-memory lexical index."""

    def __init__(self, root: str | os.PathLike | None = None) -> None:
        base = Path(root or os.environ.get("CTXKIT_HOME") or Path.home() / ".ctxkit")
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / "memory.jsonl"
        self._lock = threading.RLock()
        self._items: dict[str, Memory] = {}
        self._tokens: dict[str, list[str]] = {}
        self._df: dict[str, int] = {}
        self._load()

    # ── persistence ────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a torn trailing line must never break startup
                if obj.get("_op") == "delete":
                    self._forget_index(obj.get("id", ""))
                    continue
                mem = Memory(
                    id=obj.get("id") or uuid.uuid4().hex,
                    text=obj.get("text", ""),
                    tags=list(obj.get("tags") or []),
                    ts=float(obj.get("ts") or time.time()),
                    source=obj.get("source", "manual"),
                )
                self._index(mem)

    def _index(self, mem: Memory) -> None:
        self._items[mem.id] = mem
        toks = _tokenize(mem.text + " " + " ".join(mem.tags))
        self._tokens[mem.id] = toks
        for tok in set(toks):
            self._df[tok] = self._df.get(tok, 0) + 1

    def _forget_index(self, mem_id: str) -> None:
        mem = self._items.pop(mem_id, None)
        if not mem:
            return
        for tok in set(self._tokens.pop(mem_id, [])):
            n = self._df.get(tok, 0) - 1
            if n <= 0:
                self._df.pop(tok, None)
            else:
                self._df[tok] = n

    def _append(self, obj: dict[str, Any]) -> None:
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

    # ── public API ─────────────────────────────────────────────────────
    def remember(self, text: str, tags: Iterable[str] | None = None,
                 source: str = "manual") -> Memory:
        text = (text or "").strip()
        if not text:
            raise ValueError("text must not be empty")
        if len(text) > 100_000:
            raise ValueError("text too long (100k chars max)")
        mem = Memory(id=uuid.uuid4().hex, text=text,
                     tags=[t.strip() for t in (tags or []) if t.strip()],
                     ts=time.time(), source=source)
        with self._lock:
            self._append({"id": mem.id, "text": mem.text, "tags": mem.tags,
                          "ts": mem.ts, "source": mem.source})
            self._index(mem)
        return mem

    def recall(self, query: str, limit: int = 5,
               tags: Iterable[str] | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        want = {t.strip() for t in (tags or []) if t.strip()}
        q = _tokenize(query)
        qset = set(q)
        n = max(1, len(self._items))
        avgdl = (sum(len(v) for v in self._tokens.values()) / n) if n else 1.0

        k1, b = 1.5, 0.75
        scored: list[tuple[float, Memory]] = []
        with self._lock:
            items = list(self._items.values())
        for mem in items:
            if want and not want.issubset(set(mem.tags)):
                continue
            toks = self._tokens.get(mem.id, [])
            tf: list[str] = list(toks)
            dl = len(toks) or 1
            score = 0.0
            unique_terms = list(dict.fromkeys(q))
            for term in unique_terms:
                f = tf.count(term)
                if not f:
                    continue
                idf = math.log(1 + (n - self._df.get(term, 0) + 0.5)
                               / (self._df.get(term, 0) + 0.5))
                score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
            if qset:
                # Exact whole-query substring hit is the strongest relevance
                # signal; without it a 3-word doc can beat the longer doc that
                # literally contains the phrase the user typed.
                if query.strip() and query.strip().lower() in mem.text.lower():
                    score *= 1.5
                if score <= 0:
                    continue
            scored.append((score, mem))

        scored.sort(key=lambda p: (p[0], p[1].ts), reverse=True)
        out = []
        for score, mem in scored[:limit]:
            out.append({"id": mem.id, "text": mem.text, "tags": mem.tags,
                        "ts": mem.ts, "age_days": round((time.time() - mem.ts) / 86400, 1),
                        "score": round(score, 4)})
        return out

    def forget(self, mem_id: str) -> bool:
        with self._lock:
            if mem_id not in self._items:
                return False
            self._append({"_op": "delete", "id": mem_id})
            self._forget_index(mem_id)
            self._compact_if_needed()
        return True

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "count": len(self._items),
                "path": str(self.path),
                "tags": sorted({t for m in self._items.values() for t in m.tags}),
                "vocab": len(self._df),
            }

    def _compact_if_needed(self, ratio: float = 0.4) -> None:
        """Rewrite the log when deletes dominate, so it never grows forever."""
        try:
            raw_lines = sum(1 for _ in self.path.open("r", encoding="utf-8"))
        except OSError:
            return
        live = len(self._items)
        if raw_lines < 500 or live > raw_lines * (1 - ratio):
            return
        tmp = self.path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for mem in self._items.values():
                fh.write(mem.to_json() + "\n")
        os.replace(tmp, self.path)
