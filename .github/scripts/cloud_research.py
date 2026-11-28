"""Cloud checkpoint runner for the real v3.2 topic workflow.

No LLM/API calls or artificial academic approvals. Only small, non-sensitive
structured research records are persisted; raw interviews, web pages, PDFs,
credentials and request/response logs must use a separate approved store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "00_项目控制/v009_第9版/tools/staged_topic.py"
COMPARE = ROOT / "00_项目控制/v009_第9版/tools/event_protocol.py"
RUN_MODE = ROOT / "00_项目控制/v007_第7版/tools/run_mode.py"
RUNS = ROOT / "00_项目控制/v007_第7版/runs_dev"
MAX_FILES = 40
MAX_FILE_BYTES = 300_000
MAX_TOTAL_BYTES = 2_000_000
ALLOWED = {
    "run_manifest.json", "staged_topic.json", "reality.json",
    "event_comparison.json", "explanation_exchange.json", "issue_plan.json",
    "s08_topic.json", "cloud_run_status.json", "cloud_next_task.json",
    "merged_literature.json", "initial/theories.json", "initial/literature_matrix.json",
    "writing/writing_plan_review_request.json", "writing/论文写作方案.md",
}
PATH_PATTERNS = (
    re.compile(r"topic/(config|round-[0-9]+)\.json\Z"),
    re.compile(r"qualitative_framework/[a-zA-Z0-9_-]+/(framework|material_receipt|analysis_matrix(?:_[a-zA-Z0-9_-]+)?)\.json\Z"),
)
SENSITIVE_KEYS = re.compile(
    r"(^|_)(password|api_?key|secret|token|cookie|authorization|private_?key|"
    r"phone|email|身份证|手机号)(_|$)", re.I,
)
SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._-]{15,}|sk-[a-z0-9_-]{20,}|"
    r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----|"
    r"(?:api[_-]?key|password|secret|access[_-]?token)\s*[=:]\s*\S+)"
)


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".tmp")
    pending.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(path)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_runid(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value):
        raise ValueError("Invalid run ID")


def is_allowed(name):
    return name in ALLOWED or any(pattern.fullmatch(name) for pattern in PATH_PATTERNS)


def validate_public(record):
    """Fail closed on common credentials; no automated PII guarantee."""
    def visit(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if SENSITIVE_KEYS.search(str(key)):
                    raise ValueError("Potential secret key in public checkpoint")
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
        elif isinstance(node, str) and SECRET_VALUE.search(node):
            raise ValueError("Potential secret value in public checkpoint")
    visit(record)


def cmd(parts):
    process = subprocess.run([sys.executable, "-B", *map(str, parts)],
                             cwd=ROOT, capture_output=True, text=True, timeout=120)
    if process.returncode:
        raise RuntimeError(
            "Command failed: " + " ".join(map(str, parts[:3])) + "\n" +
            (process.stderr or process.stdout)[-3000:])
    return process.stdout.strip()


def run(args):
    validate_runid(args.run_id)
    work = RUNS / args.run_id
    status = {"run_id": args.run_id, "mode": "dev", "cloud_execution": True,
              "paid_model_calls": 0, "formal_eligible": False,
              "origin": "new_topic_from_reality_not_archived_freeze",
              "persisted_public_records_only": True}
    try:
        if not (work / "run_manifest.json").exists():
            cmd([STAGE, "init", args.run_id, "--mode", "dev", "--theme", args.theme])
            status["initialized"] = True
        else:
            status["initialized"] = False
            sys.path.insert(0, str(RUN_MODE.parent))
            import run_mode
            manifest = run_mode.verified_run(work)
            if manifest["theme"] != args.theme:
                raise ValueError("Cannot change the frozen theme on resume")
        current = load(work / "staged_topic.json")
        if current["status"] == "reality" and args.reality:
            evidence = load(Path(args.reality))
            validate_public(evidence)
            local = work / "cloud_reality_input.json"
            dump(local, evidence)
            cmd([STAGE, "reality", args.run_id, "--mode", "dev", "--report", local])
            local.unlink()
            current = load(work / "staged_topic.json")
            status["reality_recorded"] = True
        if current["status"] == "explanation_exchange" and args.events:
            input_packet = load(Path(args.events))
            validate_public(input_packet)
            local = work / "cloud_event_input.json"
            dump(local, input_packet)
            if not (work / "event_comparison.json").exists():
                cmd([COMPARE, "--dev-run", work, "--input", local])
            local.unlink()
            status["event_comparison_recorded"] = True
        current = load(work / "staged_topic.json")
        task = json.loads(cmd([STAGE, "prepare", args.run_id, "--mode", "dev"]))
        dump(work / "cloud_next_task.json", task)
        status["stage"] = current["status"]
        status["event_count"] = (load(work / "event_comparison.json")["event_count"]
                                 if (work / "event_comparison.json").exists() else 0)
        status["next_action"] = {
            "reality": "supply_verified_public_reality_packet",
            "explanation_exchange": "independent_critical_exchange_required_before_issue_positioning",
            "issue_positioning": "supply_independent_exchange_and_source_justified_issue_plan",
            "initial": "run_bounded_verified_literature_search",
        }.get(current["status"], "follow_staged_topic_gate")
        status["success"] = True
        print(json.dumps(status, ensure_ascii=False, indent=2))
    except Exception as exc:
        status.update(success=False, stage=(load(work / "staged_topic.json").get("status")
                     if (work / "staged_topic.json").is_file() else "init_failed"),
                     error=str(exc)[:2400])
        print(json.dumps(status, ensure_ascii=False, indent=2))
        raise
    finally:
        if work.is_dir():
            dump(work / "cloud_run_status.json", status)


def list_allowed(work):
    selected = []
    for item in work.rglob("*"):
        if not item.is_file() or item.is_symlink():
            continue
        relative = item.relative_to(work).as_posix()
        if is_allowed(relative):
            selected.append((relative, item))
    return sorted(selected)


def store(args):
    validate_runid(args.run_id)
    work = RUNS / args.run_id
    destination = Path(args.store).resolve() / "cloud_runs" / args.run_id
    destination.mkdir(parents=True, exist_ok=True)
    inputs = list_allowed(work)
    if not inputs or len(inputs) > MAX_FILES:
        raise ValueError("Unexpected checkpoint count")
    manifest = {"schema_version": 1, "run_id": args.run_id,
                "purpose": "public-source-metadata-only; no raw interviews or credentials",
                "files": {}}
    total = 0
    for relative, file in inputs:
        data = file.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError("Checkpoint exceeds single-file bound: " + relative)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Checkpoint total bytes exceeded")
        if file.suffix == ".json":
            validate_public(json.loads(data))
        elif SECRET_VALUE.search(data.decode("utf-8")):
            raise ValueError("Possible secret in markdown")
        target = destination / PurePosixPath(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest["files"][relative] = {"sha256": sha(data), "bytes": len(data)}
    dump(destination / "snapshot_manifest.json", manifest)
    print(json.dumps({"stored": len(inputs), "bytes": total,
                      "destination": str(destination)}, ensure_ascii=False))


def restore(args):
    validate_runid(args.run_id)
    source = Path(args.store).resolve() / "cloud_runs" / args.run_id
    manifest_path = source / "snapshot_manifest.json"
    if not manifest_path.is_file():
        print(json.dumps({"restored": 0, "reason": "fresh_run"}))
        return
    manifest = load(manifest_path)
    if manifest.get("run_id") != args.run_id or manifest.get("schema_version") != 1:
        raise ValueError("State identity/schema mismatch")
    if len(manifest["files"]) > MAX_FILES:
        raise ValueError("State file limit exceeded")
    work = RUNS / args.run_id
    if work.exists() and any(work.iterdir()):
        raise ValueError("Refusing restore over nonempty run directory")
    total = 0
    for name, descriptor in manifest["files"].items():
        if not is_allowed(name):
            raise ValueError("Unapproved restore path")
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("Path traversal")
        data = (source / p).read_bytes()
        total += len(data)
        if (len(data) != descriptor["bytes"] or
                sha(data) != descriptor["sha256"] or
                len(data) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES):
            raise ValueError("Checkpoint checksum/budget mismatch: " + name)
        if p.suffix == ".json":
            validate_public(json.loads(data))
        target = work / p
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    print(json.dumps({"restored": len(manifest["files"]),
                      "run_id": args.run_id}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "store", "restore"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--theme", default="城市共享单车停放与数字平台治理")
    parser.add_argument("--reality")
    parser.add_argument("--events")
    parser.add_argument("--store")
    args = parser.parse_args()
    if args.command in ("store", "restore") and not args.store:
        parser.error("--store is required for store and restore")
    {"run": run, "store": store, "restore": restore}[args.command](args)


if __name__ == "__main__":
    main()
