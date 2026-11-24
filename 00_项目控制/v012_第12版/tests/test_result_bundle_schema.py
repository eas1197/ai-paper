"""C11 shared result identity and separate provenance; structure only."""
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/result_bundle.schema.json"


def provenance(kind):
    if kind == "chat_native_web":
        return {"kind": kind, "record_refs": [], "citation_refs": [], "missing_fields": ["raw_tool_log"]}
    if kind == "codex_cli":
        return {"kind": kind, "command": None, "thread_id": None, "exit_code": None,
                "events": None, "response": None, "stderr": None, "prompt": None,
                "schema": None, "login": None, "missing_fields": ["not_executed"]}
    return {"kind": kind, "submitter": None, "submitted_at": None, "source_type": "uploaded_file",
            "verification_status": "unverified", "original_files": [], "missing_fields": ["submitter"]}


def result(kind="chat_native_web"):
    return {"schema_version": 1,
            "task_snapshot": {"research_id": "fixture", "stage_id": "initial",
                              "task_id": "fixture_001", "snapshot_sha256": "a" * 64},
            "executor": kind, "provenance": provenance(kind)}


class ResultEnvelopeTest(unittest.TestCase):
    def setUp(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def test_common_identity_and_executor_variants(self):
        for kind in ("chat_native_web", "codex_cli", "manual"):
            sample = result(kind)
            self.validator.validate(sample)
            for key in ("research_id", "stage_id", "task_id", "snapshot_sha256"):
                broken = result(kind)
                del broken["task_snapshot"][key]
                self.assertFalse(self.validator.is_valid(broken))

    def test_cross_executor_provenance_rejected(self):
        for source in ("chat_native_web", "codex_cli", "manual"):
            for target in ("chat_native_web", "codex_cli", "manual"):
                if source != target:
                    self.assertFalse(self.validator.is_valid(
                        dict(result(source), provenance=provenance(target))))
        chat = result()
        chat["provenance"]["thread_id"] = "fabricated"
        self.assertFalse(self.validator.is_valid(chat))
        cli = result("codex_cli")
        cli["provenance"]["citation_refs"] = ["chat-only"]
        self.assertFalse(self.validator.is_valid(cli))

    def test_no_self_asserted_formal_pass(self):
        self.assertFalse(self.validator.is_valid(dict(result(), formal_eligible=True)))
        self.assertFalse(self.validator.is_valid(dict(result(), executor="human")))


if __name__ == "__main__":
    unittest.main()
