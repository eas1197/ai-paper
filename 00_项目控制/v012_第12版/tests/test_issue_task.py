import shutil
import unittest
import uuid
from unittest.mock import Mock
import ai_paper5_strict as strict
import task_packet
from autopilot_v3 import prepare_issue_task, step


class IssueTaskTest(unittest.TestCase):
    def setUp(self):
        self.run="e10_fixture_"+uuid.uuid4().hex
        self.work=strict.RUNS/self.run
        self.addCleanup(shutil.rmtree,self.work,ignore_errors=True)
        strict.original_call(strict.original_command("init",self.run,theme="Synthetic offline test"))
        state=strict.state_of(self.run)
        reality={"phenomenon":"fixture","search_focus":"fixture","sources":[{"url":"https://example.org","kind":"fixture","supports":"fixture","limits":"fixture"}]}
        exchange={"candidate_question":"Synthetic question","search_focus":"fixture"}
        comparison={"run_id":self.run,"event_count":2,"reality_sha256":task_packet._digest(reality),
                    "events":[{"identity":"A"},{"identity":"B"}],"pending_sources":["fixture"]}
        for name,value in (("reality",reality),("event_comparison",comparison),("explanation_exchange",exchange)):
            strict.write(self.work/(name+".json"),value)
        state.update(status="issue_positioning",reality_sha256=task_packet._digest(reality),
            event_comparison_sha256=task_packet._digest(comparison),exchange_sha256=task_packet._digest(exchange))
        strict.write(self.work/"staged_topic.json",state)

    def test_original_prepare_three_layers_frozen_and_idempotent(self):
        before=(self.work/"staged_topic.json").read_bytes()
        result=prepare_issue_task(self.run)
        self.assertEqual(result,prepare_issue_task(self.run))
        self.assertEqual(len(result["task_packet"]["source_scope"]["journals"]),9)
        self.assertFalse(result["dispatch_authorized"])
        self.assertIn("theory_search",result["task_packet"]["output_schema"]["schema"]["required"])
        self.assertIn("object_search",result["instruction"])
        self.assertIn("issue_search",result["instruction"])
        self.assertEqual(before,(self.work/"staged_topic.json").read_bytes())
        self.assertEqual(task_packet.verify_snapshot(result["task_snapshot"],current_run_id=self.run)["packet"],result["task_packet"])

    def test_changed_input_blocks_without_dispatch(self):
        strict.write(self.work/"event_comparison.json",{"event_count":2})
        engine=Mock()
        with self.assertRaisesRegex(ValueError,"evidence changed"):
            step(self.run,executor=engine)
        engine.call.assert_not_called()

    def test_original_stage_mismatch(self):
        state=strict.state_of(self.run)
        state["status"]="initial"
        strict.write(self.work/"staged_topic.json",state)
        with self.assertRaisesRegex(ValueError,"not due"):
            prepare_issue_task(self.run)


if __name__=="__main__": unittest.main()
