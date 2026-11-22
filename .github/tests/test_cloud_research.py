"""Offline safety and continuity tests for GitHub Actions topic state."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

HERE = Path(__file__).resolve().parents[1] / "scripts/cloud_research.py"
spec = importlib.util.spec_from_file_location("cloud_research", HERE)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


class PersistentRunTests(unittest.TestCase):
    def test_round_trip_and_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            runs = temp / "runs"
            work = runs / "topic001"
            work.mkdir(parents=True)
            (work / "run_manifest.json").write_text('{"run_id":"topic001"}', encoding="utf-8")
            (work / "staged_topic.json").write_text('{"run_id":"topic001","status":"reality"}', encoding="utf-8")
            (work / "cloud_run_status.json").write_text('{"formal_eligible":false}', encoding="utf-8")
            (work / "raw_interview.txt").write_text("NEVER UPLOAD", encoding="utf-8")
            with patch.object(subject, "RUNS", runs):
                subject.store(SimpleNamespace(run_id="topic001", store=str(temp / "state")))
                self.assertFalse((temp / "state/cloud_runs/topic001/raw_interview.txt").exists())
                manifest = json.loads((temp / "state/cloud_runs/topic001/snapshot_manifest.json").read_text())
                self.assertEqual(set(manifest["files"]),
                                 {"run_manifest.json", "staged_topic.json", "cloud_run_status.json"})
                import shutil
                shutil.rmtree(work)
                subject.restore(SimpleNamespace(run_id="topic001", store=str(temp / "state")))
                self.assertEqual(json.loads((work / "staged_topic.json").read_text())["status"], "reality")
                with self.assertRaisesRegex(ValueError, "nonempty"):
                    subject.restore(SimpleNamespace(run_id="topic001", store=str(temp / "state")))

    def test_reject_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            runs = temp / "runs"
            work = runs / "topic002"
            work.mkdir(parents=True)
            (work / "run_manifest.json").write_text('{"secret":"unsafe"}', encoding="utf-8")
            with patch.object(subject, "RUNS", runs):
                with self.assertRaisesRegex(ValueError, "secret"):
                    subject.store(SimpleNamespace(run_id="topic002", store=str(temp / "state")))

    def test_manifest_integrity_rejects_modified_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder)
            runs = temp / "runs"
            work = runs / "topic003"
            work.mkdir(parents=True)
            (work / "run_manifest.json").write_text('{"run_id":"topic003"}', encoding="utf-8")
            with patch.object(subject, "RUNS", runs):
                subject.store(SimpleNamespace(run_id="topic003", store=str(temp / "state")))
                import shutil
                shutil.rmtree(work)
                saved = temp / "state/cloud_runs/topic003/run_manifest.json"
                saved.write_text('{"run_id":"changed"}', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "checksum"):
                    subject.restore(SimpleNamespace(run_id="topic003", store=str(temp / "state")))


if __name__ == "__main__":
    unittest.main()
