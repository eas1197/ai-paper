"""D23: candidate pass routing; the original gates alone may mutate state."""
from review_binding import read_review_candidate


def _topic_gate(state, context):
    stage = state["status"]
    kind = context["review_kind"]
    if context["gate_ref"] != "00/v009 staged_topic.review:" + stage:
        raise ValueError("Review is not for the current original topic gate")
    if stage not in {"preliminary_review", "design_review", "final_review", "materials_pending", "S02", "S03", "S05", "S06"}:
        raise ValueError("Original topic review is not due")
    final = stage == "final_review" or state.get("review_phase") == "final"
    if final:
        if kind != "final_research":
            raise ValueError("Final gate requires final research review")
        return ["pass"], ["s08_ready"]
    if kind == "preliminary_academic" and stage != "design_review":
        return ["academic_pass", "pass"], ["design_review", "supplemental"]
    if kind == "research_design" and stage != "preliminary_review":
        return ["pass"], ["supplemental"]
    raise ValueError("Candidate kind differs from original academic gate")


def pass_contract(state, context):
    """Describe existing native routes; this is not a state transition function."""
    kind, gate = context["review_kind"], context["gate_ref"]
    if kind in {"preliminary_academic", "research_design", "final_research"}:
        outcomes, targets = _topic_gate(state, context)
        return {"native_handler": "v009 staged_topic.review", "native_outcomes": outcomes,
                "possible_original_states": targets,
                "native_report_required": True, "original_state_machine": True}
    if kind == "qualitative_design" and gate == "06/v005 qual_materials.record_review" and state["status"] in {"design_review", "materials_pending", "final_review"}:
        return {"native_handler": "06/v005 qual_materials.record_review", "native_outcomes": ["pass"],
                "possible_original_states": [], "possible_module_status": "qualitative_design_ready",
                "native_report_required": True, "original_state_machine": True}
    if state["status"] == "frozen":
        if kind == "empirical_matrix" and gate == "00/v009 resume_writing.resume":
            return {"native_handler": "v009 resume_writing.resume + material_adequacy.writing_material_status",
                    "native_outcomes": ["pass"], "possible_original_states": [],
                    "possible_module_status": "ready only with sufficient material assessment",
                    "native_report_required": True, "original_state_machine": True}
        if kind == "writing_plan" and gate == "00/v009 resume_writing.resume + V15":
            return {"native_handler": "v009 resume_writing.resume", "native_outcomes": ["pass"],
                    "possible_original_states": [], "possible_module_status": "reviewed_plan (experimental)",
                    "native_report_required": True, "original_state_machine": True}
        if kind == "qualitative_g7" and gate == "V16 writing_review_request":
            return {"native_handler": None, "native_outcomes": [], "possible_original_states": [],
                    "possible_module_status": "formal G7 authorization not implemented",
                    "native_report_required": True, "original_state_machine": True}
    raise ValueError("No supported original pass route; do not create a parallel gate")


def plan_candidate_pass(report_path, *, current_run_id, expected_reference, context_path):
    """Only inspect a receiver-selected frozen candidate; never call or bypass a native gate."""
    import task_packet
    run, path, context_file, packet, inputs, report, context, schema, audit = read_review_candidate(
        report_path, current_run_id=current_run_id, expected_reference=expected_reference, context_path=context_path)
    if report["decision"] != "pass":
        raise ValueError("Pass route requires a candidate pass report")
    state = task_packet.heritage.state_of(current_run_id)
    route = pass_contract(state, context)
    return {"task_snapshot": expected_reference, "report_sha256": audit["report_sha256"],
            "proposed_decision": "pass", "route": route, "status": "awaiting_independent_authorization",
            "advance_gate": False, "formal_eligible": False, "independent_review_verified": False,
            "reason": "A common report cannot create native academic_value, data_feasibility, method or adequacy fields; actual authorized original report required."}
