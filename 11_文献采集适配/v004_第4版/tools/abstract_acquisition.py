"""Candidate-only abstract collection, with bounded requests and durable checkpoints."""
import hashlib
import os
import re
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit

from acquisition import SEEDS
from collect_common import AccessStop, digest, load, normalize, now, write
from abstract_sources import CNKISource, JournalSource

MODE = "abstract_only"
TARGET = 100
FIELDS = ("title", "authors", "journal", "year", "doi", "source_record_id", "url")
CONCEPTS = (
    (("教育分流", "普职分流", "学轨制", "教育轨道", "education tracking"),
     ("中学教育分流", "重点学校制度", "教育分层", "教育机会", "education tracking")),
    (("教育不平等", "教育机会不平等", "教育分层", "教育差距", "educational inequality"),
     ("教育分层", "教育机会", "升学差异", "educational inequality")),
    (("教育机会", "升学机会", "高中教育", "高中入学", "教育获得", "educational opportunity"),
     ("升学机会", "高中教育", "教育获得", "educational opportunity")),
    (("家庭背景", "家庭资源", "家庭社会经济地位", "父母教育", "家庭阶层", "family background"),
     ("家庭背景", "家庭社会经济地位", "文化资本", "family background")),
    (("社会流动", "代际流动", "阶层流动", "social mobility"),
     ("代际流动", "职业地位获得", "social mobility")),
    (("互联网", "网络使用", "数字鸿沟", "上网", "digital divide"),
     ("互联网使用", "数字鸿沟", "digital divide")),
)
BLOCK_SOURCE = {"requires_user_access", "access_denied", "requires_purchase", "layout_changed", "source_start_failed"}
RETRYABLE = (URLError, TimeoutError, ConnectionError)


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_url(url):
    if not isinstance(url, str):
        return False
    try:
        u = urlsplit(url)
        return (u.scheme == "https" and bool(u.hostname) and not u.username and not u.password
                and not re.search(r"\.(?:pdf|caj|zip|docx?)(?:/|$)|/download", u.path, re.I))
    except ValueError:
        return False


def clean_doi(value):
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", str(value or "").strip(), flags=re.I)
    return text.casefold() if re.fullmatch(r"10\.\d{4,9}/[^\s]+", text) else None


def prepare(config):
    if config.get("acquisition_mode") != MODE or config.get("journals") != SEEDS:
        raise ValueError("需显式选择 abstract_only 及配置指定六刊")
    if (config.get("abstract_target") != TARGET or config.get("download_scope") != "none"
            or any(config.get(k) is not False for k in ("download_pdf", "download_fulltext",
                                                         "require_fulltext_reading", "require_subscription"))):
        raise ValueError("摘要模式目标为100，且全文、PDF、精读及订阅均关闭")
    if any(k in config for k in ("core_target", "core_fulltext_target", "selection_file", "fulltext_locator")):
        raise ValueError("摘要模式不接收旧全文配置")
    topic = config.get("theme")
    if not isinstance(topic, str) or not 2 <= len(topic.strip()) <= 160:
        raise ValueError("研究主题须为 2–160 字")
    query = re.sub(r"^(?:请|帮我|给我|写一篇|一篇|关于|研究)+", "", topic.strip())
    query = re.sub(r"(?:的)?(?:社会学)?(?:学术)?论文[。！!。 ]*$", "", query).strip() or topic.strip()
    groups, expansions = [], []
    pieces = re.split(r"如何影响|对(.+?)的影响$|(?<=.{2})(?:和|与)(?=.{2,})|\band\b", query, flags=re.I)
    if len(pieces) == 1:
        pieces = [query]
    pieces = [part.strip(" 的？?。") for part in pieces if part and len(part.strip(" 的？?。")) >= 2]
    for part in pieces:
        matches = [(max(len(normalize(a)) for a in aliases if normalize(a) in normalize(part)), aliases, terms)
                   for aliases, terms in CONCEPTS if any(normalize(a) in normalize(part) for a in aliases)]
        if matches:
            _, aliases, terms = max(matches, key=lambda item: item[0])
            groups.append(list(aliases))
            expansions.extend(terms)
        else:
            groups.append([part])
            if len(pieces) > 1:
                expansions.append(part)
    custom = config.get("query_terms", [])
    if not isinstance(custom, list) or len(custom) > 10 or any(
        not isinstance(term, str) or not 2 <= len(term.strip()) <= 100 for term in custom
    ):
        raise ValueError("query_terms 须为至多10个有效术语")
    queries = list(dict.fromkeys([query] + [s.strip() for s in custom] + expansions))
    limits = {}
    for key, default, low, high in (("request_budget", 320, 1, 2000), ("max_queries", 7, 1, 20),
                                     ("max_pages", 3, 1, 20), ("max_retries", 1, 0, 3)):
        val = config.get(key, default)
        if type(val) is not int or not low <= val <= high:
            raise ValueError(f"{key} 越界")
        limits[key] = val
    year = config.get("first_pass_from_year")
    if year is not None and (type(year) is not int or not 1900 <= year <= 2099):
        raise ValueError("first_pass_from_year 无效")
    # Matching is fixed for the run and never loosened to satisfy the count.
    return {"mode": MODE, "theme": topic, "queries": queries[:limits["max_queries"]],
            "relevance_groups": groups or [[query]], "first_pass_from_year": year,
            "target": TARGET, **limits}


def relevance(record, groups):
    haystack = normalize(record["title"] + " " + record["abstract_text"])
    matches = [[term for term in terms if normalize(term) in haystack] for terms in groups]
    return ("relevant" if all(matches) else "needs_review"), matches


def abstract_text(raw, title):
    if not isinstance(raw, str) or not raw.strip():
        return None
    cleaned = re.sub(r"\s+", " ", raw).strip()
    cleaned = re.sub(r"^(?:摘要|abstract)\s*[:：]\s*", "", cleaned, flags=re.I)
    if (len(normalize(cleaned)) < 40 or normalize(cleaned) == normalize(title)
            or re.search(r"登录后查看|仅显示部分摘要|点击查看全文|查看更多|版权声明|javascript|<[^>]+>", cleaned, re.I)
            or re.match(r"^(?:关键词|keywords|首页|导航|菜单|内容导航|当前位置)\s*[:：\s]", cleaned, re.I)
            or re.search(r"(?:\.{3}|…+|\[truncated\]|\[摘要截断\])\s*$", cleaned, re.I)):
        return None
    return cleaned


def article_observation(candidate, detail, provider, search_id):
    """A discovery and its authenticated-by-identity abstract, kept as separate facts."""
    base = {key: candidate.get(key) for key in FIELDS}
    base.update(provider=provider, search_id=search_id, status="metadata_only")
    if not detail:
        return base
    a, b = clean_doi(candidate.get("doi")), clean_doi(detail.get("doi"))
    if (not detail.get("title") or normalize(detail["title"]) != normalize(candidate["title"])
            or detail.get("journal") not in SEEDS or detail["journal"] != candidate["journal"]
            or a and b and a != b
            or candidate.get("year") and detail.get("year") and str(candidate["year"]) != str(detail["year"])):
        return dict(base, status="identity_mismatch")
    row = dict(base)
    row.update({key: detail[key] for key in FIELDS if detail.get(key) and key != "source_record_id"})
    row["doi"] = b or a
    row["year"] = str(row["year"] or "")
    row["authors"] = [a.strip() for a in (row["authors"] or []) if isinstance(a, str) and a.strip()]
    raw = detail.get("abstract")
    cleaned = abstract_text(raw, row["title"])
    if (not cleaned or not safe_url(row["url"]) or not detail.get("locator")
            or not row["authors"] or not re.fullmatch(r"(?:19|20)\d{2}", row["year"])):
        return dict(row, status="invalid_abstract" if raw else "missing_abstract")
    return dict(row, status="valid_abstract", raw_abstract=raw, abstract_text=cleaned,
                raw_hash=text_hash(raw), abstract_hash=text_hash(cleaned),
                locator=detail["locator"], retrieved_at=now())


def fingerprint(row):
    if row["authors"] and row["year"]:
        return (row["journal"], normalize(row["title"]),
                tuple(sorted(normalize(a) for a in row["authors"])), str(row["year"]))
    return None


def build_articles(observations, groups):
    # Transitive merge on DOI, exact bibliographic identity or source identity.
    rows = [r for r in observations if r["journal"] in SEEDS]
    parent = list(range(len(rows)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    keys = {}
    for i, row in enumerate(rows):
        doi, bib = clean_doi(row["doi"]), fingerprint(row)
        anchors = [("source", row["provider"], row["source_record_id"] or row["url"])]
        if doi:
            anchors.append(("doi", doi))
        if bib:
            anchors.append(("bibliography", bib))
        for key in anchors:
            first, second = root(i), root(keys.setdefault(key, i))
            parent[max(first, second)] = min(first, second)
    grouped = {}
    for i, row in enumerate(rows):
        grouped.setdefault(root(i), []).append(row)
    articles, conflicts = [], []
    for group in grouped.values():
        dois = {clean_doi(row["doi"]) for row in group if clean_doi(row["doi"])}
        if (len(dois) > 1 or len({r["journal"] for r in group}) > 1
                or len({normalize(r["title"]) for r in group}) > 1 and len({fingerprint(r) for r in group if fingerprint(r)}) > 1):
            conflicts.append([{"source": r["provider"], "url": r["url"], "doi": r["doi"]} for r in group])
            continue
        valid = [r for r in group if r["status"] == "valid_abstract"]
        if not valid:
            continue
        best = max(valid, key=lambda r: (relevance(r, groups)[0] == "relevant", r["provider"] == "journal_shxyj_public"))
        status, matches = relevance(best, groups)
        first = group[0]
        identity = fingerprint(first) or (first["provider"], first["source_record_id"] or first["url"])
        articles.append({
            "article_id": "A_" + digest(identity)[:24],
            "title": best["title"], "authors": best["authors"], "journal": best["journal"],
            "publication_year": int(best["year"]), "doi": next(iter(dois), None),
            "abstract_text": best["abstract_text"], "raw_abstract": best["raw_abstract"],
            "abstract_hash": best["abstract_hash"], "raw_hash": best["raw_hash"],
            "source": best["provider"], "source_url": best["url"], "search_id": best["search_id"],
            "retrieved_at": best["retrieved_at"], "locator": best["locator"],
            "acquisition_status": "abstract_available", "relevance_status": status,
            "relevance_matches": matches, "dedup_status": "merged_sources" if len(group) > 1 else "unique",
            "provenance": [{k: r.get(k) for k in ("provider", "url", "source_record_id", "search_id", "status", "raw_hash",
                                                 "raw_abstract", "abstract_hash", "locator", "retrieved_at")}
                           for r in group],
        })
    return articles, conflicts


@contextmanager
def job_lock(work):
    # OS-owned lock is released even if the process is interrupted or killed.
    with (work / ".lock").open("a+b", buffering=0) as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def jobs(spec, providers):
    strict, focused = spec["first_pass_from_year"], spec["queries"][0]
    terms = [(focused, strict, "initial")]
    if strict is not None:
        terms.append((focused, None, "widen_years"))
    terms.extend((term, None, "expand_terms") for term in spec["queries"][1:])
    return [(query, year, reason, journal, source.provider_id)
            for query, year, reason in terms for journal in SEEDS
            for source in providers if journal in source.journals]


def collect(config, work, providers=None, *, resume=False, session_requests=None):
    spec = prepare(config)
    if session_requests is not None and (type(session_requests) is not int or session_requests < 1):
        raise ValueError("单次请求暂停上限须为正整数")
    work = Path(work)
    enabled = config.get("sources", ["journal_shxyj_public", "cnki_normal_selenium"])
    factories = {
        "journal_shxyj_public": lambda: JournalSource(config.get("public_journal", {})),
        "cnki_normal_selenium": lambda: CNKISource(config.get("browser", {}), work, SEEDS),
    }
    if not isinstance(enabled, list) or not enabled or any(k not in factories for k in enabled) or len(set(enabled)) != len(enabled):
        raise ValueError("摘要来源配置无效")
    owns = providers is None
    providers = [factories[k]() for k in enabled] if owns else providers
    sources = {p.provider_id: p for p in providers}
    settings_hash = digest([spec, config, list(sources)])
    path = work / "checkpoint.json"
    if work.exists() and not path.exists() and any(item.name != ".lock" for item in work.iterdir()):
        raise FileExistsError("请使用空的独立候选目录")
    if path.exists() and load(path).get("profile") != MODE:
        raise ValueError("拒绝向非摘要候选目录写入")
    work.mkdir(parents=True, exist_ok=True)
    with job_lock(work):
        if path.exists():
            if not resume:
                raise FileExistsError("采集已存在；使用 --resume 接续")
            state = load(path)
            if state.get("profile") != MODE or state.get("config_sha256") != settings_hash:
                raise ValueError("断点与当前配置不匹配，另建采集目录")
        else:
            if resume:
                raise FileNotFoundError("找不到可恢复的摘要断点")
            if any(item.name != ".lock" for item in work.iterdir()):
                raise FileExistsError("请使用空的独立候选目录")
            state = dict(profile=MODE, schema_version=1, config_sha256=settings_hash,
                         collection_id="COL_" + digest([settings_hash, str(work.resolve()), now()])[:24],
                         spec=spec, searches={}, details={}, observed={}, requests=[],
                         source_failures={}, complete_jobs=[], status="running")
            write(path, state)

        initial_requests = len(state["requests"])

        def save():
            write(path, state)

        def request(source, operation, key, fn, charge=1):
            previous = [v for v in state["requests"] if v["key"] == key]
            for item in previous:
                if item["status"] == "started":
                    item["status"] = "interrupted_unknown"
            # An interrupted response may have been sent. Charge it and allow only
            # the remaining retry allowance rather than assuming zero cost.
            remaining = spec["max_retries"] + 1 - len(previous)
            for _ in range(remaining):
                if session_requests is not None and len(state["requests"]) - initial_requests >= session_requests:
                    return None, "paused"
                if sum(item["budget_units"] for item in state["requests"]) + charge > spec["request_budget"]:
                    return None, "budget_exhausted"
                event = dict(key=key, source=source.provider_id, operation=operation,
                             at=now(), status="started", budget_units=charge)
                state["requests"].append(event)
                save()
                try:
                    result = fn()
                except AccessStop as exc:
                    event.update(status=exc.status, reason=str(exc))
                    if exc.status in BLOCK_SOURCE:
                        state["source_failures"][source.provider_id] = exc.status
                    save()
                    return None, exc.status
                except RETRYABLE as exc:
                    event.update(status="retryable_error", reason=type(exc).__name__)
                    save()
                    continue
                except Exception as exc:
                    if type(exc).__module__.startswith("selenium") or isinstance(exc, (ImportError, FileNotFoundError)):
                        reason = "source_start_failed" if getattr(source, "client", True) is None else "layout_changed"
                        state["source_failures"][source.provider_id] = reason
                        detail = " ".join(str(getattr(exc, "msg", None) or exc).splitlines())[:240]
                        if "tab crashed" in detail.casefold():
                            reason = "browser_unavailable"
                            state["source_failures"][source.provider_id] = reason
                        event.update(status=reason, reason=type(exc).__name__, diagnostic=detail)
                        save()
                        return None, reason
                    raise
                event["status"] = "received"
                return result, "received"
            return None, "retry_limit"

        def enough():
            searched = {v["journal"] for v in state["searches"].values()}
            # A known unavailable provider is recorded separately. Never claim
            # six-journal coverage merely from its configuration.
            if not set(SEEDS).issubset(searched):
                return False
            rows, _ = build_articles(list(state["observed"].values()), spec["relevance_groups"])
            return sum(r["relevance_status"] == "relevant" for r in rows) >= TARGET

        def run_search():
            queue = jobs(spec, providers)
            # First query covers the six journals before moving to expanded terms.
            for query, year, reason, journal, provider_id in queue:
                source = sources[provider_id]
                job = digest([query, year, journal, provider_id])
                if job in state["complete_jobs"] or provider_id in state["source_failures"]:
                    continue
                previous_pages = set()
                for number in range(1, spec["max_pages"] + 1):
                    key = "S_" + digest([job, number])[:24]
                    page = state["searches"].get(key)
                    if page is None and year is None and spec["first_pass_from_year"] is not None:
                        prior_job = digest([query, spec["first_pass_from_year"], journal, provider_id])
                        prior = state["searches"].get("S_" + digest([prior_job, number])[:24])
                        if prior and prior["status"] == "accessible":
                            page = dict(prior, search_id=key, year_min=None, raw_count=0,
                                        reason="widen_years", reused_search_id=prior["search_id"])
                            state["searches"][key] = page
                            save()
                    if page is None:
                        charge = (number if isinstance(source, CNKISource)
                                  and source.position != ((query, journal, year), number - 1) else 1)
                        result, status = request(source, "search", key,
                                                  lambda: source.search(query, journal, year, number), charge)
                        if status in ("budget_exhausted", "paused"):
                            return status
                        if not result:
                            state["searches"][key] = dict(search_id=key, provider=provider_id, journal=journal,
                                                          query=query, year_min=year, reason=reason, page=number,
                                                          status=status, raw_count=0, records=[], has_next=False)
                            save()
                            break
                        records = [{field: r.get(field) for field in FIELDS}
                                   for r in result["records"] if safe_url(r.get("url"))
                                   and isinstance(r.get("title"), str) and r["title"].strip()
                                   and r.get("journal") == journal]
                        page = dict(search_id=key, provider=provider_id, journal=journal, query=query,
                                    year_min=year, reason=reason if number == 1 else "pagination",
                                    page=number, status="accessible", source_url=result.get("url"),
                                    raw_count=len(result["records"]), records=records,
                                    has_next=bool(result.get("has_next")), searched_at=now())
                        state["searches"][key] = page
                        save()
                    signature = digest([r["url"] for r in page["records"]])
                    if page["records"] and signature in previous_pages:
                        page["pagination_status"] = "repeated_page"
                        save()
                        break
                    previous_pages.add(signature)
                    for record in page["records"]:
                        cache_key = digest([provider_id, record["source_record_id"] or record["url"]])
                        prior = state["details"].get(cache_key)
                        if prior is None:
                            result, status = request(source, "abstract", cache_key, lambda: source.fetch_abstract(record))
                            if status in ("budget_exhausted", "paused"):
                                return status
                            prior = article_observation(record, result, provider_id, key)
                            if status != "received":
                                prior["status"] = status
                            state["details"][cache_key] = prior
                            save()
                        known_year = str(prior.get("year") or "")
                        if year is not None and re.fullmatch(r"(?:19|20)\d{2}", known_year) and int(known_year) < year:
                            continue
                        state["observed"].setdefault(cache_key, prior)
                        save()
                        if provider_id in state["source_failures"]:
                            break
                    if enough():
                        return "target_reached"
                    if not page["has_next"] or provider_id in state["source_failures"]:
                        break
                state["complete_jobs"].append(job)
                save()
            return "search_plan_exhausted"

        try:
            if state["status"] not in ("target_reached", "search_plan_exhausted", "budget_exhausted"):
                state["status"] = run_search()
                save()
        except KeyboardInterrupt:
            state["status"] = "interrupted"
            save()
        finally:
            if owns:
                for source in providers:
                    source.close()
        return export_collection(state, work)


def export_collection(state, work):
    articles, conflicts = build_articles(list(state["observed"].values()), state["spec"]["relevance_groups"])
    searches = list(state["searches"].values())
    relevant = sum(a["relevance_status"] == "relevant" for a in articles)
    counts = {"retrieved_records": sum(s["raw_count"] for s in searches),
              "valid_source_abstracts": sum(r["status"] == "valid_abstract" for r in state["observed"].values()),
              "unique_valid_abstracts": len(articles), "unique_relevant_abstracts": relevant}
    collection = dict(schema_version=1, acquisition_mode=MODE,
                      collection_id=state["collection_id"],
                      theme=state["spec"]["theme"], relevance_groups=state["spec"]["relevance_groups"],
                      status=state["status"], target=TARGET, counts=counts,
                      target_met=relevant >= TARGET, articles=articles, conflicts=conflicts,
                      searches=searches, source_failures=state["source_failures"],
                      attempted_journals=sorted({s["journal"] for s in searches}),
                      unattempted_journals=[j for j in SEEDS if not any(s["journal"] == j for s in searches)],
                      observation_statuses={k: r["status"] for k, r in state["details"].items()},
                      usage={"search_calls": sum(r["operation"] == "search" for r in state["requests"]),
                             "abstract_calls": sum(r["operation"] == "abstract" for r in state["requests"]),
                             "budget_units": sum(r["budget_units"] for r in state["requests"]),
                             "fulltext_requests": 0, "pdf_requests": 0, "model_calls": 0,
                             "provider_actual_cost": None,
                             "cost_unknown_reason": "本工具无第三方用量凭证"})
    write(work / "abstract_collection.json", collection)
    return collection
