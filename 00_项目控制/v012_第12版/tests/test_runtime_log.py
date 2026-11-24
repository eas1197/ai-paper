import argparse
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_paper5_strict as strict
import task_packet
from run_observation import observation
from runtime_log import record_command, attach_command_record


class RuntimeLogTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.work = self.root / "fixture"
        self.work.mkdir()
        self.state = {"run_id":"fixture","mode":"dev","status":"initial"}
        for name, value in (("run_manifest.json", {"run_id":"fixture"}),
                            ("staged_topic.json", self.state),
                            ("v5_native_calls.json", {"records":[]}),
                            ("reality.json", {"fixture":True})):
            strict.write(self.work/name,value)
        for mock in (patch.object(strict,"RUNS",self.root),
                     patch.object(task_packet.run_mode,"verified_run",return_value={"run_id":"fixture"})):
            mock.start()
            self.addCleanup(mock.stop)

    def test_i18_run_bound_record_fields_are_hash_bound_and_idempotent(self):
        args=argparse.Namespace(cmd="advance",run_id="fixture",model=None)
        runtime=observation("waiting_for_review")
        first=record_command(args,{},runtime,success=True)
        self.assertEqual(first,record_command(args,{},runtime,success=True))
        ref=first["record_ref"]
        raw=(self.work/ref["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),ref["sha256"])
        row=json.loads(raw)
        self.assertEqual(row["research_id"],"fixture")
        self.assertEqual(row["stage_id"],"initial")
        self.assertEqual(row["sources"][0]["sha256"],strict.sha(self.work/"reality.json"))
        self.assertEqual(row["budget"]["original_ledger_refs"][0]["path"],"v5_native_calls.json")
        self.assertIsNone(row["task_id"])
        self.assertIsNone(row["model_observed"])
        self.assertIsNone(row["budget"]["actual_consumption"])
        self.assertFalse(row["academic_approval_granted"])

    def test_i18_error_hash_and_no_external_path_or_raw_diagnostic(self):
        external=self.root/"external-secret.json"
        external.write_text('{"private":true}')
        args=argparse.Namespace(cmd="review",run_id="fixture",report=external)
        error="fixture private error"
        runtime=observation("failed",outcome_kind="technical_failure",error_text=error)
        ref=record_command(args,{},runtime,success=False)["record_ref"]
        raw=(self.work/ref["path"]).read_text()
        self.assertNotIn(error,raw)
        self.assertNotIn(str(external),raw)
        row=json.loads(raw)
        self.assertEqual(row["exception"]["raw_error_sha256"],hashlib.sha256(error.encode()).hexdigest())
        self.assertFalse(row["command_success"])
        self.assertEqual(row["inputs"],{})

    def test_i18_read_only_and_wrong_run_never_create_records(self):
        for args,expected in ((argparse.Namespace(cmd="status",run_id="fixture"),"read_only"),
                              (argparse.Namespace(cmd="advance",run_id="other"),"unbound_invalid_run"),
                              (argparse.Namespace(cmd="writer4"),"unbound_no_explicit_run")):
            result=attach_command_record(args,{},observation("blocked"),success=False)
            self.assertEqual(result["recording_status"],expected)
        self.assertFalse((self.work/"runtime_log").exists())
        self.assertFalse((self.root/"other").exists())


if __name__=="__main__":
    unittest.main()
