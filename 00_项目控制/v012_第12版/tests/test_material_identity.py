"""F10 exact duplication versus uncertain social event identity."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import ai_paper5_strict as strict
sys.path.insert(0,str(strict.MATERIAL.parent))
from qual_materials import read_materials,FIELDS
from material_identity import identity_candidates

class MaterialIdentityTest(unittest.TestCase):
    def test_exact_duplicates_keep_raw_observation_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            (work/"events.jsonl").write_text("synthetic",encoding="utf-8")
            row=dict.fromkeys(FIELDS,"fixture")
            row.update(url="https://example.org",kind="actor_statement",path="secondary_interviews",
                       source_type="secondary_interview",event_identity_claim="fixture event")
            strict.write(work/"response.json",{"materials":[row,row],"search_notes":[],"gaps":[]})
            with patch("qual_materials.evidence",return_value=[{"fixture":True}]),patch("qual_materials.url_event",return_value="event"):
                result=read_materials(work,2)
            self.assertEqual(len(result["materials"]),1)
            self.assertEqual(result["duplicate_raw_rows"][0]["duplicate_raw_index"],1)
            self.assertEqual(result["duplicate_raw_rows"][0]["first_raw_index"],0)
            self.assertIsNone(result["identity_candidates"]["independent_event_count"])
    def test_report_and_claim_identity_not_event_independence(self):
        rows=[{"material_id":"A","url":"https://example.org/report?utm_source=x","locator":"p1","event_identity_claim":"claim A"},
              {"material_id":"B","url":"https://example.org/report","locator":"p2","event_identity_claim":"claim B"},
              {"material_id":"C","url":"https://example.net/reprint","locator":"p1","event_identity_claim":"claim A"},
              {"material_id":"D","url":"https://example.net/unknown","locator":"p1"}]
        result=identity_candidates(rows)
        self.assertEqual(result["same_report_candidates"][0]["material_ids"],["A","B"])
        self.assertEqual(result["same_claimed_event_candidates"][0]["material_ids"],["A","C"])
        self.assertEqual(result["missing_event_identity"],["D"])
        self.assertEqual(result["cross_report_reprints_or_distinct_events"],"pending_independent_review")
        self.assertIsNone(result["independent_event_count"])
