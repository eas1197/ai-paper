"""Deterministic TEST fixtures; no CNKI account, CAPTCHA, or research downloads."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from acquisition import collect, plan
from collect_common import AccessStop, load, sha, write, article_id
from cnki import access_state, result_page, metadata, verify_pdf
from context_web import collect_context, extract_primary

def config(**kwargs):
    return dict({"theme": "TEST主题", "issue": "TEST议题", "queries": ["TEST查询"], "journals": ["TEST期刊"], "access_basis": "TEST自造材料", "max_pages_per_query": 2, "max_records": 250}, **kwargs)

def record(i):
    return {"title": f"TEST论文{i}", "authors": ["TEST作者"], "journal": "TEST期刊", "year": "2025", "source_record_id": f"TEST_FILE_{i}", "url": f"https://example.invalid/{i}"}

class Provider:
    provider_id = "TEST_fixture"
    def __init__(self, count=100, block=None, invalid=False):
        self.count=count; self.block=block; self.invalid=invalid; self.downloads=0; self.pages=[]; self.detail_reads=0
    def search(self, query, cursor=None):
        self.pages.append(cursor)
        start = 0 if cursor is None else 50
        return {"records": [record(i) for i in range(start, min(start+50, self.count))], "has_next": start+50 < self.count, "empty_confirmed": self.count==0}
    def fetch_abstract(self, r):
        self.detail_reads += 1
        if self.block == "abstract": raise AccessStop("requires_user_access", "TEST需要正常访问")
        return {"abstract": r["title"] + " TEST摘要：资源与结果的关系。"}
    def download(self, r, destination):
        self.downloads += 1
        if self.block == "pdf": raise AccessStop("requires_user_access", "TEST下载需要正常访问")
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(b"<html>login</html>" if self.invalid else b"%PDF-TEST\n" + (r["title"]+" TEST作者\fTEST结果与参考文献").encode())
        return {"status": "file_received", "path": str(destination)}
    def close(self): pass

def fake_pdf(path): return Path(path).read_bytes().decode().split("\n", 1)[1].split("\f")

class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.work = Path(self.temp.name)/"job"

    def test_hundred_abstracts_all_downloads_but_no_read_claim(self):
        p = Provider()
        result = collect(config(), self.work, p, pdf_reader=fake_pdf)
        self.assertEqual(result["status"], "collected")
        self.assertEqual(result["counts"], {"metadata": 100, "abstracts_available":100, "fulltexts_verified":100, "abstracts_read":0, "fulltexts_read":0})
        self.assertEqual(p.pages, [None, 2])
        self.assertFalse(result["business_gate_passed"])
        self.assertTrue(all(r["abstract_read_status"] == "not_read" for r in load(self.work/"literature/metadata/papers.json")))

    def test_resume_reuses_verified_files_and_does_not_duplicate_records(self):
        p=Provider(); collect(config(), self.work, p, pdf_reader=fake_pdf)
        before = sha(next((self.work/"literature/fulltext").glob("*.pdf")))
        resumed = Provider(); result=collect(config(), self.work, resumed, resume=True, pdf_reader=fake_pdf)
        self.assertEqual(result["counts"]["metadata"],100); self.assertEqual(resumed.downloads,0)
        self.assertEqual(before,sha(next((self.work/"literature/fulltext").glob("*.pdf"))))

    def test_captcha_stops_without_refresh_or_discarding_abstracts(self):
        p=Provider(block="pdf"); result=collect(config(),self.work,p,pdf_reader=fake_pdf)
        self.assertEqual(result["status"],"requires_user_access"); self.assertEqual(p.downloads,1)
        self.assertEqual(result["counts"]["abstracts_available"],100)
        result=collect(config(),self.work,Provider(),resume=True,pdf_reader=fake_pdf)
        self.assertEqual(result["counts"]["fulltexts_verified"],100)

    def test_abstract_challenge_preserves_metadata_then_resume_fetches(self):
        result=collect(config(download_scope="none"),self.work,Provider(block="abstract"),pdf_reader=fake_pdf)
        self.assertEqual(result["counts"]["metadata"],1)
        result=collect(config(download_scope="none"),self.work,Provider(),resume=True,pdf_reader=fake_pdf)
        self.assertEqual(result["counts"]["abstracts_available"],100)

    def test_html_disguised_pdf_does_not_count_success(self):
        result=collect(config(phase="scan", scan_limit=1),self.work,Provider(invalid=True),pdf_reader=fake_pdf)
        # scan intentionally does not request fulltext
        self.assertEqual(result["counts"]["fulltexts_verified"],0)
        other=Path(self.temp.name)/"other"
        result=collect(config(max_records=1),other,Provider(count=1,invalid=True),pdf_reader=fake_pdf)
        self.assertEqual(result["status"],"needs_fulltext"); self.assertEqual(result["counts"]["fulltexts_verified"],0)

    def test_config_changes_cannot_reuse_old_checkpoint(self):
        collect(config(phase="scan",scan_limit=1),self.work,Provider())
        with self.assertRaises(ValueError): collect(config(phase="scan",scan_limit=2),self.work,Provider(),resume=True)
        with self.assertRaises(FileExistsError): collect(config(phase="scan",scan_limit=1),self.work,Provider())

    def test_core_only_download_exact_25_and_reject_unknown_ids(self):
        cfg=config(download_scope="core_only")
        collect(cfg,self.work,Provider())
        records=load(self.work/"checkpoint.json")["records"]
        selection=[{"paper_id":r["paper_id"],"selection_reason":"TEST摘要复核"} for r in records[:25]]
        p=Provider(); result=collect(cfg,self.work,p,resume=True,selection=selection,pdf_reader=fake_pdf)
        self.assertEqual(p.downloads,25); self.assertEqual(result["counts"]["fulltexts_verified"],25)
        with self.assertRaises(ValueError): collect(cfg,self.work,p,resume=True,selection=selection[:1])

    def test_stale_pdf_is_not_reused_or_overwritten(self):
        cfg=config(max_records=1)
        collect(cfg,self.work,Provider(count=1),pdf_reader=fake_pdf)
        old=next((self.work/"literature/fulltext").glob("*.pdf")); old.write_bytes(b"TEST changed")
        result=collect(cfg,self.work,Provider(count=1),resume=True,pdf_reader=fake_pdf)
        self.assertEqual(old.read_bytes(),b"TEST changed"); self.assertEqual(len(list((self.work/"literature/fulltext").glob("*.pdf"))),2)

    def test_repeated_result_page_is_bounded(self):
        class Repeating(Provider):
            def search(self,q,cursor=None): return {"records":[record(1)],"has_next":True}
        result=collect(config(download_scope="none"),self.work,Repeating())
        self.assertEqual(result["counts"]["metadata"],1)
        self.assertTrue(any(e["kind"]=="repeated_page" for e in load(self.work/"checkpoint.json")["errors"]))

    def test_plan_preserves_original_journal_words_and_targets(self):
        result=plan(config(journals=["社会", "经济学研究", "探索与证明"]))
        self.assertEqual(result["journals"],["社会"]); self.assertEqual(len(result["pending_aliases"]),2)
        with self.assertRaises(ValueError): plan(config(abstract_target=15))
        with self.assertRaises(ValueError): plan(config(issue=None))

    def test_parsers_find_metadata_abstract_and_do_not_read_scripts_as_captcha(self):
        raw='<script>拼图校验</script><table class="result-table-list"><tr><td class="name"><a class="fz14" href="/detail?FileName=TEST1">TEST标题</a></td><td class="author"><a>甲</a></td><td class="source"><a>社会</a></td><td class="date">2025-01-01</td></tr></table><a id="PageNext">下一页</a>'
        page=result_page(raw,"https://kns.cnki.net/search")
        self.assertEqual(page["records"][0]["source_record_id"],"TEST1"); self.assertTrue(page["has_next"])
        self.assertEqual(access_state(raw),"accessible")
        detail='<meta name="citation_title" content="TEST标题"><meta name="citation_author" content="甲"><meta name="citation_journal_title" content="社会"><span id="ChDivSummary">摘要：TEST真实摘要</span><div class="btn-dlpdf"><a href="/download">PDF</a></div>'
        item=metadata(detail,"https://kns.cnki.net/detail?FileName=TEST1")
        self.assertEqual(item["abstract"],"TEST真实摘要"); self.assertEqual(item["download_candidates"][0]["url"],"https://kns.cnki.net/download")
        self.assertEqual(access_state('<div>拼图校验</div>'),"requires_user_access")

    def test_title_mismatch_pdf_needs_review(self):
        p=Path(self.temp.name)/"mismatch.pdf"; p.write_bytes(b"%PDF-TEST\nTEST other")
        self.assertEqual(verify_pdf(p,record(0),lambda p:["TEST other"])["status"],"identity_needs_review")

    def test_context_archives_primary_text_without_inventing_dates_or_validity(self):
        class Web:
            def search(self,q): return [{"url":"https://www.gov.cn/TEST","title":"TEST线索"}]
            def get(self,url): return {"url":url,"text":'<meta name="ArticleTitle" content="TEST政策"><article>TEST制度目标正文。</article>',"retrieved_at":"2026-11-15"}
        result=collect_context("TEST议题",self.work,provider=Web())
        self.assertEqual(result["verified"],0)
        row=load(self.work/"context_candidates.json")[0]
        self.assertIsNone(row["published_at"]); self.assertEqual(row["current_validity"],"unknown")
        self.assertTrue(Path(row["snapshot_path"]).is_file())

    def test_context_rejects_unapproved_redirect_or_source(self):
        class Web:
            def get(self,url): raise AssertionError("unapproved source must not be fetched")
        result=collect_context("TEST议题",self.work,provider=Web(),sources=[{"url":"https://example.invalid/wrong","type":"news"}])
        self.assertEqual(result["candidates"],0); self.assertTrue(result["errors"])

if __name__=="__main__": unittest.main(verbosity=2)
