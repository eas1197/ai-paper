from pathlib import Path
import hashlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from event_protocol import (build_source_receipts, compare_events, validate_exchange)


URL = "https://example.org/source"


def source_receipt(source_id="A", url=URL, *, opened=False):
    return {
        "source_id": source_id,
        "url": url,
        "event_id": "item_1",
        "event_type": "web_search",
        "action_type": "open_page" if opened else None,
        "opened": opened,
        "thread_id": "thread-1",
        "events_path": "v5_native/events/attempt_001/events.jsonl",
        "events_sha256": "a" * 64,
        "response_path": "v5_native/events/attempt_001/response.json",
        "response_sha256": "b" * 64,
    }


class EventProtocolTest(unittest.TestCase):
    def test_duplicate_case_and_uncertain_key_fact(self):
        row = {"identity": "same case", "facts": [
            {"source_id": "A", "statement": "Claim", "use": "Subjective account",
             "status": "single_account", "key": True}]}
        packet = {"sources": {"A": URL}, "events": [row], "sensitivity": "Unknown"}
        result = compare_events(packet, {"A": source_receipt()})
        self.assertEqual(result["events"][0]["critical_gaps"], ["Claim"])
        self.assertEqual(result["events"][0]["retained_facts"], [])
        self.assertEqual(result["source_receipts"]["A"]["event_id"], "item_1")
        with self.assertRaisesRegex(ValueError, "same event"):
            compare_events(dict(packet, events=[row, row]), {"A": source_receipt()})

    def test_missing_source_receipt_is_rejected(self):
        packet = {"sources": {"A": URL}, "events": [{
            "identity": "case", "facts": [{
                "source_id": "A", "statement": "Claim", "use": "Account",
                "status": "corroborated", "key": True}]}], "sensitivity": "Unknown"}
        with self.assertRaisesRegex(ValueError, "Missing source-to-event"):
            compare_events(packet, {})

    def test_source_receipt_url_must_match_source_map(self):
        packet = {"sources": {"A": URL}, "events": [{
            "identity": "case", "facts": [{
                "source_id": "A", "statement": "Claim", "use": "Account",
                "status": "corroborated", "key": True}]}], "sensitivity": "Unknown"}
        with self.assertRaisesRegex(ValueError, "URL mismatch"):
            compare_events(packet, {"A": source_receipt(url="https://other.example/source")})

    def test_source_receipts_bind_url_event_thread_and_raw_hashes(self):
        packet = {"sources": {"A": URL}}
        trace = [{"id": "item_1", "type": "web_search", "results": [{"url": URL}],
                  "action": {"type": "open_page", "url": URL}}]
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            events = work / "events.jsonl"
            response = work / "response.json"
            events.write_text('{"type":"thread.started","thread_id":"thread-1"}\n',
                              encoding="utf-8")
            response.write_text('{"sources":{"A":"https://example.org/source"}}\n',
                                encoding="utf-8")
            receipts = build_source_receipts(
                packet, trace, work=work, events_path=events, response_path=response,
                thread_id="thread-1",
                url_event_fn=lambda url, rows: "item_1" if url == URL else None,
                canonicalize=lambda url: url,
            )
            row = receipts["A"]
            self.assertEqual(row["url"], URL)
            self.assertEqual(row["event_id"], "item_1")
            self.assertEqual(row["thread_id"], "thread-1")
            self.assertEqual(row["events_sha256"], hashlib.sha256(events.read_bytes()).hexdigest())
            self.assertEqual(row["response_sha256"], hashlib.sha256(response.read_bytes()).hexdigest())
            self.assertEqual(row["events_path"], "events.jsonl")
            self.assertEqual(row["response_path"], "response.json")
            self.assertTrue(row["opened"])

    def test_source_receipt_rejects_url_absent_from_native_trace(self):
        packet = {"sources": {"A": URL}}
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            events = work / "events.jsonl"
            response = work / "response.json"
            events.write_text("{}", encoding="utf-8")
            response.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not present in this native search attempt"):
                build_source_receipts(
                    packet, [], work=work, events_path=events, response_path=response,
                    thread_id="thread-1", url_event_fn=lambda url, rows: None,
                    canonicalize=lambda url: url,
                )

    def test_challenge_must_come_from_distinct_role(self):
        packet = dict.fromkeys(("expectation", "observation", "initial_explanation", "challenge",
                               "candidate_question", "critical_receipt"), "test")
        with self.assertRaisesRegex(ValueError, "independent"):
            validate_exchange(dict(packet, research_actor="A", critical_actor="A"))
        validate_exchange(dict(packet, research_actor="A", critical_actor="B"))


if __name__ == "__main__":
    unittest.main()
