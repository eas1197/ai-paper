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

    def freeze(self, method, *, reviewed_receipt=False, reviewed_scope=None):
        paths={k:{"status":"not_applicable","reason":"Synthetic fixture"}
            for k in ("quantitative","secondary_interviews","online_qualitative")}
        paths[method]={"status":"ready","reason":"Fixture","access":"verified","materials":["fixture"]}
        if method=="online_qualitative": paths[method]["approach"]="public_text"
        if reviewed_receipt:
            folder=self.work/"qualitative"/"attempt_001"
            conversion={k:"Synthetic offline fixture" for k in
                ("core_question","prior_question","theoretical_concern","reason_for_conversion",
                 "framework","literature","context")}
            conversion["new_question"]="Synthetic question"
            strict.write(folder/"conversion.json",conversion)
            strict.write(folder/"events.jsonl",{"fixture":True})
            strict.write(folder/"response.json",{"fixture":True})
            receipt={"fixture":True,"status":"pending_independent_review","run_id":self.run_id,
                "tool_events":[{"fixture":True}],
                "conversion_sha256":task_packet._digest(conversion),
                "events_sha256":strict.sha(folder/"events.jsonl"),
                "response_sha256":strict.sha(folder/"response.json"),
                "materials":[{"material_id":"fixture","path":method}]}
            strict.write(folder/"material_receipt.json",receipt)
            paths[method].update(search_attempt="attempt_001",
                receipt_sha256=strict.sha(folder/"material_receipt.json"))
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
        if reviewed_scope is not None:
            report["material_scope"]=reviewed_scope
        self.state.update(status="s08_ready",review_phase="final",reality_first=False,
            explanation_first=False,issue_search=False,qual_search_receipts=False,
            method_paths=True,question=report["question"],history=[report],research_method=selection)
        strict.write(self.work/"staged_topic.json",self.state)
        strict.original_call(strict.original_command("s08",self.run_id))


    def test_p0303_auto_material_task_waits_for_reviewed_scope(self):
        self.freeze("online_qualitative",reviewed_receipt=True)
        result=strict.status(self.run_id,progress=True)
        self.assertEqual(result["action"],"original_06_material_task")
        self.assertEqual(result["status"],"waiting_for_user")
        candidate=result["candidate"]
        self.assertEqual(candidate["task_packet"]["research_question"],"Synthetic question")
        self.assertEqual(len(candidate["unresolved_scope"]),5)
        self.assertEqual(candidate["task_packet"]["quantity_budget"],{})
        self.assertFalse(result["dispatch_authorized"])
        self.assertFalse(result["search_dispatched"])
        self.assertEqual(task_packet.verify_snapshot(candidate["task_snapshot"],current_run_id=self.run_id)["packet"],candidate["task_packet"])
        from run_observation import command_observation
        from runtime_waiting import attach_wait
        runtime=command_observation("advance",result)
        wait=attach_wait(runtime,result,run_id=self.run_id)
        self.assertEqual(wait["runtime_status"],"waiting_for_user")
        self.assertIn("advance",wait["waiting"]["resume_argv_template"])
        self.assertNotIn("literature-receive",wait["waiting"]["resume_argv_template"])
        self.assertEqual(strict.status(self.run_id,progress=True),result)

    def test_p0303_complete_scope_waits_without_launch(self):
        self.freeze("secondary_interviews",reviewed_receipt=True,reviewed_scope={
            "target_objects":["fixture"],"events":["fixture"],"time_range":"fixture",
            "material_types":["fixture"],"exclusions":["fixture"]})
        result=strict.status(self.run_id,progress=True)
        self.assertEqual(result["status"],"awaiting_original_material_results")
        self.assertEqual(result["candidate"]["unresolved_scope"],[])
        import json
        purpose=json.loads(result["candidate"]["task_packet"]["purpose"])
        manifest=strict.read(self.work/"run_manifest.json")
        self.assertEqual(purpose["original_limits"]["max_batches"],manifest["workload"]["11"]["max_batches"])
        from run_observation import command_observation
        from runtime_waiting import attach_wait
        runtime=command_observation("advance",result)
        self.assertEqual(runtime["runtime_status"],"waiting_for_chat")
        wait=attach_wait(runtime,result,run_id=self.run_id)
        self.assertFalse(wait["waiting"]["dispatch_authorized"])
        self.assertNotIn("literature-receive",wait["waiting"]["resume_argv_template"])
        self.assertFalse((self.work/"qualitative/attempt_002").exists())
        self.assertFalse(result["advance_gate"])

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

    def test_p0302_real_original_06_preflight_offline(self):
        self.freeze("online_qualitative",reviewed_receipt=True)
        state=(self.work/"staged_topic.json").read_bytes()
        frozen=(self.work/"s08_topic.json").read_bytes()
        self.assertFalse(strict.status(self.run_id)["automatic_execution"])
        result=strict.status(self.run_id,progress=True)
        self.assertTrue(result["original_06_preflight_completed"])
        self.assertEqual(result["research_id"],self.run_id)
        self.assertEqual(result["reviewed_attempt"],"attempt_001")
        self.assertFalse(result["search_dispatched"])
        self.assertFalse(result["advance_gate"])
        self.assertEqual((self.work/"staged_topic.json").read_bytes(),state)
        self.assertEqual((self.work/"s08_topic.json").read_bytes(),frozen)
        self.assertFalse((self.work/"qualitative/attempt_002").exists())
        import autopilot_v3
        second=autopilot_v3.step(self.run_id)
        self.assertEqual(second,result)

    def test_p0302_quantitative_does_not_call_06(self):
        self.freeze("quantitative")
        result=strict.status(self.run_id,progress=True)
        self.assertEqual(result["action"],"original_quantitative_handoff")
        self.assertFalse(result["stata_executed"])
        self.assertNotIn("original_06_preflight_completed",result)

    def test_p0302_missing_receipt_and_wrong_state_rejected(self):
        with self.assertRaises(Exception):
            strict.frozen_progress(self.run_id)
        self.freeze("online_qualitative")
        with self.assertRaisesRegex(ValueError,"reviewed material attempt"):
            strict.status(self.run_id,progress=True)

    def test_p0302_changed_raw_receipt_rejected(self):
        self.freeze("secondary_interviews",reviewed_receipt=True)
        strict.write(self.work/"qualitative/attempt_001/response.json",{"changed":True})
        with self.assertRaisesRegex(RuntimeError,"search receipt or raw evidence has changed"):
            strict.status(self.run_id,progress=True)

    def test_changed_freeze_is_rejected(self):
        self.freeze("quantitative")
        path=self.work/"s08_topic.json"
        frozen=strict.read(path)
        frozen["research_method"]["path"]="online_qualitative"
        strict.write(path,frozen)
        with self.assertRaisesRegex(RuntimeError,"frozen payload differs"):
            strict.status(self.run_id)


if __name__=="__main__": unittest.main()
