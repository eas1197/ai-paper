import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT=Path(__file__).with_name("check_publication.py")
spec=importlib.util.spec_from_file_location("check_publication",SCRIPT)
guard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicationTests(unittest.TestCase):
    def test_private_paths_and_binary_archive_block(self):
        for name in (".env","a/.codex/auth.json","handoff_runs/r/login.json",
                     "a/runs_dev/r/result.json","data/a.dta","handoff_runs/r/events.jsonl"):
            with self.subTest(name=name):
                self.assertIn("private_artifact_path",guard.inspect_candidate(name,b"{}"))
        self.assertIn("archive_requires_reviewed_text",guard.inspect_candidate("handoff_runs/r/data.zip",b"binary"))
        self.assertIn("non_regular_candidate",guard.inspect_candidate("link.md",b"target",mode="120000"))

    def test_synthetic_credentials_and_archive_private_paths(self):
        samples=[("gh"+"p_"+"x"*36,"github_token"),("s"+"k-proj-"+"x"*45,"openai_token"),
                 ("-----BEGIN "+"PRIVATE KEY-----","private_key_material"),
                 ("Bearer "+"x"*30,"bearer_token")]
        for value,kind in samples:
            self.assertIn(kind,guard.inspect_candidate("code.txt",value.encode()))
        self.assertIn("credential_assignment",guard.inspect_candidate("handoff_runs/r/a.json",b'{"password":"synthetic-value-only"}'))
        self.assertIn("local_home_path",guard.inspect_candidate("handoff_runs/r/a.md",b"/home/"+b"fixture-user/source"))
        self.assertFalse(guard.inspect_candidate(".env.example",b"ZHIPUAI_API_KEY=\n"))
        self.assertFalse(guard.inspect_candidate("handoff_runs/r/summary.json",b'{"status":"pending","formal_eligible":false}'))

    def test_staged_blob_not_worktree_and_no_secret_output(self):
        previous=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                subprocess.run(["git","init","-q"],check=True)
                secret="gh"+"p_"+"x"*36
                Path("candidate.md").write_text(secret)
                subprocess.run(["git","add","candidate.md"],check=True)
                Path("candidate.md").write_text("safe worktree")
                out=io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(guard.main(["--staged"]),1)
                self.assertIn("github_token",out.getvalue())
                self.assertNotIn(secret,out.getvalue())
                self.assertNotIn("candidate.md",out.getvalue())
            finally:
                os.chdir(previous)

    def test_commit_diff_does_not_scan_unrelated_historical_content(self):
        previous=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                def git(*args):
                    return subprocess.check_output(["git",*args],text=True).strip()
                git("init","-q");git("config","user.email","fixture@example.invalid")
                git("config","user.name","Fixture")
                Path("old.md").write_text("gh"+"p_"+"x"*36)
                git("add","old.md");git("commit","-qm","historical")
                base=git("rev-parse","HEAD")
                Path("new.md").write_text("reviewed public summary")
                git("add","new.md");git("commit","-qm","new")
                self.assertEqual(guard.check_git(staged=False,base=base,head="HEAD"),(1,{}))
            finally:
                os.chdir(previous)


if __name__=="__main__":
    unittest.main()
