from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from event_protocol import compare_events, validate_exchange


class EventProtocolTest(unittest.TestCase):
    def test_duplicate_case_and_uncertain_key_fact(self):
        row = {"identity": "same case", "facts": [
            {"source_id": "A", "statement": "Claim", "use": "Subjective account",
             "status": "single_account", "key": True}]}
        packet = {"sources": {"A": "https://example.org"}, "events": [row], "sensitivity": "Unknown"}
        result = compare_events(packet)
        self.assertEqual(result["events"][0]["critical_gaps"], ["Claim"])
        self.assertEqual(result["events"][0]["retained_facts"], [])
        with self.assertRaisesRegex(ValueError, "same event"):
            compare_events(dict(packet, events=[row, row]))

    def test_challenge_must_come_from_distinct_role(self):
        packet = dict.fromkeys(("expectation", "observation", "initial_explanation", "challenge",
                               "candidate_question", "critical_receipt"), "test")
        with self.assertRaisesRegex(ValueError, "independent"):
            validate_exchange(dict(packet, research_actor="A", critical_actor="A"))
        validate_exchange(dict(packet, research_actor="A", critical_actor="B"))
