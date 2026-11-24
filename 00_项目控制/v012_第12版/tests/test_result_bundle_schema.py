"""C11 shared result identity and separate provenance; structure only."""
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/result_bundle.schema.json"


def provenance(kind):
    if kind == "chat_native_web":
        return {"kind": kind, "record_refs": [], "citation_refs": [], "missing_fields": ["raw_tool_log"]}
    if kind == "codex_cli":
        return {"kind": kind, "command": None, "thread_id": None, "exit_code": None,
                "events": None, "response": None, "stderr": None, "prompt": None,
                "schema": None, "login": None, "missing_fields": ["not_executed"]}
    return {"kind": kind, "submitter": None, "submitted_at": None, "source_type": "uploaded_file",
            "verification_status": "unverified", "original_files": [], "missing_fields": ["submitter"]}


def result(kind="chat_native_web"):
    return {"schema_version": 1,
            "task_snapshot": {"research_id": "fixture", "stage_id": "initial",
                              "task_id": "fixture_001", "snapshot_sha256": "a" * 64},
            "executor": kind, "provenance": provenance(kind),
            "execution_time": {"started_at": None, "finished_at": None},
            "search_actions": [], "sources": [], "failure_reasons": ["Offline fixture"]}

def source():
    return {
        "source_id": "fixture-source", "source_type": "literature",
        "original_url": "https://example.org/paper", "metadata_url": "https://example.org/paper",
        "abstract_url": "https://example.org/abstract", "title": "Fixture paper",
        "authors": ["Fixture author"], "publication": "Fixture journal",
        "publication_date": "2024", "doi": None, "abstract_locator": "Abstract section",
        "open_status": "opened", "excerpt": "Synthetic excerpt", "paraphrase": "Fixture paraphrase",
        "relevance_reason": "Fixture rationale", "dedup_key": "fixture-key",
        "limits": ["Not actual evidence"], "failure_reasons": [], "action_ids": ["open-1"],
        "literature_stages": {"discovery_status": "discovered", "abstract_read_status": "unknown",
                              "fulltext_read_status": "not_read", "formal_inclusion_status": "pending_original_gate"},
        "empirical_material": None,
    }


def empirical_source():
    return dict(source(), source_type="empirical", literature_stages=None,
                empirical_material={
                    "source_description": "Offline report fixture",
                    "event_or_subject": "Reported action in a fixture",
                    "event_date": "2024-01", "locator": "Paragraph 2",
                    "content_type": "reporter_account", "context": "Fixture context",
                    "collection_path": "online_qualitative", "access": "Fixture only",
                    "verifiable_facts": [{"statement": "An action was reported",
                        "locator": "Paragraph 2", "status": "reported",
                        "limits": ["Report is not independent corroboration"]}],
                    "researcher_interpretations": ["Possible coordination mechanism"],
                    "unsupported_judgments": ["Actual prevalence and causal effect"],
                })


def search_action():
    return {"action_id": "open-1", "action_type": "open_page",
            "occurred_at": "2026-11-24T00:00:00Z", "query": None,
            "original_url": "https://example.org/abstract", "record_locator": "fixture locator",
            "source_ids": ["fixture-source"], "failure_reason": None}


class ResultEnvelopeTest(unittest.TestCase):
    def setUp(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def test_common_identity_and_executor_variants(self):
        for kind in ("chat_native_web", "codex_cli", "manual"):
            sample = result(kind)
            self.validator.validate(sample)
            for key in ("research_id", "stage_id", "task_id", "snapshot_sha256"):
                broken = result(kind)
                del broken["task_snapshot"][key]
                self.assertFalse(self.validator.is_valid(broken))

    def test_cross_executor_provenance_rejected(self):
        for source in ("chat_native_web", "codex_cli", "manual"):
            for target in ("chat_native_web", "codex_cli", "manual"):
                if source != target:
                    self.assertFalse(self.validator.is_valid(
                        dict(result(source), provenance=provenance(target))))
        chat = result()
        chat["provenance"]["thread_id"] = "fabricated"
        self.assertFalse(self.validator.is_valid(chat))
        cli = result("codex_cli")
        cli["provenance"]["citation_refs"] = ["chat-only"]
        self.assertFalse(self.validator.is_valid(cli))

    def test_no_self_asserted_formal_pass(self):
        self.assertFalse(self.validator.is_valid(dict(result(), formal_eligible=True)))
        self.assertFalse(self.validator.is_valid(dict(result(), executor="human")))

    def test_c12_all_result_fields(self):
        sample = dict(result(), sources=[source()], search_actions=[search_action()],
                      execution_time={"started_at": "2026-11-24T00:00:00Z",
                                      "finished_at": "2026-11-24T00:01:00Z"})
        self.validator.validate(sample)
        for key in source():
            broken = source()
            del broken[key]
            self.assertFalse(self.validator.is_valid(dict(result(), sources=[broken])))

    def test_c12_missing_and_failed_sources_are_representable(self):
        item = source()
        for key in ("original_url", "metadata_url", "abstract_url", "title", "publication",
                    "publication_date", "abstract_locator", "excerpt", "paraphrase",
                    "relevance_reason", "dedup_key"):
            item[key] = None
        item.update(authors=[], open_status="unknown", action_ids=[],
                    failure_reasons=["Unable to access source"])
        self.validator.validate(dict(result(), sources=[item]))
        self.validator.validate(result("manual"))
        self.assertFalse(self.validator.is_valid(dict(result(), sources=[dict(item, open_status=True)])))

    def test_c12_time_and_action_contract(self):
        sample = dict(result(), search_actions=[search_action()])
        self.validator.validate(sample)
        self.assertFalse(self.validator.is_valid(dict(sample, execution_time={
            "started_at": "yesterday", "finished_at": None})))
        self.assertFalse(self.validator.is_valid(dict(sample, search_actions=[
            dict(search_action(), action_type="invented_tool")])))

    def test_c13_literature_stages_independent(self):
        item = source()
        stages = item["literature_stages"]
        # Opened does not assert reading or inclusion.
        self.validator.validate(dict(result(), sources=[item]))
        self.assertEqual(item["open_status"], "opened")
        self.assertEqual(stages["abstract_read_status"], "unknown")
        self.assertEqual(stages["fulltext_read_status"], "not_read")
        for key in stages:
            broken = dict(stages)
            del broken[key]
            self.assertFalse(self.validator.is_valid(dict(result(), sources=[
                dict(item, literature_stages=broken)])))
        sample = dict(stages, abstract_read_status="read", fulltext_read_status="read")
        self.validator.validate(dict(result(), sources=[dict(item, literature_stages=sample)]))
        self.assertEqual(sample["formal_inclusion_status"], "pending_original_gate")

    def test_c13_no_executor_self_reported_inclusion(self):
        item = source()
        stages = dict(item["literature_stages"], formal_inclusion_status="included")
        for kind in ("chat_native_web", "codex_cli", "manual"):
            self.assertFalse(self.validator.is_valid(dict(result(kind), sources=[
                dict(item, literature_stages=stages)])))
        self.assertFalse(self.validator.is_valid(dict(result(), sources=[
            dict(item, literature_stages=None)])))
        empirical = empirical_source()
        self.validator.validate(dict(result(), sources=[empirical]))
        self.assertFalse(self.validator.is_valid(dict(result(), sources=[
            dict(empirical, literature_stages=item["literature_stages"])])))

    def test_c14_empirical_fields_separate_fact_and_interpretation(self):
        item = empirical_source()
        material = item["empirical_material"]
        self.validator.validate(dict(result(), sources=[item]))
        for key in material:
            broken = dict(material)
            del broken[key]
            self.assertFalse(self.validator.is_valid(dict(result(), sources=[
                dict(item, empirical_material=broken)])))
        self.assertFalse(self.validator.is_valid(dict(result(), sources=[
            dict(item, empirical_material=dict(material, content_type="researcher_inference"))])))
        self.assertFalse(self.validator.is_valid(dict(result(), sources=[
            dict(item, empirical_material=dict(material, verifiable_facts=["An interpretation"]))])))

    def test_c14_missing_material_and_self_verified_fact_rejected_or_pending(self):
        item = empirical_source()
        material = item["empirical_material"]
        self.assertFalse(self.validator.is_valid(dict(result(), sources=[
            dict(item, empirical_material=None)])))
        fact = dict(material["verifiable_facts"][0], status="verified")
        self.assertFalse(self.validator.is_valid(dict(result(), sources=[
            dict(item, empirical_material=dict(material, verifiable_facts=[fact]))])))
        missing = dict(material, event_date=None, locator=None, content_type="unknown",
                       verifiable_facts=[], researcher_interpretations=[],
                       unsupported_judgments=["No accessible evidence"])
        self.validator.validate(dict(result(), sources=[dict(item, empirical_material=missing)]))
        self.assertFalse(self.validator.is_valid(dict(result(), sources=[
            dict(source(), empirical_material=material)])))


if __name__ == "__main__":
    unittest.main()
