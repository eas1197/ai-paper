from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import writing_plan
import run_mode


def chapter(identifier):
    return {
        "id": identifier, "title": identifier, "task": "State one inference",
        "bridge": "Connect its scope to the next comparison",
        "sections": [{"title": "Evidence and inference", "task": "Compare two claims",
                      "argument": "Specify where the claims diverge",
                      "evidence_use": "Contrast the recorded material with the proposition",
                      "source_ids": ["T", "E"]}],
    }


def packet(dimension_count):
    dimensions = [{"id": f"d{i}", "title": f"维度 {i}", "deduction": "Deduction for this fixture"}
                  for i in range(dimension_count)]
    return {
        "method": "secondary_interviews", "core_question": "Fixture question?",
        "answer_strategy": "Integrate comparative evidence",
        "sources": {"T": {"kind": "theory", "label": "Theory fixture", "locator": "test index T"},
                    "E": {"kind": "empirical", "label": "Evidence fixture", "locator": "test index E"}},
        "framework": {**dict.fromkeys(writing_plan.FRAMEWORK_FIELDS, "Framework detail"),
                      "dimensions": dimensions},
        "case": dict.fromkeys(writing_plan.CASE_FIELDS, "Case detail"),
        "chapters": [chapter(key) for key in ("problem", "framework", "case",
                                             *(item["id"] for item in dimensions), "conclusion")],
    }


class WritingPlanTest(unittest.TestCase):
    def test_dimension_count_follows_framework_and_sections_have_tasks(self):
        for count in (2, 4):
            report = writing_plan.render(packet(count))
            self.assertEqual(report.count("### 维度 "), count)
            self.assertIn("材料与用途", report)
        invalid = packet(2)
        invalid["chapters"][3]["sections"][0]["source_ids"] = ["T"]
        with self.assertRaisesRegex(ValueError, "empirical material"):
            writing_plan.render(invalid)
        with self.assertRaisesRegex(ValueError, "match the framework"):
            writing_plan.render(dict(invalid, chapters=invalid["chapters"][:-1]))

    def test_default_plan_and_explicit_full_policy(self):
        with tempfile.TemporaryDirectory(dir=run_mode.ROOT) as folder:
            with patch.object(run_mode, "RUNS", Path(folder)):
                for full, method, expected in ((False, "secondary_interviews", "plan"),
                                                (True, "quantitative", "full")):
                    work = run_mode.start(f"fixture_{expected}", "Test", full_paper=full)
                    manifest = run_mode.verified_run(work)
                    plan = writing_plan.produce(work, dict(packet(1), method=method), manifest)
                    review = run_mode.load(work / "writing/writing_plan_review_request.json")
                    self.assertTrue(plan.exists())
                    self.assertEqual(review["requested_deliverable"], expected)
                    self.assertEqual(review["review_status"], "pending")
                    self.assertFalse(review["formal_eligible"])

    def test_plan_input_persisted_and_hash_locked(self):
        with tempfile.TemporaryDirectory(dir=run_mode.ROOT) as folder:
            with patch.object(run_mode, "RUNS", Path(folder)):
                work = run_mode.start("fixture_stable_plan", "Test")
                manifest = run_mode.verified_run(work)
                data = packet(2)
                plan = writing_plan.produce(work, data, manifest)
                saved = plan.parent / "plan_input.json"
                request = run_mode.load(plan.parent / "writing_plan_review_request.json")
                self.assertEqual(run_mode.load(saved), data)
                self.assertEqual(request["input_sha256"], run_mode.digest(run_mode.load(saved)))
                self.assertFalse(request["formal_eligible"])
                old = saved.read_bytes()
                with self.assertRaises(FileExistsError):
                    writing_plan.produce(work, dict(data, answer_strategy="Changed"), manifest)
                self.assertEqual(saved.read_bytes(), old)
