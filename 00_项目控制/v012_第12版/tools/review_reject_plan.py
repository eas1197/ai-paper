"""D26: preserve rejected candidates; delegate original rejection classification."""
import json
import sys
from pathlib import Path
from review_binding import read_review_candidate
from review_route_plan import pass_contract


def original_academic_route(h, state, outcome):
    # Read-only invocation of the original route, not its state-mutating review.
    script = ("import json,sys; sys.path.insert(0,sys.argv[1]); "
              "from staged_topic import ACADEMIC,route; "
              "assert sys.argv[2] in ACADEMIC; print(json.dumps(route(json.loads(sys.argv[3]),sys.argv[2])))")
    return json.loads(h.original_call([sys.executable, "-B", "-c", script,
        str(h.V3_TOPIC.parent), outcome, json.dumps(state["history"])], timeout=30))


def rejection_contract(h, state, context, native_outcome):
    route = pass_contract(state, context)
    kind = context["review_kind"]
    if kind in {"preliminary_academic", "research_design", "final_research"}:
        if native_outcome not in {"concept", "value", "depth", "increment"}:
            raise ValueError("Academic reject needs an explicit original academic classification; not missing_data or technical")
        return {"native_handler": route["native_handler"], "native_outcome": native_outcome,
                "possible_original_state": original_academic_route(h, state, native_outcome)}
    if native_outcome is not None:
        raise ValueError("Do not apply original topic rejection outcomes to another module")
    return {"native_handler": route["native_handler"], "native_outcome": None,
            "possible_original_state": None, "module_action": "retain academic stop candidate; original module must decide"}


def plan_candidate_rejection(report_path, *, current_run_id, expected_reference, context_path, native_outcome=None):
    import task_packet
    run, _, _, _, _, report, context, _, audit = read_review_candidate(
        report_path, current_run_id=current_run_id, expected_reference=expected_reference, context_path=context_path)
    if report["decision"] != "reject":
        raise ValueError("Only academic reject may use rejection routing")
    h = task_packet.heritage
    state = h.state_of(current_run_id)
    route = rejection_contract(h, state, context, native_outcome)
    result = {"task_snapshot": expected_reference, "report_sha256": audit["report_sha256"],
        "proposed_decision": "reject", "reason": report["reason"],
        "blocking_issues": [i for i in report["issues"] if i["blocking"]], "route": route,
        "status": "candidate_rejection_waiting_authorization", "advance_gate": False,
        "terminate_run": False, "archive_authorized": False, "formal_eligible": False,
        "independent_review_verified": False,
        "archive_rule": "Only original missing_data with academic_value pass, blocked feasibility, all applicable paths missing and original archive fields/receipts may archive; reject alone never archives. Unknown evidence and technical failures are not academic rejection."}
    # Persist the actual reason and issue references, not an authoritative gate record.
    folder = run / "review_rejection_candidates"
    folder.mkdir(exist_ok=True)
    if folder.resolve() != folder:
        raise ValueError("Candidate directory outside run")
    target = folder / (task_packet._digest(result) + ".json")
    if target.exists():
        if target.is_symlink() or h.read(target) != result:
            raise ValueError("Existing rejection candidate changed")
    else:
        task_packet._atomic_json(target, result)
    return {**result, "candidate_path": target.relative_to(run).as_posix()}
