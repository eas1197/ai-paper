import json
from pathlib import Path
from archive_provenance import load_manifest, verify_archive

root = Path(__file__).resolve().parents[2] / "handoff_runs"
manifest = load_manifest(root / "manifest.json")
result = verify_archive(root,manifest)
print(f"Verified {result['archived_files']} archived files in {result['archived_runs']} runs; {result['omitted_files']} local-only omissions")
print("Archive is not proof of a new execution or formal authorization")

# Replay the actual archived plan input, with no model or workspace mounts.
import sys
sys.path.insert(0, str(root.parent / "07_三稿独立写作/v015_第15版/tools"))
from writing_plan import render
plan = root / "bike_parking_20261122/autonomous_writing/draft_0"
packet = json.loads((plan / "plan_input.json").read_bytes())
expected = (plan / "论文写作方案.md").read_text(encoding="utf-8")
assert render(packet) == expected, "Historical plan rendering differs"
print("Archived plan rendering reproduced; independent review status is unchanged")
