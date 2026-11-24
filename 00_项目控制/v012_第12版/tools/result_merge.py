"""C24: merge candidate views without merging or rewriting executor receipts."""
import json
from pathlib import Path

import chat_receiving
import codex_receiving
import result_bundle
import source_identity
import task_packet


def merge_result_bundles(selections, *, current_run_id, expected_reference,
                         reviewed_report_aliases=None):
    """Selections and execution bindings are chosen by the receiver, not the model."""
    task_packet.verify_snapshot(expected_reference, current_run_id=current_run_id)
    if not isinstance(selections, list) or not selections:
        raise ValueError("Explicit nonempty receiver selections required")
    work = (task_packet.heritage.RUNS / current_run_id).resolve()
    bundles, rows, origins = [], [], []
    digests, paths, raw_owners = set(), set(), {}
    for selection in selections:
        if (not isinstance(selection, dict)
                or not {"result_path"} <= set(selection)
                or set(selection) - {"result_path", "expected_execution", "observed_actions"}):
            raise ValueError("Invalid receiver result selection")
        rel = selection["result_path"]
        path = result_bundle._local_file(work, rel)
        if path in paths:
            raise ValueError("Duplicate result file selection")
        paths.add(path)
        submitted = json.loads(path.read_text(encoding="utf-8-sig"))
        kwargs = dict(current_run_id=current_run_id, expected_reference=expected_reference,
                      expected_execution=selection.get("expected_execution"))
        kind = submitted.get("executor")
        if kind == "chat_native_web":
            report = chat_receiving.audit_chat_records(rel, observed_actions=selection.get("observed_actions"), **kwargs)
        elif kind == "codex_cli":
            report = codex_receiving.audit_codex_records(rel, **kwargs)
        else:
            if selection.get("observed_actions") is not None:
                raise ValueError("Chat observations cannot be assigned to another executor")
            report = result_bundle.audit_result_bundle(rel, **kwargs)
        sha = report["result_sha256"]
        if task_packet.heritage.sha(path) != sha:
            raise ValueError("Result changed during merge")
        if sha in digests:
            raise ValueError("Duplicate result bytes cannot count as separate submissions")
        digests.add(sha)
        if report["executor"] != kind:
            raise ValueError("Executor changed during merge")
        for ref in report["checked_files"]:
            raw_path = result_bundle._local_file(work, ref["path"])
            prior = raw_owners.get(raw_path)
            identity = (kind, ref["sha256"])
            if prior is not None and prior != identity:
                raise ValueError("Original record path reused across executor identities or changed")
            raw_owners[raw_path] = identity
        record = {"executor": kind, "result_path": rel, "result_sha256": sha,
                  "task_snapshot": expected_reference, "provenance": submitted["provenance"],
                  "search_actions": submitted["search_actions"],
                  "execution_status": submitted["execution_status"],
                  "execution_issues": submitted["execution_issues"],
                  "failure_reasons": submitted["failure_reasons"], "audit": report}
        bundles.append(record)
        ids = set()
        for index, row in enumerate(submitted["sources"]):
            if row["source_id"] in ids:
                raise ValueError("Duplicate source ID within original result")
            ids.add(row["source_id"])
            rows.append(row)
            origins.append({"result_sha256": sha, "result_path": rel, "executor": kind,
                            "source_index": index, "original_source_id": row["source_id"],
                            "original_action_ids": row["action_ids"],
                            "acceptance_status": report["acceptance_status"]})
    if paths.intersection(raw_owners):
        raise ValueError("Original execution record cannot also be a selected result")
    # Group only non-rejected candidates. Preserve rejected rows separately.
    eligible_indexes = [i for i, origin in enumerate(origins) if origin["acceptance_status"] != "rejected"]
    grouped = source_identity.group_sources([rows[i] for i in eligible_indexes],
                                           reviewed_report_aliases=reviewed_report_aliases)
    def attach(member):
        index = eligible_indexes[member["index"]]
        return {"record": rows[index], "origin": origins[index]}
    groups = []
    for group in grouped["groups"]:
        groups.append(dict(group, members=[attach(member) for member in group["members"]]))
    conflicts = [{"reason": item["reason"], "origins": [origins[eligible_indexes[i]] for i in item["indexes"]]}
                 for item in grouped["conflicts"]]
    rejected = [{"record": rows[i], "origin": origin} for i, origin in enumerate(origins)
                if origin["acceptance_status"] == "rejected"]
    # Recheck all bytes after all inputs have been read.
    for record in bundles:
        if task_packet.heritage.sha(result_bundle._local_file(work, record["result_path"])) != record["result_sha256"]:
            raise ValueError("Original result changed during merge")
        for ref in record["audit"]["checked_files"]:
            if task_packet.heritage.sha(result_bundle._local_file(work, ref["path"])) != ref["sha256"]:
                raise ValueError("Original receipt changed during merge")
    task_packet.verify_snapshot(expected_reference, current_run_id=current_run_id)
    return {"schema_version": 1, "kind": "merged_candidate_index", "task_snapshot": expected_reference,
            "original_results": bundles, "groups": groups, "conflicts": conflicts,
            "quarantined": [attach(member) for member in grouped["quarantined"]],
            "rejected": rejected, "candidate_group_count": len(groups),
            "formal_eligible": False,
            "note": "Candidate grouping does not confer independent evidence, formal eligibility or original v009 quota."}


def write_merge_index(index, *, current_run_id, output):
    """Create a new index only; never overwrite an original record or prior index."""
    task_packet.heritage.run_id_guard(current_run_id)
    work = (task_packet.heritage.RUNS / current_run_id).resolve()
    raw = Path(output)
    if raw.is_absolute() or "\\" in output or ":" in output or ".." in raw.parts:
        raise ValueError("Merge output escapes current run")
    path = (work / raw).resolve()
    if not path.is_relative_to(work) or path == work:
        raise ValueError("Merge output escapes current run")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(index, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return path
