"""Authorized CNKI collection CLI: plan, login, collect/resume, download-core, context."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from acquisition import collect, plan
from collect_common import load, output_path

def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"): stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "login", "collect", "resume", "download-core"):
        p = sub.add_parser(command); p.add_argument("--config", required=True)
        if command != "plan": p.add_argument("--work", required=True)
        if command == "download-core": p.add_argument("--selection", required=True)
    p = sub.add_parser("context"); p.add_argument("--issue", required=True); p.add_argument("--work", required=True)
    p.add_argument("--sources"); p.add_argument("--as-of"); p.add_argument("--limit", type=int, default=12)
    args = parser.parse_args(argv)
    try:
        if args.command == "context":
            from context_web import collect_context
            result = collect_context(args.issue, output_path(args.work), sources=load(args.sources) if args.sources else None, as_of=args.as_of, limit=args.limit)
        else:
            config = load(args.config)
            if args.command == "plan": result = plan(config)
            elif args.command == "login":
                from cnki import SeleniumCNKI
                work = output_path(args.work); work.mkdir(parents=True, exist_ok=True)
                provider = SeleniumCNKI(config.get("browser", {}), work)
                try:
                    provider.login()
                    input("请在浏览器中正常登录/确认机构权限，完成后按Enter关闭并保存专用会话：")
                finally: provider.close()
                result = {"status": "session_saved_locally", "credentials_exported": False}
            else:
                result = collect(config, output_path(args.work), resume=args.command in ("resume", "download-core"),
                                 selection=load(args.selection) if args.command == "download-core" else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 3 if result.get("status") in ("requires_user_access", "access_denied", "requires_purchase", "needs_more_sources", "needs_fulltext", "layout_changed", "needs_review") else 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
