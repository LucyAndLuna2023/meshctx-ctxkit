"""ctxkit MCP server — stdio JSON-RPC, zero dependencies.

Speaks the Model Context Protocol over stdio so Claude Desktop, Cursor,
Cline, Windsurf, Zed and any MCP client can use it. Deliberately
hand-rolled (no `mcp` SDK import) so ``pip install ctxkit`` pulls
nothing: the whole point is a memory layer that works offline, in a
clean venv, on a plane.

Tools (free, fully offline):
    ctx_remember(text, tags?)       -> store a memory locally
    ctx_recall(query, limit?, tags?) -> BM25-style retrieval
    ctx_forget(id)                   -> delete a memory
    ctx_stats()                      -> store stats
    ctx_verify_text(text)            -> offline sanity checks
        (arithmetic / dates / absolutes / URLs)

Tools (optional, paid path, needs httpx + CTXKIT_API_KEY):
    ctx_consensus(question, models?) -> N-model cross-check report
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from . import __version__
from .memory import MemoryStore
from .consensus import run_offline_checks, multi_model_consensus
from .license import License, load_license_from_env
from .usage import UsageMeter

PROTOCOL_VERSION = "2024-11-05"
DEFAULT_MODELS = ["gpt-4o-mini", "claude-3-5-haiku", "gemini-2.0-flash"]


class CtxKitServer:
    def __init__(self, store: MemoryStore | None = None,
                 license_: License | None = None,
                 meter: UsageMeter | None = None) -> None:
        self.store = store or MemoryStore()
        self.license = license_ or load_license_from_env()
        self.meter = meter or UsageMeter(self.store.path.parent)

    # ── tool implementations ───────────────────────────────────────────
    def tool_remember(self, args: dict[str, Any]) -> str:
        mem = self.store.remember(
            text=args.get("text", ""),
            tags=args.get("tags") or [],
            source=args.get("source", "mcp"),
        )
        return json.dumps({"ok": True, "id": mem.id,
                           "note": "stored locally; survives restarts"},
                          ensure_ascii=False)

    def tool_recall(self, args: dict[str, Any]) -> str:
        hits = self.store.recall(
            query=args.get("query", ""),
            limit=args.get("limit", 5),
            tags=args.get("tags"),
        )
        return json.dumps({"ok": True, "hits": hits}, ensure_ascii=False)

    def tool_forget(self, args: dict[str, Any]) -> str:
        ok = self.store.forget(args.get("id", ""))
        return json.dumps({"ok": ok, "id": args.get("id", "")})

    def tool_stats(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        return json.dumps({"ok": True, **self.store.stats()}, ensure_ascii=False)

    def tool_verify(self, args: dict[str, Any]) -> str:
        text = args.get("text", "")
        if not text:
            return json.dumps({"ok": False, "error": "text required"})
        return json.dumps({"ok": True, **run_offline_checks(text)},
                          ensure_ascii=False)

    def tool_consensus(self, args: dict[str, Any]) -> str:
        question = args.get("question", "").strip()
        if not question:
            return json.dumps({"ok": False, "error": "question required"})
        lic = self.license
        if not lic.active:
            return json.dumps({
                "ok": False,
                "error": "ctx_consensus requires a paid license",
                "tier": lic.tier,
                "detail": lic.reason,
                "upgrade": "https://github.com/LucyAndLuna2023/meshctx#pricing",
                "note": "ctx_remember / ctx_recall / ctx_verify_text stay free forever",
            }, ensure_ascii=False)
        allowed, used = self.meter.check_and_consume(lic.consensus_quota)
        if not allowed:
            return json.dumps({
                "ok": False,
                "error": f"monthly consensus quota reached "
                         f"({used}/{lic.consensus_quota} on {lic.tier})",
                "resets": "1st of next month (UTC)",
            }, ensure_ascii=False)
        models = args.get("models") or _env_models() or DEFAULT_MODELS
        try:
            report = multi_model_consensus(question, models,
                                           timeout=float(args.get("timeout", 120)))
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:300]})
        report["quota"] = {"used": used, "limit": lic.consensus_quota, "tier": lic.tier}
        return json.dumps({"ok": True, **report}, ensure_ascii=False)

    def tool_license(self, args: dict[str, Any]) -> str:  # noqa: ARG002
        lic = self.license.to_dict()
        lic["usage"] = self.meter.snapshot()
        lic["free_tools"] = ["ctx_remember", "ctx_recall", "ctx_forget",
                             "ctx_stats", "ctx_verify_text"]
        return json.dumps({"ok": True, **lic}, ensure_ascii=False)

    # ── MCP protocol surface ───────────────────────────────────────────
    def tools_schema(self) -> list[dict[str, Any]]:
        return [
            {"name": "ctx_remember",
             "description": ("Save a durable local memory (facts, decisions, "
                             "preferences, project state). Survives restarts. "
                             "Stored on this machine only."),
             "inputSchema": {"type": "object", "properties": {
                 "text": {"type": "string", "description": "the fact/memory to keep"},
                 "tags": {"type": "array", "items": {"type": "string"}},
                 "source": {"type": "string", "description": "who saved it"}},
                 "required": ["text"]}},
            {"name": "ctx_recall",
             "description": ("Retrieve relevant memories by keyword query "
                             "(BM25-style, offline, no embeddings needed)."),
             "inputSchema": {"type": "object", "properties": {
                 "query": {"type": "string"},
                 "limit": {"type": "integer", "description": "default 5"},
                 "tags": {"type": "array", "items": {"type": "string"}}},
                 "required": ["query"]}},
            {"name": "ctx_forget",
             "description": "Delete a stored memory by id.",
             "inputSchema": {"type": "object", "properties": {
                 "id": {"type": "string"}}, "required": ["id"]}},
            {"name": "ctx_stats",
             "description": "Memory store statistics (count, tags, disk path).",
             "inputSchema": {"type": "object", "properties": {}}},
            {"name": "ctx_verify_text",
             "description": ("Offline sanity checks on generated text: recompute "
                             "stated arithmetic, validate dates, flag unqualified "
                             "absolutes and suspicious URLs. Free, no network."),
             "inputSchema": {"type": "object", "properties": {
                 "text": {"type": "string"}}, "required": ["text"]}},
            {"name": "ctx_consensus",
             "description": ("Ask the same question to several models and score "
                             "agreement of their key claims. Catches single-model "
                             "hallucinations. Requires CTXKIT_API_KEY (paid tier)."),
             "inputSchema": {"type": "object", "properties": {
                 "question": {"type": "string"},
                 "models": {"type": "array", "items": {"type": "string"},
                            "description": "default: 3 hosted models"},
                 "timeout": {"type": "number"}},
                 "required": ["question"]}},
            {"name": "ctx_license",
             "description": ("Show current license tier, expiry, this month's "
                             "consensus usage, and which tools are free."),
             "inputSchema": {"type": "object", "properties": {}}},
        ]

    def call_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "ctx_remember": self.tool_remember,
            "ctx_recall": self.tool_recall,
            "ctx_forget": self.tool_forget,
            "ctx_stats": self.tool_stats,
            "ctx_verify_text": self.tool_verify,
            "ctx_consensus": self.tool_consensus,
            "ctx_license": self.tool_license,
        }
        h = handlers.get(name)
        if h is None:
            return {"isError": True,
                    "content": [{"type": "text", "text": f"unknown tool: {name}"}]}
        try:
            text = h(args or {})
            return {"content": [{"type": "text", "text": text}]}
        except Exception as e:
            return {"isError": True,
                    "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}]}

    def handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        method = msg.get("method", "")
        mid = msg.get("id")
        params = msg.get("params") or {}
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ctxkit", "version": __version__}}}
        if method == "notifications/initialized":
            return None  # notification: no response
        if method == "ping":
            return {"jsonrpc": "2.0", "id": mid, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": mid, "result": {"tools": self.tools_schema()}}
        if method == "tools/call":
            name = params.get("name", "")
            result = self.call_tool(name, params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": mid, "result": result}
        if mid is not None:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32601, "message": f"method not found: {method}"}}
        return None


def _env_models() -> list[str] | None:
    raw = os.environ.get("CTXKIT_MODELS", "").strip()
    return [m.strip() for m in raw.split(",") if m.strip()] or None


def main() -> None:
    server = CtxKitServer()
    out = sys.stdout.buffer
    inp = sys.stdin.buffer
    while True:
        # readline() (not iteration): iterating stdin.buffer keeps an internal
        # read-ahead buffer and can miss EOF, leaving the process hung after
        # the MCP client closes the pipe.
        line = inp.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = server.handle(msg)
        if resp is not None:
            out.write((json.dumps(resp, ensure_ascii=False) + "\n").encode())
            out.flush()


if __name__ == "__main__":
    main()
