"""C03: original run identity checks, isolated offline fixtures."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import task_packet
from test_task_packet_schema import packet


class TaskOwnershipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for module in (task_packet.heritage, task_packet.run_mode):
            patcher = patch.object(module, "RUNS", self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        for run_id in ("offline_fixture", "other_fixture"):
            work = task_packet.run_mode.start(run_id, "Offline test only")
            (work / "staged_topic.json").write_text(
                json.dumps({"run_id": run_id, "mode": "dev", "status": "initial"}),
                encoding="utf-8")

    def test_current_original_research_matches(self):
        self.assertEqual(task_packet.validate_packet(packet(), current_run_id="offline_fixture"),
                         self.root / "offline_fixture")

    def test_cross_research_and_missing_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "different research ID"):
            task_packet.validate_packet(packet(), current_run_id="other_fixture")
        sample = packet()
        del sample["research_id"]
        with self.assertRaises(ValidationError):
            task_packet.validate_packet(sample, current_run_id="offline_fixture")

    def test_missing_run_and_invalid_current_identity_rejected(self):
        for run_id in ("../outside", "", None, 12):
            with self.subTest(run_id=run_id), self.assertRaises(ValueError):
                task_packet.validate_packet(packet(), current_run_id=run_id)
        with self.assertRaises(FileNotFoundError):
            task_packet.validate_packet(dict(packet(), research_id="missing"),
                                        current_run_id="missing")

    def test_original_manifest_and_state_identity_must_agree(self):
        work = self.root / "offline_fixture"
        state = work / "staged_topic.json"
        original = state.read_text(encoding="utf-8")
        state.write_text(json.dumps({"run_id": "other_fixture", "mode": "dev"}), encoding="utf-8")
        with self.assertRaises(ValueError):
            task_packet.validate_packet(packet(), current_run_id="offline_fixture")
        state.write_text(original, encoding="utf-8")
        manifest = work / "run_manifest.json"
        changed = json.loads(manifest.read_text(encoding="utf-8"))
        changed["run_id"] = "other_fixture"
        manifest.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(ValueError):
            task_packet.validate_packet(packet(), current_run_id="offline_fixture")


if __name__ == "__main__":
    unittest.main()
