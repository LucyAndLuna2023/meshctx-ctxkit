"""CLI: ``ctxkit`` command line interface.

    ctxkit add "fact text" --tag project/alpha
    ctxkit search "query" [--limit 5]
    ctxkit stats
    ctxkit verify "text to check"
    ctxkit serve           # run the MCP stdio server
"""
from __future__ import annotations

import argparse
import json
import sys

from .memory import MemoryStore
from .consensus import run_offline_checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ctxkit",
                                 description="local-first memory + verification for agents")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="store a memory")
    p_add.add_argument("text")
    p_add.add_argument("--tag", action="append", default=[])

    p_search = sub.add_parser("search", help="search memories")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=5)

    sub.add_parser("stats", help="store stats")

    p_verify = sub.add_parser("verify", help="offline sanity checks on text")
    p_verify.add_argument("text")

    p_lic = sub.add_parser("license", help="show license tier, expiry and usage")
    p_lic.add_argument("--key", help="verify a specific license token instead of the stored one")

    sub.add_parser("serve", help="run MCP stdio server")

    args = ap.parse_args(argv)
    if args.cmd == "serve":
        from .server import main as serve_main
        serve_main()
        return 0
    store = MemoryStore()
    if args.cmd == "license":
        from .license import load_license_from_env, verify_license
        from .usage import UsageMeter
        lic = verify_license(args.key) if args.key else load_license_from_env()
        out = lic.to_dict()
        out["usage"] = UsageMeter(store.path.parent).snapshot()
        out["free_tools"] = ["ctx_remember", "ctx_recall", "ctx_forget",
                             "ctx_stats", "ctx_verify_text"]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "add":
        mem = store.remember(args.text, tags=args.tag)
        print(json.dumps({"ok": True, "id": mem.id}, ensure_ascii=False))
    elif args.cmd == "search":
        print(json.dumps({"hits": store.recall(args.query, args.limit)},
                         ensure_ascii=False, indent=2))
    elif args.cmd == "stats":
        print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
    elif args.cmd == "verify":
        print(json.dumps(run_offline_checks(args.text), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
