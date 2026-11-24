"""Actual 3.x contracts are authoritative; no fake Chat source promotion."""
from pathlib import Path
import importlib.util
import subprocess
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
            with patch.object(m,"original_call",return_value="original research output") as fn, \
                 patch.object(m,"codex_task",return_value={"task_snapshot":{"snapshot_sha256":"fixture"}}) as packet:
                result=m.status("paper_a",progress=True)
                packet.assert_called_once_with("paper_a","initial")
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

    def test_original_v009_direct_cli_init_prepare_without_wrapper(self):
        import uuid
        import shutil
        run_id="direct_cli_"+uuid.uuid4().hex[:12]
        work=m.RUNS/run_id
        try:
            init_result=subprocess.run(
                m.original_command("init",run_id,theme="教育分流"),
                cwd=m.ROOT,capture_output=True,text=True,timeout=90)
            self.assertEqual(init_result.returncode,0,init_result.stderr+init_result.stdout)
            self.assertEqual(m.state_of(run_id)["status"],"reality")
            prepare_result=subprocess.run(
                m.original_command("prepare",run_id),
                cwd=m.ROOT,capture_output=True,text=True,timeout=90)
            self.assertEqual(prepare_result.returncode,0,
                             prepare_result.stderr+prepare_result.stdout)
            self.assertIn("reality_task",prepare_result.stdout)
            self.assertEqual(m.status(run_id)["action"],
                             "original_v3_requires_staged_evidence_or_independent_review")
        finally:
            if work.exists():
                shutil.rmtree(work)

    def test_original_cli_help_smoke_without_v012_execution(self):
        modules=(m.V3_TOPIC,m.V3_EVENTS,m.MATERIAL,m.REVISION,m.V15,m.V16)
        for module in modules:
            with self.subTest(module=module.name):
                result=subprocess.run(
                    [sys.executable,"-B",str(module),"--help"],
                    cwd=m.ROOT,capture_output=True,text=True,timeout=45)
                self.assertEqual(result.returncode,0,
                                 str(module)+"\n"+result.stderr+result.stdout)
                self.assertIn("usage:",result.stdout.lower())

    def test_v012_adapters_route_to_original_v009_v005_v016_modules(self):
        topic=m.original_command("prepare","sample")
        self.assertEqual(Path(topic[2]),m.V3_TOPIC)

        materials=m.original_material_command("sample",conversion=Path("conversion.json"))
        self.assertEqual(Path(materials[2]),m.MATERIAL)

        writing=m.original_writing_command("sample")
        self.assertEqual(Path(writing[2]),m.REVISION)

        writer4=m.original_writer4_command(
            "prepare",packet=Path("plan_input.json"),
            workspace=Path("writer4_workspace"),mode="exploratory")
        self.assertEqual(Path(writer4[2]),m.V16)
        self.assertEqual(writer4[3],"prepare")
        self.assertIn("--packet",writer4)
        self.assertIn("--workspace",writer4)
        self.assertIn("--mode",writer4)

        resume_source=Path(m.REVISION).read_text(encoding="utf-8-sig")
        self.assertIn("from material_adequacy import writing_material_status",resume_source)
        self.assertIn("from repair_materials import",resume_source)
        self.assertIn("from writing_plan import produce",resume_source)
        writer_source=Path(m.V16).read_text(encoding="utf-8-sig")
        self.assertIn("from writing_plan import render",writer_source)

    def test_writer4_cli_dispatches_v016_through_original_adapter(self):
        with patch.object(m,"doctor",return_value={}), \
             patch.object(m,"original_call",return_value="writer4 complete") as original:
            result=m.main(["writer4","--action","prepare","--packet","plan_input.json",
                           "--workspace","writer4_workspace","--mode","exploratory"])
        self.assertEqual(result,0)
        command=original.call_args.args[0]
        self.assertEqual(Path(command[2]),m.V16)
        self.assertEqual(command[3],"prepare")

    def test_v016_adapter_rejects_incomplete_dispatch_arguments(self):
        with self.assertRaisesRegex(ValueError,"workspace"):
            m.original_writer4_command("prepare",packet=Path("plan.json"))
        with self.assertRaisesRegex(ValueError,"manuscript and claims"):
            m.original_writer4_command("submit",packet=Path("plan.json"),
                                       workspace=Path("writer4"))
        with self.assertRaisesRegex(ValueError,"Unknown original v016"):
            m.original_writer4_command("unknown",packet=Path("plan.json"))

    def test_same_fixture_chat_native_run_is_separate_and_nonformal(self):
        base=m.ROOT/"handoff_runs"/"digital_mutual_aid_20261122"
        parent=m.read(base/"staged_topic.json")
        chat=m.read(base/"chat_native_20261122"/"Chat实验状态.json")
        self.assertEqual(parent["status"],"explanation_exchange")
        self.assertFalse(parent["formal_eligible"])
        self.assertEqual(chat["parent_staged_topic_status"],parent["status"])
        self.assertFalse(chat["parent_modified"])
        self.assertIsNone(chat["independent_model_invocation_id"])
        self.assertFalse(chat["independent_review_verified"])
        self.assertIsNone(chat["cli_tool_receipts"])
        self.assertEqual(chat["web_search_mode"],"ChatGPT native browsing, not Codex CLI")
        self.assertEqual(chat["final_gate"],
                         "not_passed_due_to_missing_independent_review_and_empirical_limitations")

    def test_chat_native_matrices_and_writing_plan_are_not_formal_v009_receipts(self):
        base=m.ROOT/"handoff_runs"/"digital_mutual_aid_20261122"/"chat_native_20261122"
        literature=m.read(base/"文献检索矩阵.json")
        materials=m.read(base/"经验材料与分析矩阵.json")
        writing=(base/"论文写作方案.md").read_text(encoding="utf-8-sig")
        self.assertEqual(literature["acquisition_mode"],"chat_native_web")
        self.assertFalse(literature["targets"]["formal"])
        self.assertEqual(materials["acquisition_mode"],"chat_native_web")
        self.assertEqual(materials["method"],
                         "public_secondhand_interview_and_reported_process_comparison")
        self.assertIn("未获独立审查放行",writing)
        self.assertIn("exploratory",writing.lower())

if __name__=="__main__":main()
