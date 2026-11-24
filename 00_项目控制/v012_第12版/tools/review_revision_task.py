"""D21d: freeze a re-review candidate only with receiver-selected historical lineage."""
import json
import re
from pathlib import Path

from review_type import audit_revision_lineage


def _path(work, raw):
    if not isinstance(raw, str) or not raw or "\\" in raw or ":" in raw:
        raise ValueError("Use a run-relative lineage file")
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts or rel.as_posix() != raw:
        raise ValueError("Lineage file escapes run")
    path = (work / rel).resolve(strict=True)
    if not path.is_relative_to(work) or not path.is_file():
        raise ValueError("Lineage file escapes run")
    return path


def _ref(work, raw, h):
    path = _path(work, raw)
    return {"path": raw, "sha256": h.sha(path)}


def _bound(work, ref, h):
    path = _path(work, ref["path"])
    if h.sha(path) != ref["sha256"]:
        raise ValueError("Revision file changed")
    return path, path.read_bytes()


def select_lineage(contract, work, prior_report, revision_record):
    """Select a historical C04 version; it need not still be active after revision."""
    if prior_report is None and revision_record is None:
        return None
    if not prior_report or not revision_record or prior_report == revision_record:
        raise ValueError("Select distinct prior report and actual revision record")
    h = contract.heritage
    report_ref, revision_ref = (_ref(work, p, h) for p in (prior_report, revision_record))
    prior = json.loads(_bound(work, report_ref, h)[1])
    old = prior.get("task_snapshot", {})
    if (set(old) != {"research_id", "stage_id", "task_id", "snapshot_sha256"}
            or old["research_id"] != work.name
            or any(not isinstance(old[k], str) or not old[k] for k in old)
            or not re.fullmatch(r"[0-9a-f]{64}", old["snapshot_sha256"])):
        raise ValueError("Prior report is outside the selected original research")
    slot = contract._slot(work, old["stage_id"], old["task_id"])
    version = old["snapshot_sha256"]
    version_path = (slot / "versions" / (version + ".json")).relative_to(work).as_posix()
    activated_path = (slot / "activated" / (version + ".json")).relative_to(work).as_posix()
    version_ref, activated_ref = (_ref(work, p, h) for p in (version_path, activated_path))
    snapshot = json.loads(_bound(work, version_ref, h)[1])
    activated = json.loads(_bound(work, activated_ref, h)[1])
    if contract._digest(snapshot) != version or contract._ref(snapshot, version) != old or activated != old:
        raise ValueError("Historical task snapshot integrity mismatch")
    contexts = [row for row in snapshot["packet"]["input_files"]
                if re.fullmatch(r"review_tasks/[0-9a-f]{64}\.json", row["path"])]
    if len(contexts) != 1:
        raise ValueError("Historical task lacks an unambiguous frozen review context")
    old_context = json.loads(_bound(work, contexts[0], h)[1])
    if (old_context["review_kind"] != prior.get("review_kind")
            or old_context["research_question"] != snapshot["packet"]["research_question"]):
        raise ValueError("Prior report differs from historical review context")
    return {"prior": prior, "old": old, "old_context": old_context, "old_packet": snapshot["packet"],
            "lineage": {"report": report_ref, "revision": revision_ref},
            "history_refs": [version_ref, activated_ref, contexts[0]]}


def attach_lineage(contract, work, context, current_refs, selected, *, stage_id):
    """Bind actual before/after bytes, without granting prior or new review authenticity."""
    if selected is None:
        return current_refs
    h = contract.heritage
    if (context["review_kind"] != selected["prior"]["review_kind"]
            or selected["old"]["stage_id"] != stage_id
            or context["research_question"] != selected["old_context"]["research_question"]):
        raise ValueError("Re-review must keep the same selected question and original gate")
    lineage = selected["lineage"]
    revision = json.loads(_bound(work, lineage["revision"], h)[1])
    old_inputs = {row["path"]: row["sha256"] for row in selected["old_packet"]["input_files"]}
    old_artifacts = {row["path"]: row["sha256"] for row in selected["old_context"]["input_materials"]}
    refs = {row["path"]: row for row in current_refs}
    extra = [lineage["report"], lineage["revision"], *selected["history_refs"]]
    for change in revision.get("changes", []):
        if not isinstance(change, dict) or set(change) != {"before", "after"}:
            raise ValueError("Revision must specify before and after")
        before, after = change["before"], change["after"]
        # Before bytes may live in an immutable archive after the original path
        # was changed. They must still match that old reviewed object, not an
        # unrelated file with an arbitrary self-reported hash.
        old_path = before["path"] if before["path"] in old_artifacts else after["path"]
        if old_artifacts.get(old_path) != before["sha256"] or old_inputs.get(old_path) != before["sha256"]:
            raise ValueError("Before artifact was not part of the historical review")
        extra.append(before)
    for row in extra:
        _bound(work, row, h)
        if row["path"] in refs and refs[row["path"]] != row:
            raise ValueError("Revision references conflicting file versions")
        refs[row["path"]] = row
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/review_result.schema.json").read_text(encoding="utf-8"))
    audit = audit_revision_lineage(work, context, lineage=lineage, inputs={k:v["sha256"] for k,v in refs.items()},
        schema=schema, read_bound=lambda root, ref: _bound(root, ref, h),
        research_id=work.name, stage_id=stage_id, review_kind=context["review_kind"])
    substantive = [p for p in audit["changed_artifacts"]
                   if p not in {"run_manifest.json", "staged_topic.json"}
                   and not p.endswith(("review_request.json", "review.json", "writer_manifest.json"))]
    if not substantive:
        raise ValueError("Re-review requires changed substantive evidence or argument, not only status metadata")
    context.update(review_type="independent_re_review", prior_review=lineage)
    context["input_binding"]["historical_task_snapshot"] = selected["old"]
    context["input_binding"]["revision_audit"] = audit
    context["evidence_scope"]["limitations"].append("Historical report lineage is bound; prior and new independent identities still require separate authentication.")
    return list(refs.values())


def revision_task_id(contract, base, selected):
    if selected is None:
        return base
    return base + "_rereview_" + contract._digest(selected["lineage"])[:24]
