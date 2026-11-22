"""Frozen workload policy shared by project development runs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
CONTROL = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "00_项目控制/v005_第5版"
RUNS = CONTROL / "runs_dev"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def writing_policy(manifest):
    policy = manifest.get("writing_policy", {"deliverable": "plan", "explicit_full_paper": False})
    expected = ("full" if policy.get("explicit_full_paper") is True else "plan")
    if (policy.get("deliverable") != expected
            or ("writing_policy" in manifest and digest(policy) != manifest.get("writing_policy_sha256"))):
        raise ValueError("Invalid or changed experimental writing policy")
    return policy


def start(run_id, theme, *, full_paper=False):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", run_id):
        raise ValueError("Invalid experimental run ID")
    policy = load(CONTROL / "dev_profile.json")
    registry = load(PRODUCTION / "module_registry.json")
    if {m["module_id"] for m in registry["modules"]} != set(policy):
        raise ValueError("Experimental policy must account for every registered module")
    work = RUNS / run_id
    work.mkdir(parents=True, exist_ok=False)
    manifest = dict(run_id=run_id, theme=theme, run_mode="dev", formal_eligible=False,
                    scope="experimental", workload=policy, workload_sha256=digest(policy),
                    registry_sha256=digest(registry), stages=[
                        dict(module=m["module_id"], limits=policy[m["module_id"]], status="planned")
                        for m in registry["modules"]
                    ])
    manifest["writing_policy"] = {"deliverable": "full" if full_paper else "plan",
                                  "explicit_full_paper": full_paper}
    manifest["writing_policy_sha256"] = digest(manifest["writing_policy"])
    write(work / "run_manifest.json", manifest)
    return work


def verified_run(path):
    work = Path(path).resolve()
    manifest = load(work / "run_manifest.json")
    current = load(CONTROL / "dev_profile.json")
    legacy = {**current, "11": {key: value for key, value in current["11"].items()
                               if key != "topic_batches_per_phase"}}
    if (work.parent != RUNS.resolve() or work.name != manifest.get("run_id")
            or manifest.get("run_mode") != "dev"
            or manifest.get("formal_eligible") is not False
            or digest(manifest["workload"]) != manifest["workload_sha256"]
            or manifest["workload"] not in (current, legacy)
            or manifest["registry_sha256"] != digest(load(PRODUCTION / "module_registry.json"))):
        raise ValueError("Invalid or changed experiment contract")
    writing_policy(manifest)
    return manifest


def enforce(work, module, requested):
    """Check a planned workload before executing any expensive operation."""
    manifest = verified_run(work)
    limits = manifest["workload"][module]
    for key, units in requested.items():
        limit = limits[key]
        if type(limit) is bool:
            if type(units) is not bool or units and not limit:
                raise ValueError(f"{module}.{key} exceeds experimental permission")
        elif type(units) is not int or not 0 <= units <= limit:
            raise ValueError(f"{module}.{key} exceeds experimental workload: {limit}")
    return limits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("formal", "dev"), default="formal")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--theme")
    parser.add_argument("--full-paper", action="store_true",
                        help="Explicitly request full drafting for this new experimental run")
    stages = parser.add_mutually_exclusive_group()
    stages.add_argument("--topic", nargs=argparse.REMAINDER, metavar="COMMAND")
    stages.add_argument("--literature", choices=("start", "resume", "verify"))
    stages.add_argument("--writing-plan", type=Path, metavar="INPUT")
    args = parser.parse_args()
    if args.mode == "formal":
        if not args.theme or args.topic is not None or args.literature or args.writing_plan or args.full_paper:
            parser.error("Formal initialization requires --theme and accepts no experimental stages")
        return subprocess.call([sys.executable, "-B", str(PRODUCTION / "tools/project.py"),
                                "init", "--run-id", args.run_id, "--theme", args.theme])
    if args.topic is not None or args.literature or args.writing_plan:
        if args.full_paper:
            parser.error("--full-paper is only accepted when initializing a new experiment")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", args.run_id):
            parser.error("Invalid experimental run ID")
        work = RUNS / args.run_id
        manifest = verified_run(work)
        if args.theme is not None and args.theme != manifest["theme"]:
            parser.error("The theme is frozen at initialization")
        if args.writing_plan:
            script = ROOT / "07_三稿独立写作/v015_第15版/tools/writing_plan.py"
            return subprocess.call([sys.executable, "-B", str(script), "--dev-run", str(work),
                                    "--input", str(args.writing_plan)])
        if args.topic is not None:
            if not args.topic or args.topic[0] not in {"init", "status", "prepare", "allowance", "record"}:
                parser.error("Specify an experimental topic command")
            script = ROOT / "00_项目控制/v006_第6版/tools/topic_run.py"
            command, *options = args.topic
            return subprocess.call([sys.executable, "-B", str(script), command, args.run_id, *options],
                                   env={**os.environ, "AI_PAPER_DEV_RUN": str(work)})
        candidate = load(ROOT / "00_项目控制/v006_第6版/v3.1_Codex检索候选注册表.json")
        script = ROOT / candidate["modules"]["04"] / "tools/native_library.py"
        options = {"start": [], "resume": ["--resume"], "verify": ["--verify-only"]}
        return subprocess.call([sys.executable, "-B", str(script), "--profile", candidate["profile"],
                                "--work", str(work / "literature"), "--dev-run", str(work),
                                *options[args.literature]])
    if not args.theme:
        parser.error("Experimental initialization requires --theme")
    print(start(args.run_id, args.theme, full_paper=args.full_paper))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
