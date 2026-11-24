"""C16 identity rules preserve original observations, offline fixtures only."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from source_identity import group_sources, canonical_report_url


def paper(**kw):
    row = {"source_id": "p", "source_type": "literature", "title": "Education and family",
           "publication": "社会学研究", "publication_date": "2024", "authors": ["Alice Zhang"],
           "doi": "10.1234/example", "original_url": "https://example.org/p",
           "action_ids": ["a"]}
    row.update(kw)
    return row


def report(**kw):
    row = {"source_id": "r", "source_type": "empirical", "title": "A reported event",
           "original_url": "https://example.org/report", "action_ids": ["a"],
           "empirical_material": {"event_or_subject": "same event"}}
    row.update(kw)
    return row


class SourceIdentityTest(unittest.TestCase):
    def test_same_doi_compatible_preserves_observations(self):
        a, b = paper(), paper(source_id="q", original_url="https://other.org/p", action_ids=["b"])
        result = group_sources([a, b])
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual([m["record"] for m in result["groups"][0]["members"]], [a, b])
        self.assertEqual(result["groups"][0]["source_identity"],
                         group_sources([b, a])["groups"][0]["source_identity"])

    def test_doi_conflict_and_different_versions(self):
        conflict = group_sources([paper(), paper(authors=["Different person"])])
        self.assertEqual(len(conflict["quarantined"]), 2)
        self.assertFalse(conflict["groups"])
        different = group_sources([paper(), paper(doi="10.1234/version2", publication_date="2025")])
        self.assertEqual(len(different["groups"]), 2)
        self.assertFalse(different["quarantined"])

    def test_multiple_urls_and_reprint_only_with_reviewed_alias(self):
        a = report()
        b = report(original_url="https://example.org/report?utm_source=feed#paragraph")
        c = report(original_url="https://other.org/reprint")
        d = report(original_url="https://third.org/independent")
        self.assertEqual(len(group_sources([a,b,c,d])["groups"]), 3)
        aliases = {"https://example.org/report": "reviewed-report-1",
                   "https://other.org/reprint": "reviewed-report-1"}
        groups = group_sources([a,b,c,d], reviewed_report_aliases=aliases)["groups"]
        self.assertEqual(sorted(len(g["members"]) for g in groups), [1,3])
        self.assertTrue(all(not g["formal_eligible"] for g in groups))

    def test_url_parameters_and_missing_identity(self):
        self.assertNotEqual(canonical_report_url("https://example.org/p?id=1"),
                            canonical_report_url("https://example.org/p?id=2"))
        self.assertIsNone(canonical_report_url("https://user@example.org/p"))
        groups = group_sources([report(original_url=None), report(source_id="s", original_url=None)])["groups"]
        self.assertEqual(len(groups), 2)


if __name__ == "__main__":
    unittest.main()
