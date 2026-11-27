import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from urllib.error import URLError

VERSION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERSION / "tools"))
from abstract_library import load_candidate, receive
collect = load_candidate()
from abstract_acquisition import SEEDS, prepare, text_hash
from collect_common import AccessStop, load, write

RAW = ("  本文以教育分流与教育分层为研究对象，比较不同教育轨道的机会差异，\n"
       "说明样本的选择条件并检验家庭背景如何影响升学机会，报告不同群体的结果与研究范围。  ")


def paper(i, journal=None, *, doi=None):
    return dict(title=f"教育分流研究{i:04d}", authors=["王某"], journal=journal or SEEDS[0],
                year="2021", doi=doi, url=f"https://example.test/article/{i}", source_record_id=str(i))


class Source:
    journals = SEEDS

    def __init__(self, pages, details=None, source="fixture"):
        self.provider_id = source
        self.pages = pages
        self.details = details or {}
        self.calls = Counter()
        self.log = []

    def search(self, query, journal, year_min, page):
        self.calls["search"] += 1
        self.log.append((query, journal, year_min, page))
        result = self.pages.get((query, journal, page), [])
        if isinstance(result, BaseException):
            raise result
        return {"records": result, "has_next": (query, journal, page + 1) in self.pages,
                "url": "https://example.test/search"}

    def fetch_abstract(self, record):
        key = record["url"]
        self.calls[key] += 1
        response = self.details.get(key, RAW)
        if isinstance(response, list):
            response = response.pop(0) if len(response) > 1 else response[0]
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, dict):
            return response
        return dict(record, abstract=response, locator="abstract")

    def resolve_fulltext(self, *_):
        self.calls["fulltext"] += 1
        raise AssertionError("abstract path tried to resolve fulltext")

    def download(self, *_):
        self.calls["download"] += 1
        raise AssertionError("abstract path tried to download")


class TestAbstractLibrary(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name) / "job"
        self.config = load(VERSION / "templates/abstract_request.json")
        self.config.update(max_queries=4, max_pages=2, first_pass_from_year=None)

    def run_source(self, *sources, resume=False):
        collection = collect(self.config, self.work, list(sources), resume=resume)
        matrix = receive(self.work)
        self.assertEqual(matrix["collection_id"], collection["collection_id"])
        self.assertEqual(matrix["counts"], collection["counts"])
        self.assertFalse(any(s.calls["fulltext"] or s.calls["download"] for s in sources))
        return collection, matrix

    def pages(self, rows):
        return {("教育分流", SEEDS[0], 1): rows}

    def test_normal_raw_and_matrix(self):
        result, matrix = self.run_source(Source(self.pages([paper(1)])))
        row, = matrix["rows"]
        self.assertEqual(row["raw_abstract"], RAW)
        self.assertEqual(row["raw_hash"], text_hash(RAW))
        self.assertNotEqual(row["abstract_text"], RAW)
        self.assertEqual(row["analysis_status"], "not_analyzed")
        self.assertEqual(result["usage"]["fulltext_requests"], 0)
        self.assertEqual(result["usage"]["pdf_requests"], 0)
        self.assertNotIn("fulltext_locator", row)
        data = load(self.work / "abstract_collection.json")
        data["articles"][0]["raw_abstract"] += "改变"
        write(self.work / "abstract_collection.json", data)
        with self.assertRaises(ValueError):
            receive(self.work)

    def test_empty_missing_noise_truncated_wrong_identity_and_off_scope(self):
        rows = [paper(i) for i in range(1, 8)] + [paper(8, "其他期刊")]
        details = {r["url"]: value for r, value in zip(rows, [
            "", {**paper(2), "locator": "abstract"}, "首页：导航、首页、栏目、请选择、登录后查看摘要",
            RAW + "……", dict(paper(5), title="不同题目", abstract=RAW, locator="abstract"),
            dict(paper(6), journal=SEEDS[1], abstract=RAW, locator="abstract"),
            dict(paper(7), abstract=RAW, locator="abstract", year="1990")])}
        source = Source(self.pages(rows), details)
        result, matrix = self.run_source(source)
        self.assertEqual(result["counts"]["retrieved_records"], 8)
        self.assertEqual(matrix["rows"], [])
        self.assertEqual(source.calls[rows[-1]["url"]], 0)
        self.assertIn("identity_mismatch", result["observation_statuses"].values())
        self.assertIn("missing_abstract", result["observation_statuses"].values())
        self.assertIn("invalid_abstract", result["observation_statuses"].values())

    def test_doi_and_bibliographic_merges_preserve_sources(self):
        first = paper(1, doi="https://doi.org/10.1234/study1")
        second = paper(2)
        source_a = Source(self.pages([first, second]), source="a")
        other_first = dict(first, url="https://example.test/a", source_record_id="a", doi="10.1234/STUDY1")
        other_second = dict(second, url="https://example.test/b", source_record_id="b")
        source_b = Source(self.pages([other_first, other_second]), source="b")
        result, matrix = self.run_source(source_a, source_b)
        self.assertEqual(result["counts"]["valid_source_abstracts"], 4)
        self.assertEqual(result["counts"]["unique_relevant_abstracts"], 2)
        self.assertTrue(all(len(row["provenance"]) == 2 for row in matrix["rows"]))
        self.assertTrue(all(row["dedup_status"] == "merged_sources" for row in matrix["rows"]))

    def test_conflicting_doi_is_quarantined(self):
        one = paper(1, doi="10.1234/one")
        two = dict(one, url="https://example.test/other", doi="10.1234/two", source_record_id="other")
        result, matrix = self.run_source(Source(self.pages([one, two])))
        self.assertEqual(matrix["rows"], [])
        self.assertEqual(len(result["conflicts"]), 1)

    def test_source_access_failure_and_alternative(self):
        blocked = Source({("教育分流", SEEDS[0], 1): AccessStop("requires_user_access", "fixture")}, source="blocked")
        result, _ = self.run_source(blocked, Source(self.pages([paper(1)]), source="public"))
        self.assertEqual(result["source_failures"], {"blocked": "requires_user_access"})
        self.assertEqual(result["counts"]["unique_relevant_abstracts"], 1)
        self.assertEqual(blocked.calls["search"], 1)

    def test_pagination_and_query_expansion(self):
        self.config["first_pass_from_year"] = 2022
        query = prepare(self.config)["queries"][1]
        one, two = paper(1), paper(2)
        pages = self.pages([one])
        pages[("教育分流", SEEDS[0], 2)] = [two]
        pages[(query, SEEDS[0], 1)] = [one, paper(3)]
        source = Source(pages)
        result, _ = self.run_source(source)
        self.assertEqual(result["counts"]["unique_relevant_abstracts"], 3)
        self.assertIn(("教育分流", SEEDS[0], 2022, 2), source.log)
        self.assertNotIn(("教育分流", SEEDS[0], None, 1), source.log)
        self.assertTrue(any(entry.get("reused_search_id") for entry in result["searches"]))
        self.assertEqual(source.calls[one["url"]], 1)

    def test_network_retry_and_resume(self):
        one, two = paper(1), paper(2)
        source = Source(self.pages([one, two]), {
            one["url"]: [URLError("network interruption"), RAW],
            two["url"]: [KeyboardInterrupt(), RAW],
        })
        interrupted, _ = self.run_source(source)
        self.assertEqual(interrupted["status"], "interrupted")
        self.assertEqual(interrupted["counts"]["unique_relevant_abstracts"], 1)
        before = source.calls["search"]
        resumed, _ = self.run_source(source, resume=True)
        self.assertEqual(resumed["collection_id"], interrupted["collection_id"])
        self.assertEqual(resumed["counts"]["unique_relevant_abstracts"], 2)
        self.assertEqual(source.calls[one["url"]], 2)
        self.assertIn("interrupted_unknown", [v["status"] for v in load(self.work / "checkpoint.json")["requests"]])
        self.assertEqual(source.log[:before], [("教育分流", SEEDS[0], None, 1)])

    def test_100_and_pdf_endpoint_unavailable(self):
        rows = [paper(i) for i in range(100)]
        source = Source(self.pages(rows))
        result, _ = self.run_source(source)
        self.assertEqual(result["status"], "target_reached")
        self.assertEqual(result["counts"]["unique_relevant_abstracts"], 100)
        self.assertTrue(result["target_met"])
        self.assertTrue(set(SEEDS) <= {entry[1] for entry in source.log})

    def test_99_repeated_missing_and_nonrelevant_do_not_fill_gap(self):
        rows = [paper(i) for i in range(99)]
        no_abstract = [paper(i) for i in range(100, 125)]
        unrelated = dict(paper(126), title="城市就业统计")
        details = {r["url"]: None for r in no_abstract}
        details[unrelated["url"]] = "本文基于就业登记资料考察居民职业结构的区域关系，描述不同产业就业人口的分布以及经济周期内劳动力参与率的长期变化。"
        source = Source(self.pages(rows + rows + no_abstract + [unrelated]), details)
        result, matrix = self.run_source(source)
        self.assertEqual(result["status"], "search_plan_exhausted")
        self.assertEqual(result["counts"]["retrieved_records"], 224)
        self.assertEqual(result["counts"]["unique_valid_abstracts"], 100)
        self.assertEqual(result["counts"]["unique_relevant_abstracts"], 99)
        self.assertEqual(matrix["gap"], 1)
        self.assertTrue(any(q != "教育分流" for q, _, _, _ in source.log))
        self.assertTrue(all(source.calls[r["url"]] == 1 for r in rows))

    def test_budget_and_retry_limit(self):
        self.config.update(request_budget=3, max_retries=1)
        one = paper(1)
        result, _ = self.run_source(Source(self.pages([one]), {one["url"]: URLError("timeout")}))
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(result["usage"]["budget_units"], 3)
        self.assertEqual(result["usage"]["abstract_calls"], 2)
        self.assertIn("retry_limit", result["observation_statuses"].values())

    def test_search_expansion_does_not_relax_relevance(self):
        self.config["theme"] = "性别与教育分流"
        spec = prepare(self.config)
        self.assertIn(["性别"], spec["relevance_groups"])
        self.assertNotIn("教育机会", spec["relevance_groups"][-1])
        source = Source({("性别与教育分流", SEEDS[0], 1): [paper(1)]})
        result, _ = self.run_source(source)
        self.assertEqual(result["counts"]["unique_valid_abstracts"], 1)
        self.assertEqual(result["counts"]["unique_relevant_abstracts"], 0)

    def test_bounded_pause_retains_already_saved_source(self):
        source = Source(self.pages([paper(1), paper(2)]))
        first = collect(self.config, self.work, [source], session_requests=2)
        self.assertEqual(first["status"], "paused")
        final, _ = self.run_source(source, resume=True)
        self.assertEqual(final["collection_id"], first["collection_id"])
        self.assertEqual(final["counts"]["unique_valid_abstracts"], 2)
        self.assertEqual(source.calls[paper(1)["url"]], 1)

    def test_pdf_url_is_never_requested(self):
        offered = dict(paper(1), url="https://example.test/offered.pdf")
        source = Source(self.pages([offered]))
        result, matrix = self.run_source(source)
        self.assertEqual(result["counts"]["retrieved_records"], 1)
        self.assertEqual(source.calls[offered["url"]], 0)
        self.assertEqual(matrix["rows"], [])

    def test_production_directory_refused_without_writing(self):
        self.work.mkdir()
        (self.work / "legacy.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            collect(self.config, self.work, [Source({})])
        self.assertEqual([f.name for f in self.work.iterdir()], ["legacy.json"])

    def test_reject_legacy_and_wrong_resume(self):
        with self.assertRaises(ValueError):
            prepare(dict(self.config, core_target=25))
        with self.assertRaises(ValueError):
            prepare(dict(self.config, download_pdf=True))
        source = Source(self.pages([paper(1)]))
        self.run_source(source)
        with self.assertRaises(FileExistsError):
            self.run_source(source)
        with self.assertRaises(ValueError):
            collect(dict(self.config, theme="其他主题"), self.work, [source], resume=True)


if __name__ == "__main__":
    unittest.main()
