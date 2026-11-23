import json
from pathlib import Path
import sys
import unittest


VERSION = Path(__file__).resolve().parents[1]
ROOT = VERSION.parents[1]
sys.path.insert(0, str(VERSION / "tools"))
from native_library import registry

V3_POLICY = json.loads((ROOT / "00_项目控制/v009_第9版/search_policy.json").read_text(encoding="utf-8-sig"))

PROFILE = registry()
from codex_literature import group, observation, proof


URL = "https://www.society.shu.edu.cn/CN/abstract/abstract7154.shtml"
TRACE = [{"id": "item_1", "type": "web_search", "results": [{"url": URL}]}]


def record(**changes):
    return dict({
        "title": "研究作者选取的论文题目",
        "journal": "社会",
        "authors": ["张甲"],
        "year": 2016,
        "doi": "10.1234/demo",
        "metadata_url": URL,
        "abstract_url": URL,
        "abstract_locator": "摘要",
        "abstract_excerpt": "用来定位的一小段引文",
        "abstract_summary": "本文比较不同职业教育和普通高中的学生在学校学习后获得的技能与职业机会，并说明样本和分析设计以及结果的适用范围。",
        "relevance": "direct",
        "relevance_reason": "分流后的两条教育路径与机会比较",
    }, **changes)


class NativeContract(unittest.TestCase):
    def test_nine_journal_scope_matches_v3_policy_and_templates(self):
        self.assertEqual(len(PROFILE["journals"]), 9)
        self.assertEqual(len(set(PROFILE["journals"])), 9)
        self.assertEqual(PROFILE["journals"], V3_POLICY["journals"])
        for name in ("native_request.json", "native_100_request.json"):
            config = json.loads((VERSION / "templates" / name).read_text(encoding="utf-8-sig"))
            self.assertEqual(config["journals"], PROFILE["journals"])

    def test_asr_and_ajs_are_accepted_by_native_candidate_scope(self):
        for index, (journal, url) in enumerate(zip(
            ("American Sociological Review", "American Journal of Sociology"),
            V3_POLICY["preferred_platforms"],
        ), 1):
            trace = [{"id": f"item_{index}", "type": "web_search", "results": [{"url": url}]}]
            observed = observation(
                record(journal=journal, metadata_url=url, abstract_url=url),
                trace, PROFILE["journals"], f"batch_{index:03d}", index,
            )
            self.assertEqual(observed["journal"], journal)

    def test_source_must_be_in_actual_native_tool_return(self):
        self.assertTrue(proof(URL + "?utm_source=example", "item_1", TRACE))
        self.assertFalse(proof(URL, "different_item", TRACE))
        with self.assertRaisesRegex(ValueError, "missing_native_tool_receipt"):
            observation(record(abstract_url="https://public.example/abs"),
                        TRACE, PROFILE["journals"], "batch_001", 1)

    def test_registered_journals_use_same_identity_resolver(self):
        first = observation(record(), TRACE, PROFILE["journals"], "batch_001", 1)
        again = observation(record(), TRACE, PROFILE["journals"], "batch_002", 1)
        papers, conflicts = group([first, again])
        self.assertEqual(len(papers), 1)
        self.assertEqual(len(papers[0]["provenance"]), 2)
        self.assertEqual(conflicts, [])
        conflict = observation(record(year=2017), TRACE, PROFILE["journals"], "batch_002", 2)
        papers, conflicts = group([first, conflict])
        self.assertEqual(papers, [])
        self.assertEqual(conflicts[0]["reason"], "year_conflict")

    def test_venue_and_semantic_relevance_are_required(self):
        with self.assertRaisesRegex(ValueError, "out_of_scope"):
            observation(record(journal="社会科学"), TRACE, PROFILE["journals"], "batch_001", 1)
        with self.assertRaisesRegex(ValueError, "relevance_unconfirmed"):
            observation(record(relevance_reason=""), TRACE, PROFILE["journals"], "batch_001", 1)
