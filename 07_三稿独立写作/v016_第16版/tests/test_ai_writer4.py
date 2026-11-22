"""Offline contract tests for ai-writer 4.0 qualitative drafting bridge."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ai_writer4 as writer


def packet(method="secondary_interviews"):
    dimensions = [{"id": "d1", "title": "可信性", "deduction": "derive uncertainty management"}]
    chapter_ids = ["problem", "framework", "case", "d1", "conclusion"]
    chapters = []
    for cid in chapter_ids:
        chapters.append({
            "id": cid, "task": "Explain this specific relation",
            "bridge": "Continue from earlier evidence",
            "sections": [{
                "title": "Study", "task": "Compare two situations",
                "argument": "Claims bounded to reported action",
                "evidence_use": "Use cited material to distinguish facts from claims",
                "source_ids": ["E", "T"],
                "paragraphs": ["State the unit and observed action"]
            }]
        })
    return {
        "run_id": "fixture_writer4", "method": method,
        "core_question": "How does coordination proceed?",
        "answer_strategy": "Compare reported sequences",
        "framework": {
            "prior_explanation": "Prior studies", "gap": "Comparable boundaries",
            "theory_choice": "Action organization", "deduction": "Define testable dimensions",
            "increment": "Provisional comparison", "integration": "Connect dimensions",
            "core_concept": "行动可执行性", "dimensions": dimensions
        },
        "case": {
            "background": "Two cases", "selection": "Relevant variation",
            "materials": "Two linked reports", "method": "Comparative document analysis"
        },
        "sources": {
            "T": {"kind": "theory", "label": "Literature", "locator": "DOI 123"},
            "E": {"kind": "empirical", "label": "Interview report", "locator": "URL line 22"}
        },
        "chapters": chapters,
        "gate_status": {
            "independent_review_verified": False,
            "strict_literature_complete": False,
            "empirical_mechanism_verified": False,
            "formally_frozen": False,
            "independent_writing_approval": False,
        },
        "policy": {"max_words": 2500}
    }


class Writer4Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = packet()
        self.packet_path = self.root / "input.json"
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        self.work = self.root / "writing"

    def tearDown(self):
        self.tmp.cleanup()

    def test_qualitative_preparation_reuses_exact_language_resources(self):
        record = writer.prepare(self.packet_path, self.work)
        self.assertEqual(record["task_count"], 5)
        self.assertEqual(record["status"], "awaiting_draft")
        manifest = writer.load(self.work / "writer_manifest.json")
        self.assertEqual(manifest["language_formal_resource_status"], "needs_review")
        self.assertFalse(manifest["formal_eligible"])
        self.assertEqual(len(manifest["resource_sha256"]), 10)
        self.assertIn("how_to_write", (writer.load(self.work / "tasks/d1_01.json"))["style_rules"][0])
        self.assertIn("分析框架", (self.work / "writing_plan_v15.md").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "exists"):
            writer.prepare(self.packet_path, self.work)

    def test_routes_quantitative_to_existing_v014_without_change(self):
        self.data["method"] = "quantitative"
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        self.assertIn("v014", writer.route(self.packet_path)["writer"])
        with self.assertRaisesRegex(ValueError, "v014"):
            writer.prepare(self.packet_path, self.work)

    def test_formal_drafting_does_not_invent_independent_receipt(self):
        with self.assertRaisesRegex(ValueError, "upstream gates"):
            writer.prepare(self.packet_path, self.work, mode="formal")
        self.assertFalse(self.work.exists())

    def test_audits_source_bound_claims_and_rejects_changed_input(self):
        writer.prepare(self.packet_path, self.work)
        draft = self.root / "draft.md"
        draft.write_text(
            "## 一、问题\n材料表明需要协调（来源，2022）。\n"
            "## 二、理论\n对照理论与报道。\n"
            "## 三、案例\n案例为两个组织。\n"
            "## 四、可信性\n报道中的核验行为。\n"
            "## 五、结论\n材料表明需要协调。\n"
            "## 参考文献\n来源（2022）。\n", encoding="utf-8")
        claims = self.root / "claims.json"
        claims.write_text(json.dumps({"claims": [{"claim_id": "C1",
            "exact_text": "材料表明需要协调", "source_ids": ["E", "T"]}]}, ensure_ascii=False), encoding="utf-8")
        output = writer.review_draft(self.packet_path, self.work, draft, claims)
        self.assertEqual(output["status"], "exploratory_draft_awaiting_review")
        self.assertFalse(writer.load(self.work / "writing_review_request.json")["formal_pass"])
        self.data["core_question"] = "Different question?"
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        result = writer.review_draft(self.packet_path, self.work, draft, claims)
        self.assertEqual(result["status"], "technical_revisions_needed")
        self.assertTrue(any("packet changed" in s for s in result["errors"]))

    def test_rejects_missing_evidence_from_dimension(self):
        self.data["chapters"][3]["sections"][0]["source_ids"] = ["T"]
        self.packet_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "empirical"):
            writer.prepare(self.packet_path, self.work)


if __name__ == "__main__":
    unittest.main()
