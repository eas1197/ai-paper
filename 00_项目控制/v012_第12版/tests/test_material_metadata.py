"""F08 original material metadata receipt; synthetic offline sources only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import ai_paper5_strict as strict
sys.path.insert(0,str(strict.MATERIAL.parent))
from qual_materials import read_materials, FIELDS

class MaterialMetadataTest(unittest.TestCase):
    def test_metadata_preserved_and_missing_fields_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            (work/"events.jsonl").write_text("synthetic fixture",encoding="utf-8")
            row=dict.fromkeys(FIELDS,"fixture")
            row.update(url="https://example.org",kind="actor_statement",path="secondary_interviews",
                date="publication date unknown",subject="anonymous interviewee",
                locator="paragraph 2",access="public; permission unknown",limits="reported claim only")
            bad=dict(row);bad.pop("date")
            bad2=dict(row,locator=None)
            strict.write(work/"response.json",{"materials":[row,bad,bad2],"search_notes":["fixture"],"gaps":["date unknown"]})
            with patch("qual_materials.evidence",return_value=[{"fixture":True}]),patch("qual_materials.url_event",return_value="action-1"):
                result=read_materials(work,2)
            self.assertEqual(len(result["materials"]),1)
            self.assertEqual(result["materials"][0],dict(row,event_id="action-1",material_id=result["materials"][0]["material_id"]))
            self.assertEqual(result["excluded"][0]["missing_fields"],["date"])
            self.assertEqual(result["excluded"][1]["missing_fields"],["locator"])
            self.assertEqual(result["events_sha256"],strict.sha(work/"events.jsonl"))
            self.assertEqual(result["response_sha256"],strict.sha(work/"response.json"))
            self.assertEqual(result["status"],"pending_independent_review")
    def test_unobserved_url_and_excess_budget_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            (work/"events.jsonl").write_text("synthetic fixture",encoding="utf-8")
            row=dict.fromkeys(FIELDS,"fixture")
            row.update(url="https://example.org",kind="official_rule",path="online_qualitative")
            strict.write(work/"response.json",{"materials":[row],"search_notes":[],"gaps":[]})
            with patch("qual_materials.evidence",return_value=[{"fixture":True}]),patch("qual_materials.url_event",return_value=None):
                self.assertEqual(read_materials(work,1)["materials"],[])
                with self.assertRaisesRegex(ValueError,"budget exceeded"): read_materials(work,0)
