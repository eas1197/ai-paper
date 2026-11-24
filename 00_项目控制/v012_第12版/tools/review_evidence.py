"""D11 evidence-location audit only. Caller selects the D09 context; no gate approval."""
import hashlib
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/review_result.schema.json"


def _index(rows, key):
    result = {}
    for row in rows:
        value = row[key]
        if not isinstance(value, str) or not value.strip() or value in result:
            raise ValueError(f"Invalid or duplicate {key}")
        result[value] = row
    return result


def _located(data, locator):
    if locator["kind"] == "lines":
        lines = data.decode("utf-8-sig").splitlines()
        start, end = locator["start"], locator["end"]
        if not 1 <= start <= end <= len(lines):
            raise ValueError("Invalid evidence line range")
        return "\n".join(lines[start-1:end]), []
    tokens = [token.replace("~1", "/").replace("~0", "~")
              for token in locator["pointer"].split("/")[1:]]
    node = json.loads(data.decode("utf-8-sig"))
    for token in tokens:
        if isinstance(node, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token) or int(token) >= len(node):
                raise ValueError("Invalid evidence array index")
            node = node[int(token)]
        elif isinstance(node, dict) and token in node:
            node = node[token]
        else:
            raise ValueError("Evidence JSON pointer does not exist")
    return node, tokens


def _has_id(node, identifier):
    if isinstance(node, dict):
        return identifier in node or any(_has_id(v, identifier) for v in node.values())
    if isinstance(node, list):
        return any(_has_id(v, identifier) for v in node)
    if isinstance(node, str):
        return bool(re.search(r"(?<![\w.-])" + re.escape(identifier) + r"(?![\w.-])", node))
    return False


def audit_review_evidence(run, context, report):
    """Check D11 fields, selected context IDs and actual bytes/locators; not identity or semantics."""
    Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8"))).validate(report)
    if report["review_kind"] != context["review_kind"]:
        raise ValueError("Review kind differs from selected context")
    run = Path(run).resolve(strict=True)
    artifacts = _index(context["input_materials"], "artifact_id")
    dimensions = _index(context["review_dimensions"], "dimension_id")
    claims = _index(context["key_claims"], "claim_id")
    allowed = set(context["evidence_scope"]["allowed_ids"])
    pending = set(context["evidence_scope"]["excluded_or_pending_ids"])
    if allowed & pending:
        raise ValueError("Evidence scope is ambiguous")
    for issue in _index(report["issues"], "issue_id").values():
        if issue["dimension_id"] not in dimensions or not set(issue["evidence_ids"]) <= allowed | pending:
            raise ValueError("Issue names unknown dimension or evidence")
    seen, reviewed_dimensions, reviewed_claims = set(), set(), set()
    cache = {}
    for finding in report["evidence_findings"]:
        dim, claim = finding["dimension_id"], finding["claim_id"]
        key = (dim, claim)
        if dim not in dimensions or (claim is not None and claim not in claims) or key in seen:
            raise ValueError("Unknown or duplicate finding target")
        seen.add(key)
        reviewed_dimensions.add(dim)
        if claim is not None:
            reviewed_claims.add(claim)
        for evidence in finding["evidence"]:
            eid, aid = evidence["evidence_id"], evidence["artifact_id"]
            if eid not in allowed or aid not in artifacts:
                raise ValueError("Evidence is outside the selected allowed scope")
            artifact = artifacts[aid]
            if (evidence["path"], evidence["sha256"]) != (artifact["path"], artifact["sha256"]):
                raise ValueError("Evidence file reference differs from selected artifact")
            if aid not in cache:
                rel = Path(artifact["path"])
                path = (run / rel).resolve(strict=True)
                if rel.is_absolute() or ".." in rel.parts or not path.is_relative_to(run) or not path.is_file():
                    raise ValueError("Evidence path escapes selected run")
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != artifact["sha256"]:
                    raise ValueError("Evidence bytes changed")
                cache[aid] = data
            node, tokens = _located(cache[aid], evidence["locator"])
            if eid != aid and eid not in tokens and not _has_id(node, eid):
                raise ValueError("Located record does not identify the claimed evidence ID")
    if report["decision"] == "pass" and (reviewed_dimensions != set(dimensions) or reviewed_claims != set(claims)):
        raise ValueError("Pass requires findings for every selected dimension and key claim")
    return {"status": "evidence_locations_checked", "finding_count": len(seen),
            "formal_eligible": False, "independent_review_verified": False}
