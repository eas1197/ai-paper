"""C25 local dual-executor handoff and acceptance check.

No search dispatch, no fabricated original logs, no automatic task completion.
The receiver must select independently captured evidence from actual runs.
"""
import argparse
import json
from pathlib import Path
import re
import sys

import ai_paper5_strict as heritage
import task_packet
import result_bundle
import original_literature_gate


def preflight():
    """Explicit local CLI/login probe using the original implementation."""
    original_literature_gate._original()
    from codex_literature import cli_executable, cli_environment, login_probe
    try:
        executable = cli_executable()
    except RuntimeError as exc:
        return {"status": "blocked_missing_authorized_codex_environment",
                "cli_available": False, "login_checked": False, "reason": str(exc)}
    try:
        login = login_probe(executable, cli_environment())
    except (OSError, RuntimeError, heritage.subprocess.TimeoutExpired) as exc:
        return {"status": "blocked_login_probe", "cli_available": True,
                "login_checked": False, "reason": type(exc).__name__}
    return {"status": "local_login_confirmed" if login["chatgpt"] else "blocked_login",
            "cli_available": True, "login_checked": True,
            "chatgpt_login": login["chatgpt"], "exit_code": login["exit_code"],
            "search_executed": False}


def _write_new(path, obj):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _ref(work, path):
    return {"path": path.relative_to(work).as_posix(),
            "sha256": heritage.sha(path)}


def prepare_pair(run_id, phase, attempt):
    """Prepare two handoffs from the same actual permitted original phase."""
    heritage.run_id_guard(run_id)
    if phase not in heritage.PHASES or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", attempt):
        raise ValueError("Invalid phase or acceptance attempt")
    work = (heritage.RUNS / run_id).resolve()
    folder = (work / "c25_acceptance" / phase / attempt).resolve()
    if not folder.is_relative_to(work) or folder.exists():
        raise ValueError("Acceptance attempt must be a new in-run directory")
    chat = heritage.chat_task(run_id, phase)
    native = heritage.codex_task(run_id, phase)
    if (chat["task_packet"], chat["task_snapshot"]) != (native["task_packet"], native["task_snapshot"]):
        raise ValueError("Executors do not share the same frozen task")
    snapshot = task_packet.verify_snapshot(chat["task_snapshot"], current_run_id=run_id)
    if snapshot["packet"] != chat["task_packet"]:
        raise ValueError("Prepared task differs from the frozen packet")
    folder.mkdir(parents=True, exist_ok=False)
    for name, obj in (("chat_task.json", chat), ("codex_task.json", native)):
        _write_new(folder / name, obj)
    manifest = {"schema_version": 1, "kind": "c25_dual_executor_handoff",
                "task_snapshot": chat["task_snapshot"],
                "chat_task": _ref(work, folder / "chat_task.json"),
                "codex_task": _ref(work, folder / "codex_task.json"),
                "search_executed": False}
    _write_new(folder / "pair.json", manifest)
    return {"status": "prepared_only", "pair": _ref(work, folder / "pair.json"),
            "task_snapshot": chat["task_snapshot"], "formal_eligible": False}


def _read_ref(work, ref):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("Expected independently selected file reference")
    path = result_bundle._local_file(work, ref["path"])
    if heritage.sha(path) != ref["sha256"]:
        raise ValueError("Prepared handoff file hash changed")
    return heritage.read(path)


def audit_pair(run_id, pair_path, selections):
    """Run the same authoritative receiver on both actual saved result files.

    A matched report is a check of the supplied records only. The local
    operator must independently establish that both real executions occurred.
    """
    heritage.run_id_guard(run_id)
    work = (heritage.RUNS / run_id).resolve()
    manifest = heritage.read(result_bundle._local_file(work, pair_path))
    if (manifest.get("schema_version"), manifest.get("kind"), manifest.get("search_executed")) != (
            1, "c25_dual_executor_handoff", False):
        raise ValueError("Invalid prepared C25 handoff")
    reference = manifest["task_snapshot"]
    snapshot = task_packet.verify_snapshot(reference, current_run_id=run_id)
    for name, kind in (("chat_task", "chat_native_web"), ("codex_task", None)):
        task = _read_ref(work, manifest[name])
        if (task.get("task_snapshot") != reference or task.get("task_packet") != snapshot["packet"]
                or task.get("source_mode") != kind):
            raise ValueError("Prepared handoff does not match executor or current task")
    if not isinstance(selections, dict) or set(selections) != {"chat_native_web", "codex_cli"}:
        raise ValueError("Select exactly one result for each original executor")
    reports = {}
    checked_paths = set()
    for kind in ("chat_native_web", "codex_cli"):
        selection = selections[kind]
        allowed = {"result_path", "execution_binding"}
        if kind == "chat_native_web":
            allowed.add("observed_actions")
        if not isinstance(selection, dict) or set(selection) - allowed or not {"result_path", "execution_binding"} <= set(selection):
            raise ValueError("Select result and independent binding for " + kind)
        result_path = result_bundle._local_file(work, selection["result_path"])
        binding_path = result_bundle._local_file(work, selection["execution_binding"])
        if result_path == binding_path or result_path in checked_paths or binding_path in checked_paths:
            raise ValueError("Each selected result and binding must be separate files")
        checked_paths.update((result_path, binding_path))
        submitted = heritage.read(result_path)
        if submitted.get("executor") != kind or submitted.get("task_snapshot") != reference:
            raise ValueError("Selected result has wrong executor or task")
        observed = None
        if selection.get("observed_actions") is not None:
            observed_path = result_bundle._local_file(work, selection["observed_actions"])
            if observed_path in checked_paths:
                raise ValueError("Observed action selection must be a separate file")
            checked_paths.add(observed_path)
            observed = heritage.read(observed_path)
        report = original_literature_gate.audit_unified_literature(
            selection["result_path"], current_run_id=run_id, expected_reference=reference,
            expected_execution=heritage.read(binding_path), observed_actions=observed)
        if report["executor"] != kind or report["task_snapshot"] != reference:
            raise ValueError("Receiver identity mismatch")
        reports[kind] = report
    task_packet.verify_snapshot(reference, current_run_id=run_id)
    chat, native = reports["chat_native_web"], reports["codex_cli"]
    ready = (chat.get("independent_binding_matched") is True
             and bool(chat.get("matched_action_ids"))
             and chat.get("chat_record_status") == "matched_visible_records_pending_authentication"
             and chat.get("acceptance_status") != "rejected"
             and native.get("native_cli_receipt") is True
             and native.get("acceptance_status") != "rejected"
             and bool(native.get("original_abstract_eligible_ids"))
             and native.get("original_gate_status") == "original_abstract_receipt_matched_pending_stage_review")
    return {"status": "interface_records_matched_pending_operator_review" if ready
            else "pending_missing_dual_execution_evidence",
            "same_receiver_read_both": True, "task_snapshot": reference,
            "reports": reports, "formal_eligible": False,
            "c25_verified": False,
            "note": "Actual dual execution and independent provenance require operator confirmation; this check cannot authenticate Chat host records or complete C25."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight")
    p = sub.add_parser("prepare")
    p.add_argument("--run-id", required=True)
    p.add_argument("--phase", required=True, choices=sorted(heritage.PHASES))
    p.add_argument("--attempt", required=True)
    p = sub.add_parser("check")
    p.add_argument("--run-id", required=True)
    p.add_argument("--pair", required=True, help="Run-relative prepared pair.json")
    p.add_argument("--selections", required=True, help="Run-relative receiver selection JSON")
    args = parser.parse_args(argv)
    try:
        if args.command == "preflight":
            report = preflight()
        elif args.command == "prepare":
            report = prepare_pair(args.run_id, args.phase, args.attempt)
        else:
            heritage.run_id_guard(args.run_id)
            work = (heritage.RUNS / args.run_id).resolve()
            report = audit_pair(args.run_id, args.pair, heritage.read(
                result_bundle._local_file(work, args.selections)))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] in {"local_login_confirmed", "prepared_only",
                                          "interface_records_matched_pending_operator_review"} else 2
    except (ValueError, KeyError, TypeError, RuntimeError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    sys.exit(main())
