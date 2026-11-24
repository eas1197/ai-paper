import shutil
import unittest
import uuid
from unittest.mock import Mock
import ai_paper5_strict as strict
from autopilot_v3 import step
from user_wait import request_hold, acknowledge_hold, cancel_run
from run_observation import command_observation
from runtime_waiting import attach_wait


class UserWaitTest(unittest.TestCase):
    def setUp(self):
        self.run="e19_fixture_"+uuid.uuid4().hex
        self.work=strict.RUNS/self.run
        self.addCleanup(shutil.rmtree,self.work,ignore_errors=True)
        strict.original_call(strict.original_command("init",self.run,theme="Synthetic offline test"))

    def test_original_material_and_budget_wait(self):
        for phase,reason in (("materials_pending","materials"),("literature_budget_exhausted","budget")):
            state=strict.state_of(self.run);state["status"]=phase
            strict.write(self.work/"staged_topic.json",state)
            engine=Mock()
            result=step(self.run,executor=engine)
            self.assertEqual(result,strict.status(self.run,progress=True))
            self.assertEqual(result["user_wait_reason"],reason)
            self.assertFalse(result["budget_changed"])
            self.assertFalse(result["advance_gate"])
            runtime=command_observation("advance",result)
            self.assertEqual(runtime["runtime_status"],"waiting_for_user")
            self.assertEqual(attach_wait(runtime,result,run_id=self.run)["wait_record_status"],"recorded")
            engine.call.assert_not_called()

    def test_explicit_question_hold_blocks_autopilot(self):
        before=(self.work/"staged_topic.json").read_bytes()
        hold=request_hold(self.run,"question")
        self.assertEqual(hold,request_hold(self.run,"question"))
        engine=Mock()
        self.assertEqual(hold,step(self.run,executor=engine))
        self.assertEqual(hold,strict.status(self.run,progress=True))
        self.assertEqual(before,(self.work/"staged_topic.json").read_bytes())
        engine.call.assert_not_called()

    def test_acknowledgement_requires_matching_hold_and_does_not_execute(self):
        hold=request_hold(self.run,"question")
        path=self.work/"fixture_decision.json"
        decision={"research_id":self.run,"hold_id":"wrong","continue_original_task":True,"decision":"Synthetic fixture"}
        strict.write(path,decision)
        with self.assertRaises(ValueError): acknowledge_hold(self.run,path)
        decision["hold_id"]=hold["user_hold_id"]
        strict.write(path,decision)
        result=acknowledge_hold(self.run,path)
        self.assertEqual(result["status"],"queued")
        self.assertEqual(strict.state_of(self.run)["status"],"reality")
        self.assertFalse(result["advance_gate"])
        self.assertNotEqual(strict.status(self.run).get("status"),"waiting_for_user")

    def test_explicit_cancel_preserves_original_and_stops_scheduler(self):
        before=(self.work/"staged_topic.json").read_bytes()
        with self.assertRaises(ValueError): cancel_run(self.run,"")
        result=cancel_run(self.run,"Synthetic operator cancellation")
        self.assertEqual(result,cancel_run(self.run,"Synthetic operator cancellation"))
        engine=Mock()
        self.assertEqual(result,step(self.run,executor=engine))
        self.assertEqual(result,strict.status(self.run,progress=True))
        self.assertEqual(command_observation("advance",result)["outcome_kind"],"user_cancelled")
        self.assertEqual(before,(self.work/"staged_topic.json").read_bytes())
        engine.call.assert_not_called()
        with self.assertRaises(ValueError): request_hold(self.run,"question")


if __name__=="__main__": unittest.main()
