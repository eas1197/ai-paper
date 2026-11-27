"""Bind an S08 design to the existing, evidence-backed qualitative handoff."""

import hashlib
import json
from pathlib import Path

from run_mode import digest, load


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def artifact_lineage(work, directory):
    """Expose hash encodings and immutable paths to a reviewer without browser calls."""
    history = []
    while True:
        framework = directory / "framework.json"
        receipt_path = directory / "material_receipt.json"
        receipt = load(receipt_path)
        history.append({
            "framework_path": framework.relative_to(work).as_posix(),
            "framework_file_sha256": file_hash(framework),
            "framework_canonical_json_sha256": evidence_digest(load(framework)),
            "receipt_path": receipt_path.relative_to(work).as_posix(),
            "receipt_file_sha256": file_hash(receipt_path),
            "matrix_collection_sha256_equals_receipt_canonical_json_sha256": evidence_digest(receipt),
            "acquisition_events_sha256": file_hash(directory / "events.jsonl"),
            "acquisition_response_sha256": file_hash(directory / "response.json"),
            "parent_receipt_sha256": receipt.get("parent_receipt_sha256"),
        })
        if not receipt.get("parent_attempt"):
            return history
        directory = directory.parent / receipt["parent_attempt"]


def binding(work, directory):
    work, directory = Path(work).resolve(), Path(directory).resolve()
    if directory.parent != work / "qualitative_framework":
        raise ValueError("Framework is outside this run")
    frozen = load(work / "s08_topic.json")
    state = load(work / "staged_topic.json")
    framework = load(directory / "framework.json")
    conversion = load(directory / "conversion.json")
    receipt = load(directory / "material_receipt.json")
    if receipt.get("parent_attempt"):
        parent = directory.parent / receipt["parent_attempt"]
        if (parent.parent.resolve() != directory.parent or parent == directory
                or file_hash(parent / "material_receipt.json") != receipt["parent_receipt_sha256"]):
            raise ValueError("Parent material receipt changed")
        binding(work, parent)
        earlier = load(parent / "material_receipt.json")
        prior_rows = {row["material_id"]: row for row in earlier["materials"]}
        active = {row["material_id"]: row for row in receipt["materials"]}
        added, retired = set(receipt["added_material_ids"]), set(receipt["retired_material_ids"])
        if (not retired <= prior_rows.keys() or added & prior_rows.keys()
                or set(active) != (prior_rows.keys() - retired) | added
                or any(active[key] != prior_rows[key] for key in prior_rows.keys() - retired)
                or set(active) != {row["material_id"] for row in receipt["materials"]}
                or len(active) != len(receipt["materials"])):
            raise ValueError("Amended receipt does not preserve unmodified evidence")
    method = frozen["research_method"]
    reviewed = state["history"][-1]
    from staged_topic import evidence_hash
    if (state["status"] != "frozen" or state["question"] != frozen["question"]
            or reviewed["outcome"] != "pass" or reviewed["question"] != frozen["question"]
            or reviewed["evidence_sha256"] != frozen["evidence_sha256"]
            or frozen["evidence_sha256"] != evidence_hash(
                work, state, work / "merged_literature.json", work / "initial/theories.json")
            or evidence_digest(reviewed) != frozen["review_sha256"]
            or conversion["new_question"] != frozen["question"]
            or conversion["core_question"] != framework["core_question"]
            or receipt["run_id"] != work.name or receipt["phase"] != "framework_collection"
            or receipt["conversion_sha256"] != evidence_digest(conversion)
            or receipt["framework_sha256"] != evidence_digest(framework)
            or receipt["events_sha256"] != file_hash(directory / "events.jsonl")
            or receipt["response_sha256"] != file_hash(directory / "response.json")):
        raise ValueError("Question, reviewed freeze or qualitative evidence changed")
    return {
        "question_id": "RQ-" + digest([work.name, "S08"])[:24],
        "semantic_version": digest([framework["core_question"], frozen["question"], method,
                                    frozen["design"], frozen["review_sha256"]]),
        "core_question": framework["core_question"], "specific_question": frozen["question"],
        "method": method["path"], "freeze_sha256": file_hash(work / "s08_topic.json"),
        "framework_sha256": file_hash(directory / "framework.json"),
        "receipt_sha256": file_hash(directory / "material_receipt.json"),
    }
