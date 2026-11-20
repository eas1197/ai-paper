"""第5版 TRACE 控制工具，提供项目校验、计划、初始化与只读接续查询。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTROL = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def contained(root, relative):
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"路径越出项目范围: {relative}")
    return candidate


def registry(root=ROOT):
    return read_json(Path(root) / CONTROL.relative_to(ROOT) / "module_registry.json")


def config(root=ROOT):
    return read_json(Path(root) / CONTROL.relative_to(ROOT) / "project_config.json")


def ordered_modules(reg):
    rows = reg["modules"]
    ids = [m["module_id"] for m in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("模块ID重复")
    index = {m["module_id"]: m for m in rows}
    visiting, done, order = set(), set(), []

    def visit(mid):
        if mid in visiting:
            raise ValueError(f"模块依赖成环: {mid}")
        if mid in done:
            return
        if mid not in index:
            raise ValueError(f"依赖不存在: {mid}")
        visiting.add(mid)
        for dep in index[mid]["depends_on"]:
            visit(dep)
        visiting.remove(mid)
        done.add(mid)
        order.append(index[mid])

    for mid in ids:
        visit(mid)
    return order


def validate(root=ROOT, *, check_trace_evidence=True):
    root = Path(root)
    problems = []
    try:
        reg = registry(root)
        ordered_modules(reg)
        conf = config(root)
        if conf["writing"]["mode"] not in ("single", "three_plus_review"):
            problems.append("不支持的写作模式")
        for mode in ("single", "three_plus_review"):
            ordered_modules(effective_registry(reg, mode))
        if conf["submission"]["enabled"] or conf["runtime"]["network_execution_enabled"]:
            problems.append("第2版框架默认投稿和网络执行必须关闭")
        for name in ("AGENTS.md", "基础要求.md", "项目架构.md", "README.md"):
            if not (root / name).is_file():
                problems.append(f"缺根文件: {name}")
        management = conf["management"]
        if management["workflow"] != "TRACE" or not isinstance(management["model_quota_recording_enabled"], bool):
            problems.append("TRACE 管理或额度记录配置不符")
        for field in ("current_state", "requirement_matrix"):
            if not contained(root, management[field]).is_file():
                problems.append(f"缺 TRACE 管理入口: {field}")
        with contained(root, management["requirement_matrix"]).open(encoding="utf-8-sig", newline="") as stream:
            seen = set()
            for row in csv.DictReader(stream):
                rid = row["requirement_id"]
                if not rid or rid in seen or not all(row.values()):
                    problems.append(f"TRACE 需求编号重复或字段欠缺: {rid}")
                seen.add(rid)
                for key in ("original_location", "evidence"):
                    location = contained(root, row[key].split("#", 1)[0])
                    if check_trace_evidence and not location.is_file():
                        problems.append(f"TRACE 需求定位缺失: {rid}/{key}")
            if not seen:
                problems.append("TRACE 需求矩阵为空")
        for m in reg["modules"]:
            base = contained(root, m["path"])
            if not re.fullmatch(r"v\d{3}_第\d+版", base.name):
                problems.append(f"版本命名不合规: {base.name}")
            mf = read_json(base / "manifest.json")
            if (mf["module_id"], mf["version"], mf["depends_on"]) != (
                m["module_id"], m["version"], m["depends_on"]
            ):
                problems.append(f"注册表/manifest不一致: {m['module_id']}")
            for name in ("模块说明.md", "CHANGELOG.md", "manifest.json"):
                if not (base / name).is_file():
                    problems.append(f"模块缺文件: {m['module_id']}/{name}")
            if not (base.parent / "版本索引.md").is_file():
                problems.append(f"模块缺版本索引: {m['module_id']}")
            if m.get("entrypoint") and not contained(base, m["entrypoint"]).is_file():
                problems.append(f"模块入口不存在: {m['module_id']}")
            for folder in mf["folders"]:
                if not contained(base, folder).is_dir():
                    problems.append(f"模块缺目录: {m['module_id']}/{folder}")
            for file in base.rglob("*.json"):
                if "runs" not in file.relative_to(base).parts:
                    read_json(file)
            for file in base.rglob("*.csv"):
                if "runs" in file.relative_to(base).parts:
                    continue
                with file.open(encoding="utf-8-sig", newline="") as stream:
                    reader = csv.reader(stream)
                    header = next(reader, [])
                    if not header or len(header) != len(set(header)):
                        problems.append(f"CSV表头为空或重复: {file.relative_to(root)}")
                    for line_no, row in enumerate(reader, 2):
                        if len(row) != len(header):
                            problems.append(f"CSV列数不匹配: {file.relative_to(root)}:{line_no}")
        shared = next(m for m in reg["modules"] if m["module_id"] == "10")
        sql = (root / shared["path"] / "knowledge.sql").read_text(encoding="utf-8")
        with sqlite3.connect(":memory:") as db:
            db.executescript(sql)
            if db.execute("PRAGMA foreign_key_check").fetchall():
                problems.append("SQLite外键检查失败")
            table_count = db.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
        schema = read_json(root / shared["path"] / "schemas/records.schema.json")
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            problems.append("记录Schema版本不正确")
    except (OSError, ValueError, KeyError, StopIteration, sqlite3.Error) as exc:
        problems.append(str(exc))
        table_count = 0
    return {"framework_valid": not problems, "problems": problems,
            "database_table_count": table_count, "research_gates_evaluated": False,
            "note": "通过表示框架校验有效，研究关卡以对应报告为准。"}


def effective_registry(reg, mode):
    if mode not in ("single", "three_plus_review"):
        raise ValueError(f"不支持的写作模式: {mode}")
    return {**reg, "modules": [
        {**m, "depends_on": list(dict.fromkeys(
            m["depends_on"] + m.get("conditional_dependencies", {}).get(mode, [])))}
        for m in reg["modules"]]}


def resource_bindings(root=ROOT):
    root = Path(root)
    result = []
    for mid, relative in config(root)["shared_resources"]["resource_manifests"].items():
        path = contained(root, relative)
        row = {"module_id": mid, "snapshot_manifest_path": relative,
               "resource_snapshot_id": None, "status": "not_built",
               "manifest_sha256": None, "files": []}
        if path.is_file():
            snapshot = read_json(path)
            if snapshot.get("module_id") != mid:
                raise ValueError(f"公共资源模块ID不一致: {mid}")
            row.update(resource_snapshot_id=snapshot.get("resource_snapshot_id"),
                       status=snapshot.get("status", "not_built"),
                       manifest_sha256=digest(path), files=snapshot.get("files", []))
            for item in row["files"]:
                file = contained(root, item["path"])
                if not file.is_file() or digest(file) != item["sha256"]:
                    row["status"] = "stale"
            if row["status"] == "passed" and (
                not row["resource_snapshot_id"] or not row["files"]
                or not snapshot.get("business_gate_report")
            ):
                row["status"] = "needs_review"
        result.append(row)
    return result


def plan(root=ROOT, writing_mode=None):
    conf = config(root)
    mode = writing_mode or conf["writing"]["mode"]
    resource_states = {r["module_id"]: r["status"] for r in resource_bindings(root)}
    rows = []
    for m in ordered_modules(effective_registry(registry(root), mode)):
        mid = m["module_id"]
        enabled = (mode == "three_plus_review" if mid == "08"
                   else conf["submission"]["enabled"] if mid == "09" else True)
        scope = m["execution_scope"]
        rows.append({"module_id": mid, "path": m["path"],
                     "depends_on": m["depends_on"], "enabled": enabled,
                     "execution_scope": scope, "writing_mode": mode,
                     "run_action": "bind_existing_snapshot" if scope == "shared_resource"
                                   else "plan_stage" if enabled else "skip",
                     "business_status": resource_states.get(mid, "planned") if enabled else "skipped"})
    return rows


def init_run(run_id, theme=None, issue=None, question=None, root=ROOT, writing_mode=None,
             topic_decision=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("run_id须为1—64位英文数字、下划线或连字符，首位英文或数字")
    root = Path(root).resolve()
    if theme is not None and not theme.strip():
        raise ValueError("主题不能为空")
    if topic_decision and any(value is not None for value in (theme, issue, question)):
        raise ValueError("--topic-decision 与主题、议题、问题参数分开使用")
    decision_file = None
    decision_hash = None
    if topic_decision:
        decision_file = contained(root, topic_decision)
        decision_hash = digest(decision_file)
        decision = read_json(decision_file)
        if not isinstance(decision, dict) or decision.get("status") != "selected_for_stage_04":
            raise ValueError("选题记录尚未选出可进入第4步的方向")
        theme, issue = decision.get("theme"), decision.get("issue")
        if not all(isinstance(value, str) and value.strip() for value in (theme, issue)):
            raise ValueError("选题记录须含有效主题和候选议题")
        question = decision.get("question")
        if question is not None and (not isinstance(question, str) or not question.strip()):
            raise ValueError("选题记录的候选问题须为有效文字")
        if digest(decision_file) != decision_hash:
            raise ValueError("读取期间选题记录发生变化")
    issue = issue.strip() if isinstance(issue, str) and issue.strip() else None
    report = validate(root, check_trace_evidence=False)
    if not report["framework_valid"]:
        raise ValueError(f"框架未通过验证: {report['problems']}")
    reg, conf = registry(root), config(root)
    mode = writing_mode or conf["writing"]["mode"]
    effective = effective_registry(reg, mode)
    conf["writing"]["mode"] = mode
    bindings = resource_bindings(root)
    run_store = conf.get("runtime", {}).get("run_store_root", str(CONTROL.relative_to(ROOT) / "runs"))
    work = contained(root, Path(run_store) / run_id)
    if work.exists():
        raise FileExistsError(f"运行已存在，拒绝覆盖: {run_id}")
    if theme is None:
        stage05 = next(m for m in reg["modules"] if m["module_id"] == "05")
        skill = Path(stage05["path"]) / "skills/social-science-topic-selection/SKILL.md"
        return {"run_id": run_id, "status": "topic_selection_required", "writing_mode": mode,
                "topic_owner": "research_executor", "issue_hint": issue, "question_hint": question,
                "instructions": f"{CONTROL.relative_to(ROOT).as_posix()}/选题与自动论文流程.md",
                "topic_selection_skill": skill.as_posix(),
                "research_executed": False}
    locked = [root / n for n in ("AGENTS.md", "基础要求.md", "项目架构.md")]
    for m in reg["modules"]:
        base = root / m["path"]
        locked.extend(base / name for name in ("manifest.json", "模块说明.md"))
        locked.extend(f for f in base.rglob("*.py")
                      if not {"runs", "__pycache__", "private"}.intersection(f.relative_to(base).parts))
        template_dir = base / "templates"
        if template_dir.is_dir():
            locked.extend(f for f in template_dir.rglob("*") if f.is_file())
        if m["module_id"] == "10":
            locked.append(base / "knowledge.sql")
            locked.extend(f for f in (base / "schemas").rglob("*") if f.is_file())
        if m["module_id"] == "06":
            locked.extend(f for f in (base / "方法库").rglob("*") if f.is_file())
    locked.extend([root / CONTROL.relative_to(ROOT) / "project_config.json",
                   root / CONTROL.relative_to(ROOT) / "module_registry.json"])
    for binding in bindings:
        file = contained(root, binding["snapshot_manifest_path"])
        if file.is_file():
            locked.append(file)
        locked.extend(contained(root, f["path"]) for f in binding["files"]
                      if contained(root, f["path"]).is_file())
    lock_entries = [{"path": str(f.relative_to(root)).replace("\\", "/"),
                     "sha256": digest(f)} for f in sorted(set(locked))]
    if decision_file:
        decision_lock = {"path": decision_file.relative_to(root).as_posix(), "sha256": decision_hash}
        lock_entries.append(decision_lock)
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    stages = []
    for m in ordered_modules(effective):
        if m["execution_scope"] != "research":
            continue
        mid = m["module_id"]
        enabled = (mode == "three_plus_review" if mid == "08"
                   else conf["submission"]["enabled"] if mid == "09" else True)
        stages.append({"stage_id": m["module_id"], "module_path": m["path"],
                       "module_version": m["version"],
                       "depends_on": m["depends_on"],
                       "status": "planned" if enabled else "skipped", "attempt": 0,
                       "input_files": [], "output_files": [], "gate_report": None})
    data = {"schema_version": 2, "run_id": run_id, "created_at": now,
            "theme": theme, "issue": issue, "question": question,
            "topic_state": {
                "issue_status": "candidate_from_user" if issue else "to_be_generated_in_stage_04",
                "issue_is_frozen": False,
                "question_status": "candidate_from_user" if question else "to_be_generated_after_issue",
                "candidate_issues": []},
            "scope": "framework_only", "status": "planned",
            "submission_enabled": conf["submission"]["enabled"],
            "writing_mode": mode,
            "draft_labels": conf["writing"]["draft_labels_by_mode"][mode],
            "shared_resource_bindings": bindings,
            "resources_recorded_as_passed": all(b["status"] == "passed" for b in bindings),
            "stage_executor_implemented": False, "locked_files": lock_entries,
            "config_snapshot": conf, "stages": stages}
    if decision_file:
        data["topic_state"].update(selection=decision_lock, issue_status="candidate_from_selection",
                                   question_status="candidate_from_selection" if question else
                                   "to_be_generated_after_issue")
    work.mkdir(parents=True, exist_ok=False)
    (work / "run_manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    for stage in stages:
        if stage["status"] != "skipped":
            (work / f"stage_{stage['stage_id']}" / "attempt_001").mkdir(parents=True)
    for label in data["draft_labels"]:
        (work / "stage_07" / "attempt_001" / "drafts" / label).mkdir(parents=True)
    return {"run_id": run_id, "path": str(work), "status": "planned",
            "writing_mode": mode, "draft_labels": data["draft_labels"],
            "research_executed": False}


def read_runs(root, run_store):
    store = contained(root, run_store)
    rows = []
    for folder in sorted(store.iterdir()) if store.is_dir() else ():
        manifest_path = folder / "run_manifest.json"
        if not manifest_path.is_file() or folder.name.startswith("TEST_"):
            continue
        manifest = read_json(manifest_path)
        stages = []
        for stage in sorted(folder.glob("stage_*")):
            attempts = sorted(
                (p for p in stage.glob("attempt_*") if p.is_dir()
                 and p.name.removeprefix("attempt_").isdigit()),
                key=lambda p: int(p.name.removeprefix("attempt_")),
            )
            if not attempts:
                continue
            latest = attempts[-1]
            gate = latest / "gate_report.json"
            previous = next((p / "gate_report.json" for p in reversed(attempts[:-1])
                             if (p / "gate_report.json").is_file()), None)
            stages.append({
                "stage_id": stage.name.removeprefix("stage_"),
                "latest_attempt": latest.relative_to(root).as_posix(),
                "recorded_gate_status": read_json(gate).get("status") if gate.is_file() else None,
                "gate_report": gate.relative_to(root).as_posix() if gate.is_file() else None,
                "gate_sha256": digest(gate) if gate.is_file() else None,
                "previous_gate_report": previous.relative_to(root).as_posix() if previous else None,
            })
        rows.append({
            "run_id": manifest.get("run_id", folder.name),
            "manifest": manifest_path.relative_to(root).as_posix(),
            "manifest_sha256": digest(manifest_path),
            "recorded_run_status": manifest.get("status"),
            "writing_mode": manifest.get("writing_mode"),
            "stages": stages,
        })
    return rows


def inventory(root=ROOT):
    paths = config(root)["sources"]
    result = {"scanned_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
              "read_only": True, "content_verified": False, "sources": {}}
    for key, raw in paths.items():
        path = Path(raw)
        row = {"path": raw, "exists": path.exists()}
        if path.exists() and key == "zotero_storage":
            row["pdf_file_count"] = sum(1 for _ in path.rglob("*.pdf"))
        if path.exists() and key == "education_data":
            row["dta_candidate_count"] = sum(1 for _ in path.rglob("*.dta"))
            row["sav_candidate_count"] = sum(1 for _ in path.rglob("*.sav"))
            original_base = path / "ziyuan" / "Stata14"
            row["cfps_original_candidates"] = [
                {"folder": str(folder), "dta_files": [str(f) for f in sorted(folder.glob("*.dta"))]}
                for folder in sorted(original_base.glob("CFPS*Stata")) if folder.is_dir()]
            row["cgss_known_candidates"] = [str(f) for f in [
                path / "CGSS2021.sav", path / "e-c/2021/CGSS2021.sav",
                path / "ziyuan/112564395452/CGSS2023.dta"] if f.exists()]
            row["warning"] = "文件名和存在性仅为线索；原始身份、内容、问卷、许可、波次均待验证。"
        if path.is_file():
            row["sha256"] = digest(path)
        result["sources"][key] = row
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("validate", "plan", "status", "inventory", "trace"):
        command = sub.add_parser(cmd)
        if cmd == "plan":
            command.add_argument("--writing-mode", choices=["single", "three_plus_review"])
    init = sub.add_parser("init")
    init.add_argument("--run-id", required=True)
    init.add_argument("--theme", help="可选主题；默认先生成选题任务")
    init.add_argument("--topic-decision", type=Path, help="项目内已完成的选题记录 JSON")
    init.add_argument("--issue", help="可选候选议题；不填则在第4步依据现实与理论线索生成")
    init.add_argument("--question")
    init.add_argument("--writing-mode", choices=["single", "three_plus_review"])
    args = parser.parse_args()
    try:
        if args.command == "validate":
            data = validate()
        elif args.command == "plan":
            data = plan(writing_mode=args.writing_mode)
        elif args.command == "inventory":
            data = inventory()
        elif args.command == "trace":
            conf = config()
            data = {"management": conf["management"],
                    "shared_resources": resource_bindings(),
                    "runs": read_runs(ROOT, conf["runtime"]["run_store_root"])}
        elif args.command == "status":
            data = {"framework": validate(), "modules": plan(),
                    "implemented_commands": ["validate", "plan", "status", "init", "inventory", "trace"],
                    "business_executor": "not_implemented", "submission": "disabled"}
        else:
            data = init_run(args.run_id, args.theme, args.issue, args.question,
                            writing_mode=args.writing_mode, topic_decision=args.topic_decision)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 1 if isinstance(data, dict) and data.get("framework_valid") is False else 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
