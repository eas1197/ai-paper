"""ai-paper 5.0 offline contract tests; no network, model or Stata invocation."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from ai_paper5 import start, ingest, status, read

class Pipeline5Test(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.base=Path(self.t.name)
        self.work=self.base/"run"
        start(self.work,"live_5_0")
    def tearDown(self): self.t.cleanup()
    def add(self,stage,data):
        path=self.base/(stage+".json")
        path.write_text(json.dumps(data,ensure_ascii=False),encoding="utf-8")
        ingest(self.work,stage,path)
    def _prefix(self,method="secondary_interviews"):
        self.add("topic_candidates",{"candidates":[1,2],"selected":"x"})
        self.add("reality",{"phenomenon":"x","sources":[{"url":"https://example.org"}]})
        self.add("event_comparison",{"events":[{"id":"E1"},{"id":"E2"}]})
        self.add("explanation_exchange",{"expectation":"a","explanation":"b","challenge":"c","question":"d","review_mode":"same_model_adversarial"})
        self.add("literature_initial",{"articles":[{"title":"a","url":"https://ex.org/p1","read_status":"abstract"}]})
        self.add("preliminary_review",{"decision":"conditional"})
        self.add("research_design",{"method":method,"core_question":"What?"})
    def test_order_and_no_overwrite(self):
        with self.assertRaisesRegex(ValueError,"Next stage"):
            self.add("reality",{"phenomenon":"x","sources":["https://example.org"]})
        self.add("topic_candidates",{"candidates":[1,2],"selected":"x"})
        with self.assertRaisesRegex(ValueError,"already recorded"):
            self.add("topic_candidates",{"candidates":[1,2],"selected":"x"})
    def test_quant_skipping_stata_reject_false_claims(self):
        self._prefix("quantitative")
        self.add("literature_supplemental",{"articles":[]})
        self.add("final_review",{"decision":"pending","review_mode":"chat_role_play"})
        self.add("empirical_materials",{"materials":[]})
        self.add("analysis_matrix",{"dimensions":[{"id":"D1"}],"rows":[{"dimension_id":"D1"}]})
        with self.assertRaisesRegex(ValueError,"Stata"):
            self.add("writing_packet",{"method":"quantitative","sta_analysis_status":"passed"})
        self.add("writing_packet",{"method":"quantitative","sta_analysis_status":"not_executed"})
        self.assertEqual(status(self.work)["method"],"quantitative")
    def test_full_run_and_gates_not_forged(self):
        self._prefix()
        self.add("literature_supplemental",{"articles":[{"title":"b","url":"https://ex.org/p2","read_status":"abstract"}]})
        self.add("final_review",{"decision":"conditional","review_mode":"same_model_adversarial"})
        self.add("empirical_materials",{"materials":[{"id":"m","event_id":"E1","url":"https://ex.org","locator":"p1","status":"single_account"}]})
        self.add("analysis_matrix",{"dimensions":[{"id":"D1"}],"rows":[{"dimension_id":"D1","evidence":["m"]}]})
        self.add("writing_packet",{"method":"secondary_interviews","chapters":[1],"sources":{"m":1}})
        (self.base/"paper.md").write_text("## paper\nContent.",encoding="utf-8")
        (self.base/"claims.json").write_text('{"claims":[{"claim_id":"C1"}]}',encoding="utf-8")
        self.add("manuscript",{"manuscript":"paper.md","claims":"claims.json"})
        self.add("writing_review",{"reviewer_mode":"same_model_adversarial","decision":"conditional_pass","formal_g7_pass":True})
        s=status(self.work)
        self.assertTrue(s["technical_complete"])
        self.assertEqual(s["literature_deficit"],{"literature_initial":4,"literature_supplemental":4})
        self.assertFalse(read(self.work/"stages/14_writing_review.json")["formal_g7_pass"])
        self.assertEqual(s["scientific_acceptance"],"not_passed_without_genuine_independent_review")
    def test_duplicate_abstracts_rejected(self):
        self._prefix()
        with self.assertRaisesRegex(ValueError,"duplicates initial"):
            self.add("literature_supplemental",{"articles":[{"title":"same","url":"https://ex.org/p1","read_status":"abstract"}]})
    def test_stage_file_hash_tampering_detected(self):
        self.add("topic_candidates",{"candidates":[1,2],"selected":"x"})
        p=self.work/"stages/01_topic_candidates.json"
        p.write_text('{"malicious":"rewrite"}',encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"mutated"):
            status(self.work)

if __name__=="__main__":unittest.main()
