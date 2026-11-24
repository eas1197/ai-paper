from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from staged_topic import (ROOT, archive, digest, freeze, issue_plan, literature_next, load_reality,
                          record_issue_plan, record_reality, review, route, search, write)


class StagedTopicTest(unittest.TestCase):
    def test_untrusted_legacy_review_never_advances(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            state = {"status": "preliminary_review", "history": []}
            report = {"model": "gpt-6.2-sol", "invocation_id": "self-asserted",
                      "outcome": "pass", "formal_eligible": True}
            with self.assertRaisesRegex(ValueError, "unable_to_review"):
                review(Path(folder), state, report)
            self.assertEqual(state, {"status": "preliminary_review", "history": []})

    def test_literature_continues_only_for_deficit_with_budget(self):
        checkpoint = {"config": {"max_batches": 2, "search_action_budget": 24},
                      "batches": [{"batch": "batch_001", "search_events": 6}]}
        decision = literature_next(checkpoint, 4, 5)
        self.assertEqual((decision["action"], decision["deficit"]), ("resume_deficit", 1))
        checkpoint["batches"][0]["search_events"] = 24
        self.assertEqual(literature_next(checkpoint, 4, 5)["action"], "stop")
        self.assertEqual(literature_next(checkpoint, 5, 5)["action"], "verify")
        checkpoint["config"]["max_batches"] = 1
        checkpoint["batches"][0]["search_events"] = 6
        self.assertEqual(literature_next(checkpoint, 4, 5)["remaining_batches"], 0)
        self.assertEqual(literature_next(checkpoint, 4, 5)["action"], "stop")

    def test_staged_experiment_counts_old_batch_under_new_limit(self):
        checkpoint = {"config": {"max_batches": 3, "search_action_budget": 24,
                                 "topic_batch_budget": True},
                      "batches": [{"batch": "batch_001", "search_events": 24}]}
        self.assertEqual(literature_next(checkpoint, 4, 5)["remaining_batches"], 2)
        self.assertEqual(literature_next(checkpoint, 4, 5)["action"], "resume_deficit")
        checkpoint["batches"].append({"batch": "batch_002", "search_events": 8})
        self.assertEqual(literature_next(checkpoint, 5, 5)["action"], "verify")
        checkpoint["batches"].append({"batch": "batch_003", "search_events": 5})
        self.assertEqual(literature_next(checkpoint, 4, 5)["action"], "stop")

    def test_issue_plan_requires_topical_justification_and_keeps_search_locked(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            state = {"status": "issue_positioning"}
            with self.assertRaisesRegex(ValueError, "Search not authorized"):
                search(work, state, "initial", False)
            plan = dict.fromkeys(("issue", "why", "object_search", "issue_search",
                                  "theory_search"), "fixture rationale")
            with self.assertRaisesRegex(ValueError, "Added journals"):
                record_issue_plan(work, state, dict(plan, specialist_journals=[{"name": "Journal"}]))
            record_issue_plan(work, state, plan)
            self.assertEqual(state["status"], "initial")
            self.assertEqual(issue_plan(work, state), plan)
            write(work / "issue_plan.json", dict(plan, why="changed"))
            with self.assertRaisesRegex(ValueError, "issue plan changed"):
                issue_plan(work, state)

    def test_reality_stage_precedes_search_and_binds_source_limits(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            state = {"status": "reality"}
            with self.assertRaisesRegex(ValueError, "Search not authorized"):
                search(work, state, "initial", False)
            packet = {"phenomenon": "Case", "search_focus": "Accountability",
                      "sources": [{"url": "https://example.org", "kind": "interview",
                                   "supports": "a reported case", "limits": "no prevalence inference"}]}
            record_reality(work, state, packet)
            self.assertEqual(state["status"], "initial")
            self.assertEqual(load_reality(work, state), packet)
            write(work / "reality.json", dict(packet, phenomenon="Replaced"))
            with self.assertRaisesRegex(ValueError, "Reality evidence changed"):
                load_reality(work, state)

    def test_retry_budget_excludes_technical_failure(self):
        history = [{"outcome": "concept"}, {"outcome": "technical"}]
        self.assertEqual(route(history, "depth"), "S06")
        self.assertEqual(route([*history, {"outcome": "depth"}], "increment"), "eliminated")
        self.assertEqual(route(history, "technical"), "retry_technical")

    @patch("staged_topic.require_original_review")
    def test_reality_first_review_keeps_question_and_expectations_bound(self, _isolated_gate):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            state = {"status": "reality", "reality_first": True, "history": []}
            reality = {"phenomenon": "Case", "search_focus": "Focus",
                       "sources": [{"url": "https://example.org", "kind": "interview",
                                    "supports": "Case", "limits": "Only one case"}]}
            record_reality(work, state, reality)
            state["status"] = "preliminary_review"
            (work / "initial").mkdir()
            papers, theories = {"rows": []}, []
            write(work / "initial/literature_matrix.json", papers)
            write(work / "initial/theories.json", theories)
            report = {"outcome": "pass", "model": "gpt-6.2-sol", "invocation_id": "review",
                      "reason": "fixture", "question": "Why?", "academic_value": "pass",
                      "data_feasibility": "pass",
                      "evidence_sha256": digest({"papers": papers, "theories": theories, "reality": reality})}
            with self.assertRaisesRegex(ValueError, "reviewed question"):
                review(work, state, report)
            report["research_case"] = {"core_question": "Why?", "context": "a school",
                                       "hypotheses_or_propositions": ["A competing proposition"]}
            review(work, state, report)
            self.assertEqual(state["status"], "supplemental")

    def test_archive_is_idempotent(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / "library.md"
            case = dict.fromkeys(("core", "question", "value", "literature", "missing",
                                  "access", "run", "review"), "test archive")
            self.assertEqual(archive(case, path), archive(case, path))
            self.assertEqual(path.read_text(encoding="utf-8").count("<!-- topic:"), 1)

    def test_s08_ready_label_alone_cannot_freeze(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            (work / "initial").mkdir()
            papers, theories = {"rows": []}, [{"claim": "Fixture"}]
            write(work / "merged_literature.json", papers)
            write(work / "initial/theories.json", theories)
            final = {"outcome": "pass", "academic_value": "pass", "data_feasibility": "pass",
                     "model": "gpt-6.2-sol", "invocation_id": "fixture", "reason": "fixture",
                     "question": "fixture", "design": "fixture",
                     "evidence_sha256": digest({"papers": papers, "theories": theories})}
            state = {"status": "s08_ready", "review_phase": "final", "mode": "dev",
                     "history": [final], "question": "fixture"}
            for invalid in ({"outcome": "reject"}, {"academic_value": "blocked"},
                            {"data_feasibility": "unknown"}, {"invocation_id": ""},
                            {"model": "fixture"}, {"reason": ""}):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(ValueError, "final positive"):
                        freeze(work, dict(state, history=[dict(final, **invalid)]))
                    self.assertFalse((work / "s08_topic.json").exists())
            for invalid in ({"history": []}, {"review_phase": "initial"}):
                with self.assertRaisesRegex(ValueError, "final positive"):
                    freeze(work, dict(state, **invalid))
                self.assertFalse((work / "s08_topic.json").exists())

    @patch("staged_topic.require_original_review")
    def test_search_waits_for_both_reviews_and_s08_requires_final_evidence(self, _isolated_gate):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            state = {"status": "initial", "history": [], "mode": "dev"}
            with self.assertRaisesRegex(ValueError, "Search not authorized"):
                search(work, state, "supplemental", False)
            with self.assertRaisesRegex(ValueError, "final positive"):
                freeze(work, state)
            (work / "initial").mkdir()
            papers, theories = {"rows": []}, [{"claim": "Fixture"}]
            write(work / "initial/literature_matrix.json", papers)
            write(work / "initial/theories.json", theories)
            state["status"] = "preliminary_review"
            report = {"outcome": "pass", "model": "gpt-6.2-sol", "invocation_id": "preliminary",
                      "reason": "fixture", "question": "fixture", "academic_value": "pass",
                      "data_feasibility": "blocked",
                      "evidence_sha256": digest({"papers": papers, "theories": theories})}
            with self.assertRaisesRegex(ValueError, "Data feasibility"):
                review(work, state, report)
            review(work, state, dict(report, outcome="academic_pass"))
            self.assertEqual(state["status"], "design_review")
            with self.assertRaisesRegex(ValueError, "Search not authorized"):
                search(work, state, "supplemental", False)
            review(work, state, dict(report, invocation_id="design", data_feasibility="pass"))
            self.assertEqual(state["status"], "supplemental")
            state["status"] = "final_review"
            write(work / "merged_literature.json", papers)
            review(work, state, dict(report, invocation_id="final", data_feasibility="pass", design="fixture"))
            freeze(work, state)
            self.assertEqual(state["status"], "frozen")
