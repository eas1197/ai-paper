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
                    self.assertEqual(review["material_admission"]["mode"], "exploratory_unverified")

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


    def test_reviewed_admission_requires_original_bound_adequate_matrix(self):
        from question_binding import evidence_digest, file_hash
        with tempfile.TemporaryDirectory(dir=run_mode.ROOT) as temporary:
            work = Path(temporary)
            folder = work / "qualitative_framework" / "attempt_001"
            folder.mkdir(parents=True)
            material = {"material_id": "E", "url": "https://example.org",
                        "locator": "test index E", "kind": "official_rule"}
            receipt = {"framework_sha256": "fixture-framework", "materials": [material]}
            run_mode.write(folder / "material_receipt.json", receipt)
            contract = {"core_question": "Fixture question?", "specific_question": "S08",
                        "method": "secondary_interviews",
                        "receipt_sha256": file_hash(folder / "material_receipt.json")}
            matrix = {"question_binding": contract, "collection_sha256": evidence_digest(receipt),
                      "framework_sha256": receipt["framework_sha256"], "rows": [{"evidence": [material]}]}
            run_mode.write(folder / "analysis_matrix_reviewed.json", matrix)
            data = dict(packet(1), question_binding=contract, specific_question="S08",
                        analysis_matrix="qualitative_framework/attempt_001/analysis_matrix_reviewed.json")
            adequate = {"decision": "pass", "material_adequacy": {
                "support": "sufficient", "reason": "Synthetic only", "eligible_event_ids": ["E"]}}
            with patch.object(writing_plan, "binding", return_value=contract):
                admission = writing_plan.reviewed_material_admission(work, data, adequate)
                self.assertEqual(admission["mode"], "native_reviewed")
                self.assertEqual(admission["eligible_material_ids"], ["E"])
                self.assertEqual(admission["review_sha256"], evidence_digest(adequate))
                for review in ({}, {"decision": "pass"}, dict(adequate, decision="revise")):
                    with self.subTest(review=review), self.assertRaises(ValueError):
                        writing_plan.reviewed_material_admission(work, data, review)
                with self.assertRaisesRegex(ValueError, "original reviewed matrix"):
                    writing_plan.reviewed_material_admission(work, dict(data,
                        analysis_matrix="qualitative_framework/attempt_001/analysis_matrix.json"), adequate)
                run_mode.write(folder / "analysis_matrix_reviewed.json", dict(matrix, collection_sha256="changed"))
                with self.assertRaisesRegex(ValueError, "binding differs"):
                    writing_plan.reviewed_material_admission(work, data, adequate)
