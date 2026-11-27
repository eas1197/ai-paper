"""Review contract for research-method selection, independent of analysis engines."""

import hashlib
import json
import re

PATHS = {
    "quantitative": {
        "entry06": "existing_quantitative",
        "writing07": "existing_quantitative",
        "design05": "理论、研究假设、数据与统计设计",
    },
    "secondary_interviews": {
        "entry06": "planned",
        "writing07": "planned",
        "design05": "理论分析框架、研究命题、案例选择与二手访谈来源",
    },
    "online_qualitative": {
        "entry06": "planned",
        "writing07": "planned",
        "design05": "理论分析框架、研究命题、网络场域与文本或观察设计",
    },
}


def verify_material_review(work, path, decision, question):
    """Bind claims about qualitative availability to an actual search and its raw receipts."""
    status = decision["status"]
    if status not in {"missing", "ready"}:
        return
    attempt = decision.get("search_attempt", "")
    if not re.fullmatch(r"attempt_[0-9]{3}", attempt):
        raise ValueError(f"{path}: qualified material decision requires a search attempt")
    folder = work / "qualitative" / attempt
    receipt_path = folder / "material_receipt.json"
    try:
        raw_receipt = receipt_path.read_bytes()
        receipt = json.loads(raw_receipt)
        conversion = json.loads((folder / "conversion.json").read_bytes())
    except OSError as exc:
        raise ValueError(f"{path}: no actual qualitative search receipt") from exc
    def sha(file):
        return hashlib.sha256(file.read_bytes()).hexdigest()
    conversion_hash = hashlib.sha256(json.dumps(conversion, sort_keys=True, ensure_ascii=False,
                                                 separators=(",", ":")).encode()).hexdigest()
    if (hashlib.sha256(raw_receipt).hexdigest() != decision.get("receipt_sha256")
            or receipt.get("run_id") != work.name
            or receipt.get("status") != "pending_independent_review"
            or not receipt.get("tool_events")
            or receipt.get("conversion_sha256") != conversion_hash
            or sha(folder / "events.jsonl") != receipt.get("events_sha256")
            or sha(folder / "response.json") != receipt.get("response_sha256")):
        raise ValueError(f"{path}: search receipt or raw evidence has changed")
    if conversion.get("new_question") != question and not decision.get("reviewed_reuse"):
        raise ValueError(f"{path}: explain why the existing search can be reused for the revised question")
    if status == "missing" and decision.get("search_assessment") != "reasonable_but_insufficient":
        raise ValueError(f"{path}: distinguish insufficient search from insufficient material")
    if status == "ready":
        identifiers = {row["material_id"] for row in receipt["materials"] if row["path"] == path}
        if not set(decision["materials"]) <= identifiers:
            raise ValueError(f"{path}: ready requires material IDs verified in the applicable path")


def select_method(assessment, outcome):
    """Validate an independent review's decision without scoring research methods."""
    if not isinstance(assessment, dict):
        raise ValueError("A method assessment is required")
    paths = assessment.get("paths")
    if not isinstance(paths, dict) or set(paths) != set(PATHS):
        raise ValueError("Assess all three paths; explain any inapplicable path")
    for name, row in paths.items():
        if (not isinstance(row, dict)
                or row.get("status") not in {"ready", "missing", "unknown", "not_applicable"}
                or not isinstance(row.get("reason"), str) or not row["reason"].strip()):
            raise ValueError(f"{name} requires a status and evidence-based explanation")
        if row["status"] == "ready":
            materials = row.get("materials")
            if (not isinstance(materials, list) or not materials
                    or not all(isinstance(item, str) and item.strip() for item in materials)
                    or row.get("access") != "verified"):
                raise ValueError(f"{name} requires traceable materials and verified access")
            if name == "online_qualitative":
                if row.get("approach") not in {"public_text", "ethnography"}:
                    raise ValueError("Distinguish public text analysis from online ethnography")
                if row["approach"] == "ethnography" and row.get("observation") != "verified":
                    raise ValueError("Online ethnography requires verified observation conditions")
    selected = assessment.get("selected")
    if outcome == "pass":
        if selected not in PATHS or paths[selected]["status"] != "ready":
            raise ValueError("Select a path with a positive material review")
        return {"path": selected, "approach": paths[selected].get("approach"), **PATHS[selected]}
    if outcome == "missing_data":
        applicable = [row["status"] for row in paths.values() if row["status"] != "not_applicable"]
        if selected is not None or not applicable or any(status != "missing" for status in applicable):
            raise ValueError("Archive only after confirmed material gaps on all applicable paths")
    if outcome == "materials_pending":
        if selected is not None or not any(row["status"] == "unknown" for row in paths.values()):
            raise ValueError("A pending assessment requires an unresolved material check")
    return None
