"""Offline fixtures for both method routes through V14."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import test_stage07 as writing
from test_stage07 import MODULE, load, sha, stage07, write

import s08_inputs07 as intake
from framework import FRAMEWORK_CONTEXT


def freeze(run, method, preliminary=None):
    write(run / "merged_literature.json", {"rows": []})
    write(run / "initial/theories.json", [])
    evidence = intake.staged_topic.evidence_hash(run, {}, run / "merged_literature.json", run / "initial/theories.json")
    paths = {key: {"status": "not_applicable", "reason": "fixture"} for key in
             ("quantitative", "secondary_interviews", "online_qualitative")}
    paths[method].update(status="ready", access="verified", materials=["fixture"])
    if preliminary:
        paths[method].update(approach="public_text", materials=[preliminary["materials"][0]["material_id"]],
                             search_attempt="attempt_001", receipt_sha256=sha(run / "qualitative/attempt_001/material_receipt.json"))
    final = {"question": "fixture question", "design": "fixture design", "research_case": {"core_question": "fixture question"},
             "outcome": "pass", "academic_value": "pass", "data_feasibility": "pass",
             "model": "gpt-6.2-sol", "invocation_id": "fixture-final", "evidence_sha256": evidence,
             "method_assessment": {"selected": method, "paths": paths}}
    selected = intake.select_method(final["method_assessment"], "pass")
    write(run / "staged_topic.json", {"status": "frozen", "mode": "dev", "run_id": run.name, "history": [final],
                                      "question": final["question"], "research_method": selected})
    result = {key: final[key] for key in ("question", "design", "research_case", "evidence_sha256")}
    path = run / "s08_topic.json"
    write(path, dict(result, stage="S08", scope="experimental", mode="dev", formal_eligible=False,
                     research_method=selected, review_sha256=intake.staged_topic.digest(final)))
    return path


def materials(run, folder, conversion, **bindings):
    url = "https://example.org/policy"
    write(folder / "conversion.json", conversion)
    write(folder / "response.json", {"materials": [{
        "url": url, "date": "2020-01-01", "subject": "fixture", "context": "fixture",
        "kind": "official_rule", "path": "online_qualitative", "locator": "section 2",
        "relation": "fixture", "limits": "fixture", "access": "fixture",
    }], "search_notes": [], "gaps": []})
    (folder / "events.jsonl").write_text(json.dumps({"type": "item.completed", "item": {
        "type": "web_search", "id": "fixture-search", "results": [{"url": url}]}}) + "\n", encoding="utf-8")
    receipt = intake.qual_materials.read_materials(folder, 24)
    receipt.update(run_id=run.name, formal_eligible=False, conversion_sha256=intake.staged_topic.digest(conversion), **bindings)
    write(folder / "material_receipt.json", receipt)
    return receipt


class S08IntakeTest(unittest.TestCase):
    def test_qualitative_waits_for_analysis_then_prepares_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory(dir=MODULE / "tests") as temporary:
            run = Path(temporary)
            conversion = {"core_question": "fixture original", "new_question": "fixture question"}
            write(run / "run_manifest.json", {"workload": {"11": {"native_search_actions": 24}}})
            preliminary = materials(run, run / "qualitative/attempt_001", conversion)
            s08 = freeze(run, "online_qualitative", preliminary)
            inputs = {"s08_run": str(run)}
            pending = stage07.plan(inputs)
            self.assertEqual(pending["status"], "needs_review")
            self.assertIn("analysis_matrix.json", pending["missing"])
            folder = run / "qualitative_framework/attempt_001"
            framework = dict.fromkeys(FRAMEWORK_CONTEXT, "fixture")
            framework["core_question"] = conversion["core_question"]
            framework["dimensions"] = [{"id": "D1", "name": "fixture", "deduction": "fixture",
                                        "proposition": "fixture", "needed_material": "fixture", "relationship": "fixture"}]
            receipt = materials(run, folder, conversion, phase="framework_collection",
                                framework_sha256=intake.staged_topic.digest(framework),
                                preliminary_sha256=intake.staged_topic.digest(preliminary))
            write(folder / "framework.json", framework)
            finding = {"dimension_id": "D1", "status": "tentative", "conclusion": "fixture finding",
                       "boundary": "fixture scope", "unresolved": "fixture unknown", "alternatives": "fixture rival",
                       "evidence": [{"material_id": receipt["materials"][0]["material_id"],
                                     "relation": "support", "reason": "fixture"}]}
            matrix_path = folder / "analysis_matrix.json"
            write(matrix_path, intake.analysis_matrix(framework, receipt, [finding]))
            write(folder / "matrix_review.json", {"decision": "pass", "reviewer": "gpt-6.2-sol",
                  "invocation_id": "fixture-matrix-review", "matrix_sha256": sha(matrix_path), "reason": "fixture"})
            planned = stage07.plan(inputs)
            self.assertEqual(planned["status"], "ready")
            with patch.object(stage07, "ROOT", run):
                task = load(stage07.prepare(planned)["writing_task"])
            self.assertFalse(task["formal_eligible"])
            self.assertEqual(task["findings"][0]["evidence"][0]["locator"], "section 2")
            self.assertEqual(task["language_style"]["profile_id"], "corpus20_language_style")
            self.assertIn("经验发现", {row["section"] for row in task["sections"]})
            matrix = load(matrix_path)
            matrix["rows"][0]["evidence"][0]["locator"] = "altered"
            write(matrix_path, matrix)
            with self.assertRaisesRegex(ValueError, "矩阵"):
                stage07.plan(inputs)
            changed = load(s08)
            changed["formal_eligible"] = True
            write(s08, changed)
            with self.assertRaisesRegex(ValueError, "S08"):
                stage07.plan(inputs)

    def test_quantitative_s08_retains_v14_gate_and_output(self):
        with tempfile.TemporaryDirectory(dir=MODULE / "tests") as temporary:
            root = Path(temporary)
            s08 = freeze(root / "s08", "quantitative")
            run = root / "main-run"
            spec = {"question": "fixture question", "s08_sha256": sha(s08)}
            inputs = {"run_id": run.name, "s08_run": str(s08.parent)}
            fixture = writing.WritingTest()
            fixture.fixture(run, dict(spec, s08_sha256="wrong"))
            with patch.object(stage07, "run_directory", return_value=run):
                self.assertEqual(stage07.plan(inputs)["status"], "needs_review")
            run = root / "bound-main-run"
            inputs["run_id"] = run.name
            fixture.fixture(run, spec)
            with patch.object(stage07, "run_directory", return_value=run):
                planned = stage07.plan(inputs)
                self.assertEqual(planned["status"], "ready", planned["errors"])
                run_task = stage07.prepare(planned)
                task = load(run_task["writing_task"])
                self.assertIn("R4", task["paragraph_outline"]["units"])
                self.assertEqual(task["research_question"], "fixture question")
                self.assertFalse(load(run_task["frozen_manifest"])["s08"]["formal_eligible"])
                with self.assertRaisesRegex(ValueError, "正式稿件"):
                    stage07.execute(planned)
                manifest_path = run / "run_manifest.json"
                manifest = load(manifest_path)
                next(row for row in manifest["stages"] if row["stage_id"] == "06")["status"] = "stale"
                write(manifest_path, manifest)
                self.assertEqual(stage07.plan(inputs)["status"], "needs_review")
