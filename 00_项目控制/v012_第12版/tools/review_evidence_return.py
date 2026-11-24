"""D25: need_evidence routes to original evidence collection, never text polish."""
from review_binding import read_review_candidate
from review_route_plan import pass_contract


def evidence_routes(context, state):
    kind = context["review_kind"]
    artifacts = {a["path"]: {"path": a["path"], "sha256": a["sha256"]} for a in context["input_materials"]}
    result = {}
    if kind in {"preliminary_academic", "research_design", "final_research", "writing_plan", "qualitative_g7"}:
        phase = "initial" if kind == "preliminary_academic" else "supplemental"
        if state.get("review_phase") == "final":
            phase = "supplemental"
        result["literature"] = {"original_entry": "v009 staged_topic.search/advance",
            "required_original_phase": phase, "requires_original_phase_authorization": True,
            "input_refs": [ref for path,ref in artifacts.items() if path in {
                "initial/literature_matrix.json", "initial/theories.json", "merged_literature.json", "staged_topic.json"}]}
    if kind in {"research_design", "final_research", "qualitative_design"}:
        result["material_access"] = {"original_entry": "06/v005 qual_materials conversion/material search + v009 method_paths",
            "requires_original_phase_authorization": True, "input_refs": [ref for path,ref in artifacts.items()
                if path.endswith(("conversion.json","material_receipt.json")) or path == "staged_topic.json"]}
    if kind in {"empirical_matrix", "writing_plan", "qualitative_g7"}:
        matrix_refs = [ref for path,ref in artifacts.items() if path.startswith("qualitative_framework/")
                       and path.endswith(("framework.json", "material_receipt.json", "analysis_matrix.json", "analysis_matrix_reviewed.json"))]
        if matrix_refs:
            for label in ("source", "event", "framework"):
                result[label] = {"original_entry": "v009 revision_routes.preflight + 06/v005 repair_materials.repair",
                    "original_origin": label, "requires_original_phase_authorization": True,
                    "input_refs": matrix_refs, "must_reassess": "material_adequacy.writing_material_status"}
    return result


def plan_candidate_evidence(report_path, *, current_run_id, expected_reference, context_path, gap_routes):
    import task_packet
    run, path, context_file, packet, inputs, report, context, schema, audit = read_review_candidate(
        report_path, current_run_id=current_run_id, expected_reference=expected_reference, context_path=context_path)
    if report["decision"] != "need_evidence":
        raise ValueError("Evidence route requires need_evidence")
    state = task_packet.heritage.state_of(current_run_id)
    pass_contract(state, context)
    available = evidence_routes(context, state)
    gaps = {row["issue_id"]: row for row in report["issues"] if row["blocking"] and row["category"] == "evidence_gap"}
    if not gaps or not isinstance(gap_routes, dict) or set(gap_routes) != set(gaps):
        raise ValueError("Every blocking evidence gap requires an explicit receiver-selected evidence route")
    tasks = []
    for key, gap in gaps.items():
        route = gap_routes[key]
        if not isinstance(route,str) or route not in available:
            raise ValueError("Evidence gap must return to an applicable original evidence route, not polish")
        tasks.append({"issue_id": key, "dimension_id": gap["dimension_id"], "problem": gap["detail"],
            "required_evidence": gap["required_action"], "evidence_ids": gap["evidence_ids"], "route": available[route]})
    return {"task_snapshot": expected_reference, "report_sha256": audit["report_sha256"],
        "proposed_decision": "need_evidence", "status": "candidate_evidence_return_waiting_authorization",
        "evidence_tasks": tasks, "advance_gate": False, "execute_search": False,
        "search_authorized": False, "writing_authorized": False, "formal_eligible": False,
        "independent_review_verified": False, "text_polish_substitutes_evidence": False,
        "note": "Use original deficit/batch/action limits and original state transition only after authorization; no new search quota."}
