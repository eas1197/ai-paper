"""Verify the references and source anchors of a topic evidence bundle."""

import hashlib
import json
from pathlib import Path


def validate_bundle(bundle, root):
    if bundle.get("schema_version") != 1:
        raise ValueError("Unsupported topic evidence schema")
    root = Path(root).resolve()
    indexes = {}
    for collection, field in (
        ("opportunities", "opportunity_id"), ("questions", "question_id"),
        ("evidence", "evidence_id"), ("explanations", "explanation_id"),
        ("critiques", "critique_id"),
    ):
        rows = bundle[collection]
        index = {row[field]: row for row in rows}
        if len(index) != len(rows) or any(not key for key in index):
            raise ValueError(f"Empty or duplicate identifier in {collection}")
        indexes[collection] = index

    def require(collection, keys, *, nonempty=True):
        if not isinstance(keys, list) or (nonempty and not keys) or any(key not in indexes[collection] for key in keys):
            raise ValueError(f"Missing reference in {collection}: {keys}")

    def text_fields(row, *fields):
        for field in fields:
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Record requires {field}")

    for record in bundle["evidence"]:
        text_fields(record, "source_id", "document_id", "excerpt", "path")
        if record.get("kind") not in {"abstract", "fulltext", "context"}:
            raise ValueError("Unknown evidence kind")
        if record["kind"] != "context":
            text_fields(record, "paper_id")
        text_fields(record["locator"], "section")
        path = (root / record["path"]).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"Evidence path escapes the project: {record['evidence_id']}")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError(f"Evidence hash changed: {record['evidence_id']}")
        page = record["locator"].get("page")
        source = raw.decode("utf-8-sig")
        if page is not None:
            pages = json.loads(source)
            if type(page) is not int or not isinstance(pages, list) or not 1 <= page <= len(pages):
                raise ValueError(f"Invalid source page: {record['evidence_id']}")
            source = pages[page - 1]
        excerpt = record["excerpt"]
        if not excerpt.strip() or excerpt not in source:
            raise ValueError(f"Excerpt not found: {record['evidence_id']}")

    opportunity_keys = set()
    for row in bundle["opportunities"]:
        text_fields(row, "observation", "social_process")
        key = tuple("".join(row[field].split()).casefold() for field in ("observation", "social_process"))
        if key in opportunity_keys:
            raise ValueError("Duplicate opportunity")
        opportunity_keys.add(key)
        require("evidence", row["evidence_ids"])
    for row in bundle["questions"]:
        text_fields(row, "text", "population", "scope", "comparison", "answer_value")
        if not isinstance(row.get("concepts"), list) or not row["concepts"]:
            raise ValueError("Question requires core concepts")
        require("opportunities", [row["opportunity_id"]])
    for row in bundle["explanations"]:
        text_fields(row, "author_claim", "applicable_scope", "evidence_strength")
        if any(row[key] is None for key in ("proposed_mechanism", "observed_result", "system_inference")):
            text_fields(row, "unknown_reason")
        require("questions", [row["question_id"]])
        require("evidence", row["evidence_ids"])
        if all(indexes["evidence"][key]["kind"] == "abstract" for key in row["evidence_ids"]) and row["evidence_strength"] != "author_report":
            raise ValueError("Abstract-only explanations must remain author reports")
    for row in bundle["critiques"]:
        text_fields(row, "text")
        if row.get("kind") not in {"premise", "counterexample", "competing", "boundary", "evidence"}:
            raise ValueError("Unknown critique kind")
        require("explanations", row["explanation_ids"])
        require("evidence", row["evidence_ids"])
    for row in bundle["evolution"]:
        require("questions", [row["question_id"], row["next_question_id"]])
        require("explanations", row["explanation_ids"])
        require("critiques", row["critique_ids"])
        if any(indexes["explanations"][key]["question_id"] != row["question_id"]
               for key in row["explanation_ids"]):
            raise ValueError("Explanation belongs to a different question")
        if any(not set(indexes["critiques"][key]["explanation_ids"]).issubset(row["explanation_ids"])
               for key in row["critique_ids"]):
            raise ValueError("Critique refers to an explanation outside this round")
        if row["disposition"] not in {"retained", "rejected"} or not row["increment"].strip():
            raise ValueError("Evolution record needs a stated outcome and reason")
    return {name: len(index) for name, index in indexes.items()} | {"evolution": len(bundle["evolution"])}
