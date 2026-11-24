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
LANGUAGE_V3_SNAPSHOT = ROOT / "03_学术语言学习/v003_第3版/outputs/resource_snapshot.json"
LANGUAGE_V4_PROFILE = ROOT / "03_学术语言学习/v004_第4版/outputs/style_profile.json"
LANGUAGE_V4_SNAPSHOT = ROOT / "03_学术语言学习/v004_第4版/outputs/resource_snapshot.json"
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


def verify_resource_snapshot(snapshot, label, module_version, resource_version,
                             required_paths, profile=None):
    if (snapshot.get("module_id") != "03"
            or snapshot.get("module_version") != module_version
            or snapshot.get("resource_version") != resource_version):
        raise ValueError("Language resource version mismatch: " + label)
    status = snapshot.get("status")
    if status not in {"needs_review", "passed"}:
        raise ValueError("Unknown language resource status: " + label)
    available = snapshot.get("resource_available_for_formal_writing")
    if ((status == "needs_review" and available is not False)
            or (status == "passed" and available is not True)):
        raise ValueError("Language resource availability contradicts its status: " + label)
    gate_path = snapshot.get("business_gate_report")
    if not gate_path or not (ROOT / gate_path).is_file():
        raise ValueError("Missing language business gate report: " + label)
    gate = load(ROOT / gate_path)
    if gate.get("status") != status or gate.get("passed") is not (status == "passed"):
        raise ValueError("Language snapshot and business gate disagree: " + label)
    if profile is not None and (
            profile.get("resource_version") != resource_version
            or profile.get("formal_resource_gate_status") != status):
        raise ValueError("Language profile and resource snapshot disagree: " + label)
    files = snapshot.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Language resource snapshot has no file inventory: " + label)
    required = set(required_paths) | {gate_path}
    seen, warnings = set(), []
    for item in files:
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("Malformed language resource inventory: " + label)
        path = item["path"]
        if path in seen:
            raise ValueError("Duplicate language resource inventory path: " + label)
        seen.add(path)
        source = ROOT / path
        actual = hash_file(source) if source.is_file() else None
        if actual != item["sha256"]:
            if path in required:
                raise ValueError("Language snapshot dependency changed: " + label + ":" + path)
            warnings.append({"snapshot": label, "path": path,
                             "expected_sha256": item["sha256"], "actual_sha256": actual})
    missing = sorted(required - seen)
    if missing:
        raise ValueError("Language snapshot omits required dependencies: " + label + ":" + ", ".join(missing))
    return warnings


def parse_argument_rules():
    text = LANGUAGE_V3.read_text(encoding="utf-8-sig")
    sections = re.split(r"(?=^## )", text, flags=re.M)
    parsed = {}
    for section in sections:
        heading = re.match(r"^## (L\d{2}) ([^\r\n]+)\r?\n", section)
        if not heading:
            continue
        rule_id, title = heading.group(1), heading.group(2).strip()
        body = section[heading.end():]
        principle = body.split("\n\n**", 1)[0].strip()

        def field(label):
            match = re.search(
                r"^\*\*" + re.escape(label) + r"：\*\*\s*(.*?)(?=^\*\*[^*\n]+：\*\*|\Z)",
                body, re.M | re.S)
            return " ".join(match.group(1).split()) if match else ""

        parsed[rule_id] = {
            "id": rule_id,
            "title": title,
            "principle": principle,
            "syntax_and_information_order": field("句法及信息顺序"),
            "expression_skeleton": field("表达骨架"),
            "usage_condition": field("使用条件"),
            "project_constraint": field("本项目新增约束"),
        }
    required = ("principle", "syntax_and_information_order", "expression_skeleton",
                "usage_condition", "project_constraint")
    if len(parsed) != 27 or any(not all(rule.get(key) for key in required)
                                for rule in parsed.values()):
        raise ValueError("V003 argument handbook is incomplete or its rule structure changed")
    return parsed


def language_resources():
    """Read originals, verify published content hashes and preserve unpublished-G3 status."""
    profile = load(STYLE_PROFILE)
    snapshot = load(STYLE_SNAPSHOT)
    rolemap = load(STYLE_MAP)
    v003_snapshot = load(LANGUAGE_V3_SNAPSHOT)
    v004_profile = load(LANGUAGE_V4_PROFILE)
    v004_snapshot = load(LANGUAGE_V4_SNAPSHOT)
    profile_refs = [profile["guide"], profile["examples"], profile["application"],
                    profile["paragraph_style"]["mapping"], profile["paragraph_style"]["rules"]]
    v003_required = {relative(LANGUAGE_V3)}
    v004_required = {relative(LANGUAGE_V4_PROFILE)}
    v005_required = {relative(STYLE_PROFILE), profile["paragraph_style"]["mapping"]["path"]}
    v005_required.update(item["path"] for item in profile_refs)
    snapshot_warnings = []
    snapshot_warnings.extend(verify_resource_snapshot(
        v003_snapshot, "v003", 3, 1, v003_required))
    snapshot_warnings.extend(verify_resource_snapshot(
        v004_snapshot, "v004", 4, 2, v004_required, v004_profile))
    snapshot_warnings.extend(verify_resource_snapshot(
        snapshot, "v005", 5, 3, v005_required, profile))
    if (profile.get("profile_version") != "3.0"
            or v004_profile.get("profile_version") != "2.0"
            or set(profile.get("style_ids", [])) != set(v004_profile.get("style_ids", []))):
        raise ValueError("Published v003/v004/v005 language profile versions disagree")
    snapshot_index = {item["path"]: item["sha256"] for item in snapshot["files"]}
    if any(snapshot_index.get(item["path"]) != item["sha256"] for item in profile_refs):
        raise ValueError("v005 snapshot does not bind every published language profile resource")
    v003_index = {item["path"]: item["sha256"] for item in v003_snapshot["files"]}
    if v003_index.get(relative(LANGUAGE_V3)) != hash_file(LANGUAGE_V3):
        raise ValueError("v003 argument handbook is not bound by its resource snapshot")
    v004_index = {item["path"]: item["sha256"] for item in v004_snapshot["files"]}
    if v004_index.get(relative(LANGUAGE_V4_PROFILE)) != hash_file(LANGUAGE_V4_PROFILE):
        raise ValueError("v004 style profile is not bound by its resource snapshot")
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
                        ("v003_resource_snapshot", LANGUAGE_V3_SNAPSHOT),
                        ("v004_style_profile", LANGUAGE_V4_PROFILE),
                        ("v004_resource_snapshot", LANGUAGE_V4_SNAPSHOT),
                        ("v014_writing_rules", WRITING_RULES), ("v016_qual_style_map", STYLE_MAP)]:
        if not path.is_file():
            raise ValueError("Missing language source: " + str(path))
        locks[label] = {"path": relative(path), "sha256": hash_file(path)}
    rules = load(ROOT / profile["paragraph_style"]["rules"]["path"])
    units = load(ROOT / profile["paragraph_style"]["mapping"]["path"])["units"]
    argument_rules = parse_argument_rules()
    by_id = {item["id"]: item for item in rules}
    if len(by_id) != 15 or set(profile["style_ids"]) != set(by_id):
        raise ValueError("Language pattern IDs no longer match v005 resource")
    if len(units) != 52 or any(
            not isinstance(unit, dict) or not unit.get("purpose")
            or any(style_id not in by_id for style_id in unit.get("style_ids", []))
            for unit in units.values()):
        raise ValueError("V005 paragraph-function mapping is incomplete or references unknown ST rules")
    if any(not x.get("style_ids") or any(s not in by_id for s in x["style_ids"])
           or any(unit not in units for unit in x["v005_units"])
           or any(arg not in argument_rules for arg in x["argument_audit"])
           for x in rolemap["chapters"].values()):
        raise ValueError("Invalid qualitative map or v005/V003 rule reference")
    resource_versions = {"v003": v003_snapshot["resource_version"],
                         "v004": v004_snapshot["resource_version"],
                         "v005": snapshot["resource_version"]}
    return profile, snapshot, rolemap, by_id, units, locks, argument_rules, snapshot_warnings, resource_versions


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
    profile, snapshot, rolemap, rules, units, locks, argument_rules, snapshot_warnings, resource_versions = language_resources()
    if mode != "exploratory":
        formal_gates(packet, snapshot)
    if workspace.exists():
        raise ValueError("Writing workspace exists; refusing to overwrite a prior attempt")
    workspace.mkdir(parents=True)
    tasks = []
    task_hashes = {}
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
                "v005_unit_details_as_style_hints_only": [
                    {"id": unit_id, **units[unit_id]} for unit_id in rulemap["v005_units"]
                ],
                "style_rule_ids": selected,
                "style_rules": [
                    {k: rules[i][k] for k in ("id", "name", "how_to_write", "condition", "anti_pattern")}
                    for i in selected
                ],
                "v003_argument_audit": [
                    {"id": arg, "purpose": argument_rules[arg]["title"]}
                    for arg in rulemap["argument_audit"]
                ],
                "v003_argument_rules": [argument_rules[arg] for arg in rulemap["argument_audit"]],
                "language_resource_versions": resource_versions,
                "resource_provenance": {
                    "v003_argument_handbook": locks["v003_argument_handbook"],
                    "v004_style_rules": locks["rules"],
                    "v005_function_mapping": locks["mapping"],
                },
                "instruction": (
                    "Write Chinese sociological prose answering THIS section task, not a generic overview. "
                    "Use only the cited, located sources. Distinguish interviewee claims, reported events, "
                    "literature synthesis and your inference. Bind source IDs and author-year citations. "
                    "Do not invent incidents, quotes, frequencies, participant outcomes or independent checks. "
                    "Use V004 ST rules as conditional expression choices, not fixed templates. "
                    "Use V005 units only as paragraph-function/style hints, never as research methods. "
                    "Apply V003 argument rules to check scope, inference, source attribution and evidence strength; "
                    "their skeletons are reasoning aids, not sentences to copy. Do not borrow empirical findings "
                    "from style examples. Keep original uncertainty and evidence limits. A Chat-generated draft "
                    "must not be logged as a CLI search or independent model response."
                ),
            }
            task_path = workspace / "tasks" / (task_id + ".json")
            save(task_path, task)
            tasks.append(task_id)
            task_hashes[task_id] = hash_file(task_path)
    (workspace / "writing_plan_v15.md").write_text(rendered, encoding="utf-8")
    record = {
        "product": "ai-writer 4.0", "version": 4, "run_id": packet.get("run_id"),
        "method": packet["method"], "mode": mode,
        "packet_name": packet_path.name, "packet_sha256": hash_file(packet_path),
        "sources": packet["sources"], "chapter_ids": [c["id"] for c in packet["chapters"]],
        "task_ids": tasks, "task_sha256": task_hashes, "plan_sha256": hash_file(workspace / "writing_plan_v15.md"),
        "resource_sha256": locks, "language_profile_version": profile["profile_version"],
        "language_resource_version": profile["resource_version"],
        "language_snapshot_id": snapshot["resource_snapshot_id"],
        "language_formal_resource_status": snapshot["status"],
        "resource_snapshot_warnings": snapshot_warnings,
        "v003_resource_version": resource_versions["v003"],
        "v004_resource_version": resource_versions["v004"],
        "v003_argument_rule_count": len(argument_rules),
        "v005_function_unit_count": len(units),
        "formal_eligible": False, "independent_review_verified": False,
        "stage": "awaiting_draft", "full_paper_status": "exploratory_only",
        "quantitative_writer": "unchanged main/v014/tools/stage07.py",
    }
    save(workspace / "writer_manifest.json", record)
    return {"status": "awaiting_draft", "mode": mode, "task_count": len(tasks),
            "language_gate": snapshot["status"], "workspace": str(workspace)}


def validate_draft_task_binding(packet, record, workspace, text, ledger):
    """Bind submitted text to frozen paragraph tasks; not semantic or academic proof."""
    expected = {}
    hashes = record.get("task_sha256")
    if not isinstance(hashes, dict):
        raise ValueError("Missing frozen task hashes; prepare a new attempt")
    for chapter in packet["chapters"]:
        for i, section in enumerate(chapter["sections"], 1):
            task_id = chapter["id"] + "_" + str(i).zfill(2)
            task_path = (workspace / "tasks" / (task_id + ".json")).resolve()
            if (not task_path.is_relative_to((workspace / "tasks").resolve())
                    or not task_path.is_file() or hash_file(task_path) != hashes.get(task_id)):
                raise ValueError("Frozen paragraph task changed: " + task_id)
            task = load(task_path)
            paragraphs = section.get("paragraphs", [section["task"]])
            if (task.get("task_id") != task_id or task.get("paragraphs") != paragraphs
                    or task.get("source_ids") != section["source_ids"]
                    or task.get("sources") != {key: packet["sources"][key] for key in section["source_ids"]}):
                raise ValueError("Frozen paragraph task differs from packet: " + task_id)
            for number in range(1, len(paragraphs) + 1):
                expected[(task_id, number)] = set(section["source_ids"])
    task_ids = list(dict.fromkeys(key[0] for key in expected))
    if task_ids != record.get("task_ids") or set(hashes) != set(task_ids):
        raise ValueError("Frozen task inventory differs from packet")
    rows = ledger.get("paragraph_bindings")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("Every frozen paragraph task requires a submitted paragraph binding")
    bound = {}
    last_end = 0
    for row, key in zip(rows, expected):
        if not isinstance(row, dict):
            raise ValueError("Malformed paragraph binding")
        actual = (row.get("task_id"), row.get("paragraph_index"))
        literal, refs = row.get("exact_text"), row.get("source_ids")
        start, end = row.get("start"), row.get("end")
        if (actual != key or type(actual[1]) is not int
                or not isinstance(literal, str) or not literal.strip()
                or type(start) is not int or type(end) is not int
                or not last_end <= start < end <= len(text)
                or text[start:end] != literal):
            raise ValueError("Missing, out-of-order or unlocated paragraph binding: " + str(key))
        if (not isinstance(refs, list) or any(not isinstance(x, str) for x in refs)
                or len(refs) != len(set(refs)) or not set(refs) <= expected[key]):
            raise ValueError("Paragraph source outside frozen task: " + str(key))
        bound[key] = (literal, set(refs))
        last_end = end
    for claim in ledger.get("claims", []):
        key = (claim.get("task_id"), claim.get("paragraph_index"))
        literal = claim.get("exact_text") or claim.get("claim_text")
        refs = claim.get("source_ids")
        if (type(key[1]) is not int or key not in bound or not isinstance(literal, str)
                or not literal.strip() or literal not in bound[key][0]
                or not isinstance(refs, list) or not refs
                or any(not isinstance(x, str) for x in refs)
                or not set(refs) <= bound[key][1]):
            raise ValueError("Claim not bound to a permitted paragraph and sources")
    return {"status": "task_binding_verified", "paragraph_count": len(rows),
            "task_sha256": hashes, "scope": "structural binding only; semantic coverage pending"}


def review_draft(packet_path, workspace, manuscript_path, claims_path, *, require_task_binding=False):
    workspace = Path(workspace)
    record = load(workspace / "writer_manifest.json")
    packet = load(packet_path)
    validate_packet(packet)
    def pending_language_review(errors):
        # Supersede any previous candidate request; do not consume stale language rules.
        save(workspace / "writing_review_request.json", {
            "packet_sha256": hash_file(packet_path),
            "manuscript_sha256": hash_file(manuscript_path),
            "claim_ledger_sha256": hash_file(claims_path),
            "gate": "G7", "formal_pass": False, "independent_review": "pending",
            "language_resource_status": "pending_recheck",
            "status": "technical_revisions_needed", "structural_errors": errors,
            "scope": "Language resource stop; no new style or scientific review performed",
        })
        return {"status": "technical_revisions_needed", "errors": errors,
                "language_resource_status": "pending_recheck"}

    try:
        profile, snapshot, rolemap, rules, _units, locks, _argument_rules, snapshot_warnings, resource_versions = language_resources()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return pending_language_review(["Language resource invalid: " + str(exc)])
    problems = []
    if record["resource_sha256"] != locks:
        problems.append("Language resource or writer mapping changed")
    if record.get("resource_snapshot_warnings") != snapshot_warnings:
        problems.append("Language snapshot inventory changed since prepare")
    if (record.get("language_resource_version") != resource_versions["v005"]
            or record.get("v003_resource_version") != resource_versions["v003"]
            or record.get("v004_resource_version") != resource_versions["v004"]
            or record.get("language_formal_resource_status") != snapshot["status"]):
        problems.append("Language resource version or formal status changed")
    if problems:
        return pending_language_review(problems)
    if record["packet_sha256"] != hash_file(packet_path):
        problems.append("Writing packet changed since prepare")
    if record["chapter_ids"] != [c["id"] for c in packet["chapters"]]:
        problems.append("Chapter structure changed")
    if record["mode"] != "exploratory":
        problems.append("Formal session cannot be submitted without a separate independent gate")
    text = Path(manuscript_path).read_text(encoding="utf-8-sig")
    claims_file = load(claims_path)
    draft_binding = {"status": "legacy_exploratory_unbound"}
    if require_task_binding:
        try:
            draft_binding = validate_draft_task_binding(packet, record, workspace, text, claims_file)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            problems.append("Draft task binding: " + str(exc))
            draft_binding = {"status": "pending_recheck", "reason": str(exc)}
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
        "edit_policy": "diagnostic_only",
        "manuscript_sha256": hash_file(manuscript_path),
        "claim_ledger_sha256": hash_file(claims_path),
        "semantic_equivalence": "not_verified",
        "protected_boundaries": [
            "research_conclusion", "source_attribution", "interview_and_quote_authenticity",
            "causal_strength", "research_unit", "temporal_scope", "evidence_uncertainty",
        ],
        "instruction": "Use v004 style and v005 qualitative task mapping, then compare before/after "
                       "meaning, research unit, temporal scope, source attribution, causal strength. "
                       "Do not change research conclusions, invent sources, interviews or quotations, "
                       "or promote association to causality. Do not rewrite evidence to satisfy stylistic taste. "
                       "Deterministic style findings are diagnostics only, not semantic equivalence proof."
    })
    save(workspace / "writing_review_request.json", {
        "manuscript_sha256": hash_file(manuscript_path),
        "claim_ledger_sha256": hash_file(claims_path),
        "packet_sha256": record["packet_sha256"],
        "draft_task_binding": draft_binding,
        "language_resource_version": resource_versions["v005"],
        "language_formal_resource_status": snapshot["status"],
        "resource_snapshot_warnings": snapshot_warnings,
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
            p.add_argument("--require-task-binding", action="store_true")
    args = cli.parse_args(argv)
    try:
        if args.command == "route":
            result = route(args.packet)
        elif args.command == "prepare":
            result = prepare(args.packet, args.workspace, args.mode)
        else:
            result = review_draft(args.packet, args.workspace, args.manuscript, args.claims,
                                  require_task_binding=args.require_task_binding)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") not in {"technical_revisions_needed"} else 3
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
