"""Explicit adaptive acquisition CLI; reuse the verified phase-one receiving contract."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]


def registry():
    def read(path):
        return json.loads(path.read_text(encoding="utf-8-sig"))

    profile = read(ROOT / "00_项目控制/v006_第6版/v3.1_AI检索候选注册表.json")
    if (profile["profile"], profile["scope"], profile["enabled_by_default"]) != (
        "paper_adaptive_v31",
        "adaptive_abstract_only",
        False,
    ) or (ROOT / profile["modules"]["04"]).resolve() != HERE:
        raise ValueError("Invalid candidate registry")
    previous = read(ROOT / profile["phase2_registry"])
    base = read(ROOT / previous["base_registry"])
    production = read(ROOT / base["production_registry"])
    old = {m["module_id"]: m["path"] for m in production["modules"]}
    directories = [
        old["11"],
        base["modules"]["11"],
        base["modules"]["04"],
        previous["modules"]["11"],
        profile["modules"]["11"],
    ]
    for name in directories:
        path = (ROOT / name / "tools").resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("Candidate dependency escapes the project")
        sys.path.insert(0, str(path))


registry()
from abstract_library import receive  # reused unchanged 04/v009 contract
from collect_common import contained, load
from adaptive_acquisition import ENGINE, collect


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--profile", required=True, choices=("paper_adaptive_v31",))
    p.add_argument("--work", required=True)
    actions = p.add_subparsers(dest="action", required=True)
    run = actions.add_parser("collect")
    run.add_argument(
        "--config", type=Path, default=HERE / "templates/adaptive_request.json"
    )
    run.add_argument("--theme")
    run.add_argument(
        "--seeds",
        type=Path,
        help="Optional historical bibliography, used only as verification search inputs",
    )
    run.add_argument("--resume", action="store_true")
    run.add_argument("--session-requests", type=int)
    run.add_argument("--add-budget", type=int, default=0)
    actions.add_parser("receive")
    a = p.parse_args(argv)
    work = contained(ROOT, a.work)
    if work == ROOT:
        raise ValueError("Use a separate candidate work directory")
    if a.action == "collect":
        config = load(a.config)
        if a.theme:
            config["theme"] = a.theme
        seeds = load(a.seeds) if a.seeds else []
        bundle = collect(config, work, seeds=seeds, resume=a.resume,
                         session_requests=a.session_requests, add_budget=a.add_budget)
    else:
        bundle = load(work / "abstract_collection.json")
    if bundle.get("engine") != ENGINE:
        raise ValueError("Not an adaptive abstract collection")
    matrix = receive(work)
    print(
        json.dumps(
            {
                "collection_id": matrix["collection_id"],
                "status": bundle["status"],
                "counts": matrix["counts"],
                "target": matrix["target"],
                "gap": matrix["gap"],
                "source_failures": bundle["source_failures"],
                "attempted_journals": bundle["attempted_journals"],
                "usage": bundle["usage"],
                "coverage": bundle["coverage"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if bundle["status"] == "history_completed" or (
        bundle["status"] == "target_reached" and matrix["target_met"]
    ) else 3


if __name__ == "__main__":
    raise SystemExit(main())
