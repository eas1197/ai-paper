"""Separate feasibility from actual evidentiary adequacy at writing handoff."""


def writing_material_status(assessment, material_ids):
    if assessment is None:
        return "awaiting_material_adequacy"
    if not isinstance(assessment, dict):
        raise ValueError("Independent material adequacy assessment must be an object")
    eligible = assessment.get("eligible_event_ids")
    if (not isinstance(eligible, list) or not all(isinstance(item, str) for item in eligible)
            or len(eligible) != len(set(eligible)) or not set(eligible) <= set(material_ids)):
        raise ValueError("Eligible events must use distinct IDs from the current receipt")
    if not isinstance(assessment.get("reason"), str) or not assessment["reason"].strip():
        raise ValueError("Material adequacy requires a reason")
    relation = assessment.get("support")
    if relation not in {"sufficient", "insufficient", "unknown"}:
        raise ValueError("Unknown material adequacy decision")
    if not eligible and relation == "sufficient":
        raise ValueError("No eligible evidence demonstrably answers the research question")
    return {"sufficient": "ready", "insufficient": "insufficient_core_material",
            "unknown": "awaiting_material_adequacy"}[relation]
