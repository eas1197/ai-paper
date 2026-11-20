"""04/05 shared runtime. Standard library only; no network or shell commands."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "00_项目控制/v003_第3版"
GAP_TYPES = ("reality_theory_tension", "same_level_gap", "scope_change", "relation_revision")
CHECKS = ("abstraction", "unit", "role", "time", "dimension")


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def value_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"路径越界: {relative}")
    return path


def input_path(base, raw):
    return (Path(base) / raw).resolve()


def present(value):
    return value is not None and value != "" and value != [] and value != {} and value not in ("unknown", "未知", "pending")


def valid_date(value, as_of=None):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        ceiling = datetime.fromisoformat(as_of).date() if as_of else datetime.now(timezone(timedelta(hours=8))).date()
        return parsed.date() <= ceiling
    except (TypeError, ValueError):
        return False


def require_fields(row, fields, label, errors):
    for field in fields:
        if not present(row.get(field)):
            errors.append(f"{label}: 缺少 {field}")


def indexed(rows, key, errors):
    result = {}
    for row in rows:
        identity = row.get(key)
        if not identity or identity in result:
            errors.append(f"{key}为空或重复: {identity}")
        else:
            result[identity] = row
    return result


def refs(ids, index, label, errors, required=True):
    if not isinstance(ids, list) or (required and not ids):
        errors.append(f"{label}: 必须是非空ID列表" if required else f"{label}: 必须是ID列表")
        return []
    result = []
    for identity in ids:
        if identity not in index:
            errors.append(f"{label}: 悬空引用 {identity}")
        else:
            result.append(index[identity])
    return result


def csv_write(path, rows, headers):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def registry_module(mid):
    reg = load(CONTROL / "module_registry.json")
    entry = next(m for m in reg["modules"] if m["module_id"] == mid)
    return inside(ROOT, entry["path"])


def load_stage(mid):
    base = registry_module(mid)
    file = base / "tools" / f"stage{mid}.py"
    spec = importlib.util.spec_from_file_location(f"research_stage_{mid}", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def file_lock(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def verify_locks(entries):
    changed = []
    for entry in entries:
        path = Path(entry["path"])
        if not path.is_file() or sha(path) != entry["sha256"]:
            changed.append(str(path))
    return changed


def make_plan(stage, inputs, config=None):
    config = dict(config or {})
    # Targets may increase, never silently decrease.
    if config.get("abstract_target", 100) < 100 or config.get("core_target", 25) < 25:
        raise ValueError("不得降低100摘要/25核心全文目标")
    run_id = inputs.get("run_id", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("run_id须为1—64位英文数字、下划线或连字符")
    base = Path(inputs.get("base_dir", ROOT)).resolve()
    normalized = dict(inputs, base_dir=str(base))
    locks = []
    for name in ("AGENTS.md", "基础要求.md", "项目架构.md"):
        locks.append(file_lock(ROOT / name))
    locks.extend(file_lock(CONTROL / n) for n in ("module_registry.json", "project_config.json"))
    for mid in ("04", "05", "10", "11"):
        folder = registry_module(mid)
        locks.append(file_lock(folder / "manifest.json"))
        locks.append(file_lock(folder / "模块说明.md"))
        locks.extend(file_lock(f) for f in sorted((folder / "tools").glob("*.py")))
        locks.extend(file_lock(f) for f in sorted((folder / "templates").glob("*")) if f.is_file())
        locks.extend(file_lock(f) for f in sorted((folder / "skills").rglob("SKILL.md")))
        if mid == "10":
            locks.append(file_lock(folder / "knowledge.sql"))
            locks.extend(file_lock(f) for f in sorted((folder / "schemas").glob("*.json")))
    for key in ("annotations", "quality_review", "upstream", "metadata_evidence"):
        if inputs.get(key):
            normalized[key] = str(input_path(base, inputs[key]))
            locks.append(file_lock(normalized[key]))
    for source in inputs.get("literature", []):
        locks.append(file_lock(input_path(base, source["path"])))
    return {"schema_version": 1, "stage_id": stage, "run_id": run_id, "inputs": normalized,
            "config": config, "seed": config.get("seed", 20261114),
            "created_at": now(), "input_files": locks,
            "operations": ["import_and_archive", "reasoning_tasks", "compile_reviewed_records", "validate", "export"]}


def run_directory(run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("非法run_id")
    conf = load(CONTROL / "project_config.json")
    root = inside(ROOT, conf["runtime"]["run_store_root"])
    return inside(root, run_id)


@contextmanager
def attempt(plan, module_version):
    changed = verify_locks(plan["input_files"])
    if changed:
        raise ValueError(f"计划输入已变化，重新plan: {changed}")
    run = run_directory(plan["run_id"])
    run.mkdir(parents=True, exist_ok=True)
    lock = run / ".research.lock"
    # No automatic lock stealing. A live concurrent process may own it.
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, canonical({"pid": os.getpid(), "created_at": now()}))
    os.close(fd)
    work = None
    manifest = None
    try:
        stage_root = run / f"stage_{plan['stage_id']}"
        stage_root.mkdir(exist_ok=True)
        nums = [int(p.name[8:]) for p in stage_root.glob("attempt_*") if re.fullmatch(r"attempt_\d+", p.name)]
        number = max(nums, default=0) + 1
        work = stage_root / f"attempt_{number:03d}"
        work.mkdir(exist_ok=False)
        write(work / "plan.json", plan)
        manifest = {"record_type": "stage_manifest", "schema_version": 1, "run_id": plan["run_id"],
                    "stage_id": plan["stage_id"], "attempt": number, "module_version": module_version,
                    "status": "running", "started_at": now(), "config_sha256": value_hash(plan["config"]),
                    "root_requirements_sha256": sha(ROOT / "基础要求.md"), "input_files": plan["input_files"],
                    "upstream_manifests": [], "output_files": [], "gate_report": "gate_report.json",
                    "environment": {"python": sys.version, "platform": platform.platform()},
                    "seed": plan["seed"], "model": None, "prompt_version": "04-05-v1", "deviations": []}
        write(work / "stage_manifest.json", manifest)
        yield work, manifest
        changed = verify_locks(manifest["input_files"])
        if changed:
            manifest["status"] = "stale"
            manifest["deviations"].append(f"执行期间输入变化: {changed}")
    except Exception as exc:
        if manifest is not None:
            manifest["status"] = "failed"
            manifest["deviations"].append(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        try:
            if manifest is not None:
                manifest["finished_at"] = now()
                manifest["output_files"] = [{"path": str(p.relative_to(work)).replace("\\", "/"), "sha256": sha(p)}
                                            for p in sorted(work.rglob("*")) if p.is_file() and p.name != "stage_manifest.json"]
                write(work / "stage_manifest.json", manifest)
                update_run(run, work, manifest)
        finally:
            lock.unlink(missing_ok=True)


def update_run(run, work, stage):
    path = run / "run_manifest.json"
    data = load(path) if path.exists() else {"schema_version": 2, "run_id": stage["run_id"], "stages": [], "scope": "research_04_05"}
    rows = data.setdefault("stages", [])
    row = next((s for s in rows if s["stage_id"] == stage["stage_id"]), None)
    if row is None:
        row = {"stage_id": stage["stage_id"]}
        rows.append(row)
    row.update(status=stage["status"], attempt=stage["attempt"], manifest_path=str(work / "stage_manifest.json"),
               manifest_sha256=sha(work / "stage_manifest.json"), gate_report=str(work / "gate_report.json"))
    # A new upstream attempt invalidates existing dependent results, even if it fails.
    downstream = ("05", "06", "07", "08", "09") if stage["stage_id"] == "04" else ("06", "07", "08", "09")
    for item in rows:
        if item["stage_id"] in downstream and item.get("status") not in ("planned", "skipped", "stale"):
            item["status"] = "stale"
            item["stale_reason"] = f"stage_{stage['stage_id']} attempt changed"
    data["implemented_stage_executors"] = ["04", "05"]
    data["updated_at"] = now()
    write(path, data)
    with (run / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": now(), "stage": stage["stage_id"], "attempt": stage["attempt"], "status": stage["status"]}, ensure_ascii=False) + "\n")


def integrity(work, check_inputs=True):
    work = Path(work).resolve()
    mf = load(work / "stage_manifest.json")
    errors = []
    if not mf.get("output_files"):
        errors.append("运行尚未完成或manifest没有产物锁")
    for entry in mf["output_files"]:
        path = inside(work, entry["path"])
        if not path.is_file() or sha(path) != entry["sha256"]:
            errors.append(f"产物已变化: {entry['path']}")
    if check_inputs:
        errors.extend(f"输入已变化: {p}" for p in verify_locks(mf["input_files"]))
    for entry in mf.get("upstream_manifests", []):
        p = Path(entry["path"])
        if not p.is_file() or sha(p) != entry["sha256"]:
            errors.append("上游manifest已变化")
        elif p.parent != work:
            errors.extend(integrity(p.parent, check_inputs))
    return errors


def signoff(bundle, review, errors):
    scope = value_hash(bundle)
    accepted = (isinstance(review, dict) and review.get("decision") == "accepted"
                and review.get("content_sha256") == scope and present(review.get("reviewer"))
                and valid_date(review.get("reviewed_at")) and present(review.get("assessment")))
    if not accepted:
        errors.append("需要研究复核：quality_review须绑定content_sha256，填写审查人、日期和判断依据")
    return scope


def finalize(work, manifest, bundle, report, templates):
    write(work / "bundle.json", bundle)
    write(work / "gate_report.json", report)
    write(work / "quality_review_request.json", {"content_sha256": value_hash(bundle), "decision": "pending",
          "reviewer": None, "reviewed_at": None, "assessment": None,
          "notice": "技术检查不证明实际阅读或理论质量。复核后另存文件并在下一attempt输入quality_review。"})
    for filename, key in templates.items():
        header_file = MODULE / "templates" / filename
        if not header_file.exists():
            header_file = registry_module("05") / "templates" / filename
        with header_file.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream))
        rows = bundle.get(key, [])
        if filename == "core25.csv":
            papers = {p["paper_id"]: p for p in bundle["papers"]}
            enriched = []
            for selection in rows:
                p = papers.get(selection.get("paper_id"), {})
                valid = p.get("paper_id") in report.get("valid_fulltext_ids", [])
                enriched.append(dict(selection, fulltext_path=p.get("fulltext_path"), fulltext_sha256=p.get("fulltext_sha256"),
                                     fulltext_verified=valid, read_status="fulltext_read" if valid else "not_verified"))
            rows = enriched
        csv_write(work / filename, rows, header)
    manifest["status"] = report["status"]
    (work / "阅读入口.md").write_text(f"# 第{manifest['stage_id']}步运行\n\n状态：{report['status']}。\n\n内容摘要哈希：`{value_hash(bundle)}`。\n\n"
        + "\n".join(f"- {x}" for x in report["errors"]) + "\n\n详见bundle.json、gate_report.json、reasoning_tasks.json和来源文件仓。\n", encoding="utf-8")


def export_bundle(artifacts, target_profile=None):
    """Export only a current, passed, integrity-checked stage; retain original archive."""
    work = Path(artifacts).resolve()
    problems = integrity(work)
    mf = load(work / "stage_manifest.json")
    run = load(work.parents[1] / "run_manifest.json")
    current = next(s for s in run["stages"] if s["stage_id"] == mf["stage_id"])
    if current["attempt"] != mf["attempt"] or current["status"] != "passed":
        problems.append("只允许导出当前passed attempt；旧attempt不可用于新研究")
    if mf["status"] != "passed" or load(work / "gate_report.json")["status"] != "passed":
        problems.append("研究关卡未通过")
    if problems:
        raise ValueError("; ".join(problems))
    # Destination is always under the run, cannot target Zotero or arbitrary external paths.
    dest = work.parents[1] / "exports" / f"stage_{mf['stage_id']}_attempt_{mf['attempt']:03d}"
    dest.mkdir(parents=True, exist_ok=False)
    bundle = load(work / "bundle.json")
    write(dest / "handoff.json", {"schema_version": 1, "run_id": mf["run_id"], "stage_id": mf["stage_id"],
          "attempt_path": str(work), "manifest_sha256": sha(work / "stage_manifest.json"),
          "bundle_sha256": sha(work / "bundle.json"), "profile": target_profile or "next_stage",
          "bundle": bundle, "artifact_files": mf["output_files"],
          "redistribution": "local_only; original access and share_scope apply"})
    return {"path": str(dest / "handoff.json")}
