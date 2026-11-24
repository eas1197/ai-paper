"""C20: Codex native receipt audit, retaining original 3.x source authority."""
import json
from pathlib import Path
import re
import sys

from jsonschema import ValidationError
import result_bundle
import task_packet


def _original():
    path = str(task_packet.heritage.ROOT / "04_议题文献与现实/v012_第12版/tools")
    if path not in sys.path:
        sys.path.insert(0, path)
    from native_library import registry
    registry()
    from codex_literature import evidence, proof, web_url
    return evidence, proof, web_url


def _checked_record(work, ref):
    path = result_bundle._local_file(work, ref["path"])
    if task_packet.heritage.sha(path) != ref["sha256"]:
        raise ValueError("Original Codex record changed")
    return path


def _command_matches(argv, run_id, refs):
    if not isinstance(argv, list) or not argv:
        raise ValueError("Missing actual Codex argv")
    executable = argv[0].replace("\\", "/").split("/")[-1].lower()
    if executable not in {"codex", "codex.exe"}:
        raise ValueError("Unexpected Codex executable")
    prefix = ["-a", "never", "--search", "exec", "--ignore-user-config",
              "-s", "read-only", "--ephemeral", "--skip-git-repo-check", "-C"]
    if argv[1:11] != prefix or len(argv) not in (18, 20) or argv[12:14] != ["--json", "--output-schema"] or argv[15] != "-o" or argv[-1] != "-":
        raise ValueError("Actual Codex command differs from original read-only native contract")
    if len(argv) == 20 and argv[17] != "-m":
        raise ValueError("Unexpected Codex optional arguments")
    def ends(raw, suffix):
        normalized = raw.replace("\\", "/").rstrip("/")
        return normalized.endswith("/" + run_id + "/" + suffix) or normalized == run_id + "/" + suffix
    folder = Path(refs["events"]["path"]).parent.as_posix()
    # Original v009 supplies its repository schema, not a generated run file.
    # A receiver-owned copy must still bind the actual original schema bytes.
    schema_path = argv[14].replace("\\", "/")
    original_schema = task_packet.heritage.NATIVE_SCHEMA
    original_suffix = original_schema.relative_to(task_packet.heritage.ROOT).as_posix()
    schema_matches = ends(argv[14], refs["schema"]["path"]) or (
        (schema_path.endswith("/" + original_suffix) or schema_path == original_suffix)
        and refs["schema"]["sha256"] == task_packet.heritage.sha(original_schema))
    if not ends(argv[11], folder) or not schema_matches or not ends(argv[16], refs["response"]["path"]):
        raise ValueError("Actual command paths do not match original attempt files")


def audit_codex_records(result_path, *, current_run_id, expected_reference,
                        expected_execution=None):
    try:
        report = result_bundle.audit_result_bundle(
            result_path, current_run_id=current_run_id, expected_reference=expected_reference,
            expected_execution=expected_execution)
    except ValidationError as exc:
        raise ValueError("Invalid result envelope: " + exc.message) from exc
    if report["executor"] != "codex_cli":
        raise ValueError("Only codex_cli result accepted")
    work = (task_packet.heritage.RUNS / current_run_id).resolve()
    path = result_bundle._local_file(work, result_path)
    bundle = json.loads(path.read_text(encoding="utf-8-sig"))
    if task_packet.heritage.sha(path) != report["result_sha256"]:
        raise ValueError("Result changed during intake")
    p = bundle["provenance"]
    roles = ("events", "response", "stderr", "prompt", "schema", "login")
    missing = sorted(set(report["missing_fields"]) | {
        key for key in (*roles, "command_record") if p.get(key) is None})
    trace = []
    session = None
    if p.get("events") is not None:
        events_path = _checked_record(work, p["events"])
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8-sig").splitlines()]
        sessions = [item.get("thread_id") for item in events if item.get("type") == "thread.started"]
        if len(sessions) != 1 or not sessions[0] or sessions[0] != p["thread_id"]:
            raise ValueError("Codex thread.started receipt missing or mismatched")
        session = sessions[0]
        evidence, proof, web_url = _original()
        trace = evidence(events_path)
        ids = [row.get("id") for row in trace]
        if any(not isinstance(key, str) or not key for key in ids) or len(set(ids)) != len(ids):
            raise ValueError("Missing or duplicate native event identity")
    else:
        evidence, proof, web_url = _original()
    if p.get("login") is not None:
        login = json.loads(_checked_record(work, p["login"]).read_text(encoding="utf-8-sig"))
        text = str(login.get("stdout", "")) + "\n" + str(login.get("stderr", ""))
        if login.get("chatgpt") is not True or type(login.get("exit_code")) is not int or login["exit_code"] != 0 or not any(
                re.fullmatch(r"\s*logged\s+in\s+using\s+chatgpt\s*\.?\s*", line, re.I)
                for line in text.splitlines()):
            missing.append("successful_chatgpt_login_diagnostics")
    command_matched = False
    if p.get("command_record") is not None:
        record = json.loads(_checked_record(work, p["command_record"]).read_text(encoding="utf-8-sig"))
        expected = {"task_snapshot": expected_reference, "argv": p["command"],
                    "exit_code": p["exit_code"], "thread_id": p["thread_id"],
                    "files": {role: p.get(role) for role in roles}}
        if record != expected:
            raise ValueError("Actual invocation record does not match task or files")
        if not missing:
            _command_matches(p["command"], current_run_id, p)
            command_matched = expected_execution is not None
    if p.get("response") is not None:
        response = json.loads(_checked_record(work, p["response"]).read_text(encoding="utf-8-sig"))
        if not isinstance(response, dict):
            raise ValueError("Original Codex response is not an object")
    raw_by_id = {row["id"]: row for row in trace}
    actions = {}
    for action in bundle["search_actions"]:
        key = action["action_id"]
        if key in actions:
            raise ValueError("Duplicate normalized Codex action ID")
        actions[key] = action
    sources = []
    for row in bundle["sources"]:
        urls = {row[key] for key in ("original_url", "metadata_url", "abstract_url") if row[key]}
        matched, opened = [], []
        for key in row["action_ids"]:
            item, action = raw_by_id.get(key), actions.get(key)
            if not item or not action or row["source_id"] not in action["source_ids"]:
                continue
            event_action = item.get("action") or {}
            kind = event_action.get("type")
            if kind != action["action_type"]:
                continue
            if kind == "search":
                raw_queries = event_action.get("queries") or [event_action.get("query")]
                if action["query"] is not None and action["query"] not in raw_queries:
                    continue
            supported = sorted(url for url in urls if proof(url, key, trace))
            if not supported:
                continue
            matched.append({"event_id": key, "urls": supported})
            if kind in ("open_page", "find_in_page") and action["original_url"] and web_url(action["original_url"]) == web_url(event_action.get("url")) and any(
                    web_url(url) == web_url(event_action.get("url")) for url in supported):
                opened.append(key)
        covered = {url for match in matched for url in match["urls"]}
        sources.append({"source_id": row["source_id"], "matched_events": matched,
                        "opened_event_ids": opened, "unmatched_urls": sorted(urls-covered),
                        "status": "matched_native_urls_pending_original_gate" if urls and urls <= covered
                        else "pending_native_source_receipt"})
    missing = sorted(set(missing))
    complete = (not missing and command_matched and p["exit_code"] == 0 and bool(trace)
                and report["status"] == "records_hash_bound_pending_source_verification"
                and bundle["execution_status"] in {"completed", "partial_results"}
                and bool(sources) and all(row["status"] == "matched_native_urls_pending_original_gate" for row in sources))
    if report["acceptance_status"] != "rejected" and not complete:
        report["acceptance_status"] = "pending_candidate"
        report["acceptance_reason"] = "Incomplete independent CLI execution or URL evidence"
    report.update(codex_record_status="matched_native_records_pending_original_gate" if complete
                  else "pending_native_records", codex_source_receipts=sources,
                  thread_id=session, native_event_count=len(trace),
                  command_record_matched=command_matched, missing_native_fields=missing,
                  native_cli_receipt=bool(complete), formal_eligible=False)
    return report
