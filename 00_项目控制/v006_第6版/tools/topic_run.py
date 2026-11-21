"""Persist and check each topic-stage decision before research initialization."""

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

from topic_evidence import validate_bundle
from topic_formal import final_gate, formal_init
from topic_review import COUNTERS, REVIEW_MODEL, content_hash, validate_counts, validate_review
from topic_tasks import prepare

ROOT = Path(__file__).resolve().parents[3]
STORE = ROOT / "00_项目控制/v006_第6版/outputs/topic_runs"
NEXT = {"opportunity": "question", "question": "deepening", "deepening": "formal", "final": "g5"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    serialized = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    stream = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".pending-", delete=False)
    pending = Path(stream.name)
    try:
        with stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def run_path(run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("Invalid run_id")
    return STORE / run_id


def initialize(run_id, limits, theme=None):
    if not validate_counts(limits) or min(limits.values()) < 1:
        raise ValueError("Set positive per-run model and search call limits")
    path = run_path(run_id)
    path.mkdir(parents=True, exist_ok=False)
    write_new(path / "config.json", {"run_id": run_id, "limits": limits, "theme": theme, "review_model": REVIEW_MODEL})
    return status(run_id)


def status(run_id):
    path = run_path(run_id)
    config = read(path / "config.json")
    rounds = sorted(path.glob("round-*.json"))
    previous = read(rounds[-1]) if rounds else {}
    if previous and previous["config_sha256"] != content_hash(config):
        raise ValueError("Run configuration changed after the last round")
    return {"config": config, "stage": previous.get("next_stage", "opportunity"),
            "round": len(rounds), "used": previous.get("used", dict.fromkeys(COUNTERS, 0)),
            "approved_ids": previous.get("approved_ids", []),
            "last_round": str(rounds[-1]) if rounds else None}


def allowance(run_id, requested):
    current = status(run_id)
    if not validate_counts(requested):
        raise ValueError("Invalid requested usage")
    remaining = {key: current["config"]["limits"][key] - current["used"][key] for key in COUNTERS}
    permitted = (current["stage"] in {"opportunity", "question", "deepening"}
                 and all(requested[key] <= remaining[key] for key in COUNTERS))
    return {"permitted": permitted, "remaining": remaining, "stage": current["stage"]}


def allowed_action(stage, review, remaining):
    verdict = review["verdict"]
    if verdict in {"PASS", "READY"}:
        return NEXT[stage], "quality_met"
    if verdict in {"REJECT", "STOP"} or not review["action_worth_cost"]:
        return "stopped", "no_worthwhile_followup"
    if any(review["cost"][key] > remaining[key] for key in COUNTERS) or remaining["model_calls"] == 0:
        return "stopped", "budget_exhausted"
    if stage == "question" and verdict == "REVISE" and review.get("return_to") == "opportunity":
        return "opportunity", "return_for_new_lead"
    return stage, "branch" if verdict == "BRANCH" else "targeted_revision"


def record(run_id, bundle, review, usage):
    current = status(run_id)
    stage = current["stage"]
    if stage not in {"opportunity", "question", "deepening"}:
        raise ValueError(f"Run is not accepting exploratory reviews: {stage}")
    validate_bundle(bundle, ROOT)
    validate_review(review, bundle, stage, current["config"]["review_model"])
    approved = review.get("selected_ids", [])
    if review["verdict"] in {"PASS", "READY"}:
        if stage == "opportunity":
            options = {row["opportunity_id"] for row in bundle["opportunities"]}
        elif stage == "question":
            options = {row["question_id"] for row in bundle["questions"] if row["opportunity_id"] in current["approved_ids"]}
        else:
            options = {row["next_question_id"] for row in bundle["evolution"] if row["disposition"] == "retained"
                       and row["question_id"] in current["approved_ids"]}
        if not approved or not set(approved).issubset(options):
            raise ValueError("A pass requires selected eligible IDs with approved ancestry")
        if stage == "deepening" and len(approved) != 1:
            raise ValueError("Select one primary candidate for formal literature review")
    for checkpoint in run_path(run_id).glob("round-*.json"):
        if read(checkpoint)["review"]["invocation_id"] == review["invocation_id"]:
            raise ValueError("Review invocation already recorded")
    if not validate_counts(usage) or usage["model_calls"] < 1:
        raise ValueError("Record actual calls, including the independent review")
    used = {key: current["used"][key] + usage[key] for key in COUNTERS}
    remaining = {key: current["config"]["limits"][key] - used[key] for key in COUNTERS}
    if min(remaining.values()) < 0:
        next_stage, reason = "stopped", "budget_exceeded"
    else:
        next_stage, reason = allowed_action(stage, review, remaining)
    if next_stage == stage and stage == "deepening" and (approved or review["verdict"] == "BRANCH"):
        options = {row["next_question_id"] for row in bundle["evolution"] if row["disposition"] == "retained"
                   and row["question_id"] in current["approved_ids"]}
        if not approved or not set(approved).issubset(options):
            raise ValueError("Branch requires eligible next question IDs")
    keep_selection = next_stage not in {stage, "stopped"} or (next_stage == stage == "deepening" and approved)
    round_data = {"round": current["round"] + 1, "stage": stage, "next_stage": next_stage,
                  "reason": reason, "config_sha256": content_hash(current["config"]),
                  "approved_ids": approved if keep_selection else current["approved_ids"],
                  "bundle": bundle, "review": review, "usage": usage, "used": used}
    write_new(run_path(run_id) / f"round-{round_data['round']:08d}.json", round_data)
    return status(run_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("run_id")
    init.add_argument("--theme")
    for counter in COUNTERS:
        init.add_argument("--" + counter.replace("_", "-"), type=int, required=True)
    commands.add_parser("status").add_argument("run_id")
    commands.add_parser("formal-init").add_argument("run_id")
    final = commands.add_parser("final-gate")
    for key in ("run_id", "bundle", "review", "attempt"):
        final.add_argument(key)
    task = commands.add_parser("prepare")
    task.add_argument("run_id")
    task.add_argument("--context-index", action="append", default=[])
    budget = commands.add_parser("allowance")
    budget.add_argument("run_id")
    for counter in COUNTERS:
        budget.add_argument("--" + counter.replace("_", "-"), type=int, required=True)
    submit = commands.add_parser("record")
    submit.add_argument("run_id")
    for name in ("bundle", "review", "usage"):
        submit.add_argument(name)
    args = parser.parse_args()
    if args.command == "init":
        result = initialize(args.run_id, {key: getattr(args, key) for key in COUNTERS}, args.theme)
    elif args.command == "record":
        result = record(args.run_id, read(args.bundle), read(args.review), read(args.usage))
    elif args.command == "allowance":
        result = allowance(args.run_id, {key: getattr(args, key) for key in COUNTERS})
    elif args.command == "prepare":
        result = prepare(ROOT, read, status(args.run_id), args.context_index)
    elif args.command == "formal-init":
        result = formal_init(ROOT, run_path(args.run_id), status(args.run_id), read, write_new)
    elif args.command == "final-gate":
        bundle = read(args.bundle)
        validate_bundle(bundle, ROOT)
        result = final_gate(ROOT, status(args.run_id), bundle, read(args.review), args.attempt, read)
    else:
        result = status(args.run_id)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
