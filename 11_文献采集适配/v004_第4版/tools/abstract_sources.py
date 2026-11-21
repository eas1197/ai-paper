"""Only public article HTML and the existing normal CNKI search/abstract interface."""
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cnki import SeleniumCNKI, access_state, metadata, soup
from collect_common import AccessStop

PUBLIC = "https://shxyj.ajcass.com"
PUBLIC_JOURNAL = "社会学研究"


def article_url(url, host, paths):
    target = urlsplit(url)
    return (target.scheme == "https" and target.netloc == host
            and target.path.lower().rstrip("/") in paths)


class JournalRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not article_url(newurl, "shxyj.ajcass.com", {"/magazine", "/magazine/show"}):
            raise AccessStop("access_denied", "公开期刊页面跳转到未授权位置")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class JournalSource:
    provider_id = "journal_shxyj_public"
    journals = (PUBLIC_JOURNAL,)

    def __init__(self, settings):
        self.interval = max(0.5, float(settings.get("interval_seconds", 1)))
        self.timeout = min(30, max(1, float(settings.get("timeout_seconds", 10))))
        self.previous = 0.0
        self.opener = build_opener(JournalRedirect())

    def page(self, url):
        if not article_url(url, "shxyj.ajcass.com", {"/magazine", "/magazine/show"}):
            raise AccessStop("access_denied", "仅访问期刊公开检索和文章 HTML")
        time.sleep(max(0, self.interval - (time.monotonic() - self.previous)))
        self.previous = time.monotonic()
        try:
            with self.opener.open(Request(url, headers={"Accept": "text/html"}), timeout=self.timeout) as response:
                if response.headers.get_content_type() not in ("text/html", "application/xhtml+xml"):
                    raise AccessStop("layout_changed", "来源未提供 HTML 摘要")
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise AccessStop("layout_changed", "HTML 超出读取上限")
                final = response.url
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise AccessStop("access_denied", f"HTTP {exc.code}") from exc
            if exc.code == 404:
                raise AccessStop("source_not_found", "HTTP 404") from exc
            if exc.code == 429 or exc.code >= 500:
                raise URLError(f"HTTP {exc.code}") from exc
            raise AccessStop("source_unavailable", f"HTTP {exc.code}") from exc
        status = access_state(raw, final)
        if status != "accessible":
            raise AccessStop(status, "公开来源出现访问限制")
        return soup(raw), final

    def search(self, query, journal, year_min, page):
        if journal != PUBLIC_JOURNAL:
            raise ValueError("期刊与公开来源不匹配")
        params = {"Title": query, "Year": "", "Issue": "", "JChannelID": "", "page": page}
        doc, url = self.page(PUBLIC + "/Magazine/?" + urlencode(params))
        if not doc.title or "期刊检索" not in doc.title.get_text(strip=True):
            raise AccessStop("layout_changed", "未识别期刊检索页")
        rows = []
        for link in doc.select("a[href]"):
            target = urljoin(url, link["href"])
            if not article_url(target, "shxyj.ajcass.com", {"/magazine/show"}):
                continue
            identifier = parse_qs(urlsplit(target).query).get("id", [""])[0]
            title = link.get_text(" ", strip=True)
            if identifier.isdecimal() and title:
                canonical = PUBLIC + "/Magazine/Show?" + urlencode({"id": identifier})
                rows.append({"url": canonical, "source_record_id": identifier,
                             "title": title, "journal": journal})
        numbers = [int(n) for link in doc.select("a[href]")
                   for n in parse_qs(urlsplit(link["href"]).query).get("page", []) if n.isdecimal()]
        return {"records": rows, "has_next": any(n > page for n in numbers), "url": url}

    def fetch_abstract(self, record):
        doc, url = self.page(record["url"])
        fields = {}
        for row in doc.select("tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) == 2:
                label = cells[0].get_text(" ", strip=True).strip("：: ")
                fields[label] = cells[1]
        def content(label):
            node = fields.get(label)
            return node.get_text(" ", strip=True) if node else ""
        journal = content("期刊")
        heading = doc.title.get_text(" ", strip=True) if doc.title else ""
        title = heading.removesuffix("-" + journal).strip() if journal else ""
        if not title or not journal:
            raise AccessStop("layout_changed", "缺少文章题名或期刊身份")
        date = next((content(k) for k in fields if "页码" in k), "")
        year = re.search(r"(?:19|20)\d{2}", date)
        node = fields.get("摘要")
        return {"title": title, "journal": journal, "year": year.group() if year else None,
                "authors": [a.strip() for a in re.split(r"[，,；;、]", content("作者")) if a.strip()],
                "doi": content("DOI") or None, "abstract": node.get_text(" ", strip=False) if node else None,
                "url": url, "locator": "tr: 中文摘要标签相邻单元格"}

    def close(self):
        pass


class CNKISource:
    provider_id = "cnki_normal_selenium"

    def __init__(self, settings, work, journals):
        self.journals = journals
        self.settings, self.work = settings, work
        self.client = None
        self.position = None
        self.wire_search_calls = 0

    def search(self, query, journal, year_min, page):
        if self.client is None:
            self.client = SeleniumCNKI(self.settings, self.work)
        key = (query, journal, year_min)
        start = page if self.position == (key, page - 1) else 1
        for number in range(start, page + 1):
            self.wire_search_calls += 1
            result = self.client.search(f"{query} {journal}", cursor=number if number > 1 else None)
            self.position = (key, number)
            if not result["records"] and not result.get("empty_confirmed"):
                raise AccessStop("layout_changed", "知网空页未确认")
            if number < page and not result.get("has_next"):
                return {"records": [], "has_next": False, "url": self.client.driver.current_url}
        return {"records": result["records"], "has_next": result.get("has_next", False),
                "url": self.client.driver.current_url}

    def fetch_abstract(self, record):
        target = urlsplit(record["url"])
        if (target.scheme != "https" or not target.hostname
                or not target.hostname.endswith(".cnki.net") or target.path.lower().endswith(".pdf")
                or target.username or target.password
                or "/download" in target.path.lower()):
            raise AccessStop("access_denied", "只接受知网摘要详情链接")
        self.client._detail(record["url"])
        selector = self.client.sel["abstract"]
        self.client._optional_ready([selector, "meta[name='citation_abstract']", "meta[name='DC.Description']"])
        self.client._check()
        raw, final = self.client.driver.page_source, self.client.driver.current_url
        result = metadata(raw, final, self.client.sel)
        doc = soup(raw)
        node = doc.select_one(selector)
        if node:
            result["abstract"] = node.get_text(" ", strip=False)
            locator = selector
        else:
            tag = doc.select_one("meta[name='citation_abstract' i], meta[name='DC.Description' i]")
            result["abstract"] = tag.get("content") if tag else None
            locator = f"meta:{tag.get('name')}" if tag else None
        return dict(result, locator=locator)

    def close(self):
        if self.client is not None:
            self.client.close()
