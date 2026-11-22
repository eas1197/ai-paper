"""Preserve critical exchanges and case-level evidence for experimental research."""

import argparse
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


def compare_events(packet):
    """Audit evidence attribution; academic interpretation is supplied by researchers."""
    sources = packet["sources"]
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
            if fact["source_id"] not in sources or urlsplit(sources[fact["source_id"]]).scheme != "https":
                raise ValueError("Use a traceable HTTPS source")
            if fact["status"] not in {"corroborated", "single_account", "unverified", "contradicted", "inference"}:
                raise ValueError("Classify credibility at fact level")
            if fact["status"] == "corroborated":
                retained.append(fact)
            else:
                uncertain.append(fact)
        events.append({"identity": identity, "retained_facts": retained, "uncertain_facts": uncertain,
                       "critical_gaps": [row["statement"] for row in uncertain if row["key"]]})
    return {"events": events, "event_count": len(events), "sensitivity": packet["sensitivity"],
            "interpretation_status": "pending_independent_review"}


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "v007_第7版/tools"))
    from run_mode import verified_run
    from staged_topic import digest, load, write

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-run", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    work = args.dev_run.resolve()
    manifest = verified_run(work)
    packet = load(args.input)
    state = load(work / "staged_topic.json")
    exchange_sha = state.get("exchange_sha256")
    if exchange_sha and digest(load(work / "explanation_exchange.json")) != exchange_sha:
        raise ValueError("Event comparison requires unchanged explanation and challenge")
    if not exchange_sha and state["status"] != "explanation_exchange":
        raise ValueError("Record the reality context before comparing events")
    result = compare_events(packet)
    result.update(run_id=manifest["run_id"], input_sha256=digest(packet),
                  exchange_sha256=exchange_sha, reality_sha256=state.get("reality_sha256"),
                  formal_eligible=False)
    output = work / "event_comparison.json"
    if output.exists():
        raise FileExistsError("Preserve the prior event comparison")
    write(output, result)
    print(output)


if __name__ == "__main__":
    main()
