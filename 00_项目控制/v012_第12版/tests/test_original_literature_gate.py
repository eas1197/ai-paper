"""C21 actual original receiver runs against an explicitly synthetic fixture."""
import json
import unittest
from unittest.mock import patch
from pathlib import Path

import test_result_bundle_binding as binding
from test_result_bundle_schema import result, source, search_action
import task_packet
import original_literature_gate as gate


class OriginalLiteratureGateTest(unittest.TestCase):
    setUp = binding.ResultBindingTest.setUp
    make_packet = binding.ResultBindingTest.make_packet
    raw = binding.ResultBindingTest.raw
    save = binding.ResultBindingTest.save
    expected = binding.ResultBindingTest.expected
    fixture = binding.ResultBindingTest.fixture

    def setup_ref(self):
        self.work = self.root / "offline_fixture"
        staged, _, _ = gate._original()
        state = task_packet.heritage.state_of("offline_fixture")
        state.update(status="initial", policy_sha256=staged.digest(staged.POLICY))
        task_packet.heritage.write(self.work/"staged_topic.json", state)
        self.journals = staged.POLICY["journals"]
        self.ref = task_packet.freeze_packet(self.make_packet(
            task_id="original_v3_literature_initial",
            source_scope={"journals": self.journals, "policy_refs":[]},
            quantity_budget={"target":staged.POLICY["dev"]["initial"]}),
            current_run_id="offline_fixture")
        self.result_path = "fixture/result.json"

    def sample(self):
        self.setup_ref()
        staged, _, _ = gate._original()
        from codex_literature import observation, group, ENGINE
        folder = "initial/batch_001/"
        base = "/host/offline_fixture/"+folder
        url = "https://example.org/abstract"
        paper = {"title":"研究作者选取的论文题目","journal":"社会","authors":["张甲"],
                 "year":2016,"doi":"10.1234/demo","metadata_url":url,"abstract_url":url,
                 "abstract_locator":"摘要","abstract_excerpt":"用来定位的一小段引文",
                 "abstract_summary":"本文比较不同职业教育和普通高中的学生在学校学习后获得的技能与职业机会，并说明样本和分析设计以及结果的适用范围。",
                 "relevance":"direct","relevance_reason":"分流后的两条教育路径与机会比较"}
        trace = [{"type":"web_search","id":"open-1","action":{"type":"open_page","url":url},
                  "results":[{"url":url,"snippet":paper["abstract_excerpt"]}]}]
        obs = observation(paper, trace, self.journals, "batch_001", 1)
        articles, conflicts = group([obs])
        events = [{"type":"thread.started","thread_id":"fixture-thread"},
                  {"type":"item.completed","item":trace[0]}]
        bundle = dict(result("codex_cli"),task_snapshot=self.ref,
                      execution_status="completed",failure_reasons=[])
        p = bundle["provenance"]
        p.update(command=["codex","-a","never","--search","exec","--ignore-user-config",
                          "-s","read-only","--ephemeral","--skip-git-repo-check","-C",base.rstrip("/"),
                          "--json","--output-schema",base+"schema.json","-o",base+"response.json","-"],
                 thread_id="fixture-thread",exit_code=0,missing_fields=[],
                 events=self.raw(folder+"events.jsonl",("\n".join(json.dumps(e) for e in events)+"\n").encode()),
                 response=self.raw(folder+"response.json",json.dumps({"papers":[paper],"unverified":[],"search_notes":[]}).encode()),
                 stderr=self.raw(folder+"stderr.log",b""),prompt=self.raw(folder+"prompt.txt",b"Offline fixture"),
                 schema=self.raw(folder+"schema.json",b"{}"),
                 login=self.raw(folder+"login_diagnostics.json",b'{"chatgpt":true,"exit_code":0,"stdout":"Logged in using ChatGPT","stderr":""}'))
        self.raw(folder+"login_status.json",b'{"chatgpt":true}')
        entry = {"batch":"batch_001","status":"completed","event_sha256":p["events"]["sha256"],
                 "response_sha256":p["response"]["sha256"],"notes":[],"search_events":1}
        manifest = task_packet.run_mode.verified_run(self.work)
        config = {"topic_search_phase":"initial","target":5,"journals":self.journals,
                  "run_mode":"dev","workload_sha256":manifest["workload_sha256"]}
        original = {"engine":ENGINE,"schema_version":2,"collection_id":"fixture-collection",
                    "theme":"Offline test only","journals":self.journals,"target":5,"count":1,
                    "batches":[entry],"articles":articles,"conflicts":conflicts,
                    "status":"incomplete","run_mode":"dev","workload_sha256":manifest["workload_sha256"]}
        task_packet.heritage.write(self.work/"initial/checkpoint.json",{
            "collection_id":"fixture-collection","observations":[obs],"config":config,"batches":[entry]})
        task_packet.heritage.write(self.work/"initial/abstract_collection.json",original)
        bundle["sources"] = [dict(source(), original_url=url,metadata_url=url,abstract_url=url,
            title=paper["title"],authors=paper["authors"],publication=paper["journal"],
            publication_date="2016",doi=paper["doi"],abstract_locator=paper["abstract_locator"],
            excerpt=paper["abstract_excerpt"],paraphrase=obs["abstract_summary"],
            relevance_reason=paper["relevance_reason"])]
        bundle["search_actions"]=[search_action()]
        record = {"task_snapshot":self.ref,"argv":p["command"],"exit_code":p["exit_code"],
                  "thread_id":p["thread_id"],"files":{key:p[key] for key in
                    ("events","response","stderr","prompt","schema","login")}}
        p["command_record"]=self.raw(folder+"invocation.json",json.dumps(record).encode())
        self.save(bundle)
        return bundle

    def receive(self, bundle):
        return gate.audit_unified_literature(self.result_path,current_run_id="offline_fixture",
            expected_reference=self.ref,expected_execution=self.expected(bundle))

    def test_c21_original_receiver_rebuilds_and_does_not_advance(self):
        bundle=self.sample()
        report=self.receive(bundle)
        self.assertEqual(report["original_verified_rows"],1)
        self.assertEqual(len(report["original_abstract_eligible_ids"]),1)
        self.assertFalse(report["formal_eligible"])
        self.assertFalse(report["stage_advanced"])
        self.assertEqual(task_packet.heritage.state_of("offline_fixture")["status"],"initial")
        self.assertTrue((self.work/"initial/literature_matrix.json").exists())

    def test_c30_unified_result_delegates_to_original_v009_receipt_without_advancing(self):
        bundle = self.sample()
        staged, _, _ = gate._original()
        with patch.object(staged, "receipt", wraps=staged.receipt) as original_receipt:
            report = self.receive(bundle)
        original_receipt.assert_called_once_with(self.work / "initial", self.journals)
        self.assertEqual(report["original_gate_status"],
                         "original_abstract_receipt_matched_pending_stage_review")
        self.assertEqual(report["original_verified_rows"], 1)
        self.assertEqual(len(report["original_abstract_eligible_ids"]), 1)
        self.assertFalse(report["formal_eligible"])
        self.assertFalse(report["stage_advanced"])
        self.assertEqual(task_packet.heritage.state_of("offline_fixture")["status"], "initial")
        self.assertTrue((self.work / "initial/literature_matrix.json").is_file())

    def test_c21_chat_and_fabricated_normalized_paper_never_enter_original_gate(self):
        bundle=self.sample()
        bundle["sources"][0]["title"]="Different normalized claim"
        self.save(bundle)
        report=self.receive(bundle)
        self.assertFalse(report["original_abstract_eligible_ids"])
        chat=self.fixture()
        report=self.receive(chat)
        self.assertEqual(report["original_gate_status"],"pending_original_native_receipt")
        self.assertIsNone(report["original_verified_rows"])

    def test_c27_chat_cannot_claim_native_cli_receipt_or_executor(self):
        self.setup_ref()
        chat = self.fixture()
        report = self.receive(chat)
        self.assertEqual(report["original_gate_status"], "pending_original_native_receipt")
        self.assertFalse(report["native_cli_receipt"])
        self.assertFalse(report["original_abstract_eligible_ids"])
        self.assertIsNone(report["original_verified_rows"])
        self.assertFalse(report["stage_advanced"])

        # A Chat payload cannot add a self-asserted native receipt field.
        chat["native_cli_receipt"] = True
        self.save(chat)
        with self.assertRaisesRegex(ValueError, "Invalid result envelope"):
            self.receive(chat)

        # Nor can it relabel a Chat provenance block as a Codex executor.
        chat.pop("native_cli_receipt")
        chat["executor"] = "codex_cli"
        self.save(chat)
        with self.assertRaisesRegex(ValueError, "Invalid result envelope"):
            self.receive(chat)
        self.assertFalse((self.work / "initial/literature_matrix.json").exists())
        self.assertEqual(task_packet.heritage.state_of("offline_fixture")["status"], "initial")

    def test_c21_original_scope_and_budget_remain_authoritative(self):
        bundle=self.sample()
        path=self.work/"initial/abstract_collection.json"
        original=task_packet.heritage.read(path)
        original["status"]="experimental_budget_exceeded"
        task_packet.heritage.write(path,original)
        self.assertEqual(self.receive(bundle)["original_gate_status"],"blocked_original_budget")
        original["status"]="incomplete"
        original["target"]=1
        task_packet.heritage.write(path,original)
        with self.assertRaisesRegex(ValueError,"target or workload"):
            self.receive(bundle)

    def rebind_invocation(self, bundle):
        p=bundle["provenance"]
        record={"task_snapshot":self.ref,"argv":p["command"],"exit_code":p["exit_code"],
                "thread_id":p["thread_id"],"files":{key:p.get(key) for key in
                    ("events","response","stderr","prompt","schema","login")}}
        p["command_record"]=self.raw("initial/batch_001/invocation.json",json.dumps(record).encode())
        self.save(bundle)

    def test_c29_missing_sources_or_unlocatable_abstract_stay_pending(self):
        # An otherwise well-formed CLI run with no normalized source rows is not a receipt.
        bundle = self.sample()
        bundle["sources"] = []
        self.rebind_invocation(bundle)
        report = self.receive(bundle)
        self.assertFalse(report["native_cli_receipt"])
        self.assertEqual(report["original_gate_status"], "pending_original_native_receipt")
        self.assertIsNone(report["original_verified_rows"])
        self.assertFalse(report["original_abstract_eligible_ids"])
        self.assertFalse(report["stage_advanced"])

        # A CLI event may exist, but missing locator/excerpt cannot match the original
        # v009 observation and therefore cannot create an eligible abstract row.
        for field in ("abstract_locator", "excerpt"):
            bundle = self.sample()
            bundle["sources"][0][field] = None
            self.rebind_invocation(bundle)
            report = self.receive(bundle)
            self.assertTrue(report["native_cli_receipt"])
            self.assertEqual(report["original_gate_status"], "pending_unmatched_original_observations")
            self.assertFalse(report["original_abstract_eligible_ids"])
            self.assertEqual(report["unmatched_source_ids"], ["fixture-source"])
            self.assertEqual(report["original_verified_rows"], 1)
            self.assertFalse(report["formal_eligible"])
            self.assertFalse(report["stage_advanced"])
            self.assertEqual(task_packet.heritage.state_of("offline_fixture")["status"], "initial")

    def test_c23_missing_event_reference_or_log_cannot_enter_original_gate(self):
        bundle=self.sample()
        p=bundle["provenance"]
        saved=p["events"]
        p["events"]=None
        p.pop("command_record")
        self.save(bundle)
        report=self.receive(bundle)
        self.assertFalse(report["native_cli_receipt"])
        self.assertFalse(report["original_abstract_eligible_ids"])
        self.assertIsNone(report["original_verified_rows"])
        self.assertFalse((self.work/"initial/literature_matrix.json").exists())
        p["events"]=saved
        self.rebind_invocation(bundle)
        (self.work/saved["path"]).unlink()
        with self.assertRaisesRegex(ValueError,"Missing or out-of-namespace"):
            self.receive(bundle)

    def test_c23_thread_without_web_events_and_wrong_source_id_pending(self):
        bundle=self.sample()
        p=bundle["provenance"]
        old=p["events"]
        raw=(self.work/old["path"]).read_bytes()
        p["events"]=self.raw(old["path"],b'{"type":"thread.started","thread_id":"fixture-thread"}\n')
        self.rebind_invocation(bundle)
        report=self.receive(bundle)
        self.assertEqual(report["native_event_count"],0)
        self.assertFalse(report["native_cli_receipt"])
        self.assertIsNone(report["original_verified_rows"])
        p["events"]=self.raw(old["path"],raw)
        bundle["sources"][0]["action_ids"]=["nonexistent-event"]
        self.rebind_invocation(bundle)
        report=self.receive(bundle)
        self.assertFalse(report["native_cli_receipt"])
        self.assertFalse(report["original_abstract_eligible_ids"])

    def test_c28_hand_filled_cli_actions_without_native_web_events_stay_pending(self):
        bundle = self.sample()
        p = bundle["provenance"]
        # Keep the submitted normalized search action, source action_ids, successful
        # login, argv and zero exit code; only the original event stream lacks web events.
        p["events"] = self.raw(
            "initial/batch_001/events.jsonl",
            b'{"type":"thread.started","thread_id":"fixture-thread"}\n')
        self.rebind_invocation(bundle)
        report = self.receive(bundle)
        self.assertTrue(report["command_record_matched"])
        self.assertEqual(report["native_event_count"], 0)
        self.assertFalse(report["native_cli_receipt"])
        self.assertEqual(report["acceptance_status"], "pending_candidate")
        self.assertEqual(report["original_gate_status"], "pending_original_native_receipt")
        self.assertFalse(report["original_abstract_eligible_ids"])
        self.assertIsNone(report["original_verified_rows"])
        self.assertFalse(report["stage_advanced"])
        self.assertFalse((self.work / "initial/literature_matrix.json").exists())
        self.assertEqual(task_packet.heritage.state_of("offline_fixture")["status"], "initial")

        # A manually supplied pass flag is not part of the result schema.
        bundle["native_cli_receipt"] = True
        self.save(bundle)
        with self.assertRaisesRegex(ValueError, "Invalid result envelope"):
            self.receive(bundle)

    def test_c23_failed_execution_and_self_asserted_receipt_rejected(self):
        bundle=self.sample()
        bundle.update(execution_status="failed",execution_issues=[
            {"code":"timeout","scope":"run","target_id":None,"detail":"Fixture failed","original_status":"failed"}])
        self.save(bundle)
        report=self.receive(bundle)
        self.assertEqual(report["acceptance_status"],"rejected")
        self.assertFalse(report["native_cli_receipt"])
        self.assertIsNone(report["original_verified_rows"])
        bundle["native_cli_receipt"]=True
        self.save(bundle)
        with self.assertRaisesRegex(ValueError,"Invalid result envelope"):
            self.receive(bundle)


if __name__=="__main__":
    unittest.main()
