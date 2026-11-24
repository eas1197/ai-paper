"""I10: append-only history for resumable outputs; original evidence remains read-only."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / "00_项目控制/v012_第12版/tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(ROOT / "00_项目控制/v009_第9版/tools"))
sys.path.insert(0, str(ROOT / "07_三稿独立写作/v016_第16版/tools"))
import resume_writing
import ai_writer4


class ArtifactHistoryTest(unittest.TestCase):
    def test_i10_resume_and_writer_append_prior_versions_without_touching_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "original_source.txt"
            review = root / "original_independent_review.json"
            manuscript = root / "historical_manuscript_v1.md"
            source.write_bytes(b"original source bytes")
            review.write_bytes(b'{"decision":"revise","original":true}\n')
            manuscript.write_bytes("历史稿件第一版".encode("utf-8"))
            protected = {p: p.read_bytes() for p in (source, review, manuscript)}

            resume_output = root / "autonomous_writing/revision_preflight.json"
            resume_writing.write(resume_output, {"version": 1, "items": ["old"]})
            old_resume = resume_output.read_bytes()
            resume_writing.write(resume_output, {"version": 2, "items": ["new"]})
            archive = resume_output.parent / "history" / resume_output.name / (__import__("hashlib").sha256(old_resume).hexdigest() + ".bin")
            self.assertEqual(archive.read_bytes(), old_resume)
            current_resume = resume_output.read_bytes()
            resume_writing.write(resume_output, {"version": 2, "items": ["new"]})
            self.assertEqual(resume_output.read_bytes(), current_resume)
            self.assertEqual(len(list((resume_output.parent / "history" / resume_output.name).glob("*.bin"))), 1)

            writer_output = root / "writer/writing_review_request.json"
            ai_writer4.save(writer_output, {"status": "first review request"})
            old_writer = writer_output.read_bytes()
            ai_writer4.save(writer_output, {"status": "second review request"})
            writer_archive = writer_output.parent / "history" / writer_output.name / (__import__("hashlib").sha256(old_writer).hexdigest() + ".bin")
            self.assertEqual(writer_archive.read_bytes(), old_writer)
            self.assertEqual(json.loads(writer_output.read_text(encoding="utf-8"))["status"], "second review request")
            self.assertEqual({p: p.read_bytes() for p in protected}, protected)

    def test_i10_changed_plan_gets_new_directory_and_exact_plan_reuses_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            area = Path(tmp)
            old = {"core_question": "old"}
            new = {"core_question": "new"}
            first = resume_writing.plan_output(area, 0, old)
            first.mkdir()
            (first / "plan_input.json").write_text(json.dumps(old), encoding="utf-8")
            second = resume_writing.plan_output(area, 0, new)
            self.assertNotEqual(first, second)
            self.assertTrue(second.name.startswith("draft_0_"))
            self.assertFalse(second.exists())
            self.assertEqual(resume_writing.plan_output(area, 0, new), second)
            self.assertEqual(json.loads((first / "plan_input.json").read_text()), old)


if __name__ == "__main__":
    unittest.main()
