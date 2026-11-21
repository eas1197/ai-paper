"""Launch the seven-journal Codex native search candidate."""

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
    from codex_literature import collect
    from collect_common import contained, digest, load
    from native_receiving import receive

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=(profile["profile"],))
    parser.add_argument("--work", required=True)
    parser.add_argument("--config", type=Path, default=HERE / "templates/native_request.json")
    parser.add_argument("--theme")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--expand-from", help="A copyable 20-paper acceptance run")
    parser.add_argument("--handoff-check", action="store_true")
    args = parser.parse_args()
    config = load(args.config)
    if args.theme:
        config["theme"] = args.theme
    if config["journals"] != profile["journals"]:
        raise ValueError("Require the seven registered journals")
    work = contained(ROOT, args.work)
    if work == ROOT:
        raise ValueError("Use an independent run directory")
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
    return 0 if result["count"] >= result["target"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
