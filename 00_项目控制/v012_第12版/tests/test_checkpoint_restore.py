import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from checkpoint_restore import ROOT, RUN_ID, restore


class CheckpointRestoreTests(unittest.TestCase):
    def test_real_archives_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            initial = restore("K03", base / "initial")
            latest = restore("K06", base / "latest")
            self.assertEqual((initial["original_status"], initial["file_count"]), ("reality", 3))
            self.assertEqual((latest["original_status"], latest["file_count"]), ("explanation_exchange", 6))
            work = Path(latest["workspace"])
            self.assertFalse(list(work.rglob("*.lock")))
            report, = work.glob("submitted_stage_reports/reality/*.bin")
            self.assertEqual(hashlib.sha256(report.read_bytes()).hexdigest(), report.stem)
            self.assertEqual(report.read_bytes(), (work / "reality.json").read_bytes())
            original_state = (work / "staged_topic.json").read_bytes()
            with self.assertRaises(FileExistsError):
                restore("K03", base / "latest")
            self.assertEqual((work / "staged_topic.json").read_bytes(), original_state)

    def test_corrupt_initial_state_cannot_be_hidden_by_increment(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            archive = base / "archive"
            source = ROOT / "handoff_runs"
            shutil.copytree(source / RUN_ID, archive / RUN_ID)
            shutil.copyfile(source / "manifest.json", archive / "manifest.json")
            (archive / RUN_ID / "staged_topic.json").write_bytes(b"corrupt")
            destination = base / "restore"
            with self.assertRaisesRegex(ValueError, "Archive hash mismatch"):
                restore("K06", destination, archive_root=archive)
            self.assertFalse(destination.exists())
