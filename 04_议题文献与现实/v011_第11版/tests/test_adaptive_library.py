from pathlib import Path
import sys
import tempfile
import unittest
from urllib.error import URLError


VERSION = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VERSION / "tools"))
sys.path.insert(0, str(VERSION.parent / "v010_第10版/tests"))

from adaptive_library import receive
from adaptive_acquisition import collect
from collect_common import AccessStop, load
from search_decision import validate_decision
from test_multi_library import CONTENT, Fake, row
from verified_identity import group_verified, resolve


class Model:
    provider_id = "fixture"
    model = "fixture"

    def __init__(self, *rounds):
        self.rounds = list(rounds)
        self.contexts = []

    def decide(self, context):
        self.contexts.append(context)
        return {
            "reason": "Inspect previous coverage",
            "actions": self.rounds.pop(0) if self.rounds else [],
        }, {"request_id": f"fixture-{len(self.contexts)}"}


def action(source="first", query="教育分流", **changes):
    return dict({"source": source, "query": query, "journal": "社会学研究"}, **changes)


class AdaptiveTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.config = load(VERSION / "templates/adaptive_request.json")
        self.config.update(request_budget=10, model_rounds=4, complete_coverage=False)

    def run_job(self, *sources, model, **options):
        bundle = collect(self.config, self.work, providers=sources, decider=model, **options)
        self.assertEqual(receive(self.work)["counts"], bundle["counts"])
        return bundle

    def test_conflicting_detail_author_is_not_admitted(self):
        search_row = row(authors=["张甲"])
        false_detail = dict(search_row, authors=["李乙"], abstract=CONTENT, locator="摘要")
        source = Fake("first", [search_row], abstracts={"1": false_detail})
        bundle = self.run_job(source, model=Model([action()]))
        self.assertEqual(bundle["articles"], [])
        state = load(self.work / "checkpoint.json")
        self.assertTrue(any(r["identity_decision"] == "author_conflict" for r in state["observed"].values()))

    def test_same_doi_with_different_author_or_year_is_quarantined(self):
        for changed in ({"authors": ["李乙"]}, {"year": 2020}):
            with self.subTest(changed=changed):
                a = dict(row(authors=["张甲"], doi="10.1234/shared"), status="valid_abstract")
                b = dict(a, **changed)
                rows, conflicts = group_verified([a, b], [["教育分流"]])
                self.assertEqual(rows, [])
                self.assertIn(conflicts[0]["reason"], {"author_conflict", "year_conflict"})

    def test_partial_authors_use_same_match_in_deduplication(self):
        a = row(authors=["张甲"], ident="1")
        b = row(authors=["张甲", "李乙"], ident="2")
        self.assertEqual(resolve(a, b), "bibliographic")
        bundle = self.run_job(Fake("first", [a]), Fake("second", [b]),
                              model=Model([action(), action("second")]))
        self.assertEqual(bundle["counts"]["unique_valid_abstracts"], 1)
        self.assertEqual(len(bundle["articles"][0]["provenance"]), 2)

    def test_single_author_does_not_bridge_conflicting_teams(self):
        rows = [row(authors=authors, ident=str(n)) for n, authors in enumerate(
            (["张甲", "李乙"], ["张甲"], ["张甲", "赵丙"]), 1
        )]
        result = self.run_job(Fake("first", rows), model=Model([action()]))
        self.assertEqual(result["articles"], [])
        self.assertTrue(result["conflicts"][0]["reason"].startswith("ambiguous_bridge"))

    def test_source_parser_error_does_not_stop_other_source_and_can_recover(self):
        bad = Fake("first", [row()], fail=[ValueError("parser")])
        good = Fake("second", [row()])
        model = Model([action(), action("second")], [action()])
        first = self.run_job(bad, good, model=model, session_requests=2)
        self.assertEqual(first["status"], "paused")
        self.assertEqual(first["source_failures"]["first"], "source_error")
        resumed = self.run_job(bad, good, model=model, resume=True)
        self.assertEqual(resumed["counts"]["unique_valid_abstracts"], 1)
        self.assertEqual(bad.calls["search"], 2)
        self.assertNotIn("first", resumed["source_failures"])

    def test_detail_timeout_is_retried_on_resume_without_repeating_search(self):
        source = Fake("first", [row()], abstracts={"1": URLError("temporary")})
        model = Model([action(), action(query="教育机会")])
        self.run_job(source, model=model, session_requests=2)
        source.abstracts["1"] = CONTENT
        result = self.run_job(source, model=model, resume=True)
        self.assertEqual(result["counts"]["unique_valid_abstracts"], 1)
        self.assertEqual(source.calls["1"], 2)

    def test_access_failure_remains_blocked_and_does_not_consume_budget_again(self):
        blocked = Fake("first", fail=[AccessStop("requires_user_access", "verification")])
        available = Fake("second", [row()])
        model = Model([action(), action("second")])
        self.run_job(blocked, available, model=model, session_requests=1)
        result = self.run_job(blocked, available, model=model, resume=True)
        self.assertEqual(blocked.calls["search"], 1)
        self.assertEqual(result["counts"]["unique_valid_abstracts"], 1)

    def test_budget_can_be_extended_without_model_or_successful_search_replay(self):
        self.config["request_budget"] = 1
        source = Fake("first", [row()])
        model = Model([action()])
        first = self.run_job(source, model=model)
        self.assertEqual(first["status"], "budget_exhausted")
        result = self.run_job(source, model=model, resume=True, add_budget=3)
        self.assertEqual(result["counts"]["unique_relevant_abstracts"], 1)
        self.assertEqual(source.calls["search"], 1)
        self.assertEqual(len(model.contexts), 2)
        self.assertEqual(load(self.work / "checkpoint.json")["budgets"][0]["additional_units"], 3)

    def test_follow_up_decision_receives_results_and_runs_different_query(self):
        source = Fake("first", [row()])
        model = Model([action()], [action(query="阶层再生产")])
        result = self.run_job(source, model=model)
        self.assertEqual(model.contexts[0]["leads"], [])
        self.assertEqual(model.contexts[1]["leads"][0]["title"], row()["title"])
        self.assertEqual(model.contexts[1]["coverage"]["社会学研究"]["unique_relevant"], 1)
        self.assertEqual(source.queries[1][0], "阶层再生产")
        self.assertEqual(result["decisions"][1]["results"][0]["status"], "accessible")

    def test_unregistered_source_url_disguised_as_query_and_false_lead_are_rejected(self):
        context = {"sources": {"first": ["社会学研究"]}, "leads": [], "used": [],
                   "next_pages": [], "unavailable_sources": {}}
        _, actions, rejected = validate_decision({
            "reason": "test", "actions": [action("unknown"),
                action(query="https://arbitrary-site.test"), action(follow_up="unknown"),
                action(page=2)],
        }, context)
        self.assertEqual(actions, [])
        self.assertEqual(len(rejected), 4)

    def test_search_budget_does_not_mark_unreached_journals(self):
        source = Fake("first", [row()])
        result = self.run_job(source, model=Model([action()]))
        self.assertEqual(result["coverage"]["社会学研究"]["search_calls"], 1)
        self.assertEqual(result["coverage"]["中国青年研究"]["search_calls"], 0)
        self.assertFalse(result["target_met"])

    def test_empty_primary_query_has_a_real_alternate(self):
        first, other = Fake("first"), Fake("second", [row()])
        result = self.run_job(first, other, model=Model([action()]))
        self.assertEqual(result["counts"]["unique_relevant_abstracts"], 1)
        self.assertTrue(result["decisions"][0]["results"][0]["fallback_search_id"])

    def test_coverage_probe_records_each_journal_and_never_invents_results(self):
        self.config["complete_coverage"] = True
        result = self.run_job(Fake("first"), model=Model([action()]))
        self.assertEqual(len(result["coverage_sweeps"]), 5)
        self.assertTrue(all(x["search_calls"] == 1 for x in result["coverage"].values()))
        self.assertEqual(result["counts"]["unique_valid_abstracts"], 0)


if __name__ == "__main__":
    unittest.main()
