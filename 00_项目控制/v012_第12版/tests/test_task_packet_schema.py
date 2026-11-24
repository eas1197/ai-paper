"""C01 common task packet structure; no executor dispatch or research side effects."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from jsonschema import Draft202012Validator

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/task_packet.schema.json"


def packet():
    return {
        "research_id": "offline_fixture", "stage_id": "initial", "task_id": "fixture_001",
        "purpose": "Define a search task contract", "research_question": "How does coordination occur?",
        "search_levels": ["object", "issue", "theory"],
        "input_files": [{"path": "fixture/input.json", "sha256": "a" * 64}],
        "source_scope": {"journals": ["Fixture Journal"], "policy_refs": []},
        "quantity_budget": {"target": 0, "max_batches": 0},
        "time_budget_seconds": 0,
        "output_schema": {"kind": "file", "file": {"path": "fixture/output.schema.json", "sha256": "b" * 64}},
        "stop_conditions": ["budget exhausted"],
    }


class CommonTaskSchemaTest(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(self.schema)
        self.validator = Draft202012Validator(self.schema)

    def test_c01_fields_and_zero_budget(self):
        self.validator.validate(packet())
        for key in packet():
            with self.subTest(missing=key):
                sample = packet()
                del sample[key]
                self.assertFalse(self.validator.is_valid(sample))

    def test_file_hash_budget_and_output_schema_shapes(self):
        for change in (
            {"input_files": [{"path": "fixture", "sha256": "invalid"}]},
            {"quantity_budget": {"target": -1}},
            {"time_budget_seconds": -1},
            {"output_schema": {"kind": "file"}},
            {"stop_conditions": []},
        ):
            with self.subTest(change=change):
                self.assertFalse(self.validator.is_valid(dict(packet(), **change)))

    def test_inline_nonsearch_contract(self):
        sample = dict(packet(), search_levels=[], source_scope={}, quantity_budget={},
                      output_schema={"kind": "inline", "schema": {"type": "object"}})
        self.validator.validate(sample)
        # Transport structure does not establish execution identity or formal approval.
        self.assertNotIn("executor", sample)
        self.assertNotIn("formal_eligible", sample)


if __name__ == "__main__":
    unittest.main()
