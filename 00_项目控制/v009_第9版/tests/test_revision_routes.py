import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from staged_topic import ROOT
from question_binding import evidence_digest
from revision_routes import preflight, validate_routes


class RevisionRoutesTest(unittest.TestCase):
    def test_routes_require_exact_coverage(self):
        row = {"index": 0, "origin": "source", "reason": "Original locator is missing"}
        with self.assertRaises(ValueError):
            validate_routes(["first", "second"], [row, row])

    def test_source_budget_and_binding_are_separate_from_analysis(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            directory = Path(temporary) / "repair_001"
            directory.mkdir()
            framework = {"core_question": "Q"}
            receipt = {"framework_sha256": evidence_digest(framework)}
            (directory / "framework.json").write_text(json.dumps(framework), encoding="utf-8")
            (directory / "material_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            (directory / "events.jsonl").touch()
            routes = [{"origin": kind} for kind in ("source", "binding", "analysis", "framework")]
            checks = preflight(routes, directory, framework, receipt, 1)
            self.assertEqual([row["status"] for row in checks],
                             ["resource_limit", "verified", "ready", "resource_limit"])
