"""Launch the nine-journal Codex native search candidate."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def registry():
    profile = read("00_项目控制/v006_第6版/v3.1_Codex检索候选注册表.json")
    if (profile["profile"], profile["enabled_by_default"], (ROOT / profile["modules"]["04"]).resolve()) != (
        "paper_codex_native", False, HERE,
    ):
        raise ValueError("Wrong Codex candidate profile")
    journals = profile.get("journals")
    if not isinstance(journals, list) or len(journals) != 9:
        raise ValueError("Require exactly nine registered journals")
    original_policy = read("00_项目控制/v009_第9版/search_policy.json")
    if journals != original_policy.get("journals"):
        raise ValueError("Codex candidate journals must match the original v3.2 nine-journal policy")
    previous = read(profile["previous_registry"])
    multi = read(previous["phase2_registry"])
    first = read(multi["base_registry"])
    production = {row["module_id"]: row for row in read(first["production_registry"])["modules"]}
    for name in (production["04"]["path"], production["11"]["path"], first["modules"]["11"],
                 multi["modules"]["11"], profile["identity_module"], profile["modules"]["11"]):
        path = (ROOT / name / "tools").resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError("Module escapes the workspace")
        sys.path.insert(0, str(path))
    return profile


def main():
    profile = registry()
    from collect_common import contained, digest, load

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=(profile["profile"],))
    parser.add_argument("--work", required=True)
    parser.add_argument("--config", type=Path, default=HERE / "templates/native_request.json")
    parser.add_argument("--theme")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--expand-from", help="A copyable 20-paper acceptance run")
    parser.add_argument("--handoff-check", action="store_true")
    parser.add_argument("--dev-run", type=Path)
    args = parser.parse_args()
    config = load(args.config)
    if args.theme:
        config["theme"] = args.theme
    if config["journals"] != profile["journals"]:
        raise ValueError("Require the nine registered journals in canonical order")
    work = contained(ROOT, args.work)
    if work == ROOT:
        raise ValueError("Use an independent run directory")
    if args.dev_run:
        sys.path.insert(0, str(ROOT / "00_项目控制/v007_第7版/tools"))
        from run_mode import verified_run
        experiment = verified_run(args.dev_run)
        if work != args.dev_run.resolve() / "literature" or args.expand_from or args.handoff_check:
            raise ValueError("Experimental literature is confined to its own run and handoff")
        limits = experiment["workload"]
        config.update(theme=experiment["theme"], target=limits["04"]["abstract_target"],
                      max_batches=limits["11"]["max_batches"],
                      timeout_seconds=limits["11"]["timeout_seconds"],
                      search_action_budget=limits["11"]["native_search_actions"],
                      run_mode="dev", workload_sha256=experiment["workload_sha256"])
    target = config.get("target")
    max_batches = config.get("max_batches")
    if type(target) is not int or target < 0:
        raise ValueError("Target must be a non-negative integer")
    if type(max_batches) is not int or max_batches < 0:
        raise ValueError("Max batches must be a non-negative integer")
    if target == 0:
        if max_batches != 0:
            raise ValueError("A zero-target candidate must also set max_batches to zero")
        if args.resume or args.verify_only or args.expand_from or args.handoff_check:
            raise ValueError("The zero-target candidate is disabled; use a positive target for an explicit standalone run")
        print(json.dumps({
            "status": "disabled",
            "target": 0,
            "count": 0,
            "batches": [],
            "reason": "zero_target_configuration",
        }, ensure_ascii=False, indent=2))
        return 0
    if max_batches == 0:
        raise ValueError("A positive target requires at least one batch")
    from codex_literature import collect
    from native_receiving import receive
    if config.get("target") == 10 and not args.dev_run:
        raise ValueError("Ten papers requires a registered Dev Mode run")
    if args.expand_from and (config["target"] != 100 or args.resume or args.verify_only):
        raise ValueError("--expand-from starts a new 100-paper run")
    pilot = None
    if config["target"] == 100 and not (args.resume or args.verify_only):
        if not args.expand_from:
            raise ValueError("Provide an accepted 20-paper pilot before expanding to 100")
        pilot_dir = contained(ROOT, args.expand_from)
        pilot_bundle = load(pilot_dir / "abstract_collection.json")
        pilot_matrix = receive(pilot_dir, config["journals"])
        review = load(pilot_dir / "pilot_review.json")
        accepted = set(review["article_ids"])
        if (pilot_bundle["target"] != 20 or pilot_bundle["theme"] != config["theme"]
                or review.get("decision") != "accepted_20"
                or review["collection_sha256"] != digest(pilot_bundle)
                or len(accepted) < 20
                or not accepted <= {row["article_id"] for row in pilot_matrix["rows"]}):
            raise ValueError("Review must bind at least 20 eligible pilot papers")
        pilot = pilot_dir, review
    if args.verify_only:
        result = load(work / "abstract_collection.json")
        if result.get("run_mode") == "dev" and not args.dev_run:
            raise ValueError("Experimental bundle requires its frozen Dev Mode run")
        if args.dev_run and (result.get("run_mode"), result.get("workload_sha256"),
                             result.get("target"), result.get("theme")) != (
            "dev", config["workload_sha256"], config["target"], config["theme"],
        ):
            raise ValueError("Literature bundle does not match the frozen Dev Mode run")
    else:
        result = collect(config, work, HERE / "templates/search_prompt.txt",
                         HERE / "templates/native_response.schema.json", resume=args.resume,
                         pilot=pilot)
    matrix = receive(work, config["journals"])
    if args.handoff_check:
        from native_handoff import check
        check(work, matrix)
    print(json.dumps(dict(
        {key: result[key] for key in ("status", "target", "count", "batches")},
        excerpt_visible_count=matrix["excerpt_visible_count"],
    ), ensure_ascii=False, indent=2))
    return 0 if (result["count"] >= result["target"]
                 and result["status"] != "experimental_budget_exceeded") else 3


if __name__ == "__main__":
    raise SystemExit(main())
