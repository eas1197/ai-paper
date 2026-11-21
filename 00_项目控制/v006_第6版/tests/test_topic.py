import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

DEV = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEV / "tools"))
import topic_run
from topic_review import content_hash, validate_review
from topic_tasks import prepare


class TopicContractTest(unittest.TestCase):
    def setUp(self):
        self.bundle = topic_run.read(DEV / "outputs/D01_问题演化.json")
        self.review = topic_run.read(DEV / "outputs/D02_Sol原始返回.json")
        self.review.update(model="gpt-6.2-sol", invocation_id="fixture-1", input_sha256=content_hash(self.bundle))
        temporary = tempfile.TemporaryDirectory(dir=topic_run.ROOT / ".codex-task-temp")
        self.addCleanup(temporary.cleanup)
        store = patch.object(topic_run, "STORE", Path(temporary.name))
        store.start()
        self.addCleanup(store.stop)

    def test_real_review_and_bad_inputs(self):
        validate_review(self.review, self.bundle, "deepening")
        for updates in ({"model": None}, {"evidence": []}, {"input_sha256": "stale"},
                        {"next_action": None}, {"action_worth_cost": False}, {"verdict": "PASS"}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                validate_review(self.review | updates, self.bundle, "deepening")

    def test_marginal_gain_flow(self):
        for verdict, useful, remaining, expected in (
            ("DEEPEN", True, 2, ("deepening", "targeted_revision")),
            ("BRANCH", True, 2, ("deepening", "branch")),
            ("READY", False, 0, ("formal", "quality_met")),
            ("STOP", False, 2, ("stopped", "no_worthwhile_followup")),
            ("DEEPEN", True, 0, ("stopped", "budget_exhausted")),
        ):
            with self.subTest(verdict=verdict, remaining=remaining):
                self.assertEqual(expected, topic_run.allowed_action("deepening",
                    self.review | {"verdict": verdict, "action_worth_cost": useful},
                    {"model_calls": remaining, "search_calls": remaining}))

    def test_resume_checks_pending_and_duplicate_invocations(self):
        limit = {"model_calls": 3, "search_calls": 2}
        once = {"model_calls": 1, "search_calls": 1}
        run_id = "resume"
        topic_run.initialize(run_id, limit, "教育")
        current = self.review | {"stage": "opportunity", "verdict": "PASS", "selected_ids": ["O1"]}
        topic_run.record(run_id, self.bundle, current, once)
        path = topic_run.run_path(run_id)
        (path / ".pending-aborted").write_text('{"incomplete":', encoding="utf-8")
        self.assertEqual(topic_run.status(run_id)["stage"], "question")
        current = current | {"stage": "question", "selected_ids": ["Q0"]}
        with self.assertRaisesRegex(ValueError, "already recorded"):
            topic_run.record(run_id, self.bundle, current, once)
        topic_run.record(run_id, self.bundle, current | {"invocation_id": "fixture-2"}, once)
        self.assertFalse(topic_run.allowance(run_id, once)["permitted"])
        cleared = topic_run.record(run_id, self.bundle, self.review | {"invocation_id": "fixture-3"},
                                   {"model_calls": 1, "search_calls": 0})
        self.assertEqual(cleared["stage"], "stopped")
        self.assertEqual(topic_run.read(cleared["last_round"])["reason"], "budget_exhausted")

    def test_prepare_scope_and_existing_question_cards(self):
        run_id = "scope"
        calls = dict(model_calls=2, search_calls=2)
        stage = topic_run.initialize(run_id, calls, "教育分层")
        task = prepare(topic_run.ROOT, topic_run.read, stage)
        self.assertEqual("教育分层", task["theme"])
        self.assertTrue(Path(task["sources"]["stage04"]).is_file())
        decision = self.review | {"stage": "opportunity", "verdict": "PASS", "selected_ids": ["O1"]}
        stage = topic_run.record(run_id, self.bundle, decision, dict(model_calls=1, search_calls=0))
        task = prepare(topic_run.ROOT, topic_run.read, stage)
        self.assertEqual(["O1"], task["approved_ids"])
        self.assertTrue(task["question_cards"])

    def test_ineligible_candidates_and_unreviewed_formal_entry(self):
        run_id = "unapproved"
        stage = topic_run.initialize(run_id, dict(model_calls=3, search_calls=2))
        with self.assertRaisesRegex(ValueError, "reviewed READY"):
            topic_run.formal_init(topic_run.ROOT, topic_run.run_path(run_id), stage, topic_run.read, topic_run.write_new)
        decision = self.review | {"stage": "opportunity", "verdict": "PASS", "selected_ids": ["O-missing"]}
        with self.assertRaisesRegex(ValueError, "eligible IDs"):
            topic_run.record(run_id, self.bundle, decision, dict(model_calls=1, search_calls=0))

    def test_snapshot_identity_and_g5_rejection(self):
        final = self.review | {"stage": "final", "verdict": "PASS", "selected_ids": ["Q1"]}
        with self.assertRaisesRegex(ValueError, "has not reached"):
            topic_run.final_gate(topic_run.ROOT, {"stage": "stopped"}, self.bundle, final,
                                 DEV, topic_run.read)

    def test_question_can_return_to_new_leads_and_duplicate_is_rejected(self):
        remaining = dict(model_calls=1, search_calls=1)
        review = self.review | {"verdict": "REVISE", "return_to": "opportunity"}
        self.assertEqual(("opportunity", "return_for_new_lead"), topic_run.allowed_action("question", review, remaining))
        duplicate = copy.deepcopy(self.bundle)
        duplicate["opportunities"].append(duplicate["opportunities"][0] | {"opportunity_id": "O2"})
        with self.assertRaisesRegex(ValueError, "Duplicate opportunity"):
            topic_run.validate_bundle(duplicate, topic_run.ROOT)


if __name__ == "__main__":
    unittest.main()
