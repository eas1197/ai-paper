from pathlib import Path
import sys
import tempfile
import unittest
from collections import Counter
from urllib.error import URLError

VERSION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERSION / "tools"))
from multi_library import receive
from multi_acquisition import SEEDS, canonical_journal, collect, resolve
from collect_common import AccessStop, load
from cnki import soup
from vip_public import serialized

CONTENT = "本文围绕教育分流的长期作用分析家庭资源及教育机会，对样本和方法开展稳健分析，并在总结部分讨论制度条件与适用范围。"
TITLE = "教育分流与阶层再生产"


def row(
    title=TITLE,
    journal="社会学研究",
    authors=None,
    year=2021,
    ident="1",
    doi=None,
    host="public.test",
):
    return dict(
        title=title,
        journal=journal,
        authors=authors if authors is not None else ["王·某"],
        year=year,
        doi=doi,
        source_record_id=ident,
        url=f"https://{host}/article/{ident}",
    )


class Fake:
    def __init__(
        self, provider_id, records=(), *, abstracts=None, fail=None, journals=SEEDS
    ):
        self.provider_id, self.journals = provider_id, journals
        self.records = list(records)
        self.abstracts = abstracts or {}
        self.fail = list(fail or ())
        self.calls = Counter()
        self.queries = []

    def search(self, query, journal, year, page, **kwargs):
        self.calls["search"] += 1
        self.queries.append((query, journal, page))
        if self.fail:
            planned = self.fail.pop(0)
            if planned:
                raise planned
        return {
            "records": self.records,
            "has_next": False,
            "url": "https://public.test/search",
        }

    def fetch_abstract(self, record):
        self.calls[record["source_record_id"]] += 1
        info = self.abstracts.get(record["source_record_id"], CONTENT)
        if isinstance(info, BaseException):
            raise info
        if isinstance(info, dict):
            return info
        return dict(
            record, abstract=info, locator="article abstract", keywords=["文化资本"]
        )

    def resolve_fulltext(self, *_):
        raise AssertionError("Full text is forbidden")

    download = resolve_fulltext


class TestMultiLibrary(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "job"
        self.config = load(VERSION / "templates/multi_request.json")
        self.config.update(request_budget=60, max_queries=2, first_pass_from_year=None)

    def run_multi(self, *sources, seeds=(), resume=False):
        bundle = collect(
            self.config, self.path, providers=list(sources), seeds=seeds, resume=resume
        )
        matrix = receive(self.path)
        self.assertEqual(bundle["counts"], matrix["counts"])
        self.assertEqual(bundle["usage"]["fulltext_requests"], 0)
        self.assertEqual(bundle["usage"]["pdf_requests"], 0)
        return bundle, matrix

    def test_identity_rules(self):
        a = row(doi="https://doi.org/10.1234/first")
        self.assertEqual(
            resolve(a, row(doi="10.1234/FIRST", title=TITLE + "：专题")), "doi"
        )
        self.assertEqual(resolve(row(), row(authors=["王某"])), "bibliographic")
        self.assertEqual(
            resolve(row(), row(authors=["他人"])), "author_year_unconfirmed"
        )
        self.assertEqual(resolve(row(), row(year=2020)), "year_conflict")
        self.assertEqual(resolve(a, row(doi="10.1234/second")), "doi_conflict")
        self.assertEqual(
            resolve(row(), row(title="教育分流与阶层再生")), "title_unconfirmed"
        )
        self.assertEqual(
            resolve(row(), row(journal="青年研究")),
            "different_journal_or_missing_identity",
        )
        self.assertEqual(
            canonical_journal(dict(journal="Sociological Studies", issn="1002-5936")),
            "社会学研究",
        )
        self.assertIsNone(canonical_journal(dict(journal="中国青年研究", issn="wrong")))
        self.assertEqual(canonical_journal(dict(journal="青年研究")), "青年研究")

    def test_discovery_cross_source_selection_and_versions(self):
        a = row(ident="vip", doi="10.1234/a")
        b = row(ident="official", host="journal.test", doi="10.1234/a")
        primary = Fake("journal_shxyj_public", [], journals=("社会学研究",))

        def official_search(query, journal, year, page):
            primary.queries.append((query, journal, page))
            return {
                "records": [b] if query == TITLE else [],
                "has_next": False,
                "url": "https://journal.test/search",
            }

        primary.search = official_search
        other = Fake(
            "vip_public", [a], abstracts={"vip": CONTENT + "来源措辞另有补充。"}
        )
        bundle, matrix = self.run_multi(primary, other)
        (article,) = matrix["rows"]
        self.assertEqual(article["source"], "journal_shxyj_public")
        self.assertEqual(len(article["abstract_variant_hashes"]), 2)
        self.assertEqual(
            {x["provider"] for x in article["provenance"]},
            {"vip_public", "journal_shxyj_public"},
        )
        self.assertTrue(
            any(
                x["abstract_source"] == "journal_shxyj_public"
                and x["discovery_source"] == "vip_public"
                and x.get("abstract_status") == "valid_abstract"
                for x in bundle["resolutions"]
            )
        )
        self.assertEqual(primary.calls["official"], 1)
        self.assertEqual(other.calls["vip"], 1)

    def test_source_block_and_retry_then_recovery(self):
        blocked = Fake(
            "cnki_normal_selenium", fail=[AccessStop("requires_user_access", "blocked")]
        )
        other = Fake("vip_public", [row()], fail=[URLError("timeout"), None])
        bundle, _ = self.run_multi(blocked, other)
        self.assertEqual(blocked.calls["search"], 1)
        self.assertEqual(
            bundle["source_failures"]["cnki_normal_selenium"], "requires_user_access"
        )
        self.assertEqual(set(bundle["attempted_journals"]), set(SEEDS))
        self.assertEqual(bundle["counts"]["unique_relevant_abstracts"], 1)
        self.assertTrue(
            any(x["reason"] == "verified_article_term" for x in bundle["expansion"])
        )

    def test_layout_error_and_missing_abstract(self):
        earlier = Fake(
            "journal_shxyj_public", fail=[AccessStop("layout_changed", "changed")]
        )
        other = Fake(
            "vip_public",
            [row(ident="1"), row(title="教育分流机会差异", ident="2")],
            abstracts={"1": None},
        )
        bundle, matrix = self.run_multi(earlier, other)
        self.assertEqual(
            bundle["source_failures"]["journal_shxyj_public"], "layout_changed"
        )
        self.assertEqual(len(matrix["rows"]), 1)
        self.assertIn("missing_abstract", bundle["observation_statuses"].values())

    def test_article_detail_restriction_does_not_block_whole_source(self):
        source = Fake(
            "vip_public",
            [row(ident="1"), row(title="教育分流机会差异", ident="2")],
            abstracts={"1": AccessStop("requires_user_access", "article only")},
        )
        bundle, matrix = self.run_multi(source)
        self.assertEqual(bundle["source_failures"], {})
        self.assertEqual(len(matrix["rows"]), 1)
        self.assertIn("requires_user_access", bundle["observation_statuses"].values())

    def test_history_is_search_input_and_out_of_scope_is_preserved(self):
        a = row()
        b = row("完全找不到的文章", ident="2")
        off = row(journal="青年研究")
        seed = [a, b, off]
        source = Fake("vip_public", [a])
        _, matrix = self.run_multi(source, seeds=seed)
        out = load(self.path / "historical_regression.json")
        self.assertEqual(
            [x["status"] for x in out], ["recovered", "not_verified", "out_of_scope"]
        )
        self.assertEqual(len(matrix["rows"]), 1)
        self.assertTrue(any(q == a["title"] for q, j, n in source.queries))

    def test_resume_and_budgets(self):
        source = Fake("vip_public", [row()], fail=[KeyboardInterrupt(), None])
        a, _ = self.run_multi(source)
        self.assertEqual(a["status"], "interrupted")
        b, _ = self.run_multi(source, resume=True)
        self.assertEqual(a["collection_id"], b["collection_id"])
        self.assertEqual(source.calls["1"], 1)
        self.assertLessEqual(len(b["expansion"]), self.config["max_queries"])
        self.assertLessEqual(b["usage"]["budget_units"], self.config["request_budget"])

    def test_vip_only_public_serialized_literals(self):
        simple = 'window.__NUXT__=(function(a,b){return {data:[{resData:{title:a,year:b}}]}}("题名",2021));'
        self.assertEqual(
            serialized(soup("<script>" + simple + "</script>"))["resData"],
            {"title": "题名", "year": 2021},
        )
        bad = 'window.__NUXT__=(function(a){return {data:[{resData:a}]}}(fetch("https://evil.test")));'
        with self.assertRaises(ValueError):
            serialized(soup("<script>" + bad + "</script>"))

    def test_scope_and_target_with_multiple_topics(self):
        self.config.update(request_budget=230, max_queries=5)
        source = Fake("vip_public")

        def discovery(query, journal, year, page, **kwargs):
            source.queries.append((query, journal, page))
            number = len(source.queries)
            return dict(
                records=[
                    row(
                        title=f"教育分流与机会实证研究{number:02}-{i}",
                        journal=journal,
                        ident=f"{number:02}-{i}",
                    )
                    for i in range(4)
                ],
                has_next=False,
                url="https://public.test/search",
            )

        source.search = discovery
        bundle, _ = self.run_multi(source)
        self.assertEqual(bundle["status"], "target_reached")
        self.assertEqual(bundle["counts"]["unique_relevant_abstracts"], 100)
        self.assertEqual(set(bundle["attempted_journals"]), set(SEEDS))

    def test_public_real_author_delimiter_merges_without_doi(self):
        title = "中国城乡居民的中学教育分流与职业地位获得"
        p = row(title, authors=["王威海 顾源"], year=2012, ident="publisher")
        v = row(title, authors=["王威海", "顾源"], year=2012, ident="vip")
        self.assertEqual(resolve(p, v), "bibliographic")
        one = Fake("journal_shxyj_public", [p], journals=("社会学研究",))
        two = Fake("vip_public", [v])
        bundle, matrix = self.run_multi(one, two)
        self.assertEqual(bundle["counts"]["unique_relevant_abstracts"], 1)
        (article,) = matrix["rows"]
        self.assertEqual(article["authors"], ["王威海", "顾源"])
        self.assertEqual(len(article["provenance"]), 2)

    def test_similar_journal_is_not_admitted(self):
        outsiders = {"青年研究", "中国青年社会科学"}
        source = Fake(
            "vip_public",
            [row(journal=j, ident=str(i)) for i, j in enumerate(outsiders)],
        )
        bundle, matrix = self.run_multi(source)
        self.assertEqual(matrix["rows"], [])
        self.assertTrue(any(p["records"] for p in bundle["searches"]))


if __name__ == "__main__":
    unittest.main()
