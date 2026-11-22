"""ai-paper 5.0: append-only research orchestration, no web/API/Stata execution.

Chat provides sourced records from its native web research. Python verifies stage
contracts, recorded documents and the route to the existing writer. Technical
validation is NOT an independent academic review or automatic paper authoring.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

STAGES = ("topic_candidates", "reality", "event_comparison", "explanation_exchange",
          "literature_initial", "preliminary_review", "research_design",
          "literature_supplemental", "final_review", "empirical_materials",
          "analysis_matrix", "writing_packet", "manuscript", "writing_review")
METHODS = {"quantitative", "secondary_interviews", "online_qualitative"}
NON_INDEPENDENT = ("same_model_adversarial", "chat_role_play", "single_model_review")


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def start(work, run_id, *, full_draft=True):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", run_id):
        raise ValueError("Invalid run id")
    work = Path(work)
    if work.exists():
        raise FileExistsError("Do not overwrite existing experiment: " + str(work))
    work.mkdir(parents=True)
    write(work / "manifest.json", {"schema_version": 1, "system": "ai-paper 5.0",
        "run_id": run_id, "run_mode": "dev_chat_native", "formal_eligible": False,
        "paper_mode": "full_experimental" if full_draft else "plan",
        "quantitative_analyzer": "original_stata_unchanged_not_executed",
        "writing_routes": {"quantitative": "main/v014 (unchanged)",
                           "secondary_interviews": "v015/v016 ai-writer 4.0",
                           "online_qualitative": "v015/v016 ai-writer 4.0"},
        "literature_targets": {"initial": 5, "supplemental": 5},
        "stage_order": list(STAGES), "stages": {}, "academic_review": "pending_independent",
        "created_at": datetime.now(timezone.utc).isoformat()})
    return work


def _check(stage, packet, previous):
    if not isinstance(packet, dict) or not packet:
        raise ValueError("Non-empty JSON object required")
    if stage == "topic_candidates":
        if len(packet.get("candidates", [])) < 2 or not packet.get("selected"):
            raise ValueError("Select after comparing at least two concrete candidate topics")
    elif stage == "reality":
        if not packet.get("sources") or not packet.get("phenomenon"):
            raise ValueError("Real observation needs its source and bounded phenomenon")
    elif stage == "event_comparison":
        if len(packet.get("events", [])) < 2:
            raise ValueError("Compare at least two distinct observed events")
    elif stage == "explanation_exchange":
        if not all(packet.get(k) for k in ("expectation", "explanation", "challenge", "question")):
            raise ValueError("Explanation and adversarial challenge must be recorded")
        if packet.get("review_mode") not in NON_INDEPENDENT and not packet.get("independent_receipt"):
            raise ValueError("Declare role-play or provide verifiable independent receipt")
    elif stage in {"literature_initial", "literature_supplemental"}:
        articles = packet.get("articles", [])
        if not isinstance(articles, list):
            raise ValueError("Article list required")
        identifiers = [x.get("doi") or x.get("url") for x in articles]
        if any(not x.get("title") or not x.get("url") or not x.get("read_status") for x in articles):
            raise ValueError("Each article needs title, URL and actual reading status")
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate article identifiers")
        if stage == "literature_supplemental":
            prior = previous.get("literature_initial", {}).get("data", {}).get("articles", [])
            prior_ids = {x.get("doi") or x.get("url") for x in prior}
            if any(x in prior_ids for x in identifiers):
                raise ValueError("Supplemental literature duplicates initial")
    elif stage == "research_design":
        if packet.get("method") not in METHODS or not packet.get("core_question"):
            raise ValueError("Design must choose a known method and a core question")
    elif stage == "empirical_materials":
        for m in packet.get("materials", []):
            if not all(m.get(k) for k in ("id", "event_id", "url", "locator", "status")):
                raise ValueError("Empirical material missing real source locator or status")
    elif stage == "analysis_matrix":
        if not packet.get("dimensions") or not packet.get("rows"):
            raise ValueError("Need theoretically deduced dimensions and evidence rows")
        ids = {x["id"] for x in packet["dimensions"]}
        if {x.get("dimension_id") for x in packet["rows"]} != ids:
            raise ValueError("Every dimension must have one analysis row")
    elif stage == "writing_packet":
        method = previous.get("research_design", {}).get("data", {}).get("method")
        if packet.get("method") != method:
            raise ValueError("Writing method differs from research design")
        if method == "quantitative":
            if packet.get("sta_analysis_status") != "not_executed":
                raise ValueError("Skipping Stata must be explicitly recorded")
        elif not packet.get("chapters") or not packet.get("sources"):
            raise ValueError("Qualitative writer needs v015 chapters and sources")
    elif stage == "manuscript":
        if not packet.get("manuscript") or not packet.get("claims"):
            raise ValueError("Manuscript requires paths to actual text and claim ledger")
    elif stage == "writing_review":
        if not packet.get("decision") or not packet.get("reviewer_mode"):
            raise ValueError("Review must state the decision and reviewer mode")


def ingest(work, stage, file):
    work, file = Path(work), Path(file)
    manifest = read(work / "manifest.json")
    if stage not in STAGES:
        raise ValueError("Unknown stage")
    if stage in manifest["stages"]:
        raise ValueError("Append-only: stage already recorded")
    expected = STAGES[len(manifest["stages"])]
    if stage != expected:
        raise ValueError("Next stage is " + expected)
    packet = read(file)
    _check(stage, packet, manifest["stages"])
    if stage == "manuscript":
        for field in ("manuscript", "claims"):
            original = (file.parent / packet[field]).resolve()
            if not original.is_file() or not original.is_relative_to(file.parent.resolve()):
                raise ValueError("Manuscript/claims must be extant files alongside packet")
            packet[field + "_sha256"] = digest(original)
    if stage == "writing_review" and packet.get("reviewer_mode") in NON_INDEPENDENT:
        packet["independent_review_verified"] = False
        packet["formal_g7_pass"] = False
    target = work / "stages" / (f"{STAGES.index(stage)+1:02d}_{stage}.json")
    write(target, packet)
    manifest["stages"][stage] = {"sha256": digest(target), "source_sha256": digest(file),
                                  "file": str(target.relative_to(work)), "data": packet,
                                  "technical_status": "recorded_not_academically_approved"}
    if stage == "research_design":
        manifest["selected_method"] = packet["method"]
    if stage == "writing_review":
        manifest["research_end_to_end_executed"] = True
        manifest["formal_eligible"] = False
    write(work / "manifest.json", manifest)
    return stage


def status(work):
    manifest = read(Path(work) / "manifest.json")
    for stage, record in manifest["stages"].items():
        target = Path(work) / record["file"]
        if not target.is_file() or digest(target) != record["sha256"]:
            raise ValueError("Frozen stage mutated: " + stage)
    counts = {k: len(manifest["stages"].get(k, {}).get("data", {}).get("articles", []))
              for k in ("literature_initial", "literature_supplemental")}
    targets = manifest["literature_targets"]
    return {"run_id": manifest["run_id"], "recorded": list(manifest["stages"]),
            "next": STAGES[len(manifest["stages"])] if len(manifest["stages"]) < len(STAGES) else None,
            "literature_counts": counts,
            "literature_deficit": {k: max(0, targets[k.split("_")[1]]-v) for k,v in counts.items()},
            "method": manifest.get("selected_method"),
            "technical_complete": len(manifest["stages"]) == len(STAGES),
            "scientific_acceptance": "not_passed_without_genuine_independent_review",
            "stata": manifest["quantitative_analyzer"]}



def invoke_writer(work, packet, action, manuscript=None, claims=None):
    """Call the actual v016 writing interface; never synthesize an author/review receipt."""
    work, packet = Path(work).resolve(), Path(packet).resolve()
    manifest = read(work / "manifest.json")
    recorded = manifest["stages"].get("writing_packet")
    if not recorded or recorded["source_sha256"] != digest(packet):
        raise ValueError("The writer packet is not the recorded stage 12 input")
    if manifest.get("selected_method") == "quantitative":
        raise ValueError("Quantitative runs keep original v014 and have Stata not_executed")
    if action == "submit" and "manuscript" not in manifest["stages"]:
        raise ValueError("Record the actual manuscript stage before submitting to writer")
    writer = Path(__file__).resolve().parents[3] / "07_三稿独立写作/v016_第16版/tools/ai_writer4.py"
    if not writer.is_file():
        raise FileNotFoundError("Actual ai-writer 4.0 executable is missing")
    ws = work / "writer4_workspace"
    cmd = [sys.executable, "-B", str(writer), action, "--packet", str(packet),
           "--workspace", str(ws)]
    if action == "prepare":
        cmd += ["--mode", "exploratory"]
    else:
        if not manuscript or not claims:
            raise ValueError("A real manuscript and claims file are required")
        cmd += ["--manuscript", str(Path(manuscript).resolve()),
                "--claims", str(Path(claims).resolve())]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=90)
    return {"returncode": completed.returncode, "stdout": completed.stdout,
            "stderr": completed.stderr, "action": action}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="cmd", required=True)
    init = sub.add_parser("init"); init.add_argument("--work", required=True); init.add_argument("--run-id", required=True)
    item = sub.add_parser("ingest"); item.add_argument("--work", required=True); item.add_argument("--stage", required=True, choices=STAGES); item.add_argument("--input", required=True)
    stat = sub.add_parser("status"); stat.add_argument("--work", required=True)
    for action in ("prepare", "submit"):
        writer_cmd = sub.add_parser("writer-" + action)
        writer_cmd.add_argument("--work", required=True)
        writer_cmd.add_argument("--packet", required=True)
        if action == "submit":
            writer_cmd.add_argument("--manuscript", required=True)
            writer_cmd.add_argument("--claims", required=True)
    args = cli.parse_args(argv)
    try:
        if args.cmd == "init":
            result = str(start(args.work, args.run_id))
        elif args.cmd == "ingest":
            result = ingest(args.work, args.stage, args.input)
        elif args.cmd.startswith("writer-"):
            result = invoke_writer(args.work, args.packet, args.cmd.removeprefix("writer-"),
                                   getattr(args, "manuscript", None), getattr(args, "claims", None))
            if result["returncode"]:
                print(json.dumps({"status": "blocked", "result": result}, ensure_ascii=False))
                return 3
        else:
            result = status(args.work)
        print(json.dumps({"status": "ok", "result": result}, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as e:
        print(json.dumps({"status": "blocked", "reason": str(e)}, ensure_ascii=False))
        return 2

if __name__ == "__main__":
    sys.exit(main())
