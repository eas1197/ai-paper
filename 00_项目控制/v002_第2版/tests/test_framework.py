"""只检验实际工具与存储约束，不替代研究验收。所有业务样本均为内存TEST夹具。"""
import importlib.util
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools/project.py"
spec = importlib.util.spec_from_file_location("project", TOOL)
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)


class FrameworkTests(unittest.TestCase):
    def test_registry_cycle_and_missing_dependency_are_rejected(self):
        with self.assertRaises(ValueError):
            project.ordered_modules({"modules": [
                {"module_id": "a", "depends_on": ["b"]},
                {"module_id": "b", "depends_on": ["a"]}]})
        with self.assertRaises(ValueError):
            project.ordered_modules({"modules": [{"module_id": "a", "depends_on": ["missing"]}]})

    def test_escape_path_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                project.contained(tmp, "../outside")

    def test_init_refuses_overwrite_and_leaves_submission_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "framework"
            shutil.copytree(project.ROOT, root, ignore=shutil.ignore_patterns("runs", "__pycache__"))
            (root / project.CONTROL.relative_to(project.ROOT) / "runs").mkdir()
            created = project.init_run("TEST_run", "教育", "教育与阶层", root=root)
            manifest_path = Path(created["path"]) / "run_manifest.json"
            original = manifest_path.read_bytes()
            manifest = json.loads(original)
            self.assertFalse(manifest["stage_executor_implemented"])
            self.assertEqual(next(s for s in manifest["stages"] if s["stage_id"] == "09")["status"], "skipped")
            self.assertFalse((manifest_path.parent / "stage_09").exists())
            self.assertEqual(manifest["writing_mode"], "single")
            self.assertEqual(manifest["draft_labels"], ["A"])
            self.assertEqual({s["stage_id"] for s in manifest["stages"]}, {"04", "05", "06", "07", "08", "09"})
            self.assertEqual(next(s for s in manifest["stages"] if s["stage_id"] == "08")["status"], "skipped")
            self.assertFalse((manifest_path.parent / "stage_08").exists())
            self.assertEqual(sorted(p.name for p in (manifest_path.parent / "stage_07/attempt_001/drafts").iterdir()), ["A"])
            self.assertEqual({b["module_id"] for b in manifest["shared_resource_bindings"]}, {"01", "02", "03"})
            self.assertTrue(all(b["status"] == "not_built" for b in manifest["shared_resource_bindings"]))
            self.assertTrue(all(len(f["sha256"]) == 64 for f in manifest["locked_files"]))
            with self.assertRaises(FileExistsError):
                project.init_run("TEST_run", "其他主题", "其他议题", root=root)
            self.assertEqual(original, manifest_path.read_bytes())
            with self.assertRaises(ValueError):
                project.init_run("../escape", "主题", "议题", root=root)

    def test_three_mode_creates_three_drafts_and_enables_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "framework"
            shutil.copytree(project.ROOT, root, ignore=shutil.ignore_patterns("runs", "__pycache__"))
            (root / project.CONTROL.relative_to(project.ROOT) / "runs").mkdir()
            created = project.init_run("TEST_three", "教育", "教育与阶层", root=root,
                                       writing_mode="three_plus_review")
            work = Path(created["path"])
            manifest = json.loads((work / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["config_snapshot"]["writing"]["mode"], "three_plus_review")
            self.assertEqual(manifest["draft_labels"], ["A", "B", "C"])
            self.assertEqual(sorted(p.name for p in (work / "stage_07/attempt_001/drafts").iterdir()), ["A", "B", "C"])
            self.assertTrue((work / "stage_08/attempt_001").is_dir())
            self.assertEqual(next(s for s in manifest["stages"] if s["stage_id"] == "08")["status"], "planned")
            self.assertIn("08", next(s for s in manifest["stages"] if s["stage_id"] == "09")["depends_on"])
            self.assertFalse(any((work / f"stage_{mid}").exists() for mid in ["01", "02", "03"]))

    def test_plan_routes_review_and_submission_by_mode(self):
        single = {m["module_id"]: m for m in project.plan(writing_mode="single")}
        three = {m["module_id"]: m for m in project.plan(writing_mode="three_plus_review")}
        self.assertFalse(single["08"]["enabled"])
        self.assertTrue(three["08"]["enabled"])
        self.assertNotIn("08", single["09"]["depends_on"])
        self.assertIn("08", three["09"]["depends_on"])
        for mid in ["01", "02", "03"]:
            self.assertEqual(single[mid]["run_action"], "bind_existing_snapshot")
            self.assertEqual(single[mid]["execution_scope"], "shared_resource")
        with self.assertRaises(ValueError):
            project.plan(writing_mode="invalid")

    def test_v001_history_was_preserved(self):
        recorded = project.read_json(project.CONTROL / "第1版原件哈希.json")
        for relative, sha256 in recorded.items():
            self.assertEqual(project.digest(project.ROOT / relative), sha256, relative)

    def test_submission_family_and_active_slot_constraints(self):
        sql = (project.ROOT / "10_共享证据与契约/v001_第1版/knowledge.sql").read_text(encoding="utf-8")
        with sqlite3.connect(":memory:") as db:
            db.executescript(sql)
            db.execute("INSERT INTO research_runs VALUES ('TEST_run','T','I',NULL,'h','h','date','planned')")
            db.execute("INSERT INTO frozen_packs VALUES ('TEST_pack','TEST_run','p','h','date','frozen')")
            for label in ("A", "B"):
                db.execute("INSERT INTO drafts VALUES (?,?,?,?,?,?,?,?)", (
                    "TEST_"+label, "TEST_pack", label, "TEST_family", "path", "h", "TEST_context_"+label, "ready"))
            for label in ("1", "2"):
                db.execute("INSERT INTO journals VALUES (?,?,NULL,NULL,?,'PKU','date','unverified',NULL)",
                           ("TEST_J"+label, "TEST_J"+label, "{}"))
            db.execute("INSERT INTO submissions VALUES ('TEST_SUB1','TEST_family','TEST_A','TEST_J1','h','under_review',1,'date',NULL)")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO submissions VALUES ('TEST_SUB2','TEST_family','TEST_B','TEST_J2','h','submitted',1,'date',NULL)")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO submissions VALUES ('TEST_SUB3','wrong_family','TEST_A','TEST_J2','h','prepared',0,NULL,NULL)")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO submissions VALUES ('TEST_SUB4','TEST_family','TEST_A','TEST_J2','h','submitted',0,'date',NULL)")
            db.execute("UPDATE submissions SET status='rejected',active=0 WHERE submission_id='TEST_SUB1'")
            db.execute("INSERT INTO submissions VALUES ('TEST_SUB2','TEST_family','TEST_B','TEST_J2','h','submitted',1,'date',NULL)")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
