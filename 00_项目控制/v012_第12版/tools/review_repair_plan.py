"""D24: bounded candidate repair tasks. Original routes retain authorization and budgets."""
import re
from review_binding import read_review_candidate
from review_route_plan import pass_contract


G7_REPAIR_GUIDANCE = {
    "argument_progression": "Identify the failed inferential step; revise the argument and its transitions against the frozen question and evidence.",
    "material_scope": "Narrow or remove claims exceeding the admitted material, population, event or time scope; request new material through the original gate if necessary.",
    "literature_neighbour": "Compare the claimed contribution with the nearest available literature; distinguish existing explanation from the actual increment. Do not invent citations.",
    "concept_boundary": "Disambiguate concepts, define their referents and apply the same definition across sections; revise affected claims.",
    "causal_overreach": "Remove unsupported causal language or narrow the inference to the evidence; state rival explanations and limits.",
}


def revision_targets(run, context):
    """Identify editable/proposable objects from the frozen inputs, not source logs."""
    kind = context["review_kind"]
    artifacts = {a["path"]: {"path": a["path"], "sha256": a["sha256"]} for a in context["input_materials"]}
    chosen = context.get("input_binding", {}).get("selected_object", {}).get("path")
    allowed = {}
    downstream = []
    if kind in {"preliminary_academic", "research_design", "final_research"}:
        if "staged_topic.json" in artifacts:
            allowed["staged_topic.json"] = "original_gate_managed_question_or_design"
        downstream = ["supplemental", "merged_literature.json", "s08_topic.json", "qualitative_framework", "autonomous_writing"]
    elif kind == "qualitative_design":
        if chosen and re.fullmatch(r"qualitative/attempt_[0-9]{3}/material_receipt\.json", chosen):
            conversion = chosen.rsplit("/", 1)[0] + "/conversion.json"
            if conversion in artifacts:
                allowed[conversion] = "new_original_conversion_attempt"
        downstream = ["s08_topic.json", "qualitative_framework", "autonomous_writing"]
    elif kind == "empirical_matrix":
        if chosen and re.fullmatch(r"qualitative_framework/attempt_[0-9]{3}/analysis_matrix\.json", chosen):
            folder = chosen.rsplit("/", 1)[0]
            for path, mode in ((chosen, "original_analysis_revision"), (folder + "/framework.json", "original_framework_revision")):
                if path in artifacts:
                    allowed[path] = mode
            downstream = [folder + "/analysis_matrix_reviewed.json", "matrix_independent_review.json", "autonomous_writing"]
    elif kind == "writing_plan":
        if chosen and chosen.endswith("/writing_plan_review_request.json"):
            folder = chosen.rsplit("/", 1)[0]
            path = folder + "/plan_input.json"
            if path in artifacts:
                allowed[path] = "original_plan_revision_and_render"
            downstream = [folder + "/论文写作方案.md", chosen, "V16 workspaces bound to this plan"]
    elif kind == "qualitative_g7":
        import json
        if chosen in artifacts and chosen.endswith("/writing_review_request.json"):
            from review_binding import _read_bound
            _, raw = _read_bound(run, artifacts[chosen])
            request = json.loads(raw)
            for key, mode in (("manuscript_sha256", "revise_manuscript"), ("claim_ledger_sha256", "revise_claim_ledger")):
                matches = [path for path, ref in artifacts.items() if ref["sha256"] == request.get(key)]
                if len(matches) == 1:
                    allowed[matches[0]] = mode
            folder = chosen.rsplit("/", 1)[0]
            downstream = [folder + "/style_review.json", chosen, "G7 candidate assessment"]
    return artifacts, allowed, downstream


def plan_candidate_revision(report_path, *, current_run_id, expected_reference, context_path, target_map):
    import task_packet
    run, path, context_file, packet, inputs, report, context, schema, audit = read_review_candidate(
        report_path, current_run_id=current_run_id, expected_reference=expected_reference, context_path=context_path)
    if report["decision"] != "revise":
        raise ValueError("Revision route requires revise, not a missing-evidence or failure decision")
    state = task_packet.heritage.state_of(current_run_id)
    native = pass_contract(state, context)
    artifacts, allowed, downstream = revision_targets(run, context)
    blocking = {issue["issue_id"]: issue for issue in report["issues"] if issue["blocking"]}
    if not isinstance(target_map, dict) or set(target_map) != set(blocking) or not blocking:
        raise ValueError("Receiver must select targets for every blocking issue exactly once")
    tasks = []
    for key, issue in blocking.items():
        targets = target_map[key]
        if (not isinstance(targets, list) or not targets or not all(isinstance(p, str) and p in allowed for p in targets)
                or len(set(targets)) != len(targets)):
            raise ValueError("Revision target is not an allowed current artifact")
        task = {"issue_id": key, "dimension_id": issue["dimension_id"], "problem": issue["detail"],
                "required_action": issue["required_action"], "category": issue["category"],
                "evidence_ids": issue["evidence_ids"],
                "targets": [{**artifacts[p], "repair_mode": allowed[p]} for p in targets]}
        if context["review_kind"] == "qualitative_g7":
            task["revision_guidance"] = G7_REPAIR_GUIDANCE.get(issue["dimension_id"],
                "Resolve the identified issue using only current admitted evidence; record any remaining limits.")
            task["resubmit_required"] = True
            task["independent_re_review_required"] = True
        tasks.append(task)
    return {"task_snapshot": expected_reference, "report_sha256": audit["report_sha256"],
            "proposed_decision": "revise", "status": "candidate_revision_waiting_authorization",
            "native_handler": native["native_handler"], "repair_tasks": tasks,
            "affected_downstream": [{"artifact": p, "invalidation": "recheck_after_actual_change"} for p in downstream],
            "advance_gate": False, "execute_revision": False, "formal_eligible": False,
            "independent_review_verified": False, "search_authorized": False,
            "note": "Original revision_routes/preflight and original budgets remain authoritative; do not edit source receipts or legacy state directly."}
