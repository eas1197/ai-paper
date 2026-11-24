"""D21b: original prepare subprocess + real C04 freeze; synthetic inputs, no model calls."""
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ai_paper5_strict as strict
import task_packet
from review_task import prepare_review_task


class OriginalReviewTaskIntegration(unittest.TestCase):
    def setUp(self):
        self.run_id = "d21_fixture_" + uuid.uuid4().hex
        self.work = strict.RUNS / self.run_id
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        strict.original_call(strict.original_command("init", self.run_id, theme="Synthetic offline test"))
        self.state = strict.state_of(self.run_id)
        # Explicit synthetic pre-gate artifacts, never accepted research or source evidence.
        self.state.update(reality_first=False, explanation_first=False, issue_search=False,
                          qual_search_receipts=False, question="Synthetic question")
        strict.write(self.work / "initial/literature_matrix.json", {"rows": []})
        strict.write(self.work / "initial/theories.json", [{"fixture": True}])
        strict.write(self.work / "merged_literature.json", {"rows": [], "fixture": True})

    def set_stage(self, stage, phase=None):
        self.state["status"] = stage
        self.state.pop("review_phase", None)
        if phase:
            self.state["review_phase"] = phase
        strict.write(self.work / "staged_topic.json", self.state)

    def get_task(self, stage, phase=None):
        self.set_stage(stage, phase)
        before = (self.work / "staged_topic.json").read_bytes()
        result = prepare_review_task(self.run_id)
        self.assertEqual(before, (self.work / "staged_topic.json").read_bytes())
        snap = task_packet.verify_snapshot(result["task_snapshot"], current_run_id=self.run_id)
        self.assertEqual(snap["packet"], result["task_packet"])
        context = strict.read(self.work / result["context_path"])
        return result, context

    def test_original_three_stages_and_material_wait(self):
        for stage, phase, kind, matrix in (
            ("preliminary_review", None, "preliminary_academic", "initial/literature_matrix.json"),
            ("design_review", None, "research_design", "initial/literature_matrix.json"),
            ("final_review", None, "final_research", "merged_literature.json"),
            ("materials_pending", "initial", "research_design", "initial/literature_matrix.json"),
            ("materials_pending", "final", "final_research", "merged_literature.json"),
        ):
            with self.subTest(stage=stage, phase=phase):
                result, context = self.get_task(stage, phase)
                self.assertEqual(context["review_kind"], kind)
                self.assertEqual(result["task_packet"]["stage_id"], stage)
                self.assertIn(matrix, context["evidence_scope"]["allowed_ids"])
                self.assertFalse(result["dispatch_authorized"])
                self.assertFalse(result["formal_eligible"])
                self.assertEqual(result["task_packet"]["time_budget_seconds"], 0)
                self.assertEqual(prepare_review_task(self.run_id), result)

    def test_stale_state_invalidates_snapshot(self):
        result, _ = self.get_task("design_review")
        self.set_stage("final_review")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            task_packet.verify_snapshot(result["task_snapshot"], current_run_id=self.run_id)

    def test_original_prepare_checks_presearch_hash(self):
        self.state["reality_first"] = True
        self.state["reality_sha256"] = "not-the-actual-digest"
        strict.write(self.work / "reality.json", {"fixture": True})
        self.set_stage("preliminary_review")
        with self.assertRaisesRegex(RuntimeError, "Reality evidence changed"):
            prepare_review_task(self.run_id)

    def test_non_due_and_revision_without_lineage_are_blocked(self):
        for stage in ("initial", "frozen", "s08_ready", "S02", "S03", "S05", "S06", "materials_pending"):
            self.set_stage(stage)
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                prepare_review_task(self.run_id)

    def test_input_change_invalidates_snapshot(self):
        result, _ = self.get_task("preliminary_review")
        strict.write(self.work / "initial/theories.json", [{"fixture": "changed"}])
        with self.assertRaisesRegex(ValueError, "hash changed"):
            task_packet.verify_snapshot(result["task_snapshot"], current_run_id=self.run_id)
        next_task = prepare_review_task(self.run_id)
        self.assertNotEqual(result["task_snapshot"], next_task["task_snapshot"])


if __name__ == "__main__":
    unittest.main()
