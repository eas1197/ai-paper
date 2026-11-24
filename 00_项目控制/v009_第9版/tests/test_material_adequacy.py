import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from material_adequacy import writing_material_status, approved_matrix_materials, validate_reviewed_plan_sources


class MaterialAdequacyTest(unittest.TestCase):
    def test_related_receipts_do_not_imply_adequacy(self):
        self.assertEqual(writing_material_status(None, ["related"]), "awaiting_material_adequacy")
        report = {"eligible_event_ids": [], "reason": "No case meets frozen criteria"}
        self.assertEqual(writing_material_status(dict(report, support="insufficient"), ["related"]),
                         "insufficient_core_material")
        with self.assertRaises(ValueError):
            writing_material_status(dict(report, support="sufficient"), ["related"])

    def test_only_current_receipt_ids_are_accepted(self):
        report = {"eligible_event_ids": ["old"], "reason": "Legacy finding", "support": "sufficient"}
        with self.assertRaises(ValueError):
            writing_material_status(report, ["new"])


    def plan_fixture(self):
        def material(mid):
            return {"material_id": mid, "url": "https://example.org/" + mid,
                    "locator": "passage " + mid, "kind": "official_rule"}
        receipt = {"materials": [material("M1"), material("M2"), material("M3")]}
        matrix = {"rows": [{"evidence": [material("M1"), material("M2")]}]}
        assessment = {"support": "sufficient", "reason": "Synthetic only",
                      "eligible_event_ids": ["M1", "M3"]}
        contract = {"core_question": "Q", "specific_question": "S08", "method": "online_qualitative"}
        packet = dict(contract, question_binding=contract,
                      sources={"M1": {"kind": "empirical", "locator": "passage M1"}},
                      chapters=[{"sections": [{"source_ids": ["M1"]}]}])
        return receipt, matrix, assessment, contract, packet

    def test_only_reviewed_matrix_eligible_materials_enter_plan(self):
        receipt, matrix, assessment, contract, packet = self.plan_fixture()
        approved = approved_matrix_materials(assessment, receipt, matrix)
        self.assertEqual(set(approved), {"M1"})
        validate_reviewed_plan_sources(packet, contract, receipt, approved)
        for mid in ("M2", "M3", "UNKNOWN"):
            with self.subTest(mid=mid), self.assertRaisesRegex(ValueError, "outside reviewed matrix"):
                validate_reviewed_plan_sources(dict(packet, sources={mid: {"kind": "empirical",
                    "locator": "passage " + mid}}), contract, receipt, approved)

    def test_reviewed_plan_rejects_changed_question_locator_and_relabel(self):
        receipt, matrix, assessment, contract, packet = self.plan_fixture()
        approved = approved_matrix_materials(assessment, receipt, matrix)
        with self.assertRaisesRegex(ValueError, "frozen question"):
            validate_reviewed_plan_sources(dict(packet, specific_question="Changed"), contract, receipt, approved)
        for source, message in (({"kind": "empirical", "locator": "wrong"}, "locator"),
                                ({"kind": "empirical", "locator": "passage M1", "url": "wrong"}, "URL"),
                                ({"kind": "literature", "locator": "passage M1"}, "relabelled")):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, message):
                validate_reviewed_plan_sources(dict(packet, sources={"M1": source}), contract, receipt, approved)

    def test_approved_materials_require_ready_and_original_identity(self):
        receipt, matrix, assessment, _, _ = self.plan_fixture()
        with self.assertRaisesRegex(ValueError, "not ready"):
            approved_matrix_materials(dict(assessment, support="unknown"), receipt, matrix)
        matrix["rows"][0]["evidence"][0]["locator"] = "changed"
        with self.assertRaisesRegex(ValueError, "source identity"):
            approved_matrix_materials(assessment, receipt, matrix)
