"""Common task packet validation (C03: original development run ownership).

Transport validation is not research authorization. C04 adds frozen task
versions and lineage checks; C05 will connect executors.
"""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
import sys

from jsonschema import Draft202012Validator

import ai_paper5_strict as heritage

sys.path.insert(0, str(heritage.ROOT / "00_项目控制/v007_第7版/tools"))
import run_mode

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/task_packet.schema.json"


def validate_packet(packet, *, current_run_id):
    """Validate against an independently selected, existing original dev run."""
    if not isinstance(current_run_id, str):
        raise ValueError("Current research ID must be an explicit string")
    heritage.run_id_guard(current_run_id)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(packet)
    if packet["research_id"] != current_run_id:
        raise ValueError("Task packet belongs to a different research ID")
    work = heritage.RUNS / current_run_id
    # Reuse the original manifest and state checks; do not trust packet identity.
    manifest = run_mode.verified_run(work)
    state = heritage.state_of(current_run_id)
    if manifest.get("run_id") != current_run_id or state.get("run_id") != current_run_id:
        raise ValueError("Original research identity mismatch")
    return work.resolve()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _checked_file(root, item):
    """Paths are relative to the declared namespace, including on Windows."""
    raw = item["path"]
    path = Path(raw)
    if path.is_absolute() or "\\" in raw or ":" in raw or ".." in path.parts:
        raise ValueError("Input path escapes its namespace")
    root = root.resolve()
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("Missing or out-of-namespace frozen input: " + raw)
    if heritage.sha(resolved) != item["sha256"]:
        raise ValueError("Frozen input hash changed: " + raw)


def _context(packet, work):
    for item in packet["input_files"]:
        _checked_file(work, item)
    for item in packet["source_scope"].get("policy_refs", []):
        _checked_file(heritage.ROOT, item)
    if packet["output_schema"]["kind"] == "file":
        _checked_file(heritage.ROOT, packet["output_schema"]["file"])
    state = heritage.state_of(packet["research_id"])
    manifest = run_mode.verified_run(work)
    return {
        "original_question": state.get("question"),
        "original_theme": state.get("theme", manifest.get("theme")),
        "original_policy_hashes": {
            name: heritage.sha(path) for name, path in {
                "v3_policy": heritage.V3_POLICY,
                "v3_search_prompt": heritage.V3_SEARCH_PROMPT,
                "native_prompt": heritage.NATIVE_PROMPT,
                "native_schema": heritage.NATIVE_SCHEMA,
            }.items()
        },
    }


def _slot(work, stage_id, task_id):
    return work / "task_contracts" / _digest([stage_id, task_id])


def _ref(snapshot, version):
    packet = snapshot["packet"]
    return {key: packet[key] for key in ("research_id", "stage_id", "task_id")} | {
        "snapshot_sha256": version}


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".task-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify_snapshot(reference, *, current_run_id, _seen=None):
    """Reject superseded or changed versions, recursively including dependencies."""
    if (not isinstance(reference, dict)
            or set(reference) != {"research_id", "stage_id", "task_id", "snapshot_sha256"}
            or reference["research_id"] != current_run_id
            or any(not isinstance(reference[k], str) or not reference[k]
                   for k in ("research_id", "stage_id", "task_id", "snapshot_sha256"))
            or not re.fullmatch(r"[0-9a-f]{64}", reference["snapshot_sha256"])):
        raise ValueError("Invalid snapshot reference")
    heritage.run_id_guard(current_run_id)
    slot = _slot(heritage.RUNS / current_run_id, reference["stage_id"], reference["task_id"])
    seen = set() if _seen is None else _seen
    if slot in seen:
        raise ValueError("Cyclic task dependency")
    version = reference["snapshot_sha256"]
    active = heritage.read(slot / "active.json")
    if active != reference:
        raise ValueError("Superseded task snapshot")
    snapshot = heritage.read(slot / "versions" / (version + ".json"))
    if _digest(snapshot) != version or _ref(snapshot, version) != reference:
        raise ValueError("Frozen snapshot integrity mismatch")
    work = validate_packet(snapshot["packet"], current_run_id=current_run_id)
    if _context(snapshot["packet"], work) != snapshot["context"]:
        raise ValueError("Original question or search policy changed")
    for dependency in snapshot["dependencies"]:
        verify_snapshot(dependency, current_run_id=current_run_id, _seen=seen | {slot})
    return snapshot


def freeze_packet(packet, *, current_run_id, dependencies=()):
    """Freeze a new content-addressed version and activate it for this task.

    Old versions are retained. Dependent snapshots become invalid on verification,
    never silently promoted. The caller must explicitly declare its upstream tasks.
    """
    work = validate_packet(packet, current_run_id=current_run_id)
    slot = _slot(work, packet["stage_id"], packet["task_id"])
    references = list(dependencies)
    for dependency in references:
        verify_snapshot(dependency, current_run_id=current_run_id, _seen={slot})
    # Canonical dependency order makes identical inputs idempotent.
    references = sorted(references, key=lambda value: _digest(value))
    if len({_digest(value) for value in references}) != len(references):
        raise ValueError("Duplicate task dependency")
    snapshot = {"packet": packet, "context": _context(packet, work),
                "dependencies": references}
    version = _digest(snapshot)
    reference = _ref(snapshot, version)
    path = slot / "versions" / (version + ".json")
    if path.exists():
        if heritage.read(path) != snapshot:
            raise ValueError("Existing snapshot integrity mismatch")
    else:
        _atomic_json(path, snapshot)
    # Do not reactivate a historical version: that would revive stale results.
    active = slot / "active.json"
    if active.exists() and heritage.read(active) != reference and path.exists():
        # An earlier activation is marked by an immutable receipt.
        if (slot / "activated" / (version + ".json")).exists():
            raise ValueError("Historical snapshot cannot be reactivated")
    _atomic_json(slot / "activated" / (version + ".json"), reference)
    _atomic_json(active, reference)
    return reference


def validate_result_snapshot(result, *, current_run_id, expected_reference):
    """A result must refer to the independently selected current task version."""
    if not isinstance(result, dict) or result.get("task_snapshot") != expected_reference:
        raise ValueError("Result does not belong to the selected task snapshot")
    return verify_snapshot(expected_reference, current_run_id=current_run_id)
