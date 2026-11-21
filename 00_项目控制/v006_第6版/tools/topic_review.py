"""Contract for a separately invoked topic review agent."""

import hashlib
import json


REVIEW_MODEL = "gpt-6.2-sol"
VERDICTS = {
    "opportunity": {"PASS", "REVISE", "REJECT", "UNCERTAIN"},
    "question": {"PASS", "REVISE", "REJECT", "UNCERTAIN"},
    "deepening": {"DEEPEN", "BRANCH", "READY", "STOP"},
    "final": {"PASS", "REVISE", "REJECT", "UNCERTAIN"},
}
COUNTERS = ("model_calls", "search_calls")


def content_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_counts(value):
    return (isinstance(value, dict) and set(value) == set(COUNTERS)
            and all(type(count) is int and count >= 0 for count in value.values()))


def validate_review(review, bundle, stage, model=REVIEW_MODEL):
    if review.get("stage") != stage or review.get("verdict") not in VERDICTS[stage]:
        raise ValueError("Unexpected stage or verdict")
    if (review.get("model") != model or not review.get("invocation_id")
            or review.get("input_sha256") != content_hash(bundle)):
        raise ValueError("Model, independent invocation or review input could not be confirmed")
    evidence = {row["evidence_id"] for row in bundle["evidence"]}
    anchors = review.get("evidence", [])
    if not anchors or any(item.get("evidence_id") not in evidence or not item.get("locator")
                          or not item.get("finding") for item in anchors):
        raise ValueError("Review lacks verifiable evidence references")
    for field in ("strongest_objection", "actual_increment", "gap", "reason"):
        if not isinstance(review.get(field), str) or not review[field].strip():
            raise ValueError(f"Review needs {field}")
    if not validate_counts(review.get("cost")) or type(review.get("action_worth_cost")) is not bool:
        raise ValueError("Review needs estimated calls and a marginal-benefit judgment")
    if review["verdict"] in {"DEEPEN", "BRANCH", "REVISE"}:
        if not review.get("next_action") or not review.get("expected_gain") or not review["action_worth_cost"]:
            raise ValueError("Continuation requires a concrete and worthwhile next action")
