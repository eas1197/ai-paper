"""Actual 3.x contracts are authoritative; no fake Chat source promotion."""
from pathlib import Path
import importlib.util
import sys
from unittest import TestCase, main
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/"tools/ai_paper5_strict.py"
spec=importlib.util.spec_from_file_location("ai_paper5_strict",PATH)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


class StrictTests(TestCase):
    def test_real_v3_module_coverage_and_quantities(self):
        info=m.doctor()
        self.assertEqual(info["dev"],{"initial":5,"supplemental":5})
        self.assertEqual(info["formal"],{"initial":5,"supplemental":35})
        self.assertEqual(len(info["journals"]),9)
        self.assertTrue(info["sha256"]["codex_receipts"])

    def test_exact_original_controller_not_v10_or_v11(self):
        command=m.original_command("initial","paper_a")
        self.assertIn("v009_第9版/tools/staged_topic.py"," ".join(command))
        self.assertNotIn("ai_paper5_auto.py"," ".join(command))
        with self.assertRaises(ValueError):m.original_command("fake_gate","paper_a")

    def test_search_route_calls_authoritative_v3(self):
        with patch.object(m,"state_of",side_effect=[{"status":"initial"},{"status":"preliminary_review"}]):
            with patch.object(m,"original_call",return_value="original research output") as fn:
                result=m.status("paper_a",progress=True)
        self.assertEqual(result["action"],"original_native_literature_search")
        self.assertEqual(result["after"],"preliminary_review")
        self.assertEqual(fn.call_args.args[0][3],"initial")

    def test_original_06_07_and_events_are_not_reimplemented(self):
        cmd=m.original_material_command("audit_run",conversion="conversion.json")
        self.assertIn("v005_第5版/tools/qual_materials.py"," ".join(cmd))
        self.assertIn("--conversion",cmd)
        self.assertIn("v009_第9版/tools/resume_writing.py",
                      " ".join(m.original_writing_command("audit_run")))
        self.assertIn("v009_第9版/tools/event_protocol.py",
                      " ".join(m.original_event_command("audit_run","events.json")))
        with self.assertRaises(ValueError):m.original_material_command("audit_run")
        with self.assertRaises(ValueError):m.original_material_command("audit_run",review="a",matrix="b")

    def test_real_original_v3_init_and_prepare(self):
        import uuid
        import shutil
        run_id="strict_ci_"+uuid.uuid4().hex[:12]
        work=m.RUNS/run_id
        try:
            m.original_call(m.original_command("init",run_id,theme="教育分流"))
            self.assertEqual(m.state_of(run_id)["status"],"reality")
            prepared=m.original_call(m.original_command("prepare",run_id))
            self.assertIn("reality_task",prepared)
            self.assertEqual(m.status(run_id)["action"],"original_v3_requires_staged_evidence_or_independent_review")
        finally:
            if work.exists():shutil.rmtree(work)

    def test_chat_is_never_authorized_as_cli(self):
        info=m.doctor()
        task={"profile":"original_v3.2","source_mode":"chat_native_web",
              "policy_sha256":m.sha(m.V3_POLICY),"prompt_sha256":m.sha(m.NATIVE_PROMPT),
              "schema_sha256":m.sha(m.NATIVE_SCHEMA),"journals":info["journals"],
              "accepted":[],"target":5}
        sample={"title":"家庭资源与教育分流","authors":["作者甲"],"journal":"社会",
                "year":2024,"doi":"","metadata_url":"https://example.com/a",
                "abstract_url":"https://example.com/a","abstract_locator":"摘要",
                "abstract_excerpt":"家庭资源与教育分流的关联结果",
                "abstract_summary":"以家庭教育资源和学校分流为研究对象，分析不同群体进入不同教育轨道的机会和约束条件，说明资源差异可能在多个阶段影响教育路径，并进一步指出所发现的关联仍须在具体地区和学校制度背景下作谨慎理解，不能直接解释为未经证实的因果关系。",
                "relevance":"direct","relevance_reason":"研究教育分流机制"}
        result=m.audit_chat(task,{"papers":[sample,dict(sample,journal="社会科学")],
                                  "unverified":[],"search_notes":["真实搜索记录待核"]})
        self.assertFalse(result["native_cli_receipt"])
        self.assertFalse(result["formal_eligible"])
        self.assertEqual(result["provisional_count"],1)
        self.assertEqual(len(result["rejected"]),1)
        with self.assertRaises(ValueError):
            m.audit_chat(dict(task,source_mode="codex"),{"papers":[],"unverified":[],"search_notes":[]})

if __name__=="__main__":main()
