"""C21: project unified candidates onto the existing v009 abstract receiver.

Never manufacture a collection, matrix, gate pass, quota or independent review.
"""
import json
import sys
from pathlib import Path

import chat_receiving
import codex_receiving
import result_bundle
import task_packet


def _original():
    tools = str(task_packet.heritage.V32 / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import staged_topic
    from abstract_acquisition import clean_doi
    from codex_literature import web_url
    return staged_topic, clean_doi, web_url


def _matches(row, item, batch, clean_doi, web_url):
    if item.get("batch") != batch:
        return False
    fields = (
        ("title", "title"), ("authors", "authors"), ("publication", "journal"),
        ("abstract_locator", "abstract_locator"), ("excerpt", "abstract_excerpt"),
        ("paraphrase", "abstract_summary"), ("relevance_reason", "relevance_reason"),
    )
    return (all(row.get(a) == item.get(b) for a, b in fields)
            and str(row.get("publication_date") or "")[:4] == str(item.get("year"))
            and clean_doi(row.get("doi") or "") == clean_doi(item.get("doi") or "")
            and all(web_url(row.get(key)) and web_url(row[key]) == web_url(item.get(key))
                    for key in ("metadata_url", "abstract_url"))
            and {item["metadata_event_id"], item["abstract_event_id"]} <= set(row["action_ids"]))


def _phase_scope(staged, work, run_id, phase, packet, *, allow_reviewed=False):
    """Derive scope from original v009 state and workload, never submitted claims."""
    state = task_packet.heritage.state_of(run_id)
    manifest = task_packet.run_mode.verified_run(work)
    next_review = "preliminary_review" if phase == "initial" else "final_review"
    if state.get("policy_sha256") != staged.digest(staged.POLICY):
        raise ValueError("Original v009 policy binding changed")
    if state["status"] != phase and not (
            allow_reviewed and state["status"] == next_review
            and state.get("latest_search", {}).get("phase") == phase):
        raise ValueError("Original literature phase is not current")
    plan = staged.issue_plan(work, state) if state.get("issue_search") else None
    journals = [*staged.POLICY["journals"],
                *(row["name"] for row in plan.get("specialist_journals", []))] if plan else staged.POLICY["journals"]
    limit = staged.POLICY["dev"][phase]
    if packet["source_scope"].get("journals") != journals or packet["quantity_budget"].get("target") != limit:
        raise ValueError("Unified task scope or quantity differs from original v009")
    return state, manifest, next_review, journals, limit


def _validate_chat_phase_budget(staged, work, run_id, phase, packet):
    """A Chat candidate cannot reuse a closed phase or widen a frozen budget."""
    _, manifest, _, _, limit = _phase_scope(staged, work, run_id, phase, packet)
    limits = manifest["workload"]["11"]
    profile = task_packet.run_mode.load(task_packet.run_mode.CONTROL / "dev_profile.json")
    expected = {"target": limit,
                "max_batches": profile["11"]["topic_batches_per_phase"],
                "native_search_actions": limits["native_search_actions"]}
    if (packet["quantity_budget"] != expected
            or packet["time_budget_seconds"] != limits["timeout_seconds"]):
        raise ValueError("Chat frozen quantity or time budget differs from original v009")
    # This does not attest consumption, source authenticity or academic approval.


def audit_unified_literature(result_path, *, current_run_id, expected_reference,
                             expected_execution=None, observed_actions=None):
    snapshot = task_packet.verify_snapshot(expected_reference, current_run_id=current_run_id)
    packet = snapshot["packet"]
    phase = expected_reference["stage_id"]
    if phase not in {"initial", "supplemental"} or expected_reference["task_id"] != "original_v3_literature_" + phase:
        raise ValueError("Not an original v009 literature task")
    work = (task_packet.heritage.RUNS / current_run_id).resolve()
    path = result_bundle._local_file(work, result_path)
    bundle = json.loads(path.read_text(encoding="utf-8-sig"))
    kind = bundle.get("executor")
    kwargs = dict(current_run_id=current_run_id, expected_reference=expected_reference,
                  expected_execution=expected_execution)
    if kind == "chat_native_web":
        report = chat_receiving.audit_chat_records(result_path, observed_actions=observed_actions, **kwargs)
    elif kind == "codex_cli":
        report = codex_receiving.audit_codex_records(result_path, **kwargs)
    else:
        report = result_bundle.audit_result_bundle(result_path, **kwargs)
    if task_packet.heritage.sha(path) != report["result_sha256"]:
        raise ValueError("Unified result changed during original gate audit")
    report.update(original_gate_status="pending_original_native_receipt",
                  original_abstract_eligible_ids=[], original_verified_rows=None,
                  formal_eligible=False, stage_advanced=False)
    if kind == "chat_native_web":
        staged, _, _ = _original()
        _validate_chat_phase_budget(staged, work, current_run_id, phase, packet)
    if kind != "codex_cli" or not report.get("native_cli_receipt") or report["acceptance_status"] == "rejected":
        return report
    staged, clean_doi, web_url = _original()
    state, manifest, next_review, journals, limit = _phase_scope(
        staged, work, current_run_id, phase, packet, allow_reviewed=True)
    provenance = bundle["provenance"]
    events = Path(provenance["events"]["path"])
    answer = Path(provenance["response"]["path"])
    if (len(events.parts) != 3 or events.parts[0] != phase or events.name != "events.jsonl"
            or answer != events.parent / "response.json"):
        raise ValueError("Native records are not from the original v009 phase batch")
    batch = events.parts[1]
    if not (work / phase).resolve().is_relative_to(work):
        raise ValueError("Original phase directory escapes the current run")
    checkpoint_path = work / phase / "checkpoint.json"
    collection_path = work / phase / "abstract_collection.json"
    if not checkpoint_path.is_file() or not collection_path.is_file():
        report["original_gate_status"] = "pending_original_collection"
        return report
    checkpoint = staged.load(checkpoint_path)
    collection = staged.load(collection_path)
    config = checkpoint["config"]
    if (config.get("topic_search_phase"), config.get("target"), config.get("journals"),
            config.get("run_mode"), config.get("workload_sha256")) != (
            phase, limit, journals, "dev", manifest["workload_sha256"]):
        raise ValueError("Original collection does not belong to this phase/workload")
    if (collection.get("target"), collection.get("run_mode"), collection.get("workload_sha256")) != (
            limit, "dev", manifest["workload_sha256"]):
        raise ValueError("Original collection target or workload changed")
    if collection.get("status") == "experimental_budget_exceeded":
        report["original_gate_status"] = "blocked_original_budget"
        return report
    batches = [row for row in collection["batches"] if row.get("batch") == batch]
    if len(batches) != 1 or batches[0].get("status") != "completed" or (
            batches[0].get("event_sha256"), batches[0].get("response_sha256")) != (
            provenance["events"]["sha256"], provenance["response"]["sha256"]):
        raise ValueError("Unified bundle does not bind a completed original collection batch")
    # Delegate to v009, which calls the original 04/v012 native receiver and
    # reconstructs observations/groups from original files and login receipts.
    matrix, original_checkpoint = staged.receipt(work / phase, journals)
    if state["status"] == next_review and state.get("latest_search", {}).get("collection_sha256") != matrix["collection_sha256"]:
        raise ValueError("Original reviewed collection changed")
    qualified, unmatched = [], []
    for row in bundle["sources"]:
        matches = [paper for paper in matrix["rows"] if row["source_type"] == "literature" and any(
            _matches(row, item, batch, clean_doi, web_url) for item in paper["provenance"])]
        if len(matches) == 1:
            qualified.append({"source_id": row["source_id"], "article_id": matches[0]["article_id"]})
        else:
            unmatched.append(row["source_id"])
    report.update(original_gate_status="original_abstract_receipt_matched_pending_stage_review"
                  if qualified and not unmatched else "pending_unmatched_original_observations",
                  original_abstract_eligible_ids=qualified, unmatched_source_ids=unmatched,
                  original_verified_rows=matrix["verified_rows"],
                  original_collection_sha256=matrix["collection_sha256"])
    # Even original abstract-level receipt is not a formal paper or review.
    if unmatched and report["acceptance_status"] != "rejected":
        report["acceptance_status"] = "pending_candidate"
    return report
