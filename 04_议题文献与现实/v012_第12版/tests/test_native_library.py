import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid


VERSION = Path(__file__).resolve().parents[1]
ROOT = VERSION.parents[1]
sys.path.insert(0, str(VERSION / "tools"))
from native_library import main, registry

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
            self.assertEqual(config["target"], 0)
            self.assertEqual(config["max_batches"], 0)

    def test_zero_target_exits_without_codex_search_or_run_directory(self):
        work = VERSION / "outputs" / ("zero_target_test_" + uuid.uuid4().hex)
        output = StringIO()
        argv = [
            "native_library.py", "--profile", PROFILE["profile"],
            "--work", str(work),
        ]
        with patch.object(sys, "argv", argv), \
             patch("codex_literature.collect") as collect, \
             patch("native_receiving.receive") as receive, \
             redirect_stdout(output):
            exit_code = main()
        self.assertEqual(exit_code, 0)
        self.assertFalse(work.exists())
        collect.assert_not_called()
        receive.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "disabled")
        self.assertEqual(result["target"], 0)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["batches"], [])
        self.assertEqual(result["reason"], "zero_target_configuration")

    def test_asr_and_ajs_accept_original_english_metadata_and_excerpt(self):
        english_titles = (
            "Educational Stratification and School Transitions",
            "School Choice and Unequal Educational Attainment",
        )
        english_excerpt = "Educational stratification shapes later opportunities"
        for index, (journal, url, title) in enumerate(zip(
            ("American Sociological Review", "American Journal of Sociology"),
            V3_POLICY["preferred_platforms"],
            english_titles,
        ), 1):
            trace = [{"id": f"item_{index}", "type": "web_search", "results": [{"url": url}]}]
            authors = ["Alexandra Example", "Robert Researcher"]
            observed = observation(
                record(title=title, authors=authors, journal=journal,
                       abstract_excerpt=english_excerpt, metadata_url=url, abstract_url=url),
                trace, PROFILE["journals"], f"batch_{index:03d}", index,
            )
            self.assertEqual(observed["journal"], journal)
            self.assertEqual(observed["title"], title)
            self.assertEqual(observed["authors"], authors)
            self.assertEqual(observed["abstract_excerpt"], english_excerpt)

    def test_native_search_prompt_contains_bilingual_nine_journal_contract(self):
        template = (VERSION / "templates" / "search_prompt.txt").read_text(encoding="utf-8-sig")
        rendered = template.format(
            theme="教育分流", desired=20,
            journals="、".join(PROFILE["journals"]), accepted="[]",
        )
        for journal in PROFILE["journals"]:
            self.assertIn(journal, rendered)
        self.assertIn("journals.sagepub.com/home/asr", rendered)
        self.assertIn("journals.uchicago.edu/toc/ajs/current", rendered)
        self.assertIn("英文刊名及英文主题词", rendered)
        self.assertIn("英文保留约5–12个词", rendered)
        self.assertIn("中文以约8–45字为宜", rendered)
        self.assertNotIn("8到45个汉字", rendered)
        self.assertNotIn("{journals}", rendered)

    def test_response_schema_supports_original_language_and_nine_journals(self):
        schema = json.loads(
            (VERSION / "templates" / "native_response.schema.json").read_text(encoding="utf-8-sig")
        )
        paper = schema["properties"]["papers"]["items"]["properties"]
        self.assertIn("原始发表语言", paper["title"]["description"])
        self.assertIn("原始拼写", paper["authors"]["items"]["description"])
        self.assertIn("九刊", paper["journal"]["description"])
        self.assertIn("英文", paper["abstract_excerpt"]["description"])
        self.assertIn("中文改述", paper["abstract_summary"]["description"])
        self.assertIn("中文或英文", schema["properties"]["search_notes"]["items"]["description"])
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["papers"]["items"]["additionalProperties"])

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

