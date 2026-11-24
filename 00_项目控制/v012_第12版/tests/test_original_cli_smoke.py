"""B25: direct original CLI smoke, offline fixtures only (no search or formal runs)."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V9 = "00_项目控制/v009_第9版/tools/"
ENTRIES = {
    "topic": V9 + "staged_topic.py",
    "events": V9 + "event_protocol.py",
    "materials": "06_数据方法与分析/v005_第5版/tools/qual_materials.py",
    "plan": "07_三稿独立写作/v015_第15版/tools/writing_plan.py",
    "writer": "07_三稿独立写作/v016_第16版/tools/ai_writer4.py",
}


class OriginalCLISmoke(unittest.TestCase):
    def call_cli(self, name, *args, expected=0):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / ENTRIES[name]), *map(str, args)],
            cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
            timeout=30, env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout

    def test_original_help_contracts(self):
        contracts = {
            "topic": ("status", "--mode", "--theme", "--report"),
            "events": ("--dev-run", "--input", "--events-jsonl"),
            "materials": ("--dev-run", "--attempt", "--conversion", "--review", "--matrix"),
            "plan": ("--dev-run", "--input"),
            "writer": ("route", "prepare", "submit"),
        }
        for name, options in contracts.items():
            with self.subTest(entry=name):
                output = self.call_cli(name, "--help")
                for option in options:
                    self.assertIn(option, output)
        for cmd in ("route", "prepare", "submit"):
            with self.subTest(writer_command=cmd):
                self.assertIn("--packet", self.call_cli("writer", cmd, "--help"))

    def test_original_dev_status_and_legacy_event_entry(self):
        run_id = "b25_smoke_" + uuid.uuid4().hex
        work = ROOT / "00_项目控制/v007_第7版/runs_dev" / run_id
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        self.call_cli("topic", "init", run_id, "--mode", "dev", "--theme", "Offline CLI fixture")
        state_path = work / "staged_topic.json"
        before = state_path.read_bytes()
        state = json.loads(self.call_cli("topic", "status", run_id, "--mode", "dev"))
        self.assertEqual(state["status"], "reality")
        self.assertFalse(state["formal_eligible"])
        self.assertEqual(state_path.read_bytes(), before)
        # Synthetic fixture only: no real research or source verification is claimed.
        state["status"] = "explanation_exchange"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        attempt = work / "v5_native/events/attempt_001"
        attempt.mkdir(parents=True)
        response = attempt / "response.json"
        response.write_text(json.dumps({
            "sources": {"A": "https://example.org/source"},
            "events": [{"identity": "fixture", "facts": [{
                "source_id": "A", "statement": "Synthetic claim",
                "use": "Fixture", "status": "corroborated", "key": True,
            }]}], "sensitivity": "Unknown",
        }), encoding="utf-8")
        # Original command: intentionally omit --events-jsonl and do not fabricate a trace.
        self.call_cli("events", "--dev-run", work, "--input", response)
        result = json.loads((work / "event_comparison.json").read_text(encoding="utf-8"))
        self.assertEqual(result["events_path"], "v5_native/events/attempt_001/events.jsonl")
        self.assertIsNone(result["events_sha256"])
        self.assertEqual(result["events"][0]["retained_facts"], [])
        self.assertFalse(result["formal_eligible"])

    def test_original_writer_route_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            packet = Path(folder) / "packet.json"
            for method, writer in (
                ("secondary_interviews", "ai-writer 4.0 / v016"),
                ("quantitative", "main/v014/tools/stage07.py"),
            ):
                packet.write_text(json.dumps({"method": method}), encoding="utf-8")
                result = json.loads(self.call_cli("writer", "route", "--packet", packet))
                self.assertEqual(result["method"], method)
                self.assertEqual(result["writer"], writer)

    def test_original_required_parameters_fail_before_work(self):
        self.call_cli("materials", expected=2)
        self.call_cli("plan", expected=2)


if __name__ == "__main__":
    unittest.main()
