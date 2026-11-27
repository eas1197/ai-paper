from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from method_paths import select_method, verify_material_review


def assessment(**updates):
    paths = {
        "quantitative": {"status": "unknown", "reason": "Questionnaire coverage unverified"},
        "secondary_interviews": {"status": "missing", "reason": "Archive scope checked"},
        "online_qualitative": {"status": "not_applicable", "reason": "No relevant online field"},
    }
    paths.update(updates)
    return {"paths": paths}


class MethodPathsTest(unittest.TestCase):
    def test_cannot_confirm_missing_from_unsearched_or_changed_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            decision = {"status": "missing", "search_attempt": "attempt_001"}
            with self.assertRaisesRegex(ValueError, "no actual"):
                verify_material_review(work, "secondary_interviews", decision, "Question?")
            folder = work / "qualitative/attempt_001"
            folder.mkdir(parents=True)
            def put(name, value):
                content = json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()
                (folder / name).write_bytes(content)
                return hashlib.sha256(content).hexdigest()
            receipt = {"run_id": work.name, "status": "pending_independent_review", "tool_events": 1,
                       "conversion_sha256": put("conversion.json", {"new_question": "Question?"}),
                       "events_sha256": put("events.jsonl", ["fixture"]),
                       "response_sha256": put("response.json", {}),
                       "materials": []}
            decision["receipt_sha256"] = put("material_receipt.json", receipt)
            with self.assertRaisesRegex(ValueError, "insufficient search"):
                verify_material_review(work, "secondary_interviews", decision, "Question?")
            decision["search_assessment"] = "reasonable_but_insufficient"
            verify_material_review(work, "secondary_interviews", decision, "Question?")
            put("events.jsonl", ["changed fixture"])
            with self.assertRaisesRegex(ValueError, "changed"):
                verify_material_review(work, "secondary_interviews", decision, "Question?")

    def test_interviews_can_be_first_choice(self):
        case = assessment(secondary_interviews={"status": "ready", "reason": "Directly answers the question",
                                                "access": "verified", "materials": ["interview archive index"]})
        route = select_method(dict(case, selected="secondary_interviews"), "pass")
        self.assertEqual(route["entry06"], "planned")
        self.assertEqual(route["writing07"], "planned")

    def test_quantitative_keeps_existing_entries(self):
        case = assessment(quantitative={"status": "ready", "reason": "Variables verified",
                                        "access": "verified", "materials": ["survey dictionary"]})
        route = select_method(dict(case, selected="quantitative"), "pass")
        self.assertEqual(route["entry06"], "existing_quantitative")

    def test_missing_quantitative_data_alone_cannot_archive(self):
        case = assessment(quantitative={"status": "missing", "reason": "Required variables absent"},
                          secondary_interviews={"status": "unknown", "reason": "Access not yet checked"})
        self.assertIsNone(select_method(case, "materials_pending"))
        with self.assertRaisesRegex(ValueError, "all applicable paths"):
            select_method(case, "missing_data")
        case["paths"]["secondary_interviews"]["status"] = "missing"
        self.assertIsNone(select_method(case, "missing_data"))

    def test_ethnography_needs_observation_distinct_from_public_text(self):
        online = {"status": "ready", "reason": "Relevant field", "access": "verified",
                  "materials": ["public text index"], "approach": "ethnography"}
        case = dict(assessment(online_qualitative=online), selected="online_qualitative")
        with self.assertRaisesRegex(ValueError, "observation conditions"):
            select_method(case, "pass")
        online["approach"] = "public_text"
        self.assertEqual(select_method(case, "pass")["approach"], "public_text")
