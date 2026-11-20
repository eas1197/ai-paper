"""Record reproducible technical validation; no real research or external actions."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from runtime import MODULE, ROOT, load, now, registry_module, sha, write


def main():
    output = MODULE / "outputs"
    output.mkdir(exist_ok=True)
    py = [sys.executable, "-X", "utf8"]
    cases = [
        ("joint_tests", py + ["-m", "unittest", "discover", "-s", str(MODULE / "tests"), "-v"], 0),
        ("acquisition_tests", py + ["-m", "unittest", "discover", "-s", str(registry_module("11") / "tests"), "-v"], 0),
        ("stage06_compatibility", py + [str(MODULE / "tools/verify_stage06_compatibility.py")], 0),
        ("framework_regression", py + ["-m", "unittest", "discover", "-s", str(ROOT / "00_项目控制/v003_第3版/tests"), "-v"], 0),
        ("framework_validation", py + [str(ROOT / "00_项目控制/v003_第3版/tools/project.py"), "validate"], 0),
        ("skill_validation", py + ["C:/Users/hou/.codex/skills/.system/skill-creator/scripts/quick_validate.py", str(MODULE / "skills/research-evidence-hypotheses")], 0),
    ]
    records = []
    for name, argv, expected in cases:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        log = result.stdout + result.stderr
        (output / (name + ".log")).write_text(log, encoding="utf-8")
        count = re.search(r"Ran (\d+) tests?", log)
        records.append({"name": name, "command": argv, "exit_code": result.returncode,
                        "expected_exit_code": expected, "passed": result.returncode == expected,
                        "test_count": int(count.group(1)) if count else None, "log": name + ".log"})
        print(name + ": " + ("passed" if records[-1]["passed"] else "FAILED"), flush=True)
    run_id = "TEST_code_smoke_" + now().replace("-", "").replace(":", "").replace("T", "_").split(".")[0].split("+")[0]
    cli = py + [str(MODULE / "tools/research.py"), "run", "--input", str(MODULE / "templates/workflow_input.json"), "--run-id", run_id, "--stage", "both"]
    result = subprocess.run(cli, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (output / "empty_cli_smoke.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    try:
        smoke = json.loads(result.stdout)
        okay = result.returncode == 3 and [s["status"] for s in smoke["stages"]] == ["needs_review", "needs_review"]
    except (ValueError, KeyError):
        okay = False
    records.append({"name": "empty_cli_smoke", "command": cli, "exit_code": result.returncode,
                    "expected_exit_code": 3, "passed": okay, "log": "empty_cli_smoke.log", "run_id": run_id,
                    "meaning": "empty evidence must not pass; no selected real research topic"})
    files = sorted(set(MODULE.rglob("*.py")) | set((registry_module("05") / "tools").glob("*.py")) | set((registry_module("11") / "tools").glob("*.py")))
    report = {"validated_at": now(), "technical_passed": all(r["passed"] for r in records), "checks": records,
              "research_completed": False, "business_gates_certified": False,
              "real_abstracts_claimed": 0, "real_core_fulltexts_claimed": 0,
              "test_materials": "TEST fixtures in temporary directories only; no survey microdata",
              "network_or_external_messages": False, "live_cnki_download_verified": False,
              "stage06_compatibility_note": "06实现及断言未改；通过适配器将其硬编码旧04 TEST夹具指向当前04夹具，补齐新05必需研究连接字段。原旧夹具缺字段会被新关卡拒绝。",
              "code_files": [{"path": str(f.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(f)} for f in files]}
    write(output / "technical_validation.json", report)
    write(registry_module("05") / "outputs/technical_validation.json", {
        "validated_at": report["validated_at"], "technical_passed": report["technical_passed"],
        "joint_report": str((output / "technical_validation.json").relative_to(ROOT)).replace("\\", "/"),
        "joint_report_sha256": sha(output / "technical_validation.json"), "business_gates_certified": False})
    write(registry_module("11") / "outputs/technical_validation.json", {
        "validated_at": report["validated_at"], "technical_passed": report["technical_passed"],
        "joint_report": str((output / "technical_validation.json").relative_to(ROOT)).replace("\\", "/"),
        "joint_report_sha256": sha(output / "technical_validation.json"), "live_cnki_download_verified": False,
        "test_materials": "synthetic fixtures only"})
    return 0 if report["technical_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
