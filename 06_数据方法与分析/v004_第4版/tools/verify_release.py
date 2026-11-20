"""Run technical checks and retain logs. No actual research is certified."""
from __future__ import annotations

import json
import re
import subprocess
import sys

from common06 import MODULE, ROOT, environment, load, now, sha, write


def main():
    output = MODULE / "outputs"
    output.mkdir(exist_ok=True)
    py = [sys.executable, "-X", "utf8"]
    cases = [
        ("stage06_tests", py + ["-m", "unittest", "discover", "-s", str(MODULE / "tests"), "-v"], 0),
        ("stage04_05_regression", py + ["-m", "unittest", "discover", "-s", str(ROOT / "04_议题文献与现实/v004_第4版/tests"), "-v"], 0),
        ("control_regression", py + ["-m", "unittest", "discover", "-s", str(ROOT / "00_项目控制/v003_第3版/tests"), "-v"], 0),
        ("framework_validation", py + [str(ROOT / "00_项目控制/v003_第3版/tools/project.py"), "validate"], 0),
    ]
    records = []
    for name, argv, expected in cases:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        log = result.stdout + result.stderr
        (output / (name + ".log")).write_text(log, encoding="utf-8")
        match = re.search(r"Ran (\d+) tests?", log)
        record = {"name": name, "command": argv, "exit_code": result.returncode, "expected_exit_code": expected,
                  "passed": result.returncode == expected, "test_count": int(match[1]) if match else None, "log": name + ".log"}
        records.append(record)
        print(name + ": " + ("passed" if record["passed"] else "FAILED"), flush=True)
    run_id = "TEST_stage06_empty_" + now().replace("-", "").replace(":", "").replace("T", "_").split(".")[0].split("+")[0]
    command = py + [str(MODULE / "tools/stage06.py"), "run", "--input", str(MODULE / "templates/workflow_input.json"), "--run-id", run_id]
    smoke = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (output / "empty_cli_smoke.log").write_text(smoke.stdout + smoke.stderr, encoding="utf-8")
    try:
        result = json.loads(smoke.stdout)
        okay = smoke.returncode == 3 and result["status"] == "needs_review"
        gate = load(__import__("pathlib").Path(result["attempt_path"]) / "gate_report.json")
        okay = okay and gate["counts"]["results"] == 0
    except (ValueError, KeyError, OSError):
        okay = False
    records.append({"name": "empty_cli_smoke", "command": command, "exit_code": smoke.returncode, "expected_exit_code": 3,
                    "passed": okay, "run_id": run_id, "log": "empty_cli_smoke.log"})
    registered = load(ROOT / "00_项目控制/v003_第3版/module_registry.json")
    current = next(m for m in registered["modules"] if m["module_id"] == "06")
    records.append({"name": "registered_version", "passed": current["version"] == 2 and current["path"] == str(MODULE.relative_to(ROOT)).replace("\\", "/")})
    report = {"validated_at": now(), "technical_passed": all(r["passed"] for r in records), "checks": records,
              "environment": environment(), "business_gates_certified": False, "real_study_completed": False,
              "real_method_fulltexts_claimed": 0, "real_survey_cases_read": 0, "network_or_external_messages": False,
              "test_materials": "temporary TEST synthetic fixtures only",
              "files": [{"path": str(f.relative_to(ROOT)).replace("\\", "/"), "sha256": sha(f)}
                        for f in sorted(MODULE.rglob("*")) if f.is_file() and f.suffix in (".py", ".md", ".json", ".csv")
                        and not any(x in f.relative_to(MODULE).parts for x in ("outputs", "__pycache__"))]}
    write(output / "technical_validation.json", report)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    print(json.dumps({"technical_passed": report["technical_passed"], "tests": sum(r.get("test_count") or 0 for r in records),
                      "business_gates_certified": False}, ensure_ascii=False), flush=True)
    return 0 if report["technical_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
