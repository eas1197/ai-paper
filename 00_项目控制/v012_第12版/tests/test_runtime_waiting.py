import unittest
import test_review_task_integration as fixture
import ai_paper5_strict as strict
from run_observation import observation
from runtime_waiting import wait_contract, attach_wait


class WaitingContractTest(unittest.TestCase):
    setUp=fixture.OriginalReviewTaskIntegration.setUp
    set_stage=fixture.OriginalReviewTaskIntegration.set_stage

    def test_four_wait_contracts_without_automatic_retry(self):
        for kind in ("waiting_for_chat","waiting_for_codex","waiting_for_review","waiting_for_user"):
            item=wait_contract(observation(kind),self.run_id)
            self.assertTrue(item["expected_deliverables"])
            self.assertIn(self.run_id,item["resume_argv_template"])
            self.assertFalse(item["automatic_retry"])
            self.assertFalse(item["resume_is_authorization"])
            self.assertIsNone(item["timeout_policy"]["deadline"])

    def test_bound_review_wait_persistent_idempotent(self):
        self.set_stage("preliminary_review")
        result=strict.status(self.run_id,progress=True)
        runtime=observation("waiting_for_review")
        record=attach_wait(runtime,result,run_id=self.run_id)
        self.assertEqual(record,attach_wait(runtime,result,run_id=self.run_id))
        self.assertEqual(record["wait_record_status"],"recorded")
        self.assertEqual(strict.read(self.work/record["wait_record"]["path"]),record["waiting"])
        self.assertEqual(len(list((self.work/"runtime_waiting").glob("*.json"))),1)
        self.set_stage("final_review")
        with self.assertRaisesRegex(ValueError,"hash changed"):
            attach_wait(runtime,result,run_id=self.run_id)

    def test_query_only_wait_never_writes(self):
        self.set_stage("design_review")
        result=strict.status(self.run_id,progress=True)
        runtime=observation("waiting_for_review")
        view=attach_wait(runtime,result,run_id=self.run_id,persist=False)
        self.assertEqual(view["wait_record_status"],"read_only")
        self.assertFalse((self.work/"runtime_waiting").exists())

    def test_unbound_wait_does_not_create_run(self):
        view=attach_wait(observation("waiting_for_chat"),{},run_id=self.run_id)
        self.assertEqual(view["wait_record_status"],"unbound_observation_only")
        self.assertFalse((self.work/"runtime_waiting").exists())


if __name__=="__main__": unittest.main()
