import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2] / "handoff_runs"
manifest = json.loads((root / "manifest.json").read_bytes())
for name, digest in manifest["files"].items():
    path = (root / name).resolve()
    if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(name)
    if path.suffix == ".json":
        json.loads(path.read_bytes())
print(f"Verified {len(manifest['files'])} archived files")

# Replay the actual archived plan input, with no model or workspace mounts.
import sys
sys.path.insert(0, str(root.parent / "07_三稿独立写作/v015_第15版/tools"))
from writing_plan import render
plan = root / "bike_parking_20261122/autonomous_writing/draft_0"
packet = json.loads((plan / "plan_input.json").read_bytes())
expected = (plan / "论文写作方案.md").read_text(encoding="utf-8")
assert render(packet) == expected, "Historical plan rendering differs"
print("Archived plan rendering reproduced; independent review status is unchanged")
