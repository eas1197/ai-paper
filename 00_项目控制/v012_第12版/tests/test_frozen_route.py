"""E14: actual original freeze payload and post-freeze method routing, offline fixtures."""
import shutil
import unittest
import uuid
import ai_paper5_strict as strict
import task_packet
from unittest.mock import patch


class FrozenRouteTest(unittest.TestCase):
    def setUp(self):
        self.run_id="e14_fixture_"+uuid.uuid4().hex
        self.work=strict.RUNS/self.run_id
        self.addCleanup(shutil.rmtree,self.work,ignore_errors=True)
        strict.original_call(strict.original_command("init",self.run_id,theme="Synthetic offline test"))
        self.state=strict.state_of(self.run_id)
        self.papers={"rows":[]}
        self.theory=[{"fixture":True}]
        strict.write(self.work/"merged_literature.json",self.papers)
        strict.write(self.work/"initial/theories.json",self.theory)

    def freeze(self, method):
        paths={k:{"status":"not_applicable","reason":"Synthetic fixture"}
            for k in ("quantitative","secondary_interviews","online_qualitative")}
        paths[method]={"status":"ready","reason":"Fixture","access":"verified","materials":["fixture"]}
        if method=="online_qualitative": paths[method]["approach"]="public_text"
        selection={"path":method,"approach":paths[method].get("approach"),
            "entry06":"existing_quantitative" if method=="quantitative" else "planned",
            "writing07":"existing_quantitative" if method=="quantitative" else "planned",
            "design05":{"quantitative":"理论、研究假设、数据与统计设计",
                "secondary_interviews":"理论分析框架、研究命题、案例选择与二手访谈来源",
                "online_qualitative":"理论分析框架、研究命题、网络场域与文本或观察设计"}[method]}
        report={"outcome":"pass","academic_value":"pass","data_feasibility":"pass",
            "model":"gpt-6.2-sol","invocation_id":"synthetic-only","reason":"fixture",
            "question":"Synthetic question","design":"Synthetic design",
            "evidence_sha256":task_packet._digest({"papers":self.papers,"theories":self.theory}),
            "method_assessment":{"selected":method,"paths":paths}}
        self.state.update(status="s08_ready",review_phase="final",reality_first=False,
            explanation_first=False,issue_search=False,qual_search_receipts=False,
            method_paths=True,question=report["question"],history=[report],research_method=selection)
        strict.write(self.work/"staged_topic.json",self.state)
        strict.original_call(strict.original_command("s08",self.run_id))

    def test_original_quantitative_route_never_writer4(self):
        self.freeze("quantitative")
        result=strict.status(self.run_id)
        self.assertEqual(result["method"],"quantitative")
        self.assertFalse(result["stata_executed"])
        self.assertTrue(any("v004_第4版/tools/stage06.py" in p for p in result["modules"]))
        self.assertTrue(any("v014_第14版/tools/stage07.py" in p for p in result["modules"]))
        self.assertNotIn("writer4_dispatch",result)

    def test_original_qualitative_route(self):
        for index,method in enumerate(("secondary_interviews","online_qualitative")):
            if index:
                # Distinct method fixtures must not overwrite an already frozen run.
                self.setUp()
            self.freeze(method)
            result=strict.status(self.run_id)
            self.assertEqual(result["method"],method)
            self.assertEqual(result["action"],"original_06_adequacy_then_v15_v16")
            self.assertFalse(result["automatic_execution"])

    def test_h03_actual_original_plan_only(self):
        self.freeze("quantitative")
        source=self.work/"quantitative_input.json"
        strict.write(source, {"06":{"phase":"prepare"}})
        target=self.work/"cli_outputs"/"quantitative_plan.json"
        state=(self.work/"staged_topic.json").read_bytes()
        result=strict.original_quantitative_plan(self.run_id,input_path=source,output=target)
        self.assertEqual(result["status"],"original_quantitative_plan_only")
        self.assertEqual(strict.read(target)["stage_id"],"06")
        self.assertEqual(strict.read(target)["run_id"],self.run_id)
        self.assertFalse(result["analysis_executed"])
        self.assertFalse(result["stata_executed"])
        self.assertFalse(result["formal_eligible"])
        self.assertEqual((self.work/"staged_topic.json").read_bytes(),state)
        self.assertFalse((self.work/"stage_06").exists())
        self.assertFalse((strict.ROOT/"00_项目控制/v002_第2版/runs"/self.run_id).exists())

    def test_h03_qualitative_rejected_before_native_plan(self):
        self.freeze("online_qualitative")
        source=self.work/"quantitative_input.json"
        strict.write(source, {"06":{"phase":"prepare"}})
        target=self.work/"cli_outputs"/"quantitative_plan.json"
        with self.assertRaisesRegex(ValueError,"does not authorize"):
            strict.original_quantitative_plan(self.run_id,input_path=source,output=target)
        self.assertFalse(target.exists())

    def test_h03_analyze_approve_and_outside_output_rejected(self):
        self.freeze("quantitative")
        source=self.work/"quantitative_input.json"
        target=self.work/"cli_outputs"/"quantitative_plan.json"
        for phase in ("analyze","approve"):
            strict.write(source, {"06":{"phase":phase}})
            with self.assertRaisesRegex(ValueError,"prepare only"):
                strict.original_quantitative_plan(self.run_id,input_path=source,output=target)
        strict.write(source, {"06":{"phase":"prepare"}})
        with self.assertRaises(ValueError):
            strict.original_quantitative_plan(self.run_id,input_path=source,output=self.work/"stage_06"/"plan.json")
        self.assertFalse(target.exists())

    def test_h06_quantitative_resume_is_rejected_at_both_entries(self):
        import contextlib
        import io
        import json
        self.freeze("quantitative")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = strict.main(["resume-writing", "--run-id", self.run_id])
        self.assertEqual(code, 2)
        self.assertIn("Original qualitative method required", out.getvalue())
        self.assertFalse((self.work / "autonomous_writing").exists())
        with self.assertRaisesRegex(RuntimeError, "Original qualitative method required"):
            strict.original_call(strict.original_writing_command(self.run_id))
        self.assertFalse((self.work / "autonomous_writing").exists())

    def test_changed_freeze_is_rejected(self):
        self.freeze("quantitative")
        path=self.work/"s08_topic.json"
        frozen=strict.read(path)
        frozen["research_method"]["path"]="online_qualitative"
        strict.write(path,frozen)
        with self.assertRaisesRegex(RuntimeError,"frozen payload differs"):
            strict.status(self.run_id)


if __name__=="__main__": unittest.main()
