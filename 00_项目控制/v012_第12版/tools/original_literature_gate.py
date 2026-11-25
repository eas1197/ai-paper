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


def _audit_chat_abstract_checks(work, path, bundle, report, checks, journals, clean_doi, web_url):
    """Compare receiver-selected page bytes; never authenticate the receiver.

    Separate page records are not a replacement for the original search trace,
    nor can matching source text or a claimed paraphrase review grant admission.
    """
    import re
    from abstract_acquisition import abstract_text
    from collect_common import normalize
    literature = {row["source_id"]: row for row in bundle["sources"]
                  if row["source_type"] == "literature"}
    selected = {}
    if checks is not None:
        if (not isinstance(checks, dict)
                or set(checks) != {"task_snapshot", "result_sha256", "sources"}
                or checks["task_snapshot"] != report["task_snapshot"]
                or checks["result_sha256"] != report["result_sha256"]
                or not isinstance(checks["sources"], list)):
            raise ValueError("Independent abstract checks do not bind current result")
        for item in checks["sources"]:
            if (not isinstance(item, dict)
                    or set(item) != {"source_id", "metadata", "abstract", "abstract_text",
                                     "checked_paraphrase", "relevance", "relevance_reason"}
                    or item["source_id"] not in literature
                    or item["source_id"] in selected):
                raise ValueError("Invalid or duplicate receiver-selected abstract check")
            selected[item["source_id"]] = item
    excluded = {path} | {result_bundle._local_file(work, ref["path"])
                        for ref in bundle["provenance"]["record_refs"]}

    def span(selection, expected_url):
        if (not isinstance(selection, dict)
                or set(selection) != {"url", "record_ref", "line_start", "line_end"}
                or not web_url(expected_url)
                or web_url(selection["url"]) != web_url(expected_url)):
            raise ValueError("Independent page selection has wrong source URL")
        ref = selection["record_ref"]
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
            raise ValueError("Independent page selection needs exact record reference")
        record = result_bundle._local_file(work, ref["path"])
        if record in excluded:
            raise ValueError("Independent page record must be separate from submitted records")
        lines = chat_receiving._raw_record(work, ref)
        start, end = selection["line_start"], selection["line_end"]
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise ValueError("Invalid independent page record location")
        text = "\n".join(lines[start-1:end])
        if selection["url"] not in text:
            raise ValueError("Independent page URL not visible in selected record")
        return text

    def visible(value, text):
        value = normalize(value)
        return bool(value) and value in normalize(text)

    receipts = []
    for source_id, row in literature.items():
        item = selected.get(source_id)
        gaps = []
        year = str(row["publication_date"] or "")[:4]
        if (row["publication"] not in journals or not normalize(row["title"])
                or not row["authors"] or any(not normalize(a) for a in row["authors"])
                or not re.fullmatch(r"\d{4}", year) or not 1900 <= int(year) <= 2100):
            gaps.append("original_bibliography_or_journal_scope_failed")
        if (row["open_status"] != "opened"
                or row["literature_stages"]["abstract_read_status"] != "read"):
            gaps.append("abstract_access_or_read_missing")
        summary = row["paraphrase"] or ""
        excerpt = row["excerpt"] or ""
        if (not abstract_text(summary, row["title"]) or not 80 <= len(summary.strip()) <= 160
                or not 8 <= len(excerpt.strip()) <= 90
                or not (row["abstract_locator"] or "").strip()):
            gaps.append("original_abstract_content_failed")
        if item is None:
            gaps.append("missing_receiver_selected_page_records")
        else:
            metadata = span(item["metadata"], row["metadata_url"])
            abstract = span(item["abstract"], row["abstract_url"])
            if (not all(visible(value, metadata) for value in
                        [row["title"], row["publication"], *row["authors"]])
                    or not re.search(r"(?<!\d)" + re.escape(year) + r"(?!\d)", metadata)
                    or not year):
                gaps.append("independent_bibliography_mismatch")
            doi = clean_doi(row["doi"])
            if row["doi"] and (not doi or doi not in metadata.casefold()):
                gaps.append("independent_doi_mismatch")
            raw_abstract = item["abstract_text"]
            clean = abstract_text(raw_abstract, row["title"])
            if (not clean or not visible(raw_abstract, abstract)
                    or not visible(row["abstract_locator"], abstract)
                    or not excerpt.strip() or not visible(excerpt, clean)):
                gaps.append("independent_abstract_or_locator_mismatch")
            if (item["checked_paraphrase"] != summary
                    or item["relevance"] not in ("direct", "substantive")
                    or not (row["relevance_reason"] or "").strip()
                    or item["relevance_reason"] != row["relevance_reason"]):
                gaps.append("independent_paraphrase_or_relevance_not_matched")
        if report["chat_record_status"] != "matched_visible_records_pending_authentication":
            gaps.append("original_chat_records_incomplete")
        receipts.append({"source_id": source_id, "gaps": gaps,
                         "status": "pending_content_or_original_records" if gaps
                         else "content_matched_pending_receiver_authentication",
                         "receiver_authenticated": False,
                         "original_abstract_eligible": False})
    return receipts


def audit_unified_literature(result_path, *, current_run_id, expected_reference,
                             expected_execution=None, observed_actions=None, abstract_checks=None):
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
        staged, clean_doi, web_url = _original()
        _validate_chat_phase_budget(staged, work, current_run_id, phase, packet)
        report["chat_abstract_checks"] = _audit_chat_abstract_checks(
            work, path, bundle, report, abstract_checks,
            packet["source_scope"]["journals"], clean_doi, web_url)
        if report["acceptance_status"] != "rejected" and any(
                row["gaps"] for row in report["chat_abstract_checks"]):
            report["acceptance_status"] = "pending_candidate"
            report["acceptance_reason"] = "Missing independent abstract content or original Chat records"
    elif abstract_checks is not None:
        raise ValueError("Independent Chat abstract checks require chat_native_web")
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
