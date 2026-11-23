"""Preserve critical exchanges and route unverified event facts to pending."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit


OBSERVATION = (
    "优先找真实事件和行动过程。观察事件、互动、决策和认知；这些是观察角度，不是论文章节。"
    "比较现实与有依据的预期，保留证据边界；允许具有独立价值的正常现象。"
    "解释时按问题自由选择行动、结构或结构—行动视角。可关注认知、协商与选择，"
    "制度、资源和权力约束，或条件与行动的相互作用。说明会改变结果的机制与竞争解释；"
    "制度条文和操作步骤可以作材料，但单凭它们不足以解释社会结果。"
)


def validate_exchange(packet):
    for key in ("expectation", "observation", "initial_explanation", "challenge",
                "candidate_question"):
        if not isinstance(packet.get(key), str) or not packet[key].strip():
            raise ValueError("Record the observation, expectation, explanation, challenge and resulting question")
    if packet.get("research_actor") == packet.get("critical_actor") or not all(
            packet.get(key) for key in ("research_actor", "critical_actor", "critical_receipt")):
        raise ValueError("Bind the independent critical contribution before searching literature")


def valid_https(url):
    if not isinstance(url, str):
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (parsed.scheme == "https" and bool(parsed.hostname)
            and not parsed.username and not parsed.password)


def relative_receipt_path(path, work, *, require_file=True):
    resolved = Path(path).resolve()
    root = Path(work).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Source receipt paths must stay inside the current research run")
    if require_file and not resolved.is_file():
        raise ValueError("Required source receipt file is missing inside the current research run")
    return resolved.relative_to(root).as_posix()


def opened_event(url, trace, canonicalize):
    canonical = canonicalize(url)
    if not canonical:
        return None
    for event in reversed(trace):
        action = event.get("action") if isinstance(event.get("action"), dict) else {}
        if (event.get("type") == "web_search"
                and action.get("type") in ("open_page", "find_in_page")
                and canonicalize(action.get("url")) == canonical
                and bool(event.get("results"))):
            return event
    return None


def build_source_receipts(packet, trace, *, work, events_path, response_path,
                          thread_id, url_event_fn, canonicalize):
    """Create verified or pending receipts without discarding unbound sources."""
    sources = packet.get("sources")
    if not isinstance(sources, dict):
        sources = {}
    events_file = Path(events_path).resolve()
    response_file = Path(response_path).resolve()
    events_rel = relative_receipt_path(events_file, work, require_file=False)
    response_rel = relative_receipt_path(response_file, work, require_file=False)
    events_sha = hashlib.sha256(events_file.read_bytes()).hexdigest() if events_file.is_file() else None
    response_sha = hashlib.sha256(response_file.read_bytes()).hexdigest() if response_file.is_file() else None

    receipts = {}
    for source_id, url in sources.items():
        canonical = canonicalize(url) if valid_https(url) else None
        search_event_id = url_event_fn(url, trace) if canonical and trace else None
        opened = opened_event(url, trace, canonicalize) if canonical and trace else None
        reason = None
        if not isinstance(source_id, str) or not source_id.strip():
            reason = "invalid_source_id"
        elif not canonical:
            reason = "invalid_https_url"
        elif not response_sha:
            reason = "missing_response_file"
        elif not events_sha:
            reason = "missing_events_file"
        elif not isinstance(thread_id, str) or not thread_id.strip():
            reason = "missing_thread_id"
        elif not search_event_id:
            reason = "source_not_found_in_current_trace"
        elif not opened:
            reason = "page_not_opened_in_current_trace"

        verified = reason is None
        open_id = opened.get("id") if opened else None
        action = opened.get("action") if opened and isinstance(opened.get("action"), dict) else {}
        receipts[source_id] = {
            "source_id": source_id,
            "url": canonical if canonical else url,
            "event_id": open_id or search_event_id,
            "open_event_id": open_id,
            "event_type": "web_search" if (open_id or search_event_id) else None,
            "action_type": action.get("type"),
            "opened": bool(opened),
            "thread_id": thread_id,
            "events_path": events_rel,
            "events_sha256": events_sha,
            "response_path": response_rel,
            "response_sha256": response_sha,
            "verification_status": "verified" if verified else "pending",
            "verification_reason": None if verified else reason,
        }
    return receipts


def compare_events(packet, source_receipts, *, canonicalize=None):
    """Keep all facts, but only promote facts with complete opened-source receipts."""
    sources = packet.get("sources")
    if not isinstance(sources, dict):
        sources = {}
    if not isinstance(source_receipts, dict):
        source_receipts = {}

    def canonical(url):
        if not valid_https(url):
            return None
        return canonicalize(url) if canonicalize else url

    normalized_receipts = {}
    pending_sources = []
    for source_id, url in sources.items():
        receipt = source_receipts.get(source_id)
        if not isinstance(receipt, dict):
            receipt = {
                "source_id": source_id, "url": canonical(url) or url,
                "opened": False, "verification_status": "pending",
                "verification_reason": "missing_source_receipt",
            }
        else:
            receipt = dict(receipt)

        expected_url = canonical(url)
        raw_hashes_ok = all(
            isinstance(receipt.get(key), str) and len(receipt[key]) == 64
            and all(char in "0123456789abcdef" for char in receipt[key].lower())
            for key in ("events_sha256", "response_sha256")
        )
        verified = (
            receipt.get("verification_status") == "verified"
            and receipt.get("source_id") == source_id
            and expected_url is not None
            and receipt.get("url") == expected_url
            and receipt.get("event_type") == "web_search"
            and receipt.get("opened") is True
            and receipt.get("event_id")
            and receipt.get("event_id") == receipt.get("open_event_id")
            and receipt.get("action_type") in ("open_page", "find_in_page")
            and isinstance(receipt.get("thread_id"), str) and bool(receipt["thread_id"])
            and bool(receipt.get("events_path")) and bool(receipt.get("response_path"))
            and raw_hashes_ok
        )
        if verified:
            receipt["verification_status"] = "verified"
            receipt["verification_reason"] = None
        else:
            receipt["verification_status"] = "pending"
            receipt["verification_reason"] = (
                receipt.get("verification_reason") or "source_receipt_incomplete_or_mismatched"
            )
            receipt["opened"] = bool(receipt.get("opened"))
            pending_sources.append({
                "source_id": source_id,
                "reason": receipt["verification_reason"],
            })
        normalized_receipts[source_id] = receipt

    seen = set()
    events = []
    pending_fact_count = 0
    for event in packet.get("events", []):
        identity = event["identity"].strip()
        if not identity or identity in seen:
            raise ValueError("Merge repeat accounts of the same event before comparison")
        seen.add(identity)
        retained, uncertain = [], []
        for fact in event["facts"]:
            if not fact.get("statement") or not fact.get("use") or type(fact.get("key")) is not bool:
                raise ValueError("Explain what the source says and what it can support")
            status = fact.get("status")
            if status not in {"corroborated", "single_account", "unverified", "contradicted", "inference"}:
                raise ValueError("Classify credibility at fact level")
            source_id = fact.get("source_id")
            receipt = normalized_receipts.get(source_id) if source_id in normalized_receipts else None
            if not receipt or receipt.get("verification_status") != "verified":
                reason = (receipt.get("verification_reason") if receipt else
                          "missing_source_id_or_source_map_entry")
                fact = dict(fact, model_claimed_status=status, status="unverified",
                            source_verification_status="pending",
                            source_verification_reason=reason,
                            source_receipt_id=source_id if receipt else None)
                uncertain.append(fact)
                pending_fact_count += 1
                continue

            fact = dict(fact, source_verification_status="verified",
                        source_receipt_id=source_id)
            if status == "corroborated":
                retained.append(fact)
            else:
                uncertain.append(fact)
        events.append({"identity": identity, "retained_facts": retained, "uncertain_facts": uncertain,
                       "critical_gaps": [row["statement"] for row in uncertain if row["key"]]})
    return {
        "events": events,
        "event_count": len(events),
        "sensitivity": packet.get("sensitivity", "unknown"),
        "sources": dict(sources),
        "source_receipts": normalized_receipts,
        "pending_sources": pending_sources,
        "pending_fact_count": pending_fact_count,
        "source_verification_status": "pending" if pending_sources or pending_fact_count else "verified",
        "interpretation_status": "pending_independent_review",
        "formal_eligible": False,
    }


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v007_第7版/tools"))
    from run_mode import verified_run
    from staged_topic import digest, load, write
    from codex_literature import evidence, url_event, web_url
    from collect_common import sha

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-run", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--events-jsonl", type=Path, required=True)
    args = parser.parse_args()
    work = args.dev_run.resolve()
    manifest = verified_run(work)
    input_path = args.input.resolve()
    events_path = args.events_jsonl.resolve()
    input_rel = relative_receipt_path(input_path, work)
    events_rel = relative_receipt_path(events_path, work, require_file=False)
    packet = load(input_path)
    state = load(work / "staged_topic.json")
    exchange_sha = state.get("exchange_sha256")
    if exchange_sha and digest(load(work / "explanation_exchange.json")) != exchange_sha:
        raise ValueError("Event comparison requires unchanged explanation and challenge")
    if not exchange_sha and state["status"] != "explanation_exchange":
        raise ValueError("Record the reality context before comparing events")

    trace = []
    if events_path.is_file():
        try:
            trace = evidence(events_path)
        except (OSError, ValueError, json.JSONDecodeError):
            trace = []
    thread_id = None
    if events_path.is_file():
        try:
            with events_path.open(encoding="utf-8-sig") as stream:
                for line in stream:
                    event = json.loads(line)
                    if event.get("type") == "thread.started" and event.get("thread_id"):
                        thread_id = event["thread_id"]
                        break
        except (OSError, ValueError, json.JSONDecodeError):
            thread_id = None

    receipts = build_source_receipts(
        packet, trace, work=work, events_path=events_path, response_path=input_path,
        thread_id=thread_id, url_event_fn=url_event, canonicalize=web_url,
    )
    result = compare_events(packet, receipts, canonicalize=web_url)
    result.update(run_id=manifest["run_id"], input_sha256=digest(packet),
                  input_path=input_rel, response_sha256=sha(input_path),
                  events_path=events_rel,
                  events_sha256=sha(events_path) if events_path.is_file() else None,
                  thread_id=thread_id, exchange_sha256=exchange_sha,
                  reality_sha256=state.get("reality_sha256"))
    output = work / "event_comparison.json"
    if output.exists():
        raise FileExistsError("Preserve the prior event comparison")
    write(output, result)
    print(output)


if __name__ == "__main__":
    main()
