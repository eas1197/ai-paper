import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from language07 import style_findings


class CitationStyleTests(unittest.TestCase):
    def test_names_in_parenthetical_citations_and_classic_theory_remain(self):
        prose = ("常见研究在住户层面比较城乡差异（张小明，2020）。\n"
                 "费孝通讨论差序格局。\n"
                 "张小明（2020）的一项研究使用了住户调查。\n"
                 "## 参考文献\n- 张小明，2020，《比较》。\n"
                 "- 费孝通，1948，《乡土中国》。")
        self.assertEqual([(x["rule_id"], x["line"], x["match"]) for x in style_findings(prose)],
                         [("L05", 3, "张小明")])
