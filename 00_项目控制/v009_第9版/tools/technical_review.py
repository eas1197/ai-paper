"""Deterministic closure of verified artifact-only review conditions."""

import copy
import re

from question_binding import artifact_lineage, binding

TECH = re.compile(r"哈希|SHA[-_ ]?256|collection_sha256|framework_sha256|制品元数据|矩阵元数据|回执绑定|制品.{0,16}绑定", re.I)
ACADEMIC = re.compile(r"理论|命题|机制|结论|标线|锁态|关单|费用|案例|访谈|样本|phenomen|hypothes", re.I)
HEX = re.compile(r"(?<![a-f0-9])[a-f0-9]{8,64}(?![a-f0-9])", re.I)


def technical_text(text):
    return bool(TECH.search(text)) and not ACADEMIC.search(text)


def local_matrix_context(context, matrix, checks):
    """Scope analysis-only local changes when each one names existing dimensions."""
    rows = {row["dimension_id"]: row for row in matrix["rows"]}
    ids = set()
    for item in checks:
        if item.get("origin") != "analysis" or item.get("severity") != "local":
            return None
        selected = {key for key in rows if re.search(
            rf"(?<![\w]){re.escape(key)}(?![A-Za-z0-9_])", item["instruction"], re.ASCII)}
        if not selected:
            return None
        ids.update(selected)
    if not ids or ids == rows.keys():
        return None
    relevant = [row for key, row in rows.items() if key in ids]
    evidence_ids = {entry["material_id"] for row in relevant for entry in row["evidence"]}
    framework = context["framework"]
    return {
        "question_binding": context["question_binding"],
        "core_concept": framework["core_concept"],
        "dimensions": [row for row in framework["dimensions"] if row["id"] in ids],
        "matrix_rows": relevant,
        "materials": [row for row in context["receipt"]["materials"] if row["material_id"] in evidence_ids],
        "items": checks,
    }


def close_binding_review(work, folder, matrix, review):
    changes = review.get("changes") or []
    if review["decision"] != "revise" or not changes or not all(map(technical_text, changes)):
        return None
    contract = binding(work, folder)
    lineage = artifact_lineage(work, folder)
    hashes = {value for row in lineage for key, value in row.items()
              if "sha256" in key and isinstance(value, str)}
    def known(text):
        return all(any(value.startswith(prefix.lower()) for value in hashes) for prefix in HEX.findall(text))
    if not all(map(known, changes)) or matrix.get("question_binding") != contract:
        raise ValueError("Technical review refers to an unverified artifact binding")
    if matrix["collection_sha256"] != lineage[0]["matrix_collection_sha256_equals_receipt_canonical_json_sha256"]:
        raise ValueError("Matrix does not bind the current receipt")
    updated = copy.deepcopy(matrix)
    moved = []
    for row in updated["rows"]:
        for field in ("unresolved", "boundary"):
            sentences = re.findall(r"[^。！？\n]+[。！？\n]*", row[field])
            if "".join(sentences) != row[field]:
                continue
            keep = []
            for sentence in sentences:
                if technical_text(sentence) and known(sentence):
                    moved.append({"dimension_id": row["dimension_id"], "field": field, "text": sentence})
                else:
                    keep.append(sentence)
            row[field] = "".join(keep)
    if any(technical_text(sentence) for row in updated["rows"]
           for field in ("unresolved", "boundary") for sentence in row[field].split("。")):
        raise ValueError("Unresolved technical text lacks deterministic verification")
    updated["technical_metadata"] = {"artifact_lineage": lineage, "moved": moved,
                                     "resolved_conditions": changes}
    return updated
