"""F09 source form is independent of evidentiary kind; native web has no firsthand data."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
import ai_paper5_strict as strict
sys.path.insert(0,str(strict.MATERIAL.parent))
from qual_materials import schema,read_materials,FIELDS,SOURCE_TYPES

class MaterialSourceTypesTest(unittest.TestCase):
    def test_schema_distinguishes_forms_without_authorizing_firsthand(self):
        self.assertEqual(len(SOURCE_TYPES),7)
        item=schema()["properties"]["materials"]["items"]
        self.assertIn("source_type",item["required"])
        self.assertNotIn("firsthand_interview",item["properties"]["source_type"]["enum"])
        self.assertNotIn("researcher_interpretation",item["properties"]["source_type"]["enum"])
    def test_native_web_forms_and_unknown_remain_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            (work/"events.jsonl").write_text("synthetic",encoding="utf-8")
            row=dict.fromkeys(FIELDS,"fixture")
            row.update(url="https://example.org",kind="actor_statement",path="secondary_interviews")
            rows=[dict(row,source_type=k) for k in ("secondary_interview","media_report","public_document","social_media","unknown","firsthand_interview","researcher_interpretation")]
            rows.append(row)
            strict.write(work/"response.json",{"materials":rows,"search_notes":[],"gaps":[]})
            with patch("qual_materials.evidence",return_value=[{"fixture":True}]),patch("qual_materials.url_event",return_value="event"):
                result=read_materials(work,2)
            self.assertEqual(len(result["materials"]),6)
            self.assertEqual(len(result["excluded"]),2)
            self.assertEqual(len(result["source_types_pending"]),2)
            self.assertEqual(result["status"],"pending_independent_review")
            self.assertEqual(result["materials"][0]["kind"],"actor_statement")
            self.assertEqual(result["materials"][0]["source_type"],"secondary_interview")
