"""Read public VIP pages and their embedded, non-executable data."""

import hashlib
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import time

from cnki import soup
from collect_common import AccessStop

ISSNS = dict(
    zip(
        (
            "中国社会科学",
            "社会学研究",
            "探索与争鸣",
            "中国青年研究",
            "经济研究",
            "管理世界",
        ),
        ("1002-4921", "1002-5936", "1004-2229", "1002-9931", "0577-9154", "1002-5502"),
    )
)
TOKEN = re.compile(
    r'\s*(?:"(?:\\.|[^"\\])*"|[A-Za-z_$][\w$]*|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}\[\](),:])'
)


class PublicData:
    """Subset of the serialized object syntax only; no call, operator or script evaluation."""

    def __init__(self, text, pos=0, names=None):
        self.text, self.pos, self.names = text, pos, names or {}

    def peek(self):
        match = TOKEN.match(self.text, self.pos)
        if not match:
            raise ValueError("unrecognized data token")
        return match.group().strip()

    def pop(self, expected=None):
        t = self.peek()
        if expected is not None and t != expected:
            raise ValueError("unexpected data separator")
        self.pos = TOKEN.match(self.text, self.pos).end()
        return t

    def entries(self, end, item):
        result = []
        if self.peek() != end:
            while True:
                result.append(item())
                if self.peek() == end:
                    break
                self.pop(",")
        self.pop(end)
        return result

    def pair(self):
        key = self.pop()
        self.pop(":")
        return (json.loads(key) if key.startswith('"') else key, self.value())

    def value(self):
        tok = self.pop()
        if tok == "{":
            return dict(self.entries("}", self.pair))
        if tok == "[":
            return self.entries("]", self.value)
        if tok.startswith('"') or tok[:1] in "-0123456789":
            return json.loads(tok)
        if tok in ("true", "false", "null"):
            return json.loads(tok)
        if tok == "Array" and self.peek() == "(":
            self.pop("(")
            if not self.pop().isdecimal():
                raise ValueError("unsupported placeholder")
            self.pop(")")
            return None
        if tok == "void":
            self.pop("0")
            return None
        if re.fullmatch(r"[A-Za-z_$][\w$]*", tok):
            return self.names.get(tok)
        raise ValueError("unsupported executable expression")


def serialized(doc):
    raw = next(
        (
            n.string
            for n in doc.select("script")
            if n.string and n.string.startswith("window.__NUXT__=")
        ),
        "",
    )
    begin = re.match(r"window\.__NUXT__=\(function\(([\w,$]*)\)\{", raw)
    if not begin:
        raise ValueError("missing public metadata")
    body = re.search(r"(?:\{|;)return\s*(?=\{)", raw[begin.end() - 1 :])
    if not body:
        raise ValueError("missing public returned object")
    content_start = begin.end() - 1 + body.end()
    scan = PublicData(raw, content_start)
    scan.value()
    scan.pop("}")
    scan.pop("(")
    args = scan.entries(")", scan.value)
    names = dict(zip(begin.group(1).split(","), args))
    data = PublicData(raw, content_start, names).value().get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise ValueError("public data layout changed")
    return data[0]


def allowed(url):
    u = urlsplit(url)
    return (
        u.scheme == "https"
        and u.netloc == "www.cqvip.com"
        and (u.path == "/search" or bool(re.fullmatch(r"/doc/journal/\d+", u.path)))
    )


class PageRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise AccessStop(
                "requires_user_access",
                "public HTML redirected outside the search/detail pages",
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class VipPublic:
    provider_id = "vip_public"
    journals = tuple(ISSNS)
    capabilities = (
        "topic",
        "title",
        "author_title",
        "year",
        "metadata",
        "abstract",
        "keywords",
    )
    priority = 30

    def __init__(self, settings):
        self.opener = build_opener(PageRedirect())
        self.delay = max(0.5, float(settings.get("interval_seconds", 1)))
        self.timeout = min(25, max(1, float(settings.get("timeout_seconds", 9))))
        self.last = 0.0

    def page(self, url):
        if not allowed(url):
            raise AccessStop(
                "access_denied",
                "Only public VIP HTML search and article details are allowed",
            )
        time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        try:
            with self.opener.open(
                Request(url, headers={"Accept": "text/html"}), timeout=self.timeout
            ) as r:
                if r.headers.get_content_type() not in (
                    "text/html",
                    "application/xhtml+xml",
                ):
                    raise AccessStop("layout_changed", "Not an HTML article page")
                raw = r.read(2_500_001)
                if len(raw) > 2_500_000:
                    raise AccessStop(
                        "layout_changed", "Public response exceeded size limit"
                    )
        except HTTPError as exc:
            if exc.code in (401, 403):
                raise AccessStop("requires_user_access", f"HTTP {exc.code}") from exc
            if exc.code == 429 or exc.code >= 500:
                raise URLError(f"HTTP {exc.code}") from exc
            raise AccessStop("source_unavailable", f"HTTP {exc.code}") from exc
        doc = soup(raw)
        try:
            return doc, serialized(doc), hashlib.sha256(raw).hexdigest()
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            raise AccessStop(
                "layout_changed", "Public embedded metadata was not recognized"
            ) from exc

    @staticmethod
    def record(row, url):
        ji = row.get("journalInfo") or {}
        journal = ji.get("name")
        issn = ji.get("issn")
        if journal in ISSNS and issn and issn != ISSNS[journal]:
            journal = None
        authors = [
            x["name"]
            for x in row.get("authorInfo") or []
            if isinstance(x, dict) and x.get("name")
        ]
        return dict(
            title=row.get("title"),
            journal=journal,
            issn=issn,
            authors=authors,
            year=row.get("year") or ji.get("year"),
            doi=row.get("doi"),
            url=url,
            source_record_id=str(row["id"]) if row.get("id") else None,
        )

    def search(self, query, journal, year_min, page, *, kind="topic"):
        # The normal public search URL. Scope is enforced by the returned canonical journal.
        k = f"{query} {journal}" if kind == "topic" else query
        url = "https://www.cqvip.com/search?" + urlencode({"k": k})
        doc, data, page_hash = self.page(url)
        listing = data.get("listData")
        if not isinstance(listing, dict) or not isinstance(
            listing.get("records"), list
        ):
            raise AccessStop("layout_changed", "No public article search results field")
        displayed = {}
        for a in doc.select('a[href^="/doc/journal/"]'):
            supplied = urljoin(url, a["href"])
            if allowed(supplied):
                displayed[urlsplit(supplied).path.rsplit("/", 1)[1]] = supplied
        rows = []
        for row in listing["records"]:
            if not isinstance(row, dict) or str(row.get("id")) not in displayed:
                continue
            ident = str(row["id"])
            item = self.record(row, f"https://www.cqvip.com/doc/journal/{ident}")
            if item["title"] and item["journal"]:
                rows.append(dict(item, request_url=displayed[ident]))
        return dict(
            records=rows,
            has_next=False,
            url=url,
            raw_count=len(listing["records"]),
            response_sha256=page_hash,
            pagination_status="public_first_page_only",
        )

    def fetch_abstract(self, record):
        # Use only the actual article link exposed by the public results page.
        actual = record.get("request_url", record["url"])
        _, data, page_hash = self.page(actual)
        row = data.get("resData")
        if (
            not isinstance(row, dict)
            or str(row.get("id")) != record["source_record_id"]
        ):
            raise AccessStop("layout_changed", "Missing article detail identity")
        doc = self.record(row, record["url"])
        topics = row.get("keywordInfo") or []
        if not isinstance(topics, list):
            topics = []
        return dict(
            doc,
            abstract=row.get("abstr"),
            locator="public article detail: resData.abstr",
            response_sha256=page_hash,
            keywords=[
                k["name"]
                for k in topics
                if isinstance(k, dict) and isinstance(k.get("name"), str)
            ],
        )

    def close(self):
        pass
