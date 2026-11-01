"""Local usage metering for the paid tier.

Deliberately local-only: we count calls in a JSON file next to the memory
store. No telemetry, no phone-home, no user identification beyond what the
license token already contains.

The honest caveat, stated plainly: a local counter can be deleted by the
user. That is fine. The paid feature costs *us* money per call (model API
spend), so quotas protect against runaway bills and casual abuse, not
against a determined attacker. Licensing protects revenue; the counter
protects the credit card.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any


class UsageMeter:
    def __init__(self, root: str | os.PathLike) -> None:
        self.path = Path(root) / "usage.json"
        self._lock = threading.RLock()

    def _load(self) -> dict[str, int]:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                return {k: int(v) for k, v in data.items() if isinstance(v, (int, float))}
        except (OSError, json.JSONDecodeError, ValueError):
            return {}

    def _save(self, data: dict[str, int]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    @staticmethod
    def _month_key(now: float | None = None) -> str:
        t = time.gmtime(now or time.time())
        return f"consensus:{t.tm_year}-{t.tm_mon:02d}"

    def used(self, now: float | None = None) -> int:
        with self._lock:
            return self._load().get(self._month_key(now), 0)

    def check_and_consume(self, quota: int, now: float | None = None) -> tuple[bool, int]:
        """Atomically reserve one call. Returns (allowed, used_after)."""
        with self._lock:
            data = self._load()
            key = self._month_key(now)
            used = data.get(key, 0)
            if used >= quota:
                return False, used
            data[key] = used + 1
            self._save(data)
            return True, data[key]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            data = self._load()
        key = self._month_key()
        return {"month": key.split(":", 1)[1], "used": data.get(key, 0),
                "file": str(self.path)}
