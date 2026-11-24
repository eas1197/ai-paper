import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from archive_provenance import verify_archive, load_manifest


class ArchiveProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        folder=self.root/"fixture"
        folder.mkdir()
        self.path=folder/"run_manifest.json"
        self.path.write_text('{"run_id":"fixture"}')
        self.digest=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.manifest={"archive_scope":"existing_records_only","new_execution_proven":False,
            "runs":[{"run_id":"fixture","root":"local/runs_dev/fixture","files":1,"type":"historical"}],
            "files":{"fixture/run_manifest.json":self.digest},"omitted":[]}

    def test_history_is_archive_only_and_inventory_bound(self):
        result=verify_archive(self.root,self.manifest)
        self.assertFalse(result["new_execution_proven"])
        self.assertFalse(result["formal_eligible"])
        self.assertEqual(result["archived_files"],1)
        (self.root/"fixture/extra.md").write_text("not indexed")
        with self.assertRaisesRegex(ValueError,"inventory"):
            verify_archive(self.root,self.manifest)

    def test_count_and_run_identity_and_omission_mismatch(self):
        for mutate in ("count","root","omission","run"):
            with self.subTest(mutate=mutate):
                m=copy.deepcopy(self.manifest)
                if mutate=="count": m["runs"][0]["files"]=2
                elif mutate=="root": m["runs"][0]["root"]="local/runs_dev/other"
                elif mutate=="omission": m["omitted"]=[["fixture","run_manifest.json",self.digest,"local"]]
                else: m["files"]={"other/run_manifest.json":self.digest}
                with self.assertRaises(ValueError):
                    verify_archive(self.root,m)

    def test_new_snapshot_requires_independently_indexed_source_run(self):
        m=copy.deepcopy(self.manifest)
        m["runs"][0].update(type="archived_run_snapshot",source_run_id="other")
        with self.assertRaisesRegex(ValueError,"source run binding"):
            verify_archive(self.root,m)
        m["runs"][0].update(source_run_id="fixture",source_manifest={
            "path":"fixture/run_manifest.json","sha256":self.digest})
        self.assertFalse(verify_archive(self.root,m)["new_execution_proven"])
        m["runs"][0]["new_execution_proven"]=True
        with self.assertRaisesRegex(ValueError,"cannot assert"):
            verify_archive(self.root,m)

    def test_tamper_and_duplicate_json_keys(self):
        self.path.write_text('{"run_id":"other"}')
        with self.assertRaisesRegex(ValueError,"bytes"):
            verify_archive(self.root,self.manifest)
        manifest_path=self.root/"manifest.json"
        manifest_path.write_text('{"files":{},"files":{}}')
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            load_manifest(manifest_path)


if __name__=="__main__":
    unittest.main()
