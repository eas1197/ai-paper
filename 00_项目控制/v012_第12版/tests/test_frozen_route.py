"""E14: actual original freeze payload and post-freeze method routing, offline fixtures."""
import shutil
import unittest
import uuid
import ai_paper5_strict as strict
import task_packet


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

    def test_changed_freeze_is_rejected(self):
        self.freeze("quantitative")
        path=self.work/"s08_topic.json"
        frozen=strict.read(path)
        frozen["research_method"]["path"]="online_qualitative"
        strict.write(path,frozen)
        with self.assertRaisesRegex(RuntimeError,"frozen payload differs"):
            strict.status(self.run_id)


if __name__=="__main__": unittest.main()
