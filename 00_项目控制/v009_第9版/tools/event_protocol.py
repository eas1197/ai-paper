"""Preserve critical exchanges and bind event facts to native search receipts."""

import argparse
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


def relative_receipt_path(path, work):
    resolved = Path(path).resolve()
    root = Path(work).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Source receipt files must exist inside the current research run")
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
    """Bind each declared source to an event in this exact native CLI attempt."""
    sources = packet.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Event comparison requires a non-empty source map")
    events_rel = relative_receipt_path(events_path, work)
    response_rel = relative_receipt_path(response_path, work)
    events_sha = __import__("hashlib").sha256(Path(events_path).read_bytes()).hexdigest()
    response_sha = __import__("hashlib").sha256(Path(response_path).read_bytes()).hexdigest()
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("Native event receipt requires a real thread ID")

    receipts = {}
    for source_id, url in sources.items():
        if not isinstance(source_id, str) or not source_id.strip() or not valid_https(url):
            raise ValueError("Each source needs a non-empty ID and valid HTTPS URL")
        canonical = canonicalize(url)
        search_event_id = url_event_fn(url, trace)
        if not canonical or not search_event_id:
            raise ValueError("Source URL is not present in this native search attempt")
        opened = opened_event(url, trace, canonicalize)
        if not opened:
            raise ValueError("Source URL has no matching native page-open event")
        event_id = opened["id"]
        action = opened.get("action") if isinstance(opened.get("action"), dict) else {}
        action_type = action.get("type")
        receipts[source_id] = {
            "source_id": source_id,
            "url": canonical,
            "event_id": event_id,
            "open_event_id": event_id,
            "event_type": opened["type"],
            "action_type": action_type,
            "opened": True,
            "thread_id": thread_id,
            "events_path": events_rel,
            "events_sha256": events_sha,
            "response_path": response_rel,
            "response_sha256": response_sha,
        }
    return receipts


def compare_events(packet, source_receipts, *, canonicalize=None):
    """Audit event facts and require an attempt-bound receipt for each source."""
    sources = packet.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("Event comparison requires a non-empty source map")
    if not isinstance(source_receipts, dict):
        raise ValueError("Missing native source receipts")

    def canonical(url):
        return canonicalize(url) if canonicalize else url

    normalized_receipts = {}
    for source_id, url in sources.items():
        if not isinstance(source_id, str) or not source_id.strip() or not valid_https(url):
            raise ValueError("Use a traceable HTTPS source with a non-empty source ID")
        receipt = source_receipts.get(source_id)
        required = ("source_id", "url", "event_id", "open_event_id", "event_type",
                    "action_type", "thread_id", "events_path", "events_sha256",
                    "response_path", "response_sha256")
        if not isinstance(receipt, dict):
            raise ValueError("Missing source-to-event raw receipt binding")
        missing = [key for key in required
                   if key not in receipt or receipt[key] is None or receipt[key] == ""]
        if missing:
            raise ValueError("Missing source-to-event raw receipt binding: " + ", ".join(missing))
        if (receipt["source_id"] != source_id
                or receipt["url"] != canonical(url)
                or receipt["event_type"] != "web_search"):
            raise ValueError("Source receipt ID or URL mismatch; event type must be native web_search")
        if len(receipt["events_sha256"]) != 64 or len(receipt["response_sha256"]) != 64:
            raise ValueError("Source receipt raw file hashes are malformed")
        if (receipt.get("opened") is not True
                or receipt["event_id"] != receipt["open_event_id"]
                or receipt["action_type"] not in ("open_page", "find_in_page")):
            raise ValueError("Source receipt requires a matching native page-open event")
        normalized_receipts[source_id] = dict(receipt)

    seen = set()
    events = []
    for event in packet["events"]:
        identity = event["identity"].strip()
        if not identity or identity in seen:
            raise ValueError("Merge repeat accounts of the same event before comparison")
        seen.add(identity)
        retained, uncertain = [], []
        for fact in event["facts"]:
            if not fact.get("statement") or not fact.get("use") or type(fact.get("key")) is not bool:
                raise ValueError("Explain what the source says and what it can support")
            source_id = fact.get("source_id")
            if source_id not in sources or source_id not in normalized_receipts:
                raise ValueError("Every event fact must bind to a verified source receipt")
            if fact["status"] not in {"corroborated", "single_account", "unverified", "contradicted", "inference"}:
                raise ValueError("Classify credibility at fact level")
            fact = dict(fact, source_receipt_id=source_id)
            if fact["status"] == "corroborated":
                retained.append(fact)
            else:
                uncertain.append(fact)
        events.append({"identity": identity, "retained_facts": retained, "uncertain_facts": uncertain,
                       "critical_gaps": [row["statement"] for row in uncertain if row["key"]]})
    return {"events": events, "event_count": len(events), "sensitivity": packet["sensitivity"],
            "sources": dict(sources), "source_receipts": normalized_receipts,
            "interpretation_status": "pending_independent_review"}


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
    events_rel = relative_receipt_path(events_path, work)
    packet = load(input_path)
    state = load(work / "staged_topic.json")
    exchange_sha = state.get("exchange_sha256")
    if exchange_sha and digest(load(work / "explanation_exchange.json")) != exchange_sha:
        raise ValueError("Event comparison requires unchanged explanation and challenge")
    if not exchange_sha and state["status"] != "explanation_exchange":
        raise ValueError("Record the reality context before comparing events")

    trace = evidence(events_path)
    if not trace:
        raise ValueError("Event comparison requires native web_search events")
    thread_id = None
    with events_path.open(encoding="utf-8-sig") as stream:
        for line in stream:
            event = json.loads(line)
            if event.get("type") == "thread.started" and event.get("thread_id"):
                thread_id = event["thread_id"]
                break
    if not thread_id:
        raise ValueError("Event comparison raw log has no authentic thread.started ID")

    receipts = build_source_receipts(
        packet, trace, work=work, events_path=events_path, response_path=input_path,
        thread_id=thread_id, url_event_fn=url_event, canonicalize=web_url,
    )
    result = compare_events(packet, receipts, canonicalize=web_url)
    result.update(run_id=manifest["run_id"], input_sha256=digest(packet),
                  input_path=input_rel, response_sha256=sha(input_path),
                  events_path=events_rel, events_sha256=sha(events_path),
                  thread_id=thread_id, exchange_sha256=exchange_sha,
                  reality_sha256=state.get("reality_sha256"), formal_eligible=False)
    output = work / "event_comparison.json"
    if output.exists():
        raise FileExistsError("Preserve the prior event comparison")
    write(output, result)
    print(output)


if __name__ == "__main__":
    main()
