import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from material_adequacy import writing_material_status


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
