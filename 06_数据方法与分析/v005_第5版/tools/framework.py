"""Track a theoretical framework and the evidence used to test it."""

from collect_common import digest

FRAMEWORK_CONTEXT = ("core_question", "core_concept", "meaning", "choice", "nearest_study",
                     "existing_explanation", "limitation", "proposed_increment", "integration")
DIMENSION_FIELDS = ("id", "name", "deduction", "proposition", "needed_material", "relationship")
CLAIM_FIELDS = ("conclusion", "boundary", "unresolved", "alternatives")
RELATIONS = {"support", "counterexample", "competing", "context"}


def require_text(row, keys):
    if any(not isinstance(row.get(key), str) or not row[key].strip() for key in keys):
        raise ValueError("Document the required research reasoning")


def validate_framework(framework):
    require_text(framework, FRAMEWORK_CONTEXT)
    dimensions = framework.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("Supply the dimensions derived from the core concept")
    ids = {}
    for dimension in dimensions:
        require_text(dimension, DIMENSION_FIELDS)
        identifier = dimension["id"]
        if identifier in ids:
            raise ValueError("Duplicate framework dimension")
        ids[identifier] = dimension
    return ids


def analysis_matrix(framework, receipt, findings):
    dimensions = validate_framework(framework)
    if (receipt.get("phase") != "framework_collection"
            or receipt.get("framework_sha256") != digest(framework)
            or receipt.get("status") != "pending_independent_review"):
        raise ValueError("Use the collection bound to this version of the framework")
    material_rows = receipt["materials"]
    material_ids = [row["material_id"] for row in material_rows]
    if (any(not isinstance(key,str) or not key.strip() for key in material_ids)
            or len(material_ids)!=len(set(material_ids))):
        raise ValueError("Duplicate or invalid original material ID")
    materials = {row["material_id"]: row for row in material_rows}
    rows = {}
    for finding in findings:
        key = finding["dimension_id"]
        if key not in dimensions or key in rows:
            raise ValueError("Each matrix row must refer to one distinct dimension")
        require_text(finding, CLAIM_FIELDS)
        bound = []
        seen = set()
        references = finding.get("evidence")
        if not isinstance(references, list):
            raise ValueError("Record the evidence list, including an empty list where unresolved")
        for item in references:
            identifier = item["material_id"]
            if identifier not in materials or identifier in seen or item["relation"] not in RELATIONS:
                raise ValueError("Use a traceable evidence ID and describe its relation to the claim")
            require_text(item, ("reason",))
            seen.add(identifier)
            material = materials[identifier]
            source_fields = {name:material[name] for name in ("url","locator","kind")}
            # event_id is the native tool-action ID, not a social event identity.
            # Its scope is the original material receipt, including parent lineage.
            if "event_id" in material:
                source_fields["event_id"] = material["event_id"]
            for name in ("url","locator","kind","event_id"):
                if name in item and (name not in source_fields or item[name]!=source_fields[name]):
                    raise ValueError("Matrix source identity differs from original material: "+name)
            bound.append({**item, **source_fields})
        if not bound and finding.get("status") != "unresolved":
            raise ValueError("A dimension without usable evidence remains unresolved")
        if finding.get("status") not in {"tentative", "unresolved"}:
            raise ValueError("Separate exploratory interpretation from unresolved claims")
        rows[key] = {**dimensions[key], **{field: finding[field] for field in CLAIM_FIELDS},
                     "dimension_id": key, "status": finding["status"], "evidence": bound}
    if set(rows) != set(dimensions):
        raise ValueError("Include every dimension, including those still unresolved")
    return {"status": "pending_independent_review", "framework_sha256": digest(framework),
            "collection_sha256": digest(receipt), "theoretical_increment_status": "proposed",
            "rows": [rows[key] for key in dimensions]}
