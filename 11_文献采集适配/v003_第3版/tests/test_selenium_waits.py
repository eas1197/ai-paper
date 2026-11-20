"""Browser-free regressions for asynchronous CNKI page readiness."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from cnki import DEFAULT_SELECTORS, SeleniumCNKI


def row(number):
    return (f'<table class="result-table-list"><tr><td class="name">'
            f'<a class="fz14" href="/detail?FileName=TEST{number}">TEST{number}</a>'
            '</td></tr></table><a id="PageNext">下一页</a>')


class BrowserWaitTests(unittest.TestCase):
    def browser(self, driver):
        browser = SeleniumCNKI.__new__(SeleniumCNKI)
        browser.driver = driver
        browser.settings = {"element_timeout_seconds": 2}
        browser.sel = DEFAULT_SELECTORS.copy()
        browser.search_handle = "search"
        browser._pace = lambda: None
        browser._check = lambda: None
        return browser

    def test_pagination_ignores_unrelated_dom_change_until_new_records(self):
        class Driver:
            current_url = "https://kns.cnki.net/search"
            def __init__(self):
                self.clicked = False
                self.reads = 0
                self.switch_to = SimpleNamespace(window=lambda handle: None)
            @property
            def page_source(self):
                if not self.clicked:
                    return row(1)
                self.reads += 1
                return row(1) + '<span>clock changed</span>' if self.reads == 1 else row(2)
            def find_elements(self, by, selector):
                return [SimpleNamespace(click=lambda: setattr(self, "clicked", True))]
        driver = Driver()
        page = self.browser(driver).search("TEST", cursor=2)
        self.assertEqual(page["records"][0]["source_record_id"], "TEST2")
        self.assertGreaterEqual(driver.reads, 2)

    def test_detail_waits_for_abstract_and_download_instead_of_title(self):
        driver = SimpleNamespace(page_source='<meta name="citation_title" content="TEST">',
                                 current_url="https://kns.cnki.net/detail?FileName=TEST")
        browser = self.browser(driver)
        browser._detail = lambda url: None
        record = {"url": driver.current_url, "title": "TEST"}
        waits = []
        def ready(selectors):
            waits.append(selectors)
            if DEFAULT_SELECTORS["abstract"] in selectors:
                driver.page_source += '<span id="ChDivSummary">摘要：TEST delayed abstract</span>'
            if DEFAULT_SELECTORS["download"] in selectors:
                driver.page_source += '<a id="pdfDown" href="/pdf">PDF</a>'
            return True
        with patch.object(browser, "_optional_ready", side_effect=ready):
            self.assertEqual(browser.fetch_abstract(record)["abstract"], "TEST delayed abstract")
            self.assertEqual(browser.resolve_fulltext(record)[0]["url"], "https://kns.cnki.net/pdf")
        self.assertNotIn(DEFAULT_SELECTORS["detail_title"], waits[0])
        self.assertEqual(waits[1], [DEFAULT_SELECTORS["download"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
