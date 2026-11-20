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

    def test_numbered_references_and_unlisted_reporting_patterns(self):
        draft = ("已有研究发现两组参与率不同。\n"
                 "在张晓宁的研究中，两个样本来自不同地区。\n"
                 "陈文指出，教育差距与调查范围有关。\n"
                 "相同调查也覆盖了两组（李丽，2020）。李丽说控制了地区。\n"
                 "费孝通用差序格局解释社会关系。\n"
                 "韦伯的一项调查覆盖多个地点。\n"
                 "## 参考文献\n[1] 张晓宁, 刘宁. 城乡比较[J]. 社会学研究, 2020.\n"
                 "## 附录\n张晓宁指出。")
        self.assertEqual([(item['line'],item['match']) for item in style_findings(draft)],
                         [(2,'张晓宁'),(3,'陈文'),(4,'李丽'),(6,'韦伯')])

    def test_citation_groups_keep_multiple_sources(self):
        draft = ("两类社区的频率有差异（王敏，2018；张琳，2021）。\n"
                 "王敏（2018）发现两个群体有差异。")
        self.assertEqual([(row["line"],row["match"]) for row in style_findings(draft)], [(2, "王敏")])

    def test_institutional_source_is_not_flagged_as_a_person(self):
        draft = ("中国互联网络信息中心发布了统计报告。\n"
                 "## 参考文献\n- 中国互联网络信息中心，2025，《统计报告》。")
        self.assertEqual(style_findings(draft), [])
