import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "00_项目控制/v009_第9版/tools"))
sys.path.insert(0, str(ROOT / "11_文献采集适配/v007_第7版/tools"))
sys.path.insert(0, str(ROOT / "07_三稿独立写作/v014_第14版/tools"))
sys.path.insert(0, str(ROOT / "07_三稿独立写作/v014_第14版/tests"))

import staged_topic
import codex_literature
import qualitative07
from collect_common import digest, load, sha, write
from test_qualitative07 import fixture as qual_fixture, review_fixture


def _write_external_receipt(folder: Path, *, role: str, invocation_id: str, request_obj, response_obj,
                            provider="antigravity_subagent", model="gemini-4-neon"):
    folder.mkdir(parents=True, exist_ok=True)
    req_path = folder / "request.json"
    res_path = folder / "response.json"
    write(req_path, request_obj)
    write(res_path, response_obj)
    receipt = {
        "type": "external_agent",
        "status": "completed",
        "provider": provider,
        "role": role,
        "invocation_id": invocation_id,
        "model": model,
        "request_file": "request.json",
        "request_sha256": sha(req_path),
        "response_sha256": sha(res_path),
    }
    write(folder / "provider_receipt.json", receipt)
    return receipt


class ProviderAdapterPlanBTest(unittest.TestCase):
    def test_external_snapshot_literature_ingest_and_tamper_rejection(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            src = base / "incoming"
            (src / "snapshots").mkdir(parents=True)
            snap_file = src / "snapshots" / "paper1.txt"
            snap_text = (
                "社会学研究 2024年第3期 标题：通勤缩短与团队任务再分配 "
                "摘要：本研究考察城市到岗员工通勤缩短后，组织按可用性派工规则如何改变同事间临下班任务分配。"
            )
            snap_file.write_text(snap_text, encoding="utf-8")
            url = "https://shxyj.ajcass.com/Admin/UploadFile/Issue/paper1"
            batch_data = {
                "snapshots": [{"url": url, "file": "snapshots/paper1.txt", "sha256": sha(snap_file)}],
                "papers": [
                    {
                        "journal": "社会学研究",
                        "title": "通勤缩短与团队任务再分配",
                        "authors": ["张三", "李四"],
                        "year": 2024,
                        "doi": "",
                        "relevance": "direct",
                        "relevance_reason": "直接讨论通勤缩短后的组织派工与时间再分配机制",
                        "abstract_summary": "本研究考察城市到岗员工在通勤时间显著缩短之后，组织既有的按可用性派工规则如何改变团队内部同事之间临下班任务的实际分配，并结合时间地理学与组织边界理论检验不同排班与派工制度下的跨人溢出机制与边界条件。",
                        "abstract_excerpt": "组织按可用性派工规则如何改变同事间临下班任务分配",
                        "abstract_locator": "正文摘要第1段",
                        "metadata_url": url,
                        "abstract_url": url,
                    },
                    {
                        "journal": "社会学研究",
                        "title": "虚构摘要测试文献",
                        "authors": ["王五"],
                        "year": 2024,
                        "doi": "",
                        "relevance": "direct",
                        "relevance_reason": "测试防编造摘要拦截",
                        "abstract_summary": "本研究是一篇用于测试外部快照防编造摘要门禁的合成样本，重点描述了一段较长的摘要概述，但其中引用的原文短摘并不存在于已归档的网页快照文件中，门禁必须准确将其拦截拒收。",
                        "abstract_excerpt": "这段文字根本不存在于网页快照中",
                        "abstract_locator": "摘要",
                        "metadata_url": url,
                        "abstract_url": url,
                    },
                ],
                "unverified": [],
                "search_notes": ["外部快照测试批次"],
            }
            batch_manifest = src / "external_batch.json"
            write(batch_manifest, batch_data)

            work = base / "collection"
            template = base / "prompt.txt"
            template.write_text("{theme} {journals} {desired} {accepted}", encoding="utf-8")
            schema = base / "schema.json"
            write(schema, {})
            config = {
                "theme": "通勤缩短与组织时间分配",
                "journals": ["社会学研究"],
                "target": 10,
                "max_batches": 1,
                "timeout_seconds": 120,
                "run_mode": "dev",
                "search_action_budget": 12,
                "workload_sha256": digest({"dev": True}),
            }
            bundle = codex_literature.collect(config, work, template, schema, external=batch_manifest)
            self.assertEqual(bundle["engine"], codex_literature.EXTERNAL_ENGINE)
            self.assertEqual(bundle["count"], 1)
            self.assertEqual(len(bundle["unverified"]), 1)
            self.assertIn("absent from the archived snapshot", bundle["unverified"][0]["reason"])

            matrix = codex_literature.receive_external(work, ["社会学研究"])
            self.assertEqual(matrix["verified_rows"], 1)

            # Tamper with archived snapshot and confirm receive_external rejects it
            archived_snap = work / "batch_001/snapshots/paper1.txt"
            archived_snap.write_text(snap_text + " TAMPERED", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed web snapshot"):
                codex_literature.receive_external(work, ["社会学研究"])

    def test_route_b_external_critical_receipt_and_anti_tamper(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            work = Path(tmp)
            crit_dir = work / "critical_ext"
            exchange_body = {
                "expectation": "e",
                "observation": "o",
                "initial_explanation": "i",
                "challenge": "c",
                "candidate_question": "q",
                "research_actor": "antigravity-author-001",
                "critical_actor": "antigravity-crit-001",
                "search_focus": "commute task reallocation",
            }
            _write_external_receipt(
                crit_dir,
                role="critical",
                invocation_id="antigravity-crit-001",
                request_obj={"task": "independent challenge"},
                response_obj=exchange_body,
            )
            packet = {
                "reality": {
                    "phenomenon": "Commute shortening",
                    "search_focus": "Commute and task allocation",
                    "sources": [{
                        "url": "https://example.org/p1",
                        "kind": "public_post",
                        "supports": "action sequence",
                        "limits": "single account",
                    }],
                },
                "event_packet": {
                    "sources": {"S1": "https://example.org/p1", "S2": "https://example.org/p2"},
                    "events": [
                        {"identity": "E1", "facts": [{"source_id": "S1", "statement": "f1", "use": "u1", "key": True, "status": "single_account"}]},
                        {"identity": "E2", "facts": [{"source_id": "S2", "statement": "f2", "use": "u2", "key": True, "status": "single_account"}]},
                    ],
                    "sensitivity": "anonymized",
                },
                "exchange": dict(
                    exchange_body,
                    critical_receipt={
                        "provider_receipt": "critical_ext/provider_receipt.json",
                        "provider_receipt_sha256": sha(crit_dir / "provider_receipt.json"),
                    },
                ),
                "issue_plan": {
                    "issue": "workplace time",
                    "why": "mechanism",
                    "object_search": "commute China",
                    "issue_search": "task allocation",
                    "theory_search": "boundary theory",
                },
                "topic_reasoning": {
                    "opportunity": {"reasoning": "r1"},
                    "question": {"reasoning": "r2"},
                    "deepening": {"reasoning": "r3", "change_kind": "academic"},
                },
            }
            state = {
                "run_id": "b_ext_crit", "theme": "Commute", "mode": "dev",
                "research_route": "B", "status": "research_exploration",
                "reality_first": True, "explanation_first": True, "issue_search": True,
                "topic_reasoning_required": True, "history": [],
            }
            staged_topic.record_research(work, state, packet)
            self.assertEqual(state["status"], "initial")

            # Tamper with critical response and verify pre-search check rejects it
            write(crit_dir / "response.json", {"objections": ["TAMPERED"]})
            with self.assertRaisesRegex(ValueError, "changed"):
                staged_topic.verify_external_critical(work, packet["exchange"])

    def test_v14_external_author_and_external_reviewer_delivery_and_anti_self_review(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            base = Path(tmp)
            task, draft = qual_fixture()

            def make_review(content_sha):
                return {
                    "content_sha256": content_sha,
                    "decision": "accepted",
                    "assessment": "九项实质审查均已核对通过，证据链与边界完整。",
                    "checks": {k: {"status": "pass", "reason": f"{k} 经独立核对符合标准"}
                               for k in qualitative07.REVIEW_CHECKS},
                    "issues": [],
                }

            def ext_provider(role, request, folder):
                if role == "draft":
                    _write_external_receipt(
                        folder, role="draft", invocation_id="agy-author-001",
                        request_obj=request, response_obj=draft,
                    )
                    return draft, qualitative07.invocation_receipt(folder, "draft", request)
                rev = make_review(request["content_sha256"])
                _write_external_receipt(
                    folder, role="review", invocation_id="agy-reviewer-001",
                    request_obj=request, response_obj=rev,
                )
                return rev, qualitative07.invocation_receipt(folder, "review", request)

            attempt_dir = base / "attempt_001"
            report = qualitative07.run_loop(task, attempt_dir, provider=ext_provider, context={"pack_id": draft["pack_id"]})
            self.assertEqual(report["status"], "passed")
            qualitative07.publish_current(attempt_dir)
            exported = qualitative07.export_delivery(attempt_dir)
            self.assertEqual(exported["status"], "passed")

            # Tamper with manuscript.md and confirm validate_delivery rejects it
            ms = attempt_dir / "attempt_001/manuscript.md"
            ms.write_text(ms.read_text(encoding="utf-8") + "\nTAMPER", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "变化|不一致"):
                qualitative07.validate_delivery(attempt_dir)

            # Anti-self-review: reviewer reusing author invocation_id must be blocked
            def self_review_provider(role, request, folder):
                if role == "draft":
                    _write_external_receipt(
                        folder, role="draft", invocation_id="same-id-999",
                        request_obj=request, response_obj=draft,
                    )
                    return draft, qualitative07.invocation_receipt(folder, "draft", request)
                rev = make_review(request["content_sha256"])
                _write_external_receipt(
                    folder, role="review", invocation_id="same-id-999",
                    request_obj=request, response_obj=rev,
                )
                return rev, qualitative07.invocation_receipt(folder, "review", request)

            attempt_bad = base / "attempt_002"
            bad_report = qualitative07.run_loop(task, attempt_bad, provider=self_review_provider,
                                                context={"pack_id": draft["pack_id"]})
            self.assertEqual(bad_report["status"], "blocked")
            self.assertIn("重复", bad_report["feedback"]["error"])


if __name__ == "__main__":
    unittest.main()
