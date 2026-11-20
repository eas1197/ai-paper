"""CLI for both generic stages: plan / run / execute / validate / export / status."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from runtime import ROOT, integrity, load, load_stage, make_plan, run_directory, verify_locks, write


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "run"):
        p = sub.add_parser(command)
        p.add_argument("--input", required=True)
        p.add_argument("--run-id", required=True)
        p.add_argument("--stage", choices=["04", "05", "both"], default="both")
        if command == "plan":
            p.add_argument("--output", required=True, help="计划只能保存在项目目录")
    p = sub.add_parser("execute")
    p.add_argument("--plan", required=True)
    for command in ("validate", "export"):
        p = sub.add_parser(command)
        p.add_argument("--attempt", required=True)
    p = sub.add_parser("status")
    p.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command in ("plan", "run"):
            source = Path(args.input).resolve()
            config = load(source)
            base = str(source.parent)
            def inputs(mid):
                return dict(config.get(mid, {}), run_id=args.run_id, base_dir=base)
            if args.stage == "both":
                # 05 cannot lock a not-yet-created 04 manifest. Plan it after 04 executes.
                first = load_stage("04").plan(inputs("04"), config.get("config", {}))
                future = make_plan("05", inputs("05"), config.get("config", {}))
                data = {"kind": "04_then_05", "stage04_plan": first, "stage05_inputs": future["inputs"],
                        "stage05_input_files": future["input_files"], "config": config.get("config", {})}
            else:
                data = load_stage(args.stage).plan(inputs(args.stage), config.get("config", {}))
            if args.command == "plan":
                target = Path(args.output).resolve()
                if not target.is_relative_to(ROOT):
                    raise ValueError("计划输出越出项目目录")
                if target.exists():
                    raise FileExistsError("计划已存在，拒绝覆盖")
                write(target, data)
                result = {"plan_path": str(target)}
            else:
                result = execute_plan(data)
        elif args.command == "execute":
            result = execute_plan(load(args.plan))
        elif args.command == "status":
            run = run_directory(args.run_id)
            data = load(run / "run_manifest.json")
            result = {"run_id": args.run_id, "stages": []}
            for row in data["stages"]:
                current = dict(row)
                if row.get("manifest_path"):
                    changed = integrity(Path(row["manifest_path"]).parent)
                    if changed:
                        current.update(status="stale", changed=changed)
                result["stages"].append(current)
        else:
            work = Path(args.attempt).resolve()
            manifest = load(work / "stage_manifest.json")
            stage = load_stage(manifest["stage_id"])
            if args.command == "export":
                result = stage.export(work)
            else:
                problems = integrity(work)
                plan = load(work / "plan.json")
                review = load(plan["inputs"]["quality_review"]) if plan["inputs"].get("quality_review") else None
                result = stage.validate(work, {"work": work, "quality_review": review})
                result.pop("abstract_rows", None)
                if problems:
                    result.update(status="stale", integrity_errors=problems)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        statuses = [r["status"] for r in result.get("stages", [])] if "stages" in result else [result.get("status")]
        return 3 if any(s in ("needs_review", "stale", "failed") for s in statuses) else 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps({"error": str(exc), "type": type(exc).__name__}, ensure_ascii=False), file=sys.stderr)
        return 2


def execute_plan(data):
    if data.get("kind") != "04_then_05":
        return load_stage(data["stage_id"]).execute(data)
    changed = verify_locks(data["stage05_input_files"])
    if changed:
        raise ValueError(f"05预定输入已变化，重新plan: {changed}")
    result04 = load_stage("04").execute(data["stage04_plan"])
    inputs05 = dict(data["stage05_inputs"], upstream=str(Path(result04["attempt_path"]) / "stage_manifest.json"))
    stage05 = load_stage("05")
    result05 = stage05.execute(stage05.plan(inputs05, data["config"]))
    return {"stages": [result04, result05], "notice": "G4不通过时05可整理候选并反馈，但不能冻结放行"}


if __name__ == "__main__":
    raise SystemExit(main())
