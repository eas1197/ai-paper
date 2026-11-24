"""Common task packet validation (C03: original development run ownership).

Transport validation is not research authorization. C04 and C05 will add
input freezing and executor integration respectively.
"""
import json
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
