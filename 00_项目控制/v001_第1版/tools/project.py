"""第1版框架工具：不联网、不运行研究、不发投稿。Python 3.10+。"""
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


def validate(root=ROOT):
    root = Path(root)
    problems = []
    try:
        reg = registry(root)
        ordered_modules(reg)
        conf = config(root)
        if conf["submission"]["enabled"] or conf["runtime"]["network_execution_enabled"]:
            problems.append("第1版框架默认投稿和网络执行必须关闭")
        for name in ("AGENTS.md", "基础要求.md", "项目架构.md", "README.md"):
            if not (root / name).is_file():
                problems.append(f"缺根文件: {name}")
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
            "note": "通过仅代表框架结构有效，所有研究业务仍待执行。"}


def plan(root=ROOT):
    conf = config(root)
    return [{"module_id": m["module_id"], "path": m["path"],
             "depends_on": m["depends_on"],
             "enabled": not m["optional"] or conf["submission"]["enabled"],
             "business_status": "disabled" if m["optional"] else "planned"}
            for m in ordered_modules(registry(root))]


def init_run(run_id, theme, issue, question=None, root=ROOT):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("run_id须为1—64位英文数字、下划线或连字符，首位英文或数字")
    if not theme.strip() or not issue.strip():
        raise ValueError("主题和议题不能为空")
    root = Path(root).resolve()
    report = validate(root)
    if not report["framework_valid"]:
        raise ValueError(f"框架未通过验证: {report['problems']}")
    reg, conf = registry(root), config(root)
    work = contained(root, CONTROL.relative_to(ROOT) / "runs" / run_id)
    if work.exists():
        raise FileExistsError(f"运行已存在，拒绝覆盖: {run_id}")
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
    lock_entries = [{"path": str(f.relative_to(root)).replace("\\", "/"),
                     "sha256": digest(f)} for f in sorted(set(locked))]
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    stages = []
    for m in ordered_modules(reg):
        if m["module_id"] not in {f"{i:02d}" for i in range(1, 10)}:
            continue
        enabled = not m["optional"] or conf["submission"]["enabled"]
        stages.append({"stage_id": m["module_id"], "module_path": m["path"],
                       "module_version": m["version"],
                       "status": "planned" if enabled else "skipped", "attempt": 0,
                       "input_files": [], "output_files": [], "gate_report": None})
    data = {"schema_version": 1, "run_id": run_id, "created_at": now,
            "theme": theme, "issue": issue, "question": question,
            "scope": "framework_only", "status": "planned",
            "submission_enabled": conf["submission"]["enabled"],
            "stage_executor_implemented": False, "locked_files": lock_entries,
            "config_snapshot": conf, "stages": stages}
    work.mkdir(parents=True, exist_ok=False)
    (work / "run_manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    for stage in stages:
        if stage["status"] != "skipped":
            (work / f"stage_{stage['stage_id']}" / "attempt_001").mkdir(parents=True)
    return {"run_id": run_id, "path": str(work), "status": "planned",
            "research_executed": False}


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
    for cmd in ("validate", "plan", "status", "inventory"):
        sub.add_parser(cmd)
    init = sub.add_parser("init")
    init.add_argument("--run-id", required=True)
    init.add_argument("--theme", required=True)
    init.add_argument("--issue", required=True)
    init.add_argument("--question")
    args = parser.parse_args()
    try:
        if args.command == "validate":
            data = validate()
        elif args.command == "plan":
            data = plan()
        elif args.command == "inventory":
            data = inventory()
        elif args.command == "status":
            data = {"framework": validate(), "modules": plan(),
                    "implemented_commands": ["validate", "plan", "status", "init", "inventory"],
                    "business_executor": "not_implemented", "submission": "disabled"}
        else:
            data = init_run(args.run_id, args.theme, args.issue, args.question)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 1 if isinstance(data, dict) and data.get("framework_valid") is False else 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
