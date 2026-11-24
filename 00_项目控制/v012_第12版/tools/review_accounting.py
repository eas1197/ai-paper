"""D29: observation-only counters. Original budget gates remain authoritative."""
import hashlib
import json
import re
from pathlib import Path
from review_execution import file_ref, load_ref


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def record_revision_round(work, *, stage, round_key, before, after, output, substantive, local):
    """Called after original successful artifact generation, not from candidate planners."""
    work = Path(work).resolve(strict=True)
    if stage not in {"matrix", "plan"} or not isinstance(round_key, str) or not round_key:
        raise ValueError("Invalid original revision round")
    if type(substantive) is not bool or type(local) is not bool or not (substantive or local):
        raise ValueError("Record the original revision categories explicitly")
    ref = file_ref(work, Path(output).relative_to(work))
    # Preserve native expenditure even when an original plan revision is identical.
    entry = {"stage":stage, "round_key":round_key, "before_digest":digest(before),
        "after_digest":digest(after), "output":ref, "substantive":substantive, "local":local,
        "changed":before != after, "independent_review_verified":False}
    key = digest([stage, round_key, entry["before_digest"], entry["after_digest"]])
    folder = work / "revision_accounting"
    folder.mkdir(exist_ok=True)
    if folder.resolve() != folder:
        raise ValueError("Revision accounting directory escapes run")
    target = folder / (key + ".json")
    raw = json.dumps(entry, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    try:
        with target.open("x", encoding="utf-8") as stream:
            stream.write(raw)
    except FileExistsError:
        if target.is_symlink() or target.read_text(encoding="utf-8") != raw:
            raise ValueError("Existing revision accounting record changed")
    return entry


def _read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _attempt_observations(work):
    rounds, retries, unresolved = [], [], []
    seen_threads = set()
    area = work / "autonomous_writing"
    if not area.exists():
        return rounds, retries, unresolved
    for label in sorted(area.iterdir()):
        if not label.is_dir() or not label.resolve().is_relative_to(work):
            continue
        if not re.fullmatch(r"(?:matrix_review|rebuilt_matrix_review|plan_review|matrix|plan|revision_routing|framework_repair|requirements_repair|rebuilt_matrix|revision_completion)_[a-zA-Z0-9_]+", label.name):
            continue
        previous_failed = False
        previous_attempt = None
        previous_request = None
        for attempt in sorted(label.glob("attempt_[0-9][0-9][0-9]")):
            if not attempt.is_dir() or not attempt.resolve().is_relative_to(work):
                continue
            relative = attempt.relative_to(work).as_posix()
            try:
                request = _read(attempt / "request.json")
                login = _read(attempt / "login.json")
                event_path = attempt / "events.jsonl"
                events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()] if event_path.is_file() else []
                starts = [e for e in events if e.get("type") == "thread.started"]
                started = len(starts) == 1 and bool(starts[0].get("thread_id"))
                failed = login.get("chatgpt") is False or any(e.get("type") == "turn.failed" for e in events)
                if previous_failed and started and login.get("chatgpt") is True and request == previous_request:
                    retries.append({"attempt":relative, "previous_failed_attempt":previous_attempt,
                        "events":file_ref(work,event_path.relative_to(work))})
                if (attempt / "validated.json").is_file():
                    validated = _read(attempt / "validated.json")
                    if (not started or failed or not any(e.get("type") == "turn.completed" for e in events)
                        or validated.get("thread_id") != starts[0]["thread_id"]
                        or file_ref(work,(attempt/"response.json").relative_to(work))["sha256"] != validated.get("response_sha256")
                        or _read(attempt/"response.json") != validated.get("answer")):
                        raise ValueError("Native attempt record mismatch")
                    if request.get("model") == "gpt-6.2-sol" and label.name.startswith(("matrix_review_","rebuilt_matrix_review_","plan_review_")):
                        thread = validated["thread_id"]
                        if thread not in seen_threads:
                            seen_threads.add(thread)
                            rounds.append({"attempt":relative, "thread_id":thread,
                                "validated":file_ref(work,(attempt/"validated.json").relative_to(work))})
                elif not failed:
                    unresolved.append(relative)
                previous_failed = failed
                previous_attempt = relative
                previous_request = request
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                unresolved.append(relative)
                previous_failed = False
                previous_attempt = None
                previous_request = None
    return rounds,retries,unresolved


def observed_counts(run_id):
    import task_packet
    h = task_packet.heritage
    h.run_id_guard(run_id)
    work = (h.RUNS / run_id).resolve(strict=True)
    manifest = task_packet.run_mode.verified_run(work)
    state = h.state_of(run_id)
    if manifest.get("run_id") != run_id or state.get("run_id") != run_id:
        raise ValueError("Original research identity mismatch")
    history = state.get("history", [])
    topic_reviews = {r["invocation_id"]:r for r in history if r.get("outcome") != "technical" and r.get("invocation_id")}
    technical_failures = {r["invocation_id"] for r in history if r.get("outcome") == "technical" and r.get("invocation_id")}
    rounds, retries, unresolved = _attempt_observations(work)
    entries = []
    folder = work / "revision_accounting"
    if folder.exists() and folder.resolve() != folder:
        raise ValueError("Revision accounting directory escapes run")
    for path in sorted(folder.glob("*.json")):
        row = _read(path)
        key = digest([row["stage"],row["round_key"],row["before_digest"],row["after_digest"]])
        if path.stem != key or type(row["substantive"]) is not bool or type(row["local"]) is not bool:
            raise ValueError("Revision accounting record mismatch")
        try:
            load_ref(work,row["output"])
        except (ValueError,OSError):
            unresolved.append(path.relative_to(work).as_posix())
            continue
        entries.append({"record":file_ref(work,path.relative_to(work)),**row})
    status_path = work / "autonomous_writing_status.json"
    native_status = _read(status_path) if status_path.is_file() else {}
    return {"research_id":run_id, "observed_counts":{
        "review_rounds":len(topic_reviews)+len(rounds),
        "substantive_revision_rounds":sum(r["substantive"] for r in entries),
        "local_revision_rounds":sum(r["local"] for r in entries),
        "technical_retry_attempts":len(retries)},
        "topic_review_invocations":sorted(topic_reviews),
        "native_topic_technical_failure_count":len(technical_failures),
        "native_writing_review_records":rounds, "native_technical_retry_records":retries,
        "revision_round_records":entries, "unresolved_records":sorted(set(unresolved)),
        "original_reported_writing_revisions":native_status.get("revisions",native_status.get("historical_revisions")),
        "original_reported_local_rounds":native_status.get("local_rounds"),
        "complete_history_guaranteed":False, "independent_review_verified":False,
        "budget_authority":"original state/history and resume_writing limits only",
        "limitations":["Historical rounds without durable receipts are not inferred.",
          "Native observed records are not host-authenticated independent review.",
          "Technical failures without a subsequent observed start are not retries.",
          "Candidate/fixture/wait records outside native execution folders are not counted."]}
