"""专题语料的六刊范围与联网检索凭据。"""
from urllib.parse import urlsplit

from providers import norm
from runtime import valid_date


DESIGNATED = ("中国社会科学", "社会学研究", "探索与争鸣", "中国青年研究", "经济研究", "管理世界")
JOURNALS = frozenset(map(norm, DESIGNATED))


def online_record(record, searches, as_of):
    search = searches.get(record.get("search_id"), {})
    try:
        url = urlsplit(record.get("url") or "")
    except ValueError:
        return False
    return (
        norm(record.get("journal")) in JOURNALS
        and record.get("origin") == "online_search"
        and url.scheme in ("https", "http") and bool(url.hostname)
        and not url.username and not url.password
        and search.get("mode") == "online_search"
        and search.get("access_status") == "accessible"
        and bool(search.get("provider")) and bool(search.get("query"))
        and valid_date(search.get("searched_at"), as_of)
    )


def eligible_papers(bundle):
    searches = {r.get("search_id"): r for r in bundle["searches"] if r.get("search_id")}
    return {
        paper["paper_id"] for paper in bundle["papers"]
        if any(online_record(source, searches, bundle["as_of"])
               and norm(source.get("journal")) == norm(paper.get("journal"))
               and source.get("abstract") == paper.get("abstract")
               for source in paper.get("provenance", []))
    }
