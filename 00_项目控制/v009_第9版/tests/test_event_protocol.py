from pathlib import Path
import hashlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from event_protocol import (build_source_receipts, compare_events, validate_exchange)


URL = "https://example.org/source"


def source_receipt(source_id="A", url=URL, *, opened=True):
    return {
        "source_id": source_id,
        "url": url,
        "event_id": "item_1",
        "open_event_id": "item_1" if opened else None,
        "event_type": "web_search",
        "action_type": "open_page" if opened else None,
        "opened": opened,
        "thread_id": "thread-1",
        "events_path": "v5_native/events/attempt_001/events.jsonl",
        "events_sha256": "a" * 64,
        "response_path": "v5_native/events/attempt_001/response.json",
        "response_sha256": "b" * 64,
        "verification_status": "verified" if opened else "pending",
        "verification_reason": None if opened else "page_not_opened_in_current_trace",
    }


def packet_for(status="corroborated", source_id="A"):
    return {"sources": {"A": URL}, "events": [{
        "identity": "case",
        "facts": [{
            "source_id": source_id, "statement": "Claim", "use": "Account",
            "status": status, "key": True,
        }],
    }], "sensitivity": "Unknown"}


class EventProtocolTest(unittest.TestCase):
    def test_duplicate_case_and_uncertain_key_fact(self):
        packet = packet_for(status="single_account")
        result = compare_events(packet, {"A": source_receipt()})
        self.assertEqual(result["events"][0]["critical_gaps"], ["Claim"])
        self.assertEqual(result["events"][0]["retained_facts"], [])
        self.assertEqual(result["source_receipts"]["A"]["event_id"], "item_1")
        with self.assertRaisesRegex(ValueError, "same event"):
            compare_events(dict(packet, events=packet["events"] * 2), {"A": source_receipt()})

    def test_missing_source_receipt_is_preserved_as_pending(self):
        result = compare_events(packet_for(), {})
        fact = result["events"][0]["uncertain_facts"][0]
        self.assertEqual(result["events"][0]["retained_facts"], [])
        self.assertEqual(fact["status"], "unverified")
        self.assertEqual(fact["model_claimed_status"], "corroborated")
        self.assertEqual(fact["source_verification_status"], "pending")
        self.assertEqual(result["pending_fact_count"], 1)
        self.assertEqual(result["source_verification_status"], "pending")

    def test_source_receipt_url_mismatch_is_pending_not_retained(self):
        result = compare_events(
            packet_for(),
            {"A": source_receipt(url="https://other.example/source")},
        )
        fact = result["events"][0]["uncertain_facts"][0]
        self.assertEqual(result["events"][0]["retained_facts"], [])
        self.assertEqual(fact["status"], "unverified")
        self.assertEqual(fact["source_verification_reason"],
                         "source_receipt_incomplete_or_mismatched")

    def test_unopened_source_receipt_is_pending_not_retained(self):
        result = compare_events(packet_for(), {"A": source_receipt(opened=False)})
        fact = result["events"][0]["uncertain_facts"][0]
        self.assertEqual(result["events"][0]["retained_facts"], [])
        self.assertEqual(fact["status"], "unverified")
        self.assertEqual(fact["source_verification_status"], "pending")

    def test_missing_source_id_fact_is_pending(self):
        result = compare_events(packet_for(source_id="missing"), {"A": source_receipt()})
        fact = result["events"][0]["uncertain_facts"][0]
        self.assertEqual(result["events"][0]["retained_facts"], [])
        self.assertEqual(fact["status"], "unverified")
        self.assertEqual(fact["source_verification_reason"],
                         "missing_source_id_or_source_map_entry")

    def test_verified_corroborated_fact_can_be_retained(self):
        result = compare_events(packet_for(), {"A": source_receipt()})
        self.assertEqual(len(result["events"][0]["retained_facts"]), 1)
        self.assertEqual(result["events"][0]["retained_facts"][0]["source_verification_status"],
                         "verified")
        self.assertEqual(result["pending_fact_count"], 0)
        self.assertEqual(result["source_verification_status"], "verified")

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
            self.assertEqual(row["open_event_id"], "item_1")
            self.assertEqual(row["thread_id"], "thread-1")
            self.assertEqual(row["events_sha256"], hashlib.sha256(events.read_bytes()).hexdigest())
            self.assertEqual(row["response_sha256"], hashlib.sha256(response.read_bytes()).hexdigest())
            self.assertEqual(row["events_path"], "events.jsonl")
            self.assertEqual(row["response_path"], "response.json")
            self.assertTrue(row["opened"])
            self.assertEqual(row["verification_status"], "verified")

    def test_source_absent_from_native_trace_is_pending(self):
        packet = {"sources": {"A": URL}}
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            events = work / "events.jsonl"
            response = work / "response.json"
            events.write_text("{}", encoding="utf-8")
            response.write_text("{}", encoding="utf-8")
            receipts = build_source_receipts(
                packet, [], work=work, events_path=events, response_path=response,
                thread_id="thread-1", url_event_fn=lambda url, rows: None,
                canonicalize=lambda url: url,
            )
            self.assertEqual(receipts["A"]["verification_status"], "pending")
            self.assertEqual(receipts["A"]["verification_reason"],
                             "source_not_found_in_current_trace")

    def test_search_result_without_page_open_is_pending(self):
        packet = {"sources": {"A": URL}}
        trace = [{"id": "item_1", "type": "web_search", "results": [{"url": URL}]}]
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            events = work / "events.jsonl"
            response = work / "response.json"
            events.write_text("{}", encoding="utf-8")
            response.write_text("{}", encoding="utf-8")
            receipts = build_source_receipts(
                packet, trace, work=work, events_path=events, response_path=response,
                thread_id="thread-1", url_event_fn=lambda url, rows: "item_1",
                canonicalize=lambda url: url,
            )
            self.assertEqual(receipts["A"]["verification_status"], "pending")
            self.assertEqual(receipts["A"]["verification_reason"],
                             "page_not_opened_in_current_trace")
            self.assertFalse(receipts["A"]["opened"])

    def test_missing_raw_event_file_keeps_source_pending(self):
        packet = {"sources": {"A": URL}}
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            events = work / "missing.jsonl"
            response = work / "response.json"
            response.write_text("{}", encoding="utf-8")
            receipts = build_source_receipts(
                packet, [], work=work, events_path=events, response_path=response,
                thread_id=None, url_event_fn=lambda url, rows: None,
                canonicalize=lambda url: url,
            )
            self.assertEqual(receipts["A"]["verification_status"], "pending")
            self.assertEqual(receipts["A"]["verification_reason"], "missing_events_file")
            self.assertIsNone(receipts["A"]["events_sha256"])

    def test_challenge_must_come_from_distinct_role(self):
        packet = dict.fromkeys(("expectation", "observation", "initial_explanation", "challenge",
                               "candidate_question", "critical_receipt"), "test")
        with self.assertRaisesRegex(ValueError, "independent"):
            validate_exchange(dict(packet, research_actor="A", critical_actor="A"))
        validate_exchange(dict(packet, research_actor="A", critical_actor="B"))


if __name__ == "__main__":
    unittest.main()
