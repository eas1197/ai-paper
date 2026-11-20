"""定量社会学写作入口。离线准备证据包、接收作者稿件、验收并交付。"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from hashlib import sha256
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parents[1]
CONTROL = ROOT / "00_项目控制/v003_第3版"

# 与04—06使用同一个项目运行目录和锁。
with (CONTROL / "module_registry.json").open(encoding="utf-8-sig") as stream:
    SHARED = next(row["path"] for row in json.load(stream)["modules"] if row["module_id"] == "04")
sys.path.insert(0, str(ROOT / SHARED / "tools"))
from runtime import csv_write, file_lock, inside, integrity, load, now, run_directory, sha, value_hash, verify_locks, write

from inputs07 import collect, locked_output, stage_input
from manuscript07 import audit, read_checklist, review
from language07 import check_application, style_findings
from exemplars07 import writing_examples

VERSION = 10
CHECKLIST = MODULE / "templates/architecture_self_check.csv"


def plan(inputs, config=None):
    run = run_directory(inputs["run_id"])
    data = load(run / "run_manifest.json")
    errors, pack, _ = collect(run, data, MODULE, VERSION)
    return {"run_id": run.name, "stage_id": "07", "status": "needs_review" if errors else "ready",
            "errors": errors, "pack_id": value_hash(pack) if pack else None, "inputs": dict(inputs),
            "writing_mode": data.get("writing_mode"), "draft_labels": data.get("draft_labels"),
            "submission_enabled": False}


def prepare(planned):
    run = run_directory(planned["run_id"])
    data = load(run / "run_manifest.json")
    errors, pack, _ = collect(run, data, MODULE, VERSION)
    if errors or value_hash(pack) != planned["pack_id"]:
        raise ValueError(f"上游未就绪或已变化: {errors}")
    pack_id = planned["pack_id"]
    work = inside(run, Path("frozen") / pack_id)
    manifest = work / "frozen_manifest.json"
    if manifest.exists():
        if load(manifest) != pack:
            raise ValueError("已有冻结包内容不一致")
    else:
        write(manifest, pack)
    requirements = pack["writing_requirements"]
    rule_file = inside(ROOT, requirements["path"])
    rule_bytes = rule_file.read_bytes()
    if sha256(rule_bytes).hexdigest() != requirements["sha256"]:
        raise ValueError("文字要求已变化，须重新准备写作任务")
    task = {"pack_id": pack_id, "pack_manifest_sha256": sha(manifest),
            "labels": pack["draft_labels"], "writing_architecture": pack["writing_architecture"],
            "language_style": pack["language_style"], "style_materials": pack["style_materials"],
            "writing_exemplars": writing_examples(pack["writing_exemplars"], ROOT),
            "writing_requirements": dict(requirements, text=rule_bytes.decode("utf-8-sig")),
            "method_library_binding": pack["method_library_binding"], "upstream_manifests": pack["upstream_manifests"],
            "instruction": "按本任务的文字要求起草全文。读取锁定的写作架构、03语言手册和原文风格练习。先安排篇幅和论证任务，再据证据起草并核实每项事实、引用及数字。"
                           "逐节应用与当前论证任务相符的可用范例。范例提供结构和语言，研究事实与数字来自当前冻结证据。实证段以研究对象、比较、量级和条件直接展开，避免在正文转述统计学提醒。"
                           "三稿模式分别在独立上下文写作，各稿只读同一冻结包。"}
    task_path = work / "writing_task.json"
    if not task_path.exists():
        write(task_path, task)
    return dict(planned, frozen_manifest=str(manifest), writing_task=str(task_path))


def output_draft(draft, work, source_dir, label, pack, pack_id, pack_digest, bundles, profile):
    path = inside(ROOT, source_dir / draft["manuscript"])
    manuscript = path.read_bytes()
    metadata = {k: v for k, v in draft.items() if k not in ("review", "manuscript")}
    subject = {"pack_id": pack_id, "label": label, "manuscript_sha256": sha(path), "draft": metadata}
    errors = []
    if draft.get("pack_id") != pack_id or not draft.get("authorship"):
        errors.append("稿件须标明作者工具或人工起草信息，并锁定同一证据包")
    if pack["writing_mode"] == "three_plus_review" and (
            not draft.get("context_id") or draft.get("other_drafts_accessed") is not False):
        errors.append("三稿需提供各自独立上下文与未读取他稿的声明")
    text = manuscript.decode("utf-8-sig").replace("\r\n", "\n")
    counts, claims = audit(draft, text, profile, bundles, read_checklist(CHECKLIST), errors,
                           eligible_literature=pack["eligible_literature_ids"])
    notes = draft.get("language_review", {})
    check_application(notes, text, set(pack["style_ids"]), errors)
    findings = style_findings(text)
    errors.extend(f"第{hit['line']}行 {hit['rule_id']}：{hit['match']}。{hit['action']}" for hit in findings)
    signoff = load(inside(ROOT, source_dir / draft["review"])) if draft.get("review") else {}
    digest = review(subject, signoff, errors)
    output = work / "drafts" / label
    output.mkdir(parents=True)
    (output / "manuscript.md").write_bytes(manuscript)
    write(output / "writing_plan.json", counts)
    write(output / "draft_input.json", metadata)
    write(output / "language_review.json", {"application": notes, "findings": findings})
    write(output / "quality_review_request.json", {
        "content_sha256": digest, "decision": "pending", "reviewer": None, "reviewed_at": None,
        "assessment": None, "technical_errors": [e for e in errors if not e.startswith("需要研究复核")],
        "instruction": "核实所有事实句、数字、样本与因果措辞，检查表图、摘要与结论的证据一致性，给出实质评语。"
    })
    if signoff:
        write(output / "quality_review.json", signoff)
    checks = [dict(row, **{k: draft.get("checks", {}).get(row["check_id"], {}).get(k, row[k])
                           for k in ("status", "evidence_or_note")}) for row in read_checklist(CHECKLIST)]
    csv_write(output / "architecture_self_check.csv", checks, list(checks[0]))
    csv_write(output / "self_check.csv", [
        {"draft_id": label, "check_id": f"G7-{i:02d}", "category": "写作验收", "finding": e, "status": "needs_review"}
        for i, e in enumerate(errors, 1)
    ] or [{"draft_id": label, "check_id": "G7", "category": "写作验收", "finding": "技术检查及绑定的实质复核通过", "status": "passed"}],
        ("draft_id", "check_id", "category", "location", "evidence_id", "result_id", "finding", "status"))
    csv_write(output / "claims.csv", [dict(row, draft_id=label, verification_status="accepted" if not errors else "pending_review")
                                     for row in claims],
        ("claim_id", "draft_id", "sentence_id", "claim_text", "claim_type", "paper_ids", "evidence_ids",
         "result_ids", "scope_limit", "verification_status"))
    write(output / "draft_manifest.json", {
        "schema_version": 1, "run_id": pack["run_id"], "draft_id": label, "writing_mode": pack["writing_mode"],
        "pack_id": pack_id, "pack_manifest_sha256": pack_digest, "writing_architecture": pack["writing_architecture"],
        "context_id": draft.get("context_id"), "other_drafts_accessed": draft.get("other_drafts_accessed"),
        "authorship": draft.get("authorship"), "model": draft.get("model"), "prompt_version": draft.get("prompt_version"),
        "output_files": [file_lock(p) for p in sorted(output.iterdir())],
        "status": "needs_review" if errors else "passed",
    })
    return {"draft_id": label, "errors": errors, "body_characters": counts["body_characters"]}


def record(run, data, work, manifest):
    manifest["finished_at"] = now()
    manifest["output_files"] = [file_lock(path) for path in sorted(work.rglob("*"))
                                if path.is_file() and path != work / "stage_manifest.json"]
    path = work / "stage_manifest.json"
    write(path, manifest)
    stage = next(row for row in data["stages"] if row["stage_id"] == "07")
    stage.update(status=manifest["status"], attempt=manifest["attempt"], manifest_path=str(path),
                 manifest_sha256=sha(path), gate_report=str(work / "gate_report.json"))
    stage.pop("stale_reason", None)
    for row in data["stages"]:
        if row["stage_id"] in ("08", "09") and row["status"] not in ("planned", "skipped", "stale"):
            row.update(status="stale", stale_reason="stage_07 attempt changed")
    data["updated_at"] = now()
    data["implemented_stage_executors"] = sorted(set(data.get("implemented_stage_executors", [])) | {"07"})
    write(run / "run_manifest.json", data)
    with (run / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": now(), "stage": "07", "attempt": manifest["attempt"],
                                 "status": manifest["status"]}, ensure_ascii=False) + "\n")


def execute(planned, context=None):
    if planned.get("stage_id") != "07" or planned.get("status") != "ready":
        raise ValueError("第7步计划尚未就绪")
    run = run_directory(planned["run_id"])
    lock = run / ".research.lock"
    with lock.open("x", encoding="utf-8") as stream:
        json.dump({"pid": os.getpid(), "created_at": now()}, stream)
    try:
        return execute_locked(planned, run)
    finally:
        lock.unlink(missing_ok=True)


def execute_locked(planned, run):
    data = load(run / "run_manifest.json")
    errors, pack, bundles = collect(run, data, MODULE, VERSION)
    pack_id = planned["pack_id"]
    if errors or value_hash(pack) != pack_id:
        raise ValueError(f"上游未就绪或已变化: {errors}")
    frozen = run / "frozen" / pack_id / "frozen_manifest.json"
    if load(frozen) != pack:
        raise ValueError("冻结包不匹配，先运行 prepare")
    input_path = inside(ROOT, planned["inputs"]["input"])
    input_lock = file_lock(input_path)
    request = load(input_path)
    drafts = request["drafts"]
    if set(drafts) != set(pack["draft_labels"]):
        raise ValueError(f"本次运行只接受指定稿件标签: {pack['draft_labels']}")
    if pack["writing_mode"] == "three_plus_review":
        contexts = {d.get("context_id") for d in drafts.values()}
        paths = {inside(ROOT, input_path.parent / d["manuscript"]) for d in drafts.values()}
        if len(contexts) != 3 or None in contexts or len(paths) != 3 or len({sha(p) for p in paths}) != 3:
            raise ValueError("三稿须分别提供独立上下文标识与独立稿件")
    locks = [input_lock, file_lock(frozen)] + pack["input_files"] + [
        file_lock(inside(ROOT, input_path.parent / draft[key]))
        for draft in drafts.values() for key in ("manuscript", "review") if draft.get(key)
    ]
    stage = run / "stage_07"
    numbers = [int(p.name[8:]) for p in stage.glob("attempt_*") if re.fullmatch(r"attempt_\d+", p.name)]
    number = max(numbers, default=0) + 1
    work = stage / f"attempt_{number:03d}"
    work.mkdir(parents=True)
    manifest = {"schema_version": 1, "stage_id": "07", "run_id": run.name, "module_version": VERSION,
                "attempt": number, "started_at": now(), "status": "running", "gate_report": "gate_report.json",
                "input_files": locks, "config_sha256": value_hash(data["config_snapshot"]),
                "root_requirements_sha256": sha(ROOT / "基础要求.md"),
                "upstream_manifests": list(pack["upstream_manifests"].values()), "pack_id": pack_id,
                "writing_mode": pack["writing_mode"], "seed": pack["seed"], "environment": {"python": sys.version},
                "submission_enabled": False}
    report = {"gate": "G7", "run_id": run.name, "status": "running", "drafts": [], "errors": [],
              "writing_mode": pack["writing_mode"], "business_quality_automatic": False}
    write(work / "stage_manifest.json", manifest)
    try:
        profile = load(inside(ROOT, pack["writing_architecture"]["profile_path"]))
        report["drafts"] = [output_draft(drafts[label], work, input_path.parent, label, pack, pack_id,
                                         sha(frozen), bundles, profile) for label in pack["draft_labels"]]
        changed = verify_locks(locks)
        report["errors"] = [e for row in report["drafts"] for e in row["errors"]]
        if changed:
            report["errors"].append(f"运行时输入变动: {changed}")
        report["status"] = "stale" if changed else "needs_review" if report["errors"] else "passed"
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report.update(status="failed", errors=[f"{type(exc).__name__}: {exc}"])
    finally:
        if report["status"] == "running":
            report.update(status="failed", errors=["第7步中断"])
        manifest["status"] = report["status"]
        write(work / "gate_report.json", report)
        record(run, data, work, manifest)
    return dict(report, attempt_path=str(work))


def validate(artifacts, evidence=None):
    work = inside(ROOT, artifacts)
    manifest = load(work / "stage_manifest.json")
    run = run_directory(manifest["run_id"])
    data = load(run / "run_manifest.json")
    current = next(row for row in data["stages"] if row["stage_id"] == "07")
    path, mf = stage_input(run, current, "07")
    if work != path.parent:
        raise ValueError("只允许交付当前有效的第7步稿件")
    return load(locked_output(work, mf, "gate_report.json"))


def export(artifacts, target_profile=None):
    report = validate(artifacts)
    work = inside(ROOT, artifacts)
    mode = report["writing_mode"]
    manifest = load(work / "stage_manifest.json")
    outputs = manifest["output_files"]
    run = run_directory(manifest["run_id"])
    frozen = run / "frozen" / manifest["pack_id"] / "frozen_manifest.json"
    return {"status": "passed", "destination": "single_delivery" if mode == "single" else "stage_08_review",
            "submission_enabled": False, "frozen_manifest": str(frozen),
            "analysis_manifest": load(frozen)["upstream_manifests"]["06"], "files": outputs}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    for command in ("status", "prepare", "run"):
        sub = commands.add_parser(command)
        sub.add_argument("--run-id", required=True)
        if command == "run":
            sub.add_argument("--input", required=True)
    for command in ("validate", "export"):
        commands.add_parser(command).add_argument("--attempt", required=True)
    args = cli.parse_args(argv)
    try:
        if args.command in ("validate", "export"):
            result = (validate if args.command == "validate" else export)(args.attempt)
        else:
            planned = plan({"run_id": args.run_id, "input": getattr(args, "input", None)})
            result = planned
            if planned["status"] == "ready":
                if args.command == "prepare":
                    result = prepare(planned)
                elif args.command == "run":
                    result = execute(planned)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in ("passed", "ready") else 3
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
