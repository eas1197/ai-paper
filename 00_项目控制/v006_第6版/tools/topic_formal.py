"""Bridge a reviewed topic to the registered formal research tools."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from topic_evidence import validate_bundle
from topic_review import content_hash, validate_review
from topic_tasks import CONTROL, existing_module


def invoke(root, script, *arguments):
    return subprocess.run([sys.executable, "-B", str(script), *map(str, arguments)],
                          cwd=root, capture_output=True, encoding="utf-8", timeout=60,
                          env=os.environ | {"PYTHONIOENCODING": "utf-8"})


def formal_init(root, path, state, read, write_new):
    if state["stage"] != "formal" or len(state["approved_ids"]) != 1:
        raise ValueError("A reviewed READY candidate is required before formal research")
    last = read(state["last_round"])
    bundle = last["bundle"]
    validate_bundle(bundle, root)
    validate_review(last["review"], bundle, "deepening", state["config"]["review_model"])
    if last["review"]["verdict"] != "READY" or last["review"].get("selected_ids") != state["approved_ids"]:
        raise ValueError("Recorded selection no longer matches the READY review")
    question = next(row for row in bundle["questions"] if row["question_id"] == state["approved_ids"][0])
    opportunity = next(row for row in bundle["opportunities"] if row["opportunity_id"] == question["opportunity_id"])
    candidate = {"status": "selected_for_stage_04", "theme": state["config"]["theme"] or opportunity["social_process"],
                 "issue": opportunity["observation"], "question": question["text"],
                 "topic_round": Path(state["last_round"]).relative_to(root).as_posix(),
                 "topic_round_sha256": content_hash(last), "review_input_sha256": last["review"]["input_sha256"],
                 "open_gap": last["review"]["gap"], "preliminary_evidence_ids": last["review"]["evidence"]}
    decision = path / "topic_decision.json"
    if not decision.exists():
        write_new(decision, candidate)
    elif read(decision) != candidate:
        raise ValueError("Existing formal handoff was changed")
    starter = path / "formal_input.json"
    if not starter.exists():
        write_new(starter, {"04": {"theme": candidate["theme"], "literature": [], "annotations": None}, "05": {}})
    project = root / CONTROL / "tools/project.py"
    run_id = state["config"]["run_id"]
    cfg = read(root / CONTROL / "project_config.json")
    manifest = root / cfg["runtime"]["run_store_root"] / run_id / "run_manifest.json"
    if not manifest.exists():
        process = invoke(root, project, "init", "--run-id", run_id, "--topic-decision", decision.relative_to(root))
        if process.returncode:
            raise ValueError(process.stderr or process.stdout)
    saved = read(manifest).get("topic_state", {}).get("selection", {})
    if (saved.get("path") != decision.relative_to(root).as_posix()
            or saved.get("sha256") != hashlib.sha256(decision.read_bytes()).hexdigest()):
        raise ValueError("Existing run is not bound to this reviewed selection")
    return {"stage": "G4", "run_id": run_id, "manifest": str(manifest), "decision": str(decision), "input": str(starter)}


def final_gate(root, state, bundle, review, attempt, read):
    if state["stage"] != "formal":
        raise ValueError("This selection has not reached formal literature review")
    validate_review(review, bundle, "final", state["config"]["review_model"])
    if review["verdict"] != "PASS":
        raise ValueError("Final review requested revision or stopped the candidate")
    attempt = Path(attempt).resolve()
    run_id = state["config"]["run_id"]
    cfg = read(root / CONTROL / "project_config.json")
    run = root / cfg["runtime"]["run_store_root"] / run_id
    if attempt.parent != run / "stage_04":
        raise ValueError("Attempt is not a G4 attempt in the selected run")
    current = next(row for row in read(run / "run_manifest.json")["stages"] if row["stage_id"] == "04")
    if not current.get("manifest_path") or Path(current["manifest_path"]).resolve() != attempt / "stage_manifest.json":
        raise ValueError("Attempt is not the current formal G4 attempt")
    g4_manifest = attempt / "stage_manifest.json"
    g4_sha = hashlib.sha256(g4_manifest.read_bytes()).hexdigest()
    if bundle.get("formal_g4_sha256") != g4_sha:
        raise ValueError("Final review did not receive this G4 snapshot")
    if review.get("selected_ids") != state["approved_ids"]:
        raise ValueError("Final review selected a different question; revise the topic first")
    stage04 = existing_module(root, read, "04")
    result = invoke(root, stage04 / "tools/research.py", "validate", "--attempt", attempt)
    if result.returncode or json.loads(result.stdout).get("status") != "passed":
        raise ValueError("An effective G4 pass is required for G5")
    return {"status": "ready_for_existing_g5", "run_id": run_id, "g4_manifest": str(g4_manifest),
            "g4_sha256": g4_sha, "question_id": state["approved_ids"][0], "final_review": review}
