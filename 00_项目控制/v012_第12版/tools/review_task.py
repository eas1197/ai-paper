"""D21: freeze a candidate review task at an original v009 review stage."""
import json
import re
from pathlib import Path

STAGES = {
    "preliminary_review": ("preliminary_academic", ("academic_value", "concepts", "theoretical_increment")),
    "design_review": ("research_design", ("question_design_fit", "three_method_paths", "material_access")),
    "final_review": ("final_research", ("theoretical_increment", "competing_explanations", "design_feasibility")),
}


def prepare_review_task(run_id):
    import task_packet as contract
    h = contract.heritage
    h.doctor()
    state = h.state_of(run_id)
    stage = state["status"]
    if stage in {"S02", "S03", "S05", "S06"}:
        raise ValueError("Original revision state requires a frozen prior-review lineage")
    if stage == "materials_pending":
        phase = state.get("review_phase")
        if phase not in {"initial", "final"}:
            raise ValueError("Original material wait has no review phase")
        review_stage = "final_review" if phase == "final" else "design_review"
    elif stage in STAGES:
        review_stage = stage
    else:
        raise ValueError("No supported original academic review is due")
    work = (h.RUNS / run_id).resolve(strict=True)
    manifest = contract.run_mode.verified_run(work)
    if manifest.get("run_id") != run_id:
        raise ValueError("Original research identity mismatch")
    state_path = work / "staged_topic.json"
    state_sha = h.sha(state_path)
    original = json.loads(h.original_call(h.original_command("prepare", run_id)))
    if original.get("status") != stage or not original.get("evidence_sha256"):
        raise ValueError("Original review preparation is incomplete or stale")
    if h.state_of(run_id) != state or h.sha(state_path) != state_sha:
        raise ValueError("Original state changed during preparation")
    kind, dimensions = STAGES[review_stage]
    question = state.get("question") or state.get("theme")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Missing original question or theme")
    if original.get("question") != state.get("question"):
        raise ValueError("Original prepare question differs from current state")
    final = review_stage == "final_review"
    if stage in {"preliminary_review", "design_review"} and state.get("review_phase") == "final":
        raise ValueError("Inconsistent original review phase")
    papers = "merged_literature.json" if final else "initial/literature_matrix.json"
    if Path(original["papers"]).resolve() != (work / papers).resolve() or Path(original["theories"]).resolve() != (work / "initial/theories.json").resolve():
        raise ValueError("Original review inputs differ from selected run")
    names = ["run_manifest.json", "staged_topic.json", papers, "initial/theories.json"]
    if state.get("reality_first"):
        names.append("reality.json")
    if state.get("explanation_first"):
        names.append("explanation_exchange.json")
    if state.get("issue_search"):
        names.extend(("issue_plan.json", "event_comparison.json"))
    # Include existing complete material attempts as candidate evidence, never as a
    # finding of access or sufficiency. Original method_paths owns qualification.
    pending = []
    if review_stage != "preliminary_review" and state.get("qual_search_receipts"):
        for folder in sorted((work / "qualitative").glob("attempt_*")):
            if not re.fullmatch(r"attempt_[0-9]{3}", folder.name):
                continue
            paths = [folder / f for f in ("conversion.json", "material_receipt.json", "events.jsonl", "response.json")]
            if not all(path.is_file() for path in paths):
                pending.append(folder.name)
                continue
            names.extend(path.relative_to(work).as_posix() for path in paths)
    def ref(root, path):
        resolved = path.resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(root.resolve()):
            raise ValueError("Review input outside namespace")
        return {"path": path.relative_to(root).as_posix(), "sha256": h.sha(resolved)}
    artifacts = [{"artifact_id": name, "role": name, **ref(work, work / name)} for name in names]
    allowed = [a["artifact_id"] for a in artifacts]
    policy = [ref(h.ROOT, h.V3_POLICY), ref(h.ROOT, h.V3_SEARCH_PROMPT)]
    review_scope = original["review_scope"]
    if stage == "materials_pending":
        review_scope = "Reassess unresolved material availability under the original " + review_stage + " gate; unknown is not missing."
    context = {
        "context_version": 1, "review_kind": kind, "review_type": "academic_review",
        "gate_ref": "00/v009 staged_topic.review:" + stage, "research_question": question,
        "design": {"status": "not_frozen", "freeze_ref": None, "proposal_refs": []},
        "input_materials": artifacts, "key_claims": [],
        "claims_scope": "Pre-empirical academic or design review; do not claim established mechanisms.",
        "evidence_scope": {"allowed_ids": allowed, "excluded_or_pending_ids": pending,
            "limitations": ["File IDs are reviewable artifacts, not independent source or adequacy certification.", "Missing material attempts are unknown, not unavailable."], "policy_refs": policy},
        "review_dimensions": [{"dimension_id": d, "question": d + ": " + review_scope,
            "evidence_ids": allowed, "failure_condition": "Insufficient traceable support for this dimension."} for d in dimensions],
        "prohibitions": ["No search or source invention", "No state mutation or independent identity claims", "No empirical conclusion or formal approval"],
        "prior_review": None, "input_binding": {"original_evidence_sha256": original["evidence_sha256"], "state_sha256": state_sha},
    }
    # Content-addressed context keeps older task inputs intact after revisions.
    context_path = work / "review_tasks" / (contract._digest(context) + ".json")
    if not context_path.resolve().is_relative_to(work):
        raise ValueError("Review context outside run")
    if context_path.exists():
        if h.read(context_path) != context:
            raise ValueError("Existing review context differs")
    else:
        contract._atomic_json(context_path, context)
    packet = {"schema_version": 1, "research_id": run_id, "stage_id": stage,
        "task_id": "original_review_" + stage, "purpose": review_scope, "research_question": question,
        "search_levels": [], "input_files": [{"path": a["path"], "sha256": a["sha256"]} for a in artifacts] + [ref(work, context_path)],
        "source_scope": {"policy_refs": policy}, "quantity_budget": {}, "time_budget_seconds": 0,
        "output_schema": {"kind": "file", "file": ref(h.ROOT, Path(__file__).resolve().parents[1] / "schemas/review_result.schema.json")},
        "stop_conditions": ["Input or original state changed", "Independent execution unavailable", "No separate execution authorization"],
        "notes": ["Preparation only. A separate original-budget reservation is required before dispatch."]}
    if json.loads(h.original_call(h.original_command("prepare", run_id))) != original:
        raise ValueError("Original review preparation changed")
    if h.sha(state_path) != state_sha or any(a["sha256"] != h.sha(work / a["path"]) for a in artifacts):
        raise ValueError("Original review inputs changed during preparation")
    snapshot = contract.freeze_packet(packet, current_run_id=run_id)
    contract.verify_snapshot(snapshot, current_run_id=run_id)
    return {"task_packet": packet, "task_snapshot": snapshot, "context_path": context_path.relative_to(work).as_posix(), "formal_eligible": False, "dispatch_authorized": False}
