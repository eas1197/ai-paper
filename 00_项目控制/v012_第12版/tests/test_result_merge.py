"""C24 multi-executor merge fixtures. Original input bytes are preserved."""
from copy import deepcopy
import json
import unittest

import test_codex_receiving as native
from test_result_bundle_schema import source
import task_packet
import result_merge


class ResultMergeTest(unittest.TestCase):
    setUp = native.CodexReceivingTest.setUp
    make_packet = native.CodexReceivingTest.make_packet
    setup_ref = native.CodexReceivingTest.setup_ref
    raw = native.CodexReceivingTest.raw
    save = native.CodexReceivingTest.save
    expected = native.CodexReceivingTest.expected
    fixture = native.CodexReceivingTest.fixture
    sample = native.CodexReceivingTest.sample
    rebind = native.CodexReceivingTest.rebind

    def selection(self, bundle, relative):
        self.result_path = relative
        self.save(bundle)
        return {"result_path": relative, "expected_execution": self.expected(bundle)}

    def samples(self):
        native_bundle = self.sample()
        row = native_bundle["sources"][0]
        row.update(title="Education and family", publication="社会学研究",
                   authors=["Alice Zhang"], publication_date="2024", doi="10.1234/example")
        native_selection = self.selection(native_bundle, "fixture/native_result.json")
        self.result_path = "fixture/result.json"
        chat = self.fixture()
        chat["sources"] = [deepcopy(row)]
        chat_selection = self.selection(chat, "fixture/chat_result.json")
        self.result_path = "fixture/result.json"
        manual = self.fixture("manual")
        manual["sources"] = [deepcopy(row)]
        manual_selection = self.selection(manual, "fixture/manual_result.json")
        return [native_selection, chat_selection, manual_selection]

    def merge(self, selections):
        return result_merge.merge_result_bundles(selections, current_run_id="offline_fixture",
                                                 expected_reference=self.ref)

    def test_c24_same_source_preserves_three_executor_provenances(self):
        selections = self.samples()
        before = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
        index = self.merge(selections)
        self.assertEqual(index["candidate_group_count"], 1)
        members = index["groups"][0]["members"]
        self.assertEqual({m["origin"]["executor"] for m in members},
                         {"codex_cli","chat_native_web","manual"})
        self.assertEqual(len({m["origin"]["result_sha256"] for m in members}), 3)
        self.assertEqual({m["origin"]["original_source_id"] for m in members}, {"fixture-source"})
        self.assertFalse(index["formal_eligible"])
        self.assertEqual(before, {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()})
        output = result_merge.write_merge_index(index, current_run_id="offline_fixture",
                                                output="fixture/merged_index.json")
        self.assertTrue(output.is_file())
        with self.assertRaises(FileExistsError):
            result_merge.write_merge_index(index, current_run_id="offline_fixture",
                                           output="fixture/native_result.json")

    def test_c26_same_source_deduplicates_but_preserves_both_raw_receipt_sets(self):
        selections = self.samples()[:2]  # one Codex and one Chat result
        submitted = {
            "codex_cli": json.loads((self.work / selections[0]["result_path"]).read_text(encoding="utf-8")),
            "chat_native_web": json.loads((self.work / selections[1]["result_path"]).read_text(encoding="utf-8")),
        }
        before = {path: path.read_bytes() for path in self.work.rglob("*") if path.is_file()}

        index = self.merge(selections)

        self.assertEqual(index["candidate_group_count"], 1)
        members = index["groups"][0]["members"]
        self.assertEqual(len(members), 2)
        self.assertEqual({member["origin"]["executor"] for member in members},
                         {"codex_cli", "chat_native_web"})
        self.assertEqual({member["origin"]["original_source_id"] for member in members},
                         {"fixture-source"})
        self.assertEqual(len({member["origin"]["result_sha256"] for member in members}), 2)

        by_executor = {row["executor"]: row for row in index["original_results"]}
        self.assertEqual(set(by_executor), {"codex_cli", "chat_native_web"})
        for executor, original in submitted.items():
            receipt_refs = (original["provenance"]["record_refs"] if executor == "chat_native_web"
                            else [original["provenance"][key] for key in
                                  ("events", "response", "stderr", "prompt", "schema", "login", "command_record")])
            checked = {(item["path"], item["sha256"])
                       for item in by_executor[executor]["audit"]["checked_files"]}
            expected = {(item["path"], item["sha256"]) for item in receipt_refs}
            self.assertTrue(expected)
            self.assertTrue(expected <= checked)
            self.assertEqual(by_executor[executor]["provenance"], original["provenance"])
            self.assertEqual(by_executor[executor]["result_sha256"],
                             next(member["origin"]["result_sha256"] for member in members
                                  if member["origin"]["executor"] == executor))

        self.assertFalse(index["formal_eligible"])
        self.assertEqual(before, {path: path.read_bytes() for path in self.work.rglob("*") if path.is_file()})

    def test_c24_duplicate_or_cross_task_rejected(self):
        selections = self.samples()
        with self.assertRaisesRegex(ValueError,"Duplicate result file"):
            self.merge([selections[0], selections[0]])
        path = self.work / selections[1]["result_path"]
        bundle = json.loads(path.read_text(encoding="utf-8"))
        bundle["task_snapshot"]["task_id"] = "wrong-task"
        self.selection(bundle, selections[1]["result_path"])
        with self.assertRaisesRegex(ValueError,"selected task snapshot"):
            self.merge(selections)

    def test_c24_original_path_cannot_be_relabelled_as_another_executor(self):
        selections = self.samples()
        chat_path = self.work / selections[1]["result_path"]
        chat = json.loads(chat_path.read_text(encoding="utf-8"))
        manual_path = self.work / selections[2]["result_path"]
        manual = json.loads(manual_path.read_text(encoding="utf-8"))
        manual["provenance"]["original_files"] = chat["provenance"]["record_refs"]
        selections[2] = self.selection(manual, selections[2]["result_path"])
        with self.assertRaisesRegex(ValueError,"reused across executor"):
            self.merge(selections)


if __name__ == "__main__":
    unittest.main()
