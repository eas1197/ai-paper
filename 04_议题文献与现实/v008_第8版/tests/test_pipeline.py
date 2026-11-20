"""Test acquisition/04/05 connections with synthetic material, not real research."""
from __future__ import annotations
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import runtime as rt
import pipeline04 as pipe
import test_workflow as fixtures

def collector_fixture():
    file=rt.registry_module("11")/"tests/test_acquisition.py"
    pipe.collectors()
    spec=importlib.util.spec_from_file_location("collector_test_fixtures",file)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root=Path(self.temp.name)
        self.patch=patch.object(rt,"run_directory",lambda run_id:self.root/"runs"/run_id); self.patch.start(); self.addCleanup(self.patch.stop)
        self.pipe_patch=patch.object(pipe,"run_directory",lambda run_id:self.root/"runs"/run_id); self.pipe_patch.start(); self.addCleanup(self.pipe_patch.stop)
        self.cf=collector_fixture()
    def config_file(self, **kwargs):
        file=self.root/"workflow.json"
        rt.write(file,{"04":{"theme":"TEST主题"},"05":{},"collection":self.cf.config(journals=["中国青年研究"], **kwargs)})
        return file
    def provider(self):
        class JournalProvider(self.cf.Provider):
            def search(self, query, cursor=None):
                page = super().search(query, cursor)
                return dict(page, records=[dict(r, journal="中国青年研究") for r in page["records"]])
        return JournalProvider()

    def screened(self, paper_id, tags=()):
        return {"paper_id": paper_id, "decision": "included", "review_status": "verified", "reviewer": "TEST",
                "read_at": "2026-11-15", "reason": "TEST相关",
                "scores": {k: 5 for k in ("relevance", "theory_authority", "design_quality", "journal_authority", "recency")},
                "perspective_tags": list(tags)}

    def test_acquire_rank_download_core_and_bridge_never_fakes_reading(self):
        file=self.config_file()
        result=pipe.acquire(file,"TEST_pipeline",provider=self.provider())
        self.assertEqual(result["counts"]["fulltexts_verified"], 0)
        work=Path(result["work"])
        self.assertEqual(pipe.acquire(file,"TEST_pipeline",action="rank")["selected"], 0)
        screening = self.root / "screening.json"
        records = rt.load(work / "checkpoint.json")["records"]
        rt.write(screening, [self.screened(r["paper_id"]) for r in records])
        raw = rt.load(file)
        raw["collection"]["screening_file"] = str(screening)
        rt.write(file, raw)
        rank=pipe.acquire(file,"TEST_pipeline",action="rank")
        self.assertEqual(rank["selected"],25)
        collected=pipe.acquire(file,"TEST_pipeline",action="core",provider=self.provider(),pdf_reader=self.cf.fake_pdf)
        self.assertEqual(collected["counts"]["fulltexts_verified"],25)
        result=pipe.acquire(file,"TEST_pipeline",action="bridge")
        workflow=rt.load(result["workflow_input"]); annotations=rt.load(workflow["04"]["annotations"])
        self.assertEqual(result["reference_candidates"],25)
        self.assertEqual(len(annotations["paper_reviews"]),100)
        self.assertEqual(workflow["04"]["literature"][0]["origin"], "online_search")
        self.assertTrue(all(row["mode"] == "online_search" for row in annotations["searches"]))
        self.assertTrue(all(r["abstract"]["status"]=="not_read" for r in annotations["paper_reviews"].values()))
        self.assertTrue(workflow["config"]["archive_all_fulltexts"])
        again=pipe.acquire(file,"TEST_pipeline",action="bridge")
        self.assertNotEqual(result["workflow_input"],again["workflow_input"])
        self.assertEqual(rt.load(work/"core_selection_proposal.json")["confirmed_core_count"],0)
    def test_reviewed_relevance_beats_unreviewed_keyword_and_excluded_papers(self):
        file=self.config_file(download_scope="none")
        result=pipe.acquire(file,"TEST_rank",provider=self.provider())
        work=Path(result["work"]); records=rt.load(work/"checkpoint.json")["records"]
        screening=self.root/"screening.json"
        rt.write(screening,[self.screened(records[5]["paper_id"], ["counterevidence"]), {"paper_id":records[0]["paper_id"],"decision":"excluded"}])
        raw=rt.load(file); raw["collection"]["screening_file"]=str(screening); rt.write(file,raw)
        pipe.acquire(file,"TEST_rank",action="rank")
        chosen=rt.load(work/"core_selection_proposal.json")["selected"]
        self.assertEqual(chosen[0]["paper_id"],records[5]["paper_id"])
        self.assertEqual(len(chosen), 1)
        self.assertNotIn(records[0]["paper_id"],{x["paper_id"] for x in chosen})
    def test_g5_family_as_field_does_not_pass_resource_dimension_gap(self):
        stage=rt.load_stage("05"); errors=[]
        concept={"name":"经济资本","kind":"resource_dimension","abstraction":"资源维度","unit":"个人","role":"X","dimension":"资源","timing":"事前"}
        audit={"baseline":[concept],"proposed":dict(concept,name="家庭",kind="field"),"overlap_search":"TEST全文搜索", "conclusion":"TEST待细化","reviewer":"TEST","reviewed_at":"2026-11-15","review_status":"verified"}
        stage.audit_concepts("C_TEST",{"primary_advance":"same_level_gap"},audit,errors)
        self.assertTrue(any("同层级遗漏" in x for x in errors))
        audit["proposed"]=dict(concept,name="家庭时间资源")
        errors=[]; stage.audit_concepts("C_TEST",{"primary_advance":"same_level_gap"},audit,errors)
        self.assertEqual(errors,[])
    def test_r_trigger_and_national_policy_connection_are_required(self):
        # Reuse the positive fixture, then remove evidence that distinguishes R from T.
        helper=fixtures.WorkflowTests(methodName="test_empty_joint_flow_is_needs_review_not_false_success")
        helper.setUp()
        try:
            up=helper.passed04(); inputs,annotation,path=helper.fixture05(up)
            annotation["candidates"][0]["trigger"]="R"
            annotation["writing_handoff"]["introduction"]["policy_evidence_ids"]=[]
            rt.write(path,annotation)
            stage=rt.load_stage("05"); result=stage.execute(stage.plan(inputs,helper.config()))
            errors=rt.load(Path(result["attempt_path"])/"gate_report.json")["errors"]
            self.assertTrue(any("R触发" in e for e in errors)); self.assertTrue(any("国家政策" in e for e in errors))
        finally: helper.doCleanups()

if __name__=="__main__":unittest.main(verbosity=2)
