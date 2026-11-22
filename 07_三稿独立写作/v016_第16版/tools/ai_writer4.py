"""ai-writer 4.0: qualitative writing from v015 tasks with locked v003/v004/v005 language resources.

This is a Chat/Codex hand-off interface, not a model API or a source of independent academic review.
Original quantitative writer v014 and production module registry are never modified.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parents[1]
V15_TOOLS = ROOT / "07_三稿独立写作/v015_第15版/tools"
V14_TOOLS = ROOT / "07_三稿独立写作/v014_第14版/tools"
STYLE_PROFILE = ROOT / "03_学术语言学习/v005_第5版/outputs/style_profile.json"
STYLE_SNAPSHOT = ROOT / "03_学术语言学习/v005_第5版/outputs/resource_snapshot.json"
LANGUAGE_V3 = ROOT / "03_学术语言学习/v003_第3版/outputs/资源建设_attempt001/language_handbook.md"
WRITING_RULES = ROOT / "07_三稿独立写作/v014_第14版/templates/文字要求.md"
STYLE_MAP = MODULE / "assets/qualitative_style.json"
QUALITATIVE = {"secondary_interviews", "online_qualitative"}
STATUSES = {"independent_review_verified", "strict_literature_complete",
            "empirical_mechanism_verified", "formally_frozen",
            "independent_writing_approval"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hash_file(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def language_resources():
    """Read originals, verify published content hashes and preserve unpublished-G3 status."""
    profile = load(STYLE_PROFILE)
    snapshot = load(STYLE_SNAPSHOT)
    rolemap = load(STYLE_MAP)
    locks = {}
    for label, item in {
        "guide": profile["guide"], "examples": profile["examples"],
        "application": profile["application"], "mapping": profile["paragraph_style"]["mapping"],
        "rules": profile["paragraph_style"]["rules"],
    }.items():
        path = ROOT / item["path"]
        if not path.is_file() or hash_file(path) != item["sha256"]:
            raise ValueError("Published language resource changed: " + label)
        locks[label] = {"path": item["path"], "sha256": item["sha256"]}
    for label, path in [("profile", STYLE_PROFILE), ("snapshot", STYLE_SNAPSHOT),
                        ("v003_argument_handbook", LANGUAGE_V3),
                        ("v014_writing_rules", WRITING_RULES), ("v016_qual_style_map", STYLE_MAP)]:
        if not path.is_file():
            raise ValueError("Missing language source: " + str(path))
        locks[label] = {"path": relative(path), "sha256": hash_file(path)}
    rules = load(ROOT / profile["paragraph_style"]["rules"]["path"])
    units = load(ROOT / profile["paragraph_style"]["mapping"]["path"])["units"]
    by_id = {item["id"]: item for item in rules}
    if len(by_id) != 15 or set(profile["style_ids"]) != set(by_id):
        raise ValueError("Language pattern IDs no longer match v005 resource")
    if any(not x.get("style_ids") or any(s not in by_id for s in x["style_ids"])
           or any(unit not in units for unit in x["v005_units"])
           for x in rolemap["chapters"].values()):
        raise ValueError("Invalid qualitative map or v005 unit reference")
    return profile, snapshot, rolemap, by_id, locks


def validate_packet(packet):
    method = packet.get("method")
    if method == "quantitative":
        raise ValueError("Quantitative manuscripts remain on v014 stage07.py; not ai-writer 4.0")
    if method not in QUALITATIVE:
        raise ValueError("Unknown or unsupported qualitative method")
    sys.path.insert(0, str(V15_TOOLS))
    from writing_plan import render
    return render(packet)


def stage_type(chapter_id):
    return chapter_id if chapter_id in {"problem", "framework", "case", "conclusion"} else "dimension"


def formal_gates(packet, snapshot):
    decision = packet.get("gate_status") or {}
    missing = sorted(k for k in STATUSES if decision.get(k) is not True)
    if missing:
        raise ValueError("Formal writing blocked by upstream gates: " + ", ".join(missing))
    if snapshot.get("status") != "passed" or snapshot.get("resource_available_for_formal_writing") is not True:
        raise ValueError("Formal G3 language resource has not passed business review")
    # A documented flag is not an independent receipt. Formal promotion requires external verifier.
    raise ValueError("Formal writing still requires separately verified upstream receipts; flags alone cannot authorize G7")


def prepare(packet_path, workspace, mode="exploratory"):
    packet_path, workspace = Path(packet_path), Path(workspace)
    packet = load(packet_path)
    rendered = validate_packet(packet)
    profile, snapshot, rolemap, rules, locks = language_resources()
    if mode != "exploratory":
        formal_gates(packet, snapshot)
    if workspace.exists():
        raise ValueError("Writing workspace exists; refusing to overwrite a prior attempt")
    workspace.mkdir(parents=True)
    tasks = []
    for chapter in packet["chapters"]:
        typ = stage_type(chapter["id"])
        rulemap = rolemap["chapters"][typ]
        selected = rulemap["style_ids"]
        for index, section in enumerate(chapter["sections"], 1):
            task_id = chapter["id"] + "_" + str(index).zfill(2)
            task = {
                "task_id": task_id, "chapter_id": chapter["id"],
                "section_title": section["title"], "section_task": section["task"],
                "argument": section["argument"], "evidence_use": section["evidence_use"],
                "paragraphs": section.get("paragraphs", [section["task"]]),
                "source_ids": section["source_ids"],
                "sources": {i: packet["sources"][i] for i in section["source_ids"]},
                "qualitative_language_role": typ,
                "reused_v005_units_as_style_hints_only": rulemap["v005_units"],
                "style_rules": [
                    {k: rules[i][k] for k in ("id", "name", "how_to_write", "condition", "anti_pattern")}
                    for i in selected
                ],
                "v003_argument_audit": rolemap["argument_audit"],
                "instruction": (
                    "Write Chinese sociological prose answering THIS section task, not a generic overview. "
                    "Use only the cited, located sources. Distinguish interviewee claims, reported events, "
                    "literature synthesis and your inference. Bind source IDs and author-year citations. "
                    "Do not invent incidents, quotes, frequencies, participant outcomes or independent checks. "
                    "Use academic syntax without copying sentences or borrowing empirical findings from "
                    "style examples. Keep original uncertainty and evidence limits. A Chat-generated draft "
                    "must not be logged as a CLI search or independent model response."
                ),
            }
            save(workspace / "tasks" / (task_id + ".json"), task)
            tasks.append(task_id)
    (workspace / "writing_plan_v15.md").write_text(rendered, encoding="utf-8")
    record = {
        "product": "ai-writer 4.0", "version": 4, "run_id": packet.get("run_id"),
        "method": packet["method"], "mode": mode,
        "packet_name": packet_path.name, "packet_sha256": hash_file(packet_path),
        "sources": packet["sources"], "chapter_ids": [c["id"] for c in packet["chapters"]],
        "task_ids": tasks, "plan_sha256": hash_file(workspace / "writing_plan_v15.md"),
        "resource_sha256": locks, "language_profile_version": profile["profile_version"],
        "language_formal_resource_status": snapshot["status"],
        "formal_eligible": False, "independent_review_verified": False,
        "stage": "awaiting_draft", "full_paper_status": "exploratory_only",
        "quantitative_writer": "unchanged main/v014/tools/stage07.py",
    }
    save(workspace / "writer_manifest.json", record)
    return {"status": "awaiting_draft", "mode": mode, "task_count": len(tasks),
            "language_gate": snapshot["status"], "workspace": str(workspace)}


def review_draft(packet_path, workspace, manuscript_path, claims_path):
    workspace = Path(workspace)
    record = load(workspace / "writer_manifest.json")
    packet = load(packet_path)
    validate_packet(packet)
    profile, snapshot, rolemap, rules, locks = language_resources()
    problems = []
    if record["packet_sha256"] != hash_file(packet_path):
        problems.append("Writing packet changed since prepare")
    if record["resource_sha256"] != locks:
        problems.append("Language resource or writer mapping changed")
    if record["chapter_ids"] != [c["id"] for c in packet["chapters"]]:
        problems.append("Chapter structure changed")
    if record["mode"] != "exploratory":
        problems.append("Formal session cannot be submitted without a separate independent gate")
    text = Path(manuscript_path).read_text(encoding="utf-8-sig")
    claims_file = load(claims_path)
    claims = claims_file.get("claims")
    if not isinstance(claims, list) or not claims:
        problems.append("No source-bound claims ledger")
        claims = []
    seen = set()
    for claim in claims:
        cid = claim.get("claim_id")
        literal = claim.get("exact_text") or claim.get("claim_text")
        refs = claim.get("source_ids")
        if not cid or cid in seen or not isinstance(literal, str) or literal not in text:
            problems.append("Missing, duplicate or unlocated claim " + str(cid))
        seen.add(cid)
        if not isinstance(refs, list) or not refs or any(i not in packet["sources"] for i in refs):
            problems.append("Claim lacks valid evidence IDs: " + str(cid))
    headings = re.findall(r"^##\s+(?!摘要|参考文献|附录)(.+)$", text, re.M)
    if len(headings) != len(packet["chapters"]):
        problems.append("Body chapter count does not match v015 packet")
    total_chars = len(re.findall(r"[\u3400-\u9fff]", text.split("## 参考文献")[0]))
    if record["mode"] == "exploratory" and total_chars > 2500 and packet.get("policy", {}).get("max_words") == 2500:
        problems.append("Conservative experiment 2500-Chinese-character cap exceeded")
    sys.path.insert(0, str(V14_TOOLS))
    from language07 import style_findings
    style_issues = style_findings(text)
    save(workspace / "style_review.json", {
        "source": "main/v014/tools/language07.py",
        "deterministic_findings": style_issues,
        "resources_formally_passed": snapshot["status"] == "passed",
        "human_language_review": "pending",
        "instruction": "Use v004 style and v005 qualitative task mapping, then compare before/after "
                       "meaning, research unit, temporal scope, source attribution, causal strength. "
                       "Do not rewrite evidence to satisfy stylistic taste."
    })
    save(workspace / "writing_review_request.json", {
        "manuscript_sha256": hash_file(manuscript_path),
        "claim_ledger_sha256": hash_file(claims_path),
        "packet_sha256": record["packet_sha256"],
        "style_issue_count": len(style_issues), "structural_errors": problems,
        "gate": "G7", "formal_pass": False,
        "independent_review": "pending",
        "status": "technical_revisions_needed" if problems else "exploratory_draft_awaiting_review",
        "scope": "Single-model technical/style check; not a scientific approval",
    })
    return {"status": "technical_revisions_needed" if problems else "exploratory_draft_awaiting_review",
            "errors": problems, "style_issue_count": len(style_issues), "chinese_chars": total_chars}


def route(packet_path):
    method = load(packet_path).get("method")
    if method == "quantitative":
        return {"method": method, "writer": "main/v014/tools/stage07.py",
                "status": "unchanged; requires production G4-G6 and G2-G3"}
    if method in QUALITATIVE:
        return {"method": method, "writer": "ai-writer 4.0 / v016",
                "status": "use prepare and submit; no formal pass without independent academic review"}
    raise ValueError("Unknown method")


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    sub = cli.add_subparsers(dest="command", required=True)
    for cmd in ("route", "prepare", "submit"):
        p = sub.add_parser(cmd)
        p.add_argument("--packet", type=Path, required=True)
        if cmd != "route":
            p.add_argument("--workspace", type=Path, required=True)
        if cmd == "prepare":
            p.add_argument("--mode", choices=("exploratory", "formal"), default="exploratory")
        if cmd == "submit":
            p.add_argument("--manuscript", type=Path, required=True)
            p.add_argument("--claims", type=Path, required=True)
    args = cli.parse_args(argv)
    try:
        if args.command == "route":
            result = route(args.packet)
        elif args.command == "prepare":
            result = prepare(args.packet, args.workspace, args.mode)
        else:
            result = review_draft(args.packet, args.workspace, args.manuscript, args.claims)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") not in {"technical_revisions_needed"} else 3
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
