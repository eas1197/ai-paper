"""C19: Chat native record intake. No Codex event synthesis or host attestation."""
import json
import re
from pathlib import Path

import result_bundle
import task_packet
from jsonschema import ValidationError


def _raw_record(work, ref):
    path = result_bundle._local_file(work, ref["path"])
    if path.name.lower() == "events.jsonl":
        raise ValueError("Codex events.jsonl is not a Chat web record")
    text = path.read_text(encoding="utf-8-sig")
    if task_packet.heritage.sha(path) != ref["sha256"]:
        raise ValueError("Chat original record changed")
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("type") in {"thread.started", "item.completed"}:
            raise ValueError("Native CLI event stream is not a Chat web record")
    return text.splitlines()


def audit_chat_records(result_path, *, current_run_id, expected_reference,
                       expected_execution=None, observed_actions=None):
    """Check actual saved records against independently observed action extracts.

    observed_actions must be selected by a receiver from real visible tool records,
    never supplied as model-generated proof. This process cannot authenticate
    ChatGPT's host or attest independent academic review.
    """
    try:
        report = result_bundle.audit_result_bundle(
            result_path, current_run_id=current_run_id, expected_reference=expected_reference,
            expected_execution=expected_execution)
    except ValidationError as exc:
        raise ValueError("Invalid result envelope: " + exc.message) from exc
    if report["executor"] != "chat_native_web":
        raise ValueError("Only chat_native_web result accepted")
    work = (task_packet.heritage.RUNS / current_run_id).resolve()
    path = result_bundle._local_file(work, result_path)
    bundle = json.loads(path.read_text(encoding="utf-8-sig"))
    if task_packet.heritage.sha(path) != report["result_sha256"]:
        raise ValueError("Result changed during intake")
    raw = {ref["path"]: (ref, _raw_record(work, ref))
           for ref in bundle["provenance"]["record_refs"]}
    actions = {}
    for action in bundle["search_actions"]:
        key = action["action_id"]
        if key in actions:
            raise ValueError("Duplicate Chat action ID")
        actions[key] = action
    sources = {}
    for row in bundle["sources"]:
        if row["source_id"] in sources:
            raise ValueError("Duplicate Chat source ID")
        sources[row["source_id"]] = row
    matched = {}
    if observed_actions is not None and not isinstance(observed_actions, list):
        raise ValueError("Observed actions must be a receiver-selected list")
    if expected_execution is not None:
        for item in observed_actions or []:
            required = {"action_id", "action_type", "record_ref", "line_start",
                        "line_end", "query", "urls"}
            if not isinstance(item, dict) or set(item) != required:
                raise ValueError("Invalid independently observed Chat action")
            key = item["action_id"]
            if key in matched or key not in actions:
                raise ValueError("Observed Chat action does not match submitted action")
            action = actions[key]
            if item["action_type"] not in {"search", "open_page", "find_in_page"} or action["action_type"] != item["action_type"]:
                raise ValueError("Observed Chat action type mismatch")
            ref = item["record_ref"]
            if not isinstance(ref, dict) or ref.get("path") not in raw or raw[ref["path"]][0] != ref:
                raise ValueError("Observed action lacks original record binding")
            lines = raw[ref["path"]][1]
            start, end = item["line_start"], item["line_end"]
            if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
                raise ValueError("Invalid original Chat record location")
            span = "\n".join(lines[start-1:end])
            urls = item["urls"]
            if not isinstance(urls, list) or not urls or not all(
                    isinstance(url, str) and task_packet.heritage.valid_https(url) for url in urls):
                raise ValueError("Observed action needs actual HTTPS source URLs")
            tokens = set(re.findall(r'https://[^\s<>"\'\]\)]+', span))
            if not set(urls) <= tokens:
                raise ValueError("Observed URL not found at original record location")
            if item["action_type"] == "search":
                query = item["query"]
                if not isinstance(query, str) or not query.strip() or query != action["query"] or query not in span:
                    raise ValueError("Observed search query not found in original record")
            elif not action["original_url"] or action["original_url"] not in urls:
                raise ValueError("Observed page target differs from submitted action")
            matched[key] = item
    receipts = []
    for source_id, row in sources.items():
        urls = {row[key] for key in ("original_url", "metadata_url", "abstract_url") if row[key]}
        found, opened = [], []
        for key in row["action_ids"]:
            item = matched.get(key)
            action = actions.get(key)
            if not item or source_id not in action["source_ids"] or not urls.intersection(item["urls"]):
                continue
            if item["action_type"] == "search":
                found.append(key)
            elif action["original_url"] in urls:
                opened.append(key)
        abstract_matches = []
        gaps = []
        if not opened:
            gaps.append("missing_independent_open_record")
        if row["source_type"] == "literature":
            locator, excerpt, summary = (row["abstract_locator"], row["excerpt"], row["paraphrase"])
            if not row["abstract_url"] or not locator or not locator.strip():
                gaps.append("missing_abstract_location")
            if not excerpt or not 8 <= len(excerpt.strip()) <= 90:
                gaps.append("missing_or_invalid_abstract_excerpt")
            if not summary or not 80 <= len(summary.strip()) <= 160:
                gaps.append("missing_or_invalid_abstract_summary")
            if row["literature_stages"]["abstract_read_status"] != "read":
                gaps.append("abstract_read_not_claimed")
            if not gaps:
                for key in opened:
                    item = matched[key]
                    if actions[key]["original_url"] != row["abstract_url"]:
                        continue
                    lines = raw[item["record_ref"]["path"]][1]
                    span = " ".join("\n".join(lines[item["line_start"]-1:item["line_end"]]).split())
                    if " ".join(locator.split()) in span and " ".join(excerpt.split()) in span:
                        abstract_matches.append(key)
                if not abstract_matches:
                    gaps.append("abstract_locator_or_excerpt_not_visible_in_open_record")
        receipts.append({"source_id": source_id, "discovery_action_ids": found,
                         "opened_action_ids": opened, "abstract_matched_action_ids": abstract_matches,
                         "gaps": gaps,
                         "status": "record_matched_pending_source_review" if not gaps
                         else "pending_original_source_or_abstract_record"})
    missing = not matched or any(row["gaps"] for row in receipts)
    if report["acceptance_status"] != "rejected" and missing:
        report["acceptance_status"] = "pending_candidate"
        report["acceptance_reason"] = "Missing independently matched Chat source-open or abstract records"
    report.update(chat_record_status="pending_original_chat_records" if missing
                  else "matched_visible_records_pending_authentication",
                  matched_action_ids=sorted(matched), chat_source_receipts=receipts,
                  native_cli_receipt=False, host_authenticated=False, formal_eligible=False)
    return report
