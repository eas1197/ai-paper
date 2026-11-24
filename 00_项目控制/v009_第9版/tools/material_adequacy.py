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


def approved_matrix_materials(assessment, receipt, matrix):
    """Conservative writing-source scope from the original adequacy gate.

    This is a deterministic restriction, not an independent review or permission
    to write. The caller must already have passed the original review and checked
    the current matrix, frozen design and receipt binding.
    """
    materials = {row["material_id"]: row for row in receipt["materials"]}
    if len(materials) != len(receipt["materials"]):
        raise ValueError("Duplicate receipt material IDs")
    if writing_material_status(assessment, materials) != "ready":
        raise ValueError("Material adequacy is not ready for writing")
    eligible = set(assessment["eligible_event_ids"])
    refs = set()
    for row in matrix["rows"]:
        for item in row["evidence"]:
            key = item["material_id"]
            if key not in materials:
                raise ValueError("Matrix material outside current receipt")
            original = materials[key]
            for field in ("url", "locator", "kind"):
                if item.get(field) != original.get(field) or not original.get(field):
                    raise ValueError("Matrix source identity differs from original receipt")
            refs.add(key)
    # The original assessment selects eligible event material IDs. Do not
    # promote other collected records to writing evidence solely on relevance.
    return {key: materials[key] for key in sorted(refs & eligible)}


def validate_reviewed_plan_sources(packet, contract, receipt, approved):
    """Validate the native reviewed route's empirical source index."""
    for field in ("core_question", "specific_question", "method"):
        if packet.get(field) != contract[field]:
            raise ValueError("Writing input differs from the frozen question or method")
    if packet.get("question_binding") != contract:
        raise ValueError("Writing input question binding differs")
    current_ids = {row["material_id"] for row in receipt["materials"]}
    sources = packet["sources"]
    for key, source in sources.items():
        if source.get("kind") != "empirical":
            if key in current_ids:
                raise ValueError("Receipt material cannot be relabelled as nonempirical")
            continue
        if key not in approved:
            raise ValueError("Empirical source is outside reviewed matrix and eligible material IDs")
        original = approved[key]
        if source.get("locator") != original["locator"]:
            raise ValueError("Empirical source locator differs from original receipt")
        if "url" in source and source["url"] != original["url"]:
            raise ValueError("Empirical source URL differs from original receipt")
    for chapter in packet["chapters"]:
        for section in chapter["sections"]:
            if not set(section["source_ids"]) <= set(sources):
                raise ValueError("Writing section refers to unknown source")
