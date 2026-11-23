from pathlib import Path
import importlib.util
import sys
from unittest import TestCase,main
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]/"tools"
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("autopilot_v3",HERE/"autopilot_v3.py")
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

class StrictWakeTests(TestCase):
    def test_research_stages_never_replace_original_search(self):
        with patch.object(m.heritage,"doctor",return_value={}):
            with patch.object(m.heritage,"state_of",return_value={"status":"initial"}):
                with patch.object(m.heritage,"status",return_value={"action":"original_native_literature_search"}) as f:
                    self.assertEqual(m.step("sample")["action"],"original_native_literature_search")
                    self.assertTrue(f.call_args.kwargs["progress"])

    def test_critical_source_is_real_separate_session(self):
        self.assertEqual(set(m.SCHEMAS["research_exchange"]["required"]),
                         {"expectation","observation","initial_explanation","candidate_question","search_focus"})
        self.assertEqual(set(m.SCHEMAS["critical_exchange"]["required"]),{"challenge"})

    def test_source_proof_rejects_unseen_website(self):
        with self.assertRaisesRegex(ValueError,"not bound"):
            m.source_proof({"sources":[{"url":"https://example.org/source"}]},[],
                           lambda url,trace:None)

    def test_model_quota_comes_from_original_profile(self):
        self.assertTrue((m.heritage.CONTROL/"v007_第7版/dev_profile.json").is_file())

if __name__=="__main__":main()
