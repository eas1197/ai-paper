"""D13 academic-review lineage check; never grants independence or gate approval."""
import json
from jsonschema import Draft202012Validator


def audit_review_type(run, context, report, inputs, schema, read_bound):
    """The independently frozen context selects the review type and prior artifacts."""
    if (context.get("review_type") != report["review_type"]
            or "prior_review" not in context
            or context["prior_review"] != report["prior_review"]):
        raise ValueError("Review type or lineage differs from frozen context")
    if report["review_type"] == "academic_review":
        return {"review_type": "academic_review", "prior_review": None}

    def load_frozen(ref):
        Draft202012Validator(schema["$defs"]["file_ref"]).validate(ref)
        if inputs.get(ref["path"]) != ref["sha256"]:
            raise ValueError("Revision lineage is not in the current frozen task")
        return read_bound(run, ref)[1]

    lineage = report["prior_review"]
    if lineage["report"]["path"] == lineage["revision"]["path"]:
        raise ValueError("Prior report and revision record must be distinct")
    prior = json.loads(load_frozen(lineage["report"]))
    revision = json.loads(load_frozen(lineage["revision"]))
    # v3 was the previous candidate report contract. Its historical validation
    # is a receiver responsibility, not proof of independence in this function.
    previous_schema = json.loads(json.dumps(schema))
    if prior.get("schema_version") == 3:
        previous_schema["properties"]["schema_version"]["const"] = 3
        for field in ("review_type", "prior_review"):
            previous_schema["properties"].pop(field)
            previous_schema["required"].remove(field)
        previous_schema["allOf"].pop()
    Draft202012Validator(previous_schema).validate(prior)
    old, new = prior["task_snapshot"], report["task_snapshot"]
    if (old["research_id"] != new["research_id"] or old["stage_id"] != new["stage_id"]
            or old["snapshot_sha256"] == new["snapshot_sha256"]
            or prior["review_kind"] != report["review_kind"]
            or prior["decision"] not in {"revise", "need_evidence"}):
        raise ValueError("Prior report is not an applicable earlier revision decision")
    if report["execution_id"] is not None and prior["execution_id"] == report["execution_id"]:
        raise ValueError("Re-review cannot reuse the prior execution ID")
    if (not isinstance(revision, dict) or set(revision) != {"prior_report", "issues", "changes"}
            or revision["prior_report"] != lineage["report"]):
        raise ValueError("Revision record does not bind the prior report")
    required = {row["issue_id"] for row in prior["issues"] if row["blocking"]}
    issues = revision["issues"]
    if (not isinstance(issues, list) or not all(isinstance(row, dict)
            and set(row) == {"issue_id", "response"} and isinstance(row["issue_id"], str)
            and isinstance(row["response"], str) and row["response"].strip() for row in issues)
            or len({row["issue_id"] for row in issues}) != len(issues)
            or {row["issue_id"] for row in issues} != required):
        raise ValueError("Revision must address each prior blocking issue, without claiming resolution")
    changes = revision["changes"]
    if not isinstance(changes, list) or not changes:
        raise ValueError("Re-review requires an actual changed artifact")
    current = {row["path"]: row["sha256"] for row in context["input_materials"]}
    changed_paths = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"before", "after"}:
            raise ValueError("Revision must specify before and after references")
        before, after = change["before"], change["after"]
        load_frozen(before)
        load_frozen(after)
        if (before["sha256"] == after["sha256"] or after["path"] in changed_paths
                or current.get(after["path"]) != after["sha256"]):
            raise ValueError("Revision is unchanged, duplicated, or not a current review artifact")
        changed_paths.add(after["path"])
    return {"review_type": "independent_re_review", "prior_review": lineage,
            "addressed_issue_ids": sorted(required), "changed_artifacts": sorted(changed_paths)}
