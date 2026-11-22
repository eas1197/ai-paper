"""Preflight independent revision requests before dispatching a stage."""

from question_binding import evidence_digest, file_hash

ORIGINS = {"analysis", "source", "event", "framework", "binding"}


def validate_routes(changes, rows):
    if not changes or not isinstance(rows, list):
        raise ValueError("A revise decision needs actionable changes and routes")
    indices = [row["index"] for row in rows]
    if any(type(index) is not int for index in indices) or sorted(indices) != list(range(len(changes))):
        raise ValueError("Route every review instruction exactly once")
    for row in rows:
        if row["origin"] not in ORIGINS or not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ValueError("Each revision needs a supported origin and rationale")
    return [{**row, "instruction": changes[row["index"]]} for row in sorted(rows, key=lambda x: x["index"])]


def preflight(routes, directory, framework, receipt, max_batches):
    used = sum(path.is_dir() for path in directory.parent.glob("repair_*"))
    remaining = max(0, max_batches - used)
    verification = {
        "framework_file_sha256": file_hash(directory / "framework.json"),
        "framework_canonical_json_sha256": evidence_digest(framework),
        "receipt_framework_sha256": receipt["framework_sha256"],
        "receipt_file_sha256": file_hash(directory / "material_receipt.json"),
    }
    decisions = []
    for route in routes:
        origin = route["origin"]
        decision = dict(route, handler=origin)
        if origin == "analysis":
            decision["status"] = "ready"
        elif origin == "binding":
            decision["status"] = ("verified" if verification["framework_canonical_json_sha256"]
                                  == verification["receipt_framework_sha256"] else "technical_block")
            decision["verification"] = verification
        else:
            decision["status"] = "resource_limit" if not remaining else "ready"
            decision["remaining_collection_batches"] = remaining
        decisions.append(decision)
    return decisions
