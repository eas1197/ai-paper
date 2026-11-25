"""Restore the original K03 or K06 archive into a fresh, isolated directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "community_canteen_access_20261125"
INIT_LOG = "a6e3e7f3bd334ba21f11dfb37ff68f54b29978e2e2bdf78ed769be2e72b1f5db"
REALITY_LOG = "bdaf35a5b3fbf04f8fa9982eb58fdf76bcbe2a2a8955ad9fa8a704a8a8d4e9c9"


def restore(checkpoint, destination, *, archive_root=ROOT / "handoff_runs"):
    expected_status = {"K03": "reality", "K06": "explanation_exchange"}[checkpoint]
    destination = Path(destination)
    if destination.is_symlink():
        raise ValueError("Restore destination cannot be a symbolic link")
    destination = destination.resolve()
    if destination.is_relative_to(ROOT):
        raise ValueError("Choose an isolated destination outside the repository")
    hashes = json.loads((archive_root / "manifest.json").read_bytes())["files"]
    base = ("run_manifest.json", "staged_topic.json", f"runtime_log/{INIT_LOG}.json")
    mapping = [(name, name) for name in base]
    if checkpoint == "K06":
        prefix = "checkpoints/K06/"
        for name in ("staged_topic.json", "reality.json", f"runtime_log/{REALITY_LOG}.json"):
            mapping.append((prefix + name, name))
        report = prefix + "submitted_reality_report.json"
        mapping.append((report, f"submitted_stage_reports/reality/{hashes[f'{RUN_ID}/{report}']}.bin"))
    files = {}
    for source, output in mapping:
        archive_path = f"{RUN_ID}/{source}"
        data = (archive_root / archive_path).read_bytes()
        if hashlib.sha256(data).hexdigest() != hashes[archive_path]:
            raise ValueError(f"Archive hash mismatch: {archive_path}")
        files[output] = data
    state = json.loads(files["staged_topic.json"])
    manifest = json.loads(files["run_manifest.json"])
    if (state["status"] != expected_status or state["run_id"] != RUN_ID
            or manifest["run_id"] != RUN_ID or manifest["run_mode"] != "dev"
            or state["formal_eligible"] is not False or manifest["formal_eligible"] is not False):
        raise ValueError("Archived original checkpoint identity or state mismatch")

    destination.mkdir()
    work = destination / RUN_ID
    try:
        for name, data in files.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if path.read_bytes() != data:
                raise OSError(f"Restored bytes differ: {name}")
        if checkpoint == "K06":
            original = ROOT / "00_项目控制/v009_第9版/tools"
            script = ("import sys; from pathlib import Path; "
                      "sys.path.insert(0, sys.argv[1]); "
                      "from staged_topic import load, load_reality; "
                      "work = Path(sys.argv[2]); load_reality(work, load(work / 'staged_topic.json'))")
            subprocess.run([sys.executable, "-B", "-c", script, str(original), str(work)], check=True)
    except (OSError, ValueError, subprocess.SubprocessError):
        shutil.rmtree(destination)
        raise
    return {"workspace": str(work), "checkpoint": checkpoint, "original_status": expected_status,
            "file_count": len(files), "formal_eligible": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", choices=("K03", "K06"))
    parser.add_argument("destination", type=Path, help="New isolated directory with an existing parent")
    args = parser.parse_args()
    try:
        print(json.dumps(restore(args.checkpoint, args.destination)))
    except (KeyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"Checkpoint restore failed: {exc}\n")
