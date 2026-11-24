"""D21c synthetic artifact integration; real original prepare/C04, no model calls."""
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ai_paper5_strict as strict
import task_packet
from review_artifact_task import prepare_artifact_review_task, _original_binding, _language_refs


class ArtifactReviewTaskTests(unittest.TestCase):
    def setUp(self):
        self.run_id = "d21c_fixture_" + uuid.uuid4().hex
        self.work = strict.RUNS / self.run_id
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        strict.original_call(strict.original_command("init", self.run_id, theme="Synthetic offline fixture"))
        self.state = strict.state_of(self.run_id)
        self.state.update(reality_first=False, explanation_first=False, issue_search=False,
                          qual_search_receipts=False, question="Synthetic question", status="design_review")
        self.put("initial/literature_matrix.json", {"rows":[]})
        self.put("initial/theories.json", [{"fixture":True}])
        self.put("merged_literature.json", {"rows":[]})
        self.put("staged_topic.json", self.state)
        self.conversion = {"core_question":"Synthetic core", "prior_question":"Synthetic question", "new_question":"Synthetic question"}
        self.framework = {"core_question":"Synthetic core", "dimensions":[{"id":"d1"}]}
        self.material = {"material_id":"M1"}
        self.receipt("qualitative/attempt_001")

    def put(self, path, value):
        strict.write(self.work / path, value)

    def file(self, path, text):
        p = self.work/path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def sha(self, path):
        return strict.sha(self.work/path)

    def receipt(self, folder, framework=False):
        self.put(folder+"/conversion.json", self.conversion)
        self.file(folder+"/events.jsonl", "SYNTHETIC TEST ONLY")
        self.put(folder+"/response.json", {"fixture":True})
        receipt = {"run_id":self.run_id,"status":"pending_independent_review","conversion_sha256":task_packet._digest(self.conversion),
            "events_sha256":self.sha(folder+"/events.jsonl"), "response_sha256":self.sha(folder+"/response.json"),
            "tool_events":1,"materials":[self.material]}
        if framework:
            self.put(folder+"/framework.json",self.framework)
            receipt.update(phase="framework_collection",framework_sha256=task_packet._digest(self.framework))
        self.put(folder+"/material_receipt.json",receipt)
        return receipt

    def freeze(self):
        self.state.update(status="final_review", review_phase="final")
        self.put("staged_topic.json",self.state)
        import json
        orig=json.loads(strict.original_call(strict.original_command("prepare",self.run_id)))
        prior={"outcome":"pass","question":self.state["question"],"evidence_sha256":orig["evidence_sha256"]}
        method={"path":"online_qualitative"}
        self.state.update(status="frozen",history=[prior],research_method=method)
        self.put("staged_topic.json",self.state)
        self.put("s08_topic.json",{"stage":"S08","question":self.state["question"],"design":"Synthetic fixture design",
            "research_method":method,"evidence_sha256":orig["evidence_sha256"],"review_sha256":task_packet._digest(prior)})
        folder="qualitative_framework/attempt_001"
        receipt=self.receipt(folder,True)
        self.matrix_path=folder+"/analysis_matrix.json"
        self.matrix={"status":"pending_independent_review","framework_sha256":task_packet._digest(self.framework),
            "collection_sha256":task_packet._digest(receipt),"rows":[{"dimension_id":"d1","conclusion":"Synthetic finding",
            "status":"tentative","boundary":"Fixture only","evidence":[{"material_id":"M1"}]}]}
        self.put(self.matrix_path,self.matrix)
        self.binding=_original_binding(strict,self.work,self.work/folder)

    def plan(self):
        self.freeze()
        matrix=self.matrix_path.replace("analysis_matrix.json","analysis_matrix_reviewed.json")
        self.put(matrix,dict(self.matrix,question_binding=self.binding))
        self.plan_folder="autonomous_writing/draft_0"
        self.packet_path=self.plan_folder+"/plan_input.json"
        self.packet={"specific_question":self.state["question"],"core_question":"Synthetic core","method":"online_qualitative",
            "analysis_matrix":matrix,"question_binding":self.binding,
            "sources":{"M1":{"fixture":True},"L1":{"fixture":True}},
            "chapters":[{"id":"d1","sections":[{"argument":"Synthetic planned claim","source_ids":["M1","L1"]}]}]}
        self.put(self.packet_path,self.packet)
        self.file(self.plan_folder+"/论文写作方案.md","Synthetic plan")
        self.plan_req=self.plan_folder+"/writing_plan_review_request.json"
        self.put(self.plan_req,{"run_id":self.run_id,"status":"plan_prepared","review_status":"pending","formal_eligible":False,
            "input_sha256":task_packet._digest(self.packet),"plan_sha256":self.sha(self.plan_folder+"/论文写作方案.md"),
            "topic_sha256":self.sha("s08_topic.json"),"analysis_matrix_sha256":self.sha(matrix),"question_binding":self.binding})

    def task(self, path, **kwargs):
        before=(self.work/"staged_topic.json").read_bytes()
        result=prepare_artifact_review_task(self.run_id,path,**kwargs)
        self.assertEqual(before,(self.work/"staged_topic.json").read_bytes())
        self.assertFalse(result["formal_eligible"])
        self.assertFalse(result["dispatch_authorized"])
        self.assertEqual(task_packet.verify_snapshot(result["task_snapshot"],current_run_id=self.run_id)["packet"],result["task_packet"])
        return result, strict.read(self.work/result["context_path"])

    def test_design_candidate(self):
        result,context=self.task("qualitative/attempt_001/material_receipt.json")
        self.assertEqual(context["review_kind"],"qualitative_design")
        self.assertIn("M1",context["evidence_scope"]["allowed_ids"])
        self.assertEqual(context["design"]["status"],"not_frozen")
        self.put("qualitative/attempt_001/review.json",{})
        with self.assertRaises(ValueError): self.task("qualitative/attempt_001/material_receipt.json")

    def test_receipt_tampering_and_wrong_state(self):
        self.file("qualitative/attempt_001/events.jsonl","Changed")
        with self.assertRaisesRegex(ValueError,"receipt"): self.task("qualitative/attempt_001/material_receipt.json")
        with self.assertRaises(ValueError): self.task("../other/material_receipt.json")

    def test_matrix_candidate_real_original_binding(self):
        self.freeze()
        result,ctx=self.task(self.matrix_path)
        self.assertEqual(ctx["review_kind"],"empirical_matrix")
        self.assertEqual(ctx["key_claims"][0]["evidence_ids"],["M1"])
        self.assertIn("material_adequacy",[x["dimension_id"] for x in ctx["review_dimensions"]])
        self.assertEqual(ctx["design"]["status"],"frozen")
        self.put(self.matrix_path,dict(self.matrix,collection_sha256="changed"))
        with self.assertRaises(ValueError): self.task(self.matrix_path)

    def test_v15_candidate_pending_unresolved_source(self):
        self.plan()
        result,ctx=self.task(self.plan_req)
        self.assertEqual(ctx["review_kind"],"writing_plan")
        self.assertIn("L1",ctx["evidence_scope"]["excluded_or_pending_ids"])
        self.assertEqual(len(ctx["key_claims"]),2)
        self.file(self.plan_folder+"/论文写作方案.md","Changed plan")
        with self.assertRaises(ValueError): self.task(self.plan_req)

    def test_v16_candidate_and_changed_claims(self):
        self.plan()
        folder="writer4_fixture"
        manuscript=folder+"/draft.md"
        claims=folder+"/claims.json"
        request=folder+"/writing_review_request.json"
        self.file(manuscript,"Synthetic claim")
        self.put(claims,{"claims":[{"claim_id":"C1","exact_text":"Synthetic claim","source_ids":["M1"]}]})
        locks=_language_refs(strict)
        self.put(folder+"/writer_manifest.json",{"run_id":self.run_id,"mode":"exploratory",
            "packet_sha256":self.sha(self.packet_path),"resource_sha256":locks["locks"]})
        self.put(folder+"/style_review.json",{"human_language_review":"pending"})
        self.put(request,{"status":"exploratory_draft_awaiting_review","independent_review":"pending","formal_pass":False,
            "gate":"G7","structural_errors":[],"packet_sha256":self.sha(self.packet_path),
            "manuscript_sha256":self.sha(manuscript),"claim_ledger_sha256":self.sha(claims)})
        kwargs={"packet_path":self.packet_path,"manuscript_path":manuscript,"claims_path":claims}
        result,ctx=self.task(request,**kwargs)
        self.assertEqual(ctx["review_kind"],"qualitative_g7")
        self.assertEqual(ctx["key_claims"][0]["claim_id"],"C1")
        self.assertEqual(result["task_packet"]["time_budget_seconds"],0)
        self.put(claims,{"claims":[]})
        with self.assertRaises(ValueError): self.task(request,**kwargs)


if __name__ == "__main__":
    unittest.main()
