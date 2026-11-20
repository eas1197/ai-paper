"""Normal Selenium CNKI access. Stop on login/CAPTCHA/denial; never evade checks."""
from __future__ import annotations
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from bs4 import BeautifulSoup
from collect_common import AccessStop, article_id, normalize, now, sha

DEFAULT_SELECTORS = {
    "rows": ".result-table-list tbody tr, table.result-table-list tr, tr[data-cnki-record]",
    "title": "td.name a.fz14, td.name a, a.fz14, a[data-title]",
    "authors": ".author a, td.author span, [data-authors]",
    "journal": ".source a, td.source, [data-journal]",
    "date": ".date, [data-year]",
    "next": "#PageNext, a[rel='next']",
    "abstract": "#ChDivSummary, #abstract_text_label, .abstract-text, [data-abstract]",
    "detail_title": ".wx-tit h1, h1.title, h1[data-title]",
    "download": ".btn-dlpdf a, a#pdfDown, a[data-format='pdf'], a[href$='.pdf']",
    "empty": ".no-content, .no-result, [data-no-results]",
    "challenge": "#captcha, .captcha-container, iframe[src*='captcha'], #verify-wrap",
    "login": "form#loginForm, form[action*='login'] input[type='password']",
}

def soup(raw):
    return BeautifulSoup(raw, "html.parser")

def visible(raw):
    doc = soup(raw)
    for node in doc.select("script,style,noscript"):
        node.decompose()
    return doc.get_text(" ", strip=True)

def access_state(raw, url="", selectors=None):
    doc = soup(raw); sel = dict(DEFAULT_SELECTORS, **(selectors or {}))
    text = visible(raw)
    if doc.select_one(sel["challenge"]) or any(x in text for x in ("拼图校验", "请完成安全验证", "访问过于频繁", "请拖动滑块", "人机验证")):
        return "requires_user_access"
    if any(x in text for x in ("无权访问", "权限不足", "您没有下载权限", "访问被拒绝", "Access Denied")):
        return "access_denied"
    if any(x in text for x in ("余额不足", "请购买", "支付后下载", "购买全文")):
        return "requires_purchase"
    if doc.select_one(sel["login"]) or ("login" in urlparse(url).path.lower() and any(x in text for x in ("登录", "Login", "Sign in"))):
        return "requires_user_access"
    return "accessible"

def metadata(raw, url, selectors=None):
    sel = dict(DEFAULT_SELECTORS, **(selectors or {})); doc = soup(raw)
    def meta(*names):
        for name in names:
            found = doc.find("meta", attrs={"name": re.compile("^" + re.escape(name) + "$", re.I)})
            if found and found.get("content"):
                return found["content"].strip()
        return None
    def first(selector):
        found = doc.select_one(selector)
        return found.get_text(" ", strip=True) if found else None
    title = meta("citation_title", "DC.Title") or first(sel["detail_title"])
    authors = [n.get("content", "").strip() for n in doc.find_all("meta", attrs={"name": re.compile(r"^(citation_author|DC.Creator)$", re.I)})]
    abstract = first(sel["abstract"]) or meta("citation_abstract", "DC.Description")
    if abstract:
        abstract = re.sub(r"^\s*(?:摘要|Abstract)\s*[:：]?\s*", "", abstract, flags=re.I).strip()
    query = parse_qs(urlparse(url).query)
    record_id = next((vals[0] for key, vals in query.items() if key.lower() in ("filename", "file_name")), None)
    doi = meta("citation_doi", "DC.Identifier.DOI")
    year = meta("citation_publication_date", "DC.Date")
    result = {"title": title, "authors": [x for x in authors if x], "journal": meta("citation_journal_title", "DC.Source"),
              "year": year[:4] if year else None, "doi": doi, "source_record_id": record_id,
              "abstract": abstract, "url": url}
    result["download_candidates"] = [{"url": urljoin(url, a.get("href", "")), "label": a.get_text(" ", strip=True)} for a in doc.select(sel["download"]) if a.get("href") and not a["href"].lower().startswith(("javascript:", "data:"))]
    return result

def result_page(raw, url, selectors=None):
    sel = dict(DEFAULT_SELECTORS, **(selectors or {})); doc = soup(raw)
    rows = []
    for tr in doc.select(sel["rows"]):
        anchor = tr.select_one(sel["title"])
        if not anchor or not anchor.get("href"):
            continue
        link = urljoin(url, anchor["href"])
        if urlparse(link).scheme not in ("https", "http"):
            continue
        title = anchor.get_text(" ", strip=True)
        journal = tr.select_one(sel["journal"]); date = tr.select_one(sel["date"])
        authors = [a.get_text(" ", strip=True) for a in tr.select(sel["authors"])]
        year = re.search(r"(?:19|20)\d{2}", date.get_text() if date else "")
        query = parse_qs(urlparse(link).query)
        source_id = next((v[0] for k, v in query.items() if k.lower() == "filename"), None)
        rows.append({"title": title, "authors": authors, "journal": journal.get_text(" ", strip=True) if journal else None,
                     "year": year.group() if year else None, "source_record_id": source_id, "url": link})
    next_link = doc.select_one(sel["next"])
    has_next = bool(next_link and "disabled" not in next_link.get("class", []) and next_link.get("aria-disabled") != "true")
    return {"records": rows, "has_next": has_next, "empty_confirmed": bool(doc.select_one(sel["empty"]))}

def verify_pdf(path, record, pdf_reader=None):
    path = Path(path)
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("下载文件不是PDF，可能为登录页/CAJ/错误页")
    if pdf_reader:
        pages = pdf_reader(path)
    else:
        import pdfplumber
        try:
            with pdfplumber.open(path) as pdf:
                pages = [p.extract_text() or "" for p in pdf.pages]
        except Exception as exc:
            raise ValueError("PDF不可解析") from exc
    if not pages:
        raise ValueError("PDF没有页面")
    head = normalize("\n".join(pages[:2]))
    title = normalize(record.get("title"))
    if not title or title not in head:
        return {"status": "identity_needs_review", "sha256": sha(path), "page_count": len(pages), "identity_basis": "首页无法精确匹配题名；扫描件/OCR或换行差异需正常人工核查"}
    known_authors = [normalize(a) for a in record.get("authors", []) if normalize(a)]
    if known_authors and not any(a in head for a in known_authors):
        return {"status": "identity_needs_review", "sha256": sha(path), "page_count": len(pages), "identity_basis": "题名匹配但作者未匹配"}
    return {"status": "downloaded_verified", "sha256": sha(path), "page_count": len(pages), "identity_basis": "可解析PDF前两页题名及可用作者匹配；完整性与实际阅读另记"}

class SeleniumCNKI:
    provider_id = "cnki_normal_selenium"
    def __init__(self, settings, work):
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        self.settings = settings; self.work = Path(work); self.sel = dict(DEFAULT_SELECTORS, **settings.get("selectors", {}))
        self.interval = max(float(settings.get("min_interval_seconds", 3)), 1)
        self.last = 0.0
        options = webdriver.ChromeOptions()
        # Dedicated project profile; no copied credentials, no webdriver masking, TLS bypass or fingerprint spoofing.
        profile = self.work / "_private/browser_profile"; profile.mkdir(parents=True, exist_ok=True)
        options.add_argument("--user-data-dir=" + str(profile.resolve()))
        self.download_root = self.work / "_private/incoming"; self.download_root.mkdir(parents=True, exist_ok=True)
        options.add_experimental_option("prefs", {"download.default_directory": str(self.download_root.resolve()),
            "download.prompt_for_download": False, "plugins.always_open_pdf_externally": True})
        if settings.get("headless", False):
            options.add_argument("--headless=new")
        if settings.get("browser_binary"):
            options.binary_location = settings["browser_binary"]
        service = Service(executable_path=settings["driver_path"]) if settings.get("driver_path") else Service()
        self.driver = webdriver.Chrome(service=service, options=options)
        self.search_handle = self.driver.current_window_handle
        self.detail_handle = None
        self.driver.set_page_load_timeout(settings.get("page_timeout_seconds", 30))

    def _pace(self):
        remaining = self.interval - (time.monotonic() - self.last)
        if remaining > 0: time.sleep(remaining)
        self.last = time.monotonic()

    def _check(self):
        status = access_state(self.driver.page_source, self.driver.current_url, self.sel)
        if status != "accessible":
            raise AccessStop(status, "需要正常访问权限；本次停止，登录/人工验证后使用resume继续")

    def _ready(self, selectors):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        def test(driver):
            self._check()
            return any(driver.find_elements(By.CSS_SELECTOR, s) for s in selectors)
        WebDriverWait(self.driver, self.settings.get("element_timeout_seconds", 15)).until(test)

    def _optional_ready(self, selectors):
        from selenium.common.exceptions import TimeoutException
        try:
            self._ready(selectors)
            return True
        except TimeoutException:
            self._check()
            return False

    @staticmethod
    def _result_signature(page):
        return tuple((r.get("source_record_id") or r["url"], r["title"]) for r in page["records"])

    def _result_ready(self, previous=None):
        from selenium.webdriver.support.ui import WebDriverWait
        def test(driver):
            self._check()
            page = result_page(driver.page_source, driver.current_url, self.sel)
            if page["empty_confirmed"]:
                return page
            if not page["records"]:
                return False
            if previous is not None and self._result_signature(page) == previous:
                return False
            return page
        return WebDriverWait(self.driver, self.settings.get("element_timeout_seconds", 15)).until(test)

    def search(self, query, cursor=None):
        from selenium.webdriver.common.by import By
        self._pace()
        self.driver.switch_to.window(self.search_handle)
        if cursor:
            self._check()
            buttons = self.driver.find_elements(By.CSS_SELECTOR, self.sel["next"])
            if not buttons: return {"records": [], "has_next": False, "empty_confirmed": True}
            before = self._result_signature(result_page(self.driver.page_source, self.driver.current_url, self.sel))
            buttons[0].click()
            return self._result_ready(previous=before)
        else:
            endpoint = self.settings.get("search_url", "https://kns.cnki.net/kns8s/defaultresult/index")
            self.driver.get(endpoint + ("&" if "?" in endpoint else "?") + urlencode({"kw": query}))
        return self._result_ready()

    def fetch_abstract(self, record):
        self._detail(record["url"])
        self._optional_ready([self.sel["abstract"], "meta[name='citation_abstract']", "meta[name='DC.Description']"])
        self._check()
        result = metadata(self.driver.page_source, self.driver.current_url, self.sel)
        if result.get("title") and normalize(result["title"]) != normalize(record["title"]):
            raise ValueError("详情页题名与检索结果不一致")
        return {k: v for k, v in result.items() if v not in (None, [], "")}

    def resolve_fulltext(self, record):
        self._detail(record["url"]); self._check()
        self._optional_ready([self.sel["download"]])
        self._check()
        return metadata(self.driver.page_source, self.driver.current_url, self.sel)["download_candidates"]

    def download(self, record, destination):
        from selenium.webdriver.common.by import By
        candidates = self.resolve_fulltext(record)
        if not candidates:
            return {"status": "fulltext_unavailable", "reason": "没有正常可用PDF入口"}
        links = self.driver.find_elements(By.CSS_SELECTOR, self.sel["download"])
        usable = [a for a in links if a.get_attribute("href") in {c["url"] for c in candidates}]
        if not usable:
            return {"status": "layout_changed", "reason": "下载入口无法正常点击"}
        before = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in self.download_root.iterdir() if p.is_file()}
        parent = self.driver.current_window_handle; old_handles = set(self.driver.window_handles)
        self._pace(); usable[0].click()
        deadline = time.monotonic() + min(float(self.settings.get("download_timeout_seconds", 45)), 300)
        stable = {}; last_state = None
        try:
            while time.monotonic() < deadline:
                for handle in self.driver.window_handles:
                    if handle == parent or handle not in old_handles:
                        self.driver.switch_to.window(handle); self._check()
                changed = []
                for p in self.download_root.iterdir():
                    if not p.is_file() or p.suffix.lower() in (".crdownload", ".part", ".tmp"): continue
                    state = (p.stat().st_size, p.stat().st_mtime_ns)
                    if before.get(p.name) != state and p.suffix.lower() == ".pdf":
                        changed.append(p)
                        if stable.get(p.name) == state and state[0] > 0:
                            import shutil
                            target = Path(destination); target.parent.mkdir(parents=True, exist_ok=True)
                            if target.exists(): raise FileExistsError("拒绝覆盖下载全文")
                            shutil.copyfile(p, target)
                            return {"status": "file_received", "path": str(target)}
                        stable[p.name] = state
                time.sleep(0.5)
            return {"status": "download_timeout", "reason": "未收到稳定的真实PDF文件"}
        finally:
            for handle in list(self.driver.window_handles):
                if handle not in old_handles:
                    self.driver.switch_to.window(handle); self.driver.close()
            if parent in self.driver.window_handles: self.driver.switch_to.window(parent)

    def login(self):
        self.driver.switch_to.window(self.search_handle)
        self.driver.get(self.settings.get("search_url", "https://kns.cnki.net/kns8s/defaultresult/index"))

    def _detail(self, url):
        if not self.detail_handle or self.detail_handle not in self.driver.window_handles:
            self.driver.switch_to.new_window("tab")
            self.detail_handle = self.driver.current_window_handle
        self.driver.switch_to.window(self.detail_handle)
        self._pace(); self.driver.get(url)

    def close(self):
        self.driver.quit()
