from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import importlib.util
import json
import sys
from tempfile import TemporaryDirectory
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

    def test_completed_call_reuses_only_matching_raw_success(self):
        with TemporaryDirectory() as directory:
            work=Path(directory)
            folder=work/"v5_native"/"research_exchange"/"attempt_001"
            folder.mkdir(parents=True)
            task="frozen researcher task"
            m.heritage.write(folder/"task.json",{"stage":"research_exchange","instruction":task})
            response={"initial_explanation":"A bounded explanation"}
            m.heritage.write(folder/"response.json",response)
            raw=folder/"events.jsonl"
            raw.write_text(json.dumps({"type":"thread.started","thread_id":"research-1"})+"\n",
                           encoding="utf-8")
            m.heritage.write(work/"v5_native_calls.json",{"records":[{
                "stage":"research_exchange","attempt":1,"status":"completed",
                "events_sha256":m.checksum(raw),
                "response_sha256":m.checksum(folder/"response.json"),
                "thread_id":"research-1"}]})
            with patch.object(m,"native_modules",
                              return_value=(None,None,lambda path:[],lambda url,trace:None)):
                result=m.completed_call(work,"research_exchange",task)
            self.assertIsNotNone(result)
            self.assertEqual(result[0],response)
            self.assertEqual(result[2],"research-1")

    def test_failed_critic_attempt_is_never_reused(self):
        with TemporaryDirectory() as directory:
            work=Path(directory)
            folder=work/"v5_native"/"critical_exchange"/"attempt_001"
            folder.mkdir(parents=True)
            task="saved critic task"
            m.heritage.write(folder/"task.json",{"stage":"critical_exchange","instruction":task})
            m.heritage.write(folder/"response.json",{"challenge":"incomplete"})
            raw=folder/"events.jsonl"
            raw.write_text(json.dumps({"type":"thread.started","thread_id":"failed-critic"})+"\n",
                           encoding="utf-8")
            m.heritage.write(work/"v5_native_calls.json",{"records":[{
                "stage":"critical_exchange","attempt":1,"status":"failed",
                "events_sha256":m.checksum(raw),
                "response_sha256":m.checksum(folder/"response.json"),
                "thread_id":"failed-critic"}]})
            self.assertIsNone(m.completed_call(work,"critical_exchange",task))

    def test_saved_critical_input_must_match_frozen_run(self):
        with TemporaryDirectory() as directory:
            work=Path(directory)/"sample"
            work.mkdir()
            reality={"phenomenon":"saved reality"}
            comparison={"run_id":"sample","reality_sha256":"reality-hash","event_count":2}
            m.heritage.write(work/"reality.json",reality)
            m.heritage.write(work/"event_comparison.json",comparison)
            m.heritage.write(work/"staged_topic.json",{"reality_sha256":"reality-hash"})
            content=("Independently challenge this explanation.\n"+
                     json.dumps(reality,ensure_ascii=False)+"\n"+
                     json.dumps(comparison,ensure_ascii=False)+"\n")
            (work/"critical_input.txt").write_text(content,encoding="utf-8")
            saved,source=m.saved_critical_input(work)
            self.assertEqual(saved,content)
            self.assertEqual(source,work/"critical_input.txt")
            m.heritage.write(work/"event_comparison.json",{"run_id":"sample","event_count":3})
            with self.assertRaisesRegex(ValueError,"does not match"):
                m.saved_critical_input(work)

    def test_explanation_exchange_resumes_research_and_dispatches_critic(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            run_id="sample"
            work=root/run_id
            work.mkdir()
            reality={"phenomenon":"saved reality"}
            comparison={"run_id":run_id,"reality_sha256":"reality-hash","event_count":2}
            m.heritage.write(work/"reality.json",reality)
            m.heritage.write(work/"event_comparison.json",comparison)
            m.heritage.write(work/"staged_topic.json",{"reality_sha256":"reality-hash"})
            saved=("Independently challenge the tentative explanation.\n"+
                   json.dumps(reality,ensure_ascii=False)+"\n"+
                   json.dumps(comparison,ensure_ascii=False)+"\n")
            (work/"critical_input.txt").write_text(saved,encoding="utf-8")

            prepared={"expectation":"E","observation":"O",
                      "initial_explanation":"I","candidate_question":"Q","search_focus":"S"}
            research_task=json.dumps(prepared,ensure_ascii=False)+(
                "\nRecord original explanation and what evidence would distinguish it.")
            researcher={"expectation":"E","observation":"O",
                        "initial_explanation":"I","candidate_question":"Q","search_focus":"S"}
            research_folder=work/"v5_native"/"research_exchange"/"attempt_001"
            research_folder.mkdir(parents=True)
            m.heritage.write(research_folder/"task.json",
                             {"stage":"research_exchange","instruction":research_task})
            m.heritage.write(research_folder/"response.json",researcher)
            research_events=research_folder/"events.jsonl"
            research_events.write_text(
                json.dumps({"type":"thread.started","thread_id":"research-1"})+"\n",
                encoding="utf-8")
            m.heritage.write(work/"v5_native_calls.json",{"records":[{
                "stage":"research_exchange","attempt":1,"status":"completed",
                "events_sha256":m.checksum(research_events),
                "response_sha256":m.checksum(research_folder/"response.json"),
                "thread_id":"research-1"}]})

            class FakeEngine:
                def __init__(self):
                    self.calls=[]
                def call(self,work,stage,task,**kwargs):
                    self.calls.append((stage,task))
                    folder=work/"v5_native"/stage/"attempt_001"
                    folder.mkdir(parents=True)
                    response={"challenge":"A competing mechanism remains possible."}
                    m.heritage.write(folder/"response.json",response)
                    (folder/"events.jsonl").write_text(
                        json.dumps({"type":"thread.started","thread_id":"critic-1"})+"\n",
                        encoding="utf-8")
                    return response,folder,"critic-1",[],lambda url,trace:None

            engine=FakeEngine()
            with patch.object(m.heritage,"RUNS",root), \
                 patch.object(m.heritage,"ROOT",root), \
                 patch.object(m.heritage,"doctor",return_value={}), \
                 patch.object(m.heritage,"state_of",
                              side_effect=[{"status":"explanation_exchange"},
                                           {"status":"issue_positioning"}]), \
                 patch.object(m.heritage,"original_command",
                              side_effect=lambda action,run_id,**kwargs:[action]), \
                 patch.object(m.heritage,"original_call",
                              side_effect=lambda cmd:json.dumps(prepared,ensure_ascii=False)
                              if cmd[0]=="prepare" else ""), \
                 patch.object(m,"native_modules",
                              return_value=(None,None,lambda path:[],lambda url,trace:None)):
                result=m.step(run_id,executor=engine)

            self.assertEqual(result["next"],"issue_positioning")
            self.assertEqual([stage for stage,_ in engine.calls],["critical_exchange"])
            self.assertIn("Independently challenge",engine.calls[0][1])
            self.assertIn("Current researcher's evidence-bound response",engine.calls[0][1])
            critic_folder=work/"v5_native"/"critical_exchange"/"attempt_001"
            receipt=m.heritage.read(critic_folder/"critical_receipt.json")
            payload=m.heritage.read(critic_folder/"exchange_payload.json")
            self.assertEqual(receipt["research_thread_id"],"research-1")
            self.assertEqual(receipt["critical_thread_id"],"critic-1")
            self.assertEqual(receipt["thread_separation"],"verified_by_distinct_thread_ids")
            self.assertEqual(payload["critical_receipt_path"],
                             "v5_native/critical_exchange/attempt_001/critical_receipt.json")
            self.assertTrue((critic_folder/"events.jsonl").is_file())
            self.assertTrue((critic_folder/"response.json").is_file())


    def test_main_refuses_to_reinitialize_saved_handoff_checkpoint(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            runs=root/"runs_dev"
            saved=root/"handoff_runs"/"sample"
            saved.mkdir(parents=True)
            m.heritage.write(saved/"staged_topic.json",{"run_id":"sample","status":"explanation_exchange"})
            output=StringIO()
            with patch.object(m.heritage,"ROOT",root), \
                 patch.object(m.heritage,"RUNS",runs), \
                 patch.object(m.heritage,"doctor",return_value={}), \
                 patch.object(m.heritage,"original_call") as original:
                with redirect_stdout(output):
                    result=m.main(["--run-id","sample"])
            self.assertEqual(result,2)
            self.assertFalse((runs/"sample").exists())
            original.assert_not_called()
            self.assertIn("Refusing to initialize a fresh run",output.getvalue())


if __name__=="__main__":main()
