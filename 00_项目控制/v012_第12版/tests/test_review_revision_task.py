"""D21d re-review preparation: synthetic historical reports, actual C04 versions."""
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ai_paper5_strict as strict
import task_packet
from review_task import prepare_review_task


def revision_fixture(work, result, kind, before_path, after_path, write):
    old = next(row for row in result["task_packet"]["input_files"] if row["path"] == after_path)
    before = {"path":before_path,"sha256":strict.sha(work/before_path)}
    prior = {"schema_version":4,"task_snapshot":result["task_snapshot"],"review_kind":kind,
        "decision":"revise","reason":"SYNTHETIC TEST ONLY","assessment_scope":"Fixture",
        "issues":[{"issue_id":"I1","dimension_id":"academic_value","category":"academic_defect","blocking":True,
            "detail":"Fixture scope","evidence_ids":[],"required_action":"Fixture revision"}],
        "evidence_findings":[],"reviewer":{"executor":"manual","reviewer_id":"fixture-not-real",
            "model":None,"invocation_id":"fixture-not-real"},"execution_id":"fixture-not-real",
        "review_type":"academic_review","prior_review":None}
    write("fixture_prior.json",prior)
    report_ref={"path":"fixture_prior.json","sha256":strict.sha(work/"fixture_prior.json")}
    after={"path":after_path,"sha256":strict.sha(work/after_path)}
    record={"prior_report":report_ref,"issues":[{"issue_id":"I1","response":"Fixture response"}],
            "changes":[{"before":before,"after":after}]}
    write("fixture_revision.json",record)
    return record


class RevisionPreparationTests(unittest.TestCase):
    def setUp(self):
        self.run_id="d21d_fixture_"+uuid.uuid4().hex
        self.work=strict.RUNS/self.run_id
        self.addCleanup(shutil.rmtree,self.work,ignore_errors=True)
        strict.original_call(strict.original_command("init",self.run_id,theme="Synthetic test"))
        self.state=strict.state_of(self.run_id)
        self.state.update(status="preliminary_review",question="Synthetic question",
            reality_first=False,explanation_first=False,issue_search=False,qual_search_receipts=False)
        self.write("staged_topic.json",self.state)
        self.write("initial/literature_matrix.json",{"rows":[]})
        self.write("initial/theories.json",[{"fixture":True}])
        self.old=prepare_review_task(self.run_id)
        shutil.copyfile(self.work/"initial/literature_matrix.json",self.work/"archive.json")
        self.write("initial/literature_matrix.json",{"rows":[],"revised":True})
        self.state.update(status="S03",review_phase="initial")
        self.write("staged_topic.json",self.state)
        self.revision=revision_fixture(self.work,self.old,"preliminary_academic","archive.json",
            "initial/literature_matrix.json",self.write)

    def write(self,name,value):
        strict.write(self.work/name,value)

    def task(self):
        return prepare_review_task(self.run_id,prior_report="fixture_prior.json",revision_record="fixture_revision.json")

    def test_valid_historical_lineage_frozen(self):
        result=self.task()
        context=strict.read(self.work/result["context_path"])
        self.assertEqual(result["task_packet"]["stage_id"],self.old["task_packet"]["stage_id"])
        self.assertNotEqual(result["task_snapshot"],self.old["task_snapshot"])
        self.assertEqual(context["review_type"],"independent_re_review")
        self.assertEqual(context["input_binding"]["historical_task_snapshot"],self.old["task_snapshot"])
        self.assertFalse(result["dispatch_authorized"])
        task_packet.verify_snapshot(result["task_snapshot"],current_run_id=self.run_id)

    def test_consecutive_rereviews_keep_current_context(self):
        first=self.task()
        shutil.copyfile(self.work/"initial/literature_matrix.json",self.work/"archive_round2.json")
        self.write("initial/literature_matrix.json",{"rows":[],"revised":2})
        self.revision=revision_fixture(self.work,first,"preliminary_academic","archive_round2.json",
            "initial/literature_matrix.json",self.write)
        second=self.task()
        self.assertNotEqual(first["task_snapshot"],second["task_snapshot"])
        context=strict.read(self.work/second["context_path"])
        self.assertEqual(context["input_binding"]["historical_task_snapshot"],first["task_snapshot"])

    def test_missing_issue_and_unrelated_before_rejected(self):
        self.revision["issues"]=[]
        self.write("fixture_revision.json",self.revision)
        with self.assertRaisesRegex(ValueError,"blocking issue"): self.task()
        self.revision["issues"]=[{"issue_id":"I1","response":"Fixture response"}]
        self.write("unrelated.json",{"different":True})
        self.revision["changes"][0]["before"]={"path":"unrelated.json","sha256":strict.sha(self.work/"unrelated.json")}
        self.write("fixture_revision.json",self.revision)
        with self.assertRaisesRegex(ValueError,"historical review"): self.task()

    def test_new_question_and_missing_lineage_rejected(self):
        self.state["question"]="Different question"
        self.write("staged_topic.json",self.state)
        with self.assertRaisesRegex(ValueError,"same selected question"): self.task()
        with self.assertRaisesRegex(ValueError,"prior-review lineage"): prepare_review_task(self.run_id)

    def test_fabricated_old_snapshot_rejected(self):
        prior=strict.read(self.work/"fixture_prior.json")
        prior["task_snapshot"]["snapshot_sha256"]="a"*64
        self.write("fixture_prior.json",prior)
        with self.assertRaises(OSError): self.task()


if __name__ == "__main__":
    unittest.main()
