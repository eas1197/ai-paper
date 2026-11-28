import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import research_experiment
from staged_topic import (ROOT, digest, evidence_hash, init, load, prepare,
                          record_research, write)


def _sample_research_packet(work: Path):
    events_path = work / "critique_events.jsonl"
    response_path = work / "critique_response.json"
    events_path.write_text(
        "\n".join([
            json.dumps({"type": "thread.started", "thread_id": "crit-thread-001"}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}}),
        ]),
        encoding="utf-8",
    )
    response_path.write_text(json.dumps({"objections": ["counterexample"]}), encoding="utf-8")
    return {
        "reality": {
            "phenomenon": "Commute shortening and time allocation",
            "search_focus": "Urban commuting and workplace boundary",
            "sources": [{
                "url": "https://example.org/post1",
                "kind": "public_post",
                "supports": "case 1 action sequence",
                "limits": "single retrospective account",
            }],
        },
        "event_packet": {
            "sources": {
                "S1": "https://example.org/post1",
                "S2": "https://example.org/post2",
            },
            "events": [
                {
                    "identity": "E1",
                    "facts": [{
                        "source_id": "S1",
                        "statement": "Moved closer and went home at noon",
                        "use": "midday boundary",
                        "key": True,
                        "status": "single_account",
                    }],
                },
                {
                    "identity": "E2",
                    "facts": [{
                        "source_id": "S2",
                        "statement": "Stayed late at office when living nearby",
                        "use": "evening boundary",
                        "key": True,
                        "status": "single_account",
                    }],
                },
            ],
            "sensitivity": "anonymized ids",
        },
        "exchange": {
            "expectation": "Shorter commute increases discretionary time",
            "observation": "Two workers report opposite outcomes",
            "initial_explanation": "Workplace boundary rules mediate time gains",
            "challenge": "Ordinary time-budget model predicts both",
            "candidate_question": "When do workplace rules absorb commute savings?",
            "research_actor": "research-thread-001",
            "critical_actor": "crit-thread-001",
            "search_focus": "commute time allocation workplace boundary control",
            "critical_receipt": {
                "events": "critique_events.jsonl",
                "response": "critique_response.json",
                "events_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
                "response_sha256": hashlib.sha256(response_path.read_bytes()).hexdigest(),
            },
        },
        "issue_plan": {
            "issue": "Work-life temporal boundaries",
            "why": "Links spatial friction to organizational time claims",
            "object_search": "urban commuting labor supply China",
            "issue_search": "workplace temporal flexibility boundary control",
            "theory_search": "boundary theory time geography",
        },
        "topic_reasoning": {
            "opportunity": {"reasoning": "Competing mechanisms on identical commute savings"},
            "question": {"reasoning": "Distinguishes discretion from time-budget relaxation"},
            "deepening": {"reasoning": "Tests boundary claim versus ordinary scheduling", "change_kind": "academic"},
        },
    }


def _fake_manifest(model_calls=6, search_actions=24):
    workload = {
        "00": {"attempts": 2, "model_calls": model_calls, "timeout_seconds": 120},
        "11": {"native_search_actions": search_actions},
    }
    return {"workload": workload, "workload_sha256": digest(workload)}


class ResearchRouteBTest(unittest.TestCase):
    def test_route_b_requires_dev_mode_and_prepares_exploration(self):
        with self.assertRaisesRegex(ValueError, "experimental research route"):
            init("route_b_formal_reject", "formal_candidate", "theme", research_route="B")

        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            state = {"run_id": "b_test", "theme": "Commute", "research_route": "B",
                     "status": "research_exploration"}
            with patch("staged_topic.run_mode.verified_run", return_value=_fake_manifest()):
                task = prepare(work, state)
            self.assertEqual(task["research_route"], "B")
            self.assertEqual(task["status"], "research_exploration")
            self.assertIn("workload", task)

    def test_record_research_handoff_and_tamper_detection(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            state = {
                "run_id": "b_handoff", "theme": "Commute", "mode": "dev",
                "research_route": "B", "status": "research_exploration",
                "reality_first": True, "explanation_first": True, "issue_search": True,
                "topic_reasoning_required": True, "history": [],
            }
            packet = _sample_research_packet(work)
            record_research(work, state, packet)
            self.assertEqual(state["status"], "initial")
            self.assertTrue((work / "research_packet.json").exists())
            self.assertTrue((work / "reality.json").exists())
            self.assertTrue((work / "event_comparison.json").exists())
            self.assertTrue((work / "explanation_exchange.json").exists())
            self.assertTrue((work / "issue_plan.json").exists())

            (work / "initial").mkdir()
            write(work / "initial/literature_matrix.json", {"rows": []})
            write(work / "initial/theories.json", [])
            h1 = evidence_hash(work, state, work / "initial/literature_matrix.json", work / "initial/theories.json")
            self.assertTrue(h1)

            tampered = dict(packet, issue_plan=dict(packet["issue_plan"], issue="Tampered"))
            write(work / "research_packet.json", tampered)
            with self.assertRaisesRegex(ValueError, "Autonomous research packet changed"):
                evidence_hash(work, state, work / "initial/literature_matrix.json", work / "initial/theories.json")

    def test_record_research_rejects_bad_critical_receipt(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            state = {"run_id": "b_bad", "research_route": "B", "status": "research_exploration"}
            packet = _sample_research_packet(work)
            packet["exchange"]["critical_receipt"]["events_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "receipt changed"):
                record_research(work, state, packet)

    def test_experiment_retry_supports_multiple_attempts_and_remaining_search_budget(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            work = Path(folder)
            area = work / "ab_exploration"
            area.mkdir()
            context = {"phenomenon": "test"}
            manifest = _fake_manifest(model_calls=6, search_actions=24)

            # Seed completed 01_proposal (12 search events) and 02_critique
            p1 = area / "01_proposal"
            p1.mkdir()
            ans1 = {"proposal": {"title": "p1"}, "evidence_urls": [], "academic_increment": {},
                    "feasibility": {}, "limitations": []}
            p2 = area / "02_critique"
            p2.mkdir()
            ans2 = {"objections": ["o1"], "action_required": ["a1"], "limits": ["l1"]}

            # Seed two failed 03_revision attempts (03_revision used 2 search events, 03_revision_retry used 1)
            r1 = area / "03_revision"
            r1.mkdir()
            (r1 / "events.jsonl").write_text("", encoding="utf-8")
            r2 = area / "03_revision_retry"
            r2.mkdir()
            (r2 / "events.jsonl").write_text("", encoding="utf-8")

            # Compute exact requests that run_arm expects for 01 and 02
            req1 = {
                "instruction": research_experiment.COMMON + research_experiment.TASKS["B"][0]
                + "最多 12 个原生联网事件，新增证据请逐条给出真实打开页面的 URL。",
                "context": context,
                "prior": [],
            }
            req2 = {
                "instruction": (
                    "独立反诘：以同一学术标准找最强反例，审候选与近邻能否区分及材料可行性。"
                    "只分析请求内的材料。禁止调用任何工具、读文件、执行命令或联网。"
                    "不得为自己审稿。只返回 JSON，包含 objections, action_required, limits。"
                ),
                "context": context,
                "prior": [ans1],
            }
            write(p1 / "request.json", req1)
            write(p1 / "response.json", ans1)
            (p1 / "events.jsonl").write_text("", encoding="utf-8")
            write(p1 / "accepted.json", {"thread": "t1", "usage": {}, "seconds": 1.0,
                                         "answer": ans1, "answer_sha256": digest(ans1), "search_events": 12})
            write(p2 / "request.json", req2)
            write(p2 / "response.json", ans2)
            write(p2 / "accepted.json", {"thread": "t2", "usage": {}, "seconds": 1.0,
                                         "answer": ans2, "answer_sha256": digest(ans2), "search_events": 0})

            seen_folders = []
            seen_instructions = []

            def fake_native_call(folder_arg, request_arg, *, allow_search, timeout):
                seen_folders.append(folder_arg.name)
                seen_instructions.append(request_arg["instruction"])
                ans3 = {"proposal": {"title": "p3"}, "evidence_urls": [], "academic_increment": {},
                        "feasibility": {}, "limitations": []}
                write(folder_arg / "response.json", ans3)
                (folder_arg / "events.jsonl").write_text("", encoding="utf-8")
                return {"thread": "t3", "usage": {}, "seconds": 1.0}

            def fake_evidence(path: Path):
                counts = {"01_proposal": 12, "03_revision": 2, "03_revision_retry": 1, "03_revision_retry2": 5}
                return [{}] * counts.get(path.parent.name, 0)

            with patch("research_experiment.run_mode.verified_run", return_value=manifest), \
                 patch("research_experiment.native_call", side_effect=fake_native_call), \
                 patch("research_experiment.evidence", side_effect=fake_evidence):
                research_experiment.run_arm(work, context, "B", retry=True)

            self.assertEqual(seen_folders, ["03_revision_retry2"])
            # Remaining budget = 24 - (12 + 2 + 1) = 9, so turn cap should shrink to 9
            self.assertIn("最多 9 个原生联网事件", seen_instructions[0])
            self.assertTrue((area / "summary.json").exists())


if __name__ == "__main__":
    unittest.main()
