"""F05: frozen conversion and theoretical design guards; offline fixture only."""
import sys
import unittest
import test_frozen_route as fixture
import ai_paper5_strict as strict
sys.path.insert(0,str(strict.V32/"tools"))
sys.path.insert(0,str(strict.MATERIAL.parent))
from qual_materials import verify_frozen_conversion
from question_binding import require_same_theoretical_design

class FrozenConversionTest(unittest.TestCase):
    setUp=fixture.FrozenRouteTest.setUp
    freeze=fixture.FrozenRouteTest.freeze

    def test_preliminary_search_unchanged(self):
        self.assertIsNone(verify_frozen_conversion(self.work,{"new_question":"fixture"}))

    def test_changed_question_and_quantitative_blocked(self):
        self.freeze("online_qualitative")
        with self.assertRaisesRegex(ValueError,"Changing the frozen question"):
            verify_frozen_conversion(self.work,{"new_question":"different"})
        self.setUp()
        self.freeze("quantitative")
        with self.assertRaisesRegex(ValueError,"Changing the frozen question"):
            verify_frozen_conversion(self.work,{"new_question":"Synthetic question"})

    def test_same_question_without_reviewed_conversion_is_not_authorized(self):
        self.freeze("online_qualitative")
        with self.assertRaisesRegex(ValueError,"qualified material decision"):
            verify_frozen_conversion(self.work,{"new_question":"Synthetic question"})

    def test_theoretical_design_change_blocked_but_requirements_may_change(self):
        original={"core_question":"Q","core_concept":"C","dimensions":[{"id":"D","needed_material":"A","proposition":"P"}]}
        revised={"core_question":"Q","core_concept":"C","dimensions":[{"id":"D","needed_material":"B","proposition":"P"}]}
        require_same_theoretical_design(original,revised)
        with self.assertRaisesRegex(ValueError,"theoretical design"):
            require_same_theoretical_design(original,dict(revised,core_concept="Other"))
        with self.assertRaisesRegex(ValueError,"theoretical design"):
            require_same_theoretical_design(original,dict(revised,dimensions=[dict(revised["dimensions"][0],proposition="Other")]))
