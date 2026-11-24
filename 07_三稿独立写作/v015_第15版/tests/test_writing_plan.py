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
                      "framework_sha256": receipt["framework_sha256"], "rows": [{"dimension_id": "d0", "evidence": [material]}]}
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


    def test_native_resume_renders_paragraph_plan_after_adequacy(self):
        # Actual native resume + V15 renderer; only model calls and the already
        # verified S08 binding are synthetic. Never dispatch an actual review.
        import resume_writing
        from question_binding import evidence_digest, file_hash
        with tempfile.TemporaryDirectory(dir=run_mode.ROOT) as temporary:
            with patch.object(run_mode, "RUNS", Path(temporary)):
                work = run_mode.start("fixture_g03", "Synthetic test only")
                folder = work / "qualitative_framework" / "attempt_001"
                folder.mkdir(parents=True)
                (work / "initial").mkdir()
                data = packet(1)
                for ch in data["chapters"]:
                    for sec in ch["sections"]:
                        sec["paragraphs"] = ["Describe evidence", "Specify inference limit"]
                core = data["core_question"]
                framework = {"core_question": core, "core_concept": "Fixture concept",
                             "dimensions": [{"id": "d0", "name": "维度 0", "deduction": "Deduction for this fixture"}]}
                material = {"material_id": "E", "kind": "official_rule",
                            "url": "https://example.org", "locator": "test index E"}
                receipt = {"framework_sha256": evidence_digest(framework), "materials": [material]}
                matrix = {"framework_sha256": receipt["framework_sha256"],
                          "collection_sha256": evidence_digest(receipt),
                          "rows": [{"dimension_id": "d0", "evidence": [material]}]}
                run_mode.write(folder / "framework.json", framework)
                run_mode.write(folder / "material_receipt.json", receipt)
                run_mode.write(folder / "analysis_matrix.json", matrix)
                run_mode.write(work / "s08_topic.json", {"question": "S08 fixture",
                    "research_method": {"path": "secondary_interviews"}})
                run_mode.write(work / "merged_literature.json", {"rows": []})
                run_mode.write(work / "initial/theories.json", [])
                contract = {"core_question": core, "specific_question": "S08 fixture",
                            "method": "secondary_interviews",
                            "receipt_sha256": file_hash(folder / "material_receipt.json")}
                prior = work / "matrix_independent_review.json"
                review = {"decision": "pass", "reason": "Synthetic only",
                          "reviewer": resume_writing.REVIEWER, "invocation_id": "fixture-not-real",
                          "matrix_sha256": file_hash(folder / "analysis_matrix.json"),
                          "material_adequacy": {"support": "sufficient", "reason": "Synthetic only",
                                                "eligible_event_ids": ["E"]}}
                run_mode.write(prior, dict(review, material_adequacy=dict(review["material_adequacy"], support="unknown")))
                # The original freeze verifier is a separate contract (real S08
                # verification is exercised by v012 test_frozen_route).
                state = {"status": "frozen", "run_id": work.name, "fixture": True}
                run_mode.write(work / "staged_topic.json", state)
                with patch.object(resume_writing, "verified_frozen_topic",
                                  return_value=run_mode.load(work / "s08_topic.json")) as verify, \
                     patch.object(resume_writing, "binding", return_value=contract), \
                     patch.object(writing_plan, "binding", return_value=contract), \
                     patch.object(resume_writing, "dispatch") as dispatch:
                    self.assertEqual(resume_writing.resume(work, folder, prior)["status"],
                                     "awaiting_material_adequacy")
                    dispatch.assert_not_called()
                    run_mode.write(prior, review)
                    dispatch.side_effect = [{"answer": data}, {"answer": {"decision": "pass", "reason": "Fixture only"}}]
                    result = resume_writing.resume(work, folder, prior)
                    self.assertEqual(result["status"], "reviewed_plan")
                    self.assertEqual([call.args[1] for call in dispatch.call_args_list],
                                     ["plan_0", "plan_review_0"])
                    self.assertTrue(dispatch.call_args_list[1].kwargs["reviewer"])
                    self.assertEqual(verify.call_count, 2)
                    verify.assert_called_with(work, state)
                output = work / "autonomous_writing/draft_0"
                plan = (output / "论文写作方案.md").read_text(encoding="utf-8")
                saved = run_mode.load(output / "plan_input.json")
                request = run_mode.load(output / "writing_plan_review_request.json")
                self.assertIn("第 1 段 Describe evidence", plan)
                self.assertIn("第 2 段 Specify inference limit", plan)
                self.assertIn("test index E", plan)
                self.assertEqual(saved["specific_question"], contract["specific_question"])
                self.assertEqual(saved["framework"]["dimensions"][0]["id"], "d0")
                self.assertEqual(request["material_admission"]["eligible_material_ids"], ["E"])
                self.assertEqual(request["material_admission"]["chapter_empirical_source_ids"], {
                    "problem": ["E"], "framework": ["E"], "case": ["E"],
                    "d0": ["E"], "conclusion": ["E"],
                })
                self.assertEqual(request["input_sha256"], run_mode.digest(saved))
                self.assertFalse(request["formal_eligible"])


    def test_reviewed_dimension_sources_reject_cross_dimension_substitution(self):
        data = packet(2)
        data["sources"]["E2"] = {"kind": "empirical", "label": "Second fixture", "locator": "test index E2"}
        data["chapters"][4]["sections"][0]["source_ids"] = ["T", "E2"]
        matrix = {"rows": [
            {"dimension_id": "d0", "evidence": [{"material_id": "E"}]},
            {"dimension_id": "d1", "evidence": [{"material_id": "E2"}]},
        ]}
        approved = {"E": {}, "E2": {}}
        scoped = writing_plan.reviewed_dimension_sources(data, matrix, approved)
        self.assertEqual(scoped["d0"], ["E"])
        self.assertEqual(scoped["d1"], ["E2"])
        data["chapters"][4]["sections"][0]["source_ids"] = ["T", "E"]
        with self.assertRaisesRegex(ValueError, "outside its reviewed matrix dimension"):
            writing_plan.reviewed_dimension_sources(data, matrix, approved)

    def test_reviewed_dimension_sources_reject_changed_order_and_empty_scope(self):
        reordered = packet(2)
        reversed_matrix = {"rows": [
            {"dimension_id": "d1", "evidence": [{"material_id": "E2"}]},
            {"dimension_id": "d0", "evidence": [{"material_id": "E"}]},
        ]}
        with self.assertRaisesRegex(ValueError, "dimensions differ"):
            writing_plan.reviewed_dimension_sources(reordered, reversed_matrix, {"E": {}, "E2": {}})
        data = packet(1)
        matrix = {"rows": [{"dimension_id": "d0", "evidence": [{"material_id": "E"}]}]}
        with self.assertRaisesRegex(ValueError, "dimensions differ"):
            writing_plan.reviewed_dimension_sources(data, {"rows": []}, {"E": {}})
        with self.assertRaisesRegex(ValueError, "outside its reviewed matrix dimension"):
            writing_plan.reviewed_dimension_sources(data, matrix, {})
        data["chapters"][3]["sections"][0]["source_ids"] = ["T"]
        with self.assertRaisesRegex(ValueError, "no admitted matrix evidence"):
            writing_plan.reviewed_dimension_sources(data, matrix, {"E": {}})
