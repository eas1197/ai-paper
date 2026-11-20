"""Discover policy/news candidates, then archive primary pages. Unknown facts stay unknown."""
from __future__ import annotations
import time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup
from collect_common import AccessStop, digest, now, sha, write
from cnki import access_state

DOMAINS = ("gov.cn", "news.cn", "xinhuanet.com", "people.com.cn")

def allowed(url, domains):
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.hostname) and any(parsed.hostname == d or parsed.hostname.endswith("." + d) for d in domains)

class WebContextProvider:
    provider_id = "public_rss_discovery_primary_fetch"
    def __init__(self, timeout=20, min_interval=3):
        self.session = requests.Session(); self.timeout = timeout; self.interval = max(1, min_interval); self.last = 0

    def get(self, url):
        delta = self.interval - (time.monotonic() - self.last)
        if delta > 0: time.sleep(delta)
        self.last = time.monotonic()
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        if "charset" not in response.headers.get("content-type", "").lower(): response.encoding = response.apparent_encoding
        if access_state(response.text, response.url) != "accessible":
            raise AccessStop("requires_user_access", "现实资料页面需要正常访问")
        return {"url": response.url, "text": response.text, "retrieved_at": now()}

    def search(self, query):
        # Discovery adapter only: RSS dates/snippets are never treated as verified primary facts.
        url = "https://www.bing.com/search?" + urlencode({"q": query, "format": "rss"})
        response = self.get(url)
        try: root = ET.fromstring(response["text"])
        except ET.ParseError as exc: raise ValueError("检索RSS不可用/结构变化，可换提供方或导入官方URL清单") from exc
        return [{"title": n.findtext("title"), "url": n.findtext("link"), "snippet": n.findtext("description")} for n in root.findall(".//item")]

def extract_primary(raw, url):
    doc = BeautifulSoup(raw, "html.parser")
    def meta(*keys):
        for key in keys:
            tag = doc.find("meta", attrs={"name": key}) or doc.find("meta", attrs={"property": key})
            if tag and tag.get("content"): return tag["content"].strip()
        return None
    title = meta("ArticleTitle", "og:title") or (doc.h1.get_text(" ", strip=True) if doc.h1 else doc.title.get_text(" ", strip=True) if doc.title else None)
    published = meta("PubDate", "publishdate", "article:published_time", "firstpublishedtime")
    publisher = meta("ContentSource", "source", "article:author")
    content = doc.select_one("#UCAP-CONTENT, #zoom, #zoomCon, .TRS_Editor, article, .article-content")
    if content is None:
        content = doc.body or doc
    for node in content.select("script,style,nav,header,footer,noscript"): node.decompose()
    return {"title": title, "published_at": published, "publisher": publisher, "primary_url": url,
            "text": content.get_text("\n", strip=True)}

def collect_context(issue, work, *, provider=None, sources=None, as_of=None, limit=12, domains=DOMAINS):
    if not issue: raise ValueError("现实检索需要暂定议题，不能默认使用示例课题")
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    provider = provider or WebContextProvider()
    today = date.fromisoformat(as_of or now()[:10]); start = today.year - 3
    logs, candidates, errors = [], [], []
    if sources is None:
        searches = [("policy", f"site:gov.cn {issue} 政策 意见 通知"), ("news", f"{issue} {start} {today.year} 现实 新闻 新华社 人民日报")]
        for kind, query in searches:
            try:
                found = provider.search(query)
                logs.append({"query": query, "type": kind, "searched_at": now(), "hits": len(found), "status": "searched"})
                candidates += [dict(r, type=kind) for r in found if allowed(r.get("url", ""), domains)]
            except Exception as exc:
                errors.append({"phase": "search", "type": kind, "error": type(exc).__name__, "message": str(exc)})
    else:
        candidates = list(sources)
    # Interleave source types so a long policy hit list cannot consume the entire
    # shared fetch budget before any recent-news page is considered.
    policies = [c for c in candidates if c.get("type") == "policy"]
    news = [c for c in candidates if c.get("type") == "news"]
    other = [c for c in candidates if c.get("type") not in ("policy", "news")]
    candidates = [c for i in range(max(len(policies), len(news))) for group in (policies, news) for c in group[i:i+1]] + other
    unique, rows = set(), []
    for candidate in candidates:
        url = candidate.get("url", "")
        if url in unique: continue
        unique.add(url)
        if not allowed(url, domains):
            errors.append({"url": url, "error": "outside_primary_source_allowlist"}); continue
        try:
            response = provider.get(url)
            if not allowed(response["url"], domains): raise ValueError("重定向离开允许的原始来源")
            extracted = extract_primary(response["text"], response["url"])
            cid = "CTX_" + digest(response["url"])[:20]
            text_path = work / "snapshots" / (cid + ".txt"); text_path.parent.mkdir(exist_ok=True)
            # Do not archive account chrome/navigation or HTTP cookies/headers.
            if not extracted["text"]: raise ValueError("没有提取到正文，不计有效现实材料")
            text_path.write_text(extracted["text"], encoding="utf-8")
            row = dict(candidate, **{k: v for k, v in extracted.items() if k != "text"}, context_id=cid,
                       retrieved_at=response.get("retrieved_at", now()), snapshot_path=str(text_path.resolve()),
                       snapshot_sha256=sha(text_path), event_date=None, current_validity="unknown", national_level=None,
                       verification_status="unverified", source_claims_are_not_identification=True)
            if row.get("type") == "news" and row.get("published_at"):
                try:
                    pub = date.fromisoformat(row["published_at"][:10])
                    cutoff = today.replace(year=today.year - 3, day=min(today.day, 28))
                    if not cutoff <= pub <= today: row["screen_status"] = "outside_recent_window"
                except ValueError: row["screen_status"] = "publication_date_needs_review"
            else: row["screen_status"] = "requires_primary_review"
            rows.append(row)
        except Exception as exc:
            errors.append({"url": url, "error": type(exc).__name__, "message": str(exc)})
        if len(rows) >= limit: break
    write(work / "context_candidates.json", rows); write(work / "context_search_log.json", logs)
    write(work / "context_errors.json", errors)
    return {"status": "needs_review", "candidates": len(rows), "verified": 0, "errors": errors, "work": str(work)}
