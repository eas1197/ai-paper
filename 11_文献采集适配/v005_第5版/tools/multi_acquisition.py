"""Bounded search -> identity resolution -> public abstract retrieval."""

from pathlib import Path
import re
from urllib.error import URLError

from abstract_acquisition import (
    SEEDS,
    TARGET,
    abstract_text,
    article_observation,
    build_articles,
    clean_doi,
    export_collection,
    job_lock,
    prepare,
    relevance,
    safe_url,
    text_hash,
)
from abstract_sources import CNKISource, JournalSource
from collect_common import AccessStop, digest, load, normalize, now, write
from vip_public import ISSNS, VipPublic

ENGINE = "multi_v2"
FAILURES = {
    "requires_user_access",
    "access_denied",
    "requires_purchase",
    "layout_changed",
    "browser_unavailable",
}
RETRY = (TimeoutError, ConnectionError, URLError)
PRIORITY = {"journal_shxyj_public": 0, "vip_public": 10, "cnki_normal_selenium": 20}
ALIASES = {"Sociological Studies": "社会学研究", "China Youth Study": "中国青年研究"}
TITLE_TERM = re.compile(
    r"[\u4e00-\u9fff]{4,14}(?:资本|分层|分流|机会|流动|不平等|家庭|婚恋|关系|教育|制度)$"
)


def canonical_journal(row):
    name = str(row.get("journal") or "").strip("《》 ")
    if name in SEEDS:
        return name if not row.get("issn") or row["issn"] == ISSNS[name] else None
    mapped = ALIASES.get(name)
    return mapped if mapped and row.get("issn") == ISSNS[mapped] else name or None


def author_names(row):
    result = []
    for value in row.get("authors") or []:
        if not isinstance(value, str):
            continue
        tokens = value.split()
        # On the journal website a single field can join multiple Chinese authors
        # with spaces. Never split a romanized personal name on that basis.
        if len(tokens) > 1 and all(
            re.fullmatch(r"[\u4e00-\u9fff]{2,5}", part) for part in tokens
        ):
            result.extend(tokens)
        elif value.strip():
            result.append(value.strip())
    return result


def author_keys(row):
    return {normalize(a) for a in author_names(row)}


def resolve(anchor, candidate):
    """Match independent observations, only auto-accept sufficiently corroborated identity."""
    a, b = clean_doi(anchor.get("doi")), clean_doi(candidate.get("doi"))
    left, right = normalize(anchor.get("title")), normalize(candidate.get("title"))
    if (
        not left
        or not right
        or not canonical_journal(anchor)
        or canonical_journal(anchor) != canonical_journal(candidate)
    ):
        return "different_journal_or_missing_identity"
    if a and b and a != b:
        return "doi_conflict"
    if (
        anchor.get("year")
        and candidate.get("year")
        and str(anchor["year"]) != str(candidate["year"])
    ):
        return "year_conflict"
    first, second = author_keys(anchor), author_keys(candidate)
    if a and a == b:
        if left == right or (
            first & second and (left.startswith(right) or right.startswith(left))
        ):
            return "doi"
        return "doi_title_conflict"
    if left != right:
        return "title_unconfirmed"
    if (
        first
        and second
        and (first == second or min(len(first), len(second)) == 1 and first & second)
    ):
        if anchor.get("year") and candidate.get("year"):
            return "bibliographic"
    return "author_year_unconfirmed"


def keywords(articles, observations, done):
    """Adapt from verified article keywords, ranking without weakening relevance."""
    links = {r["url"] for r in articles if r["relevance_status"] == "relevant"}
    score = {}
    for row in observations:
        if row["url"] not in links:
            continue
        verified = row.get("keywords", [])
        # Keyword phrases from structured details. Title segments are supplemental.
        pieces = re.split(r"[：:——、，。；（）()？！]", row["title"])
        for key in dict.fromkeys(
            [*verified, *(p for p in pieces if TITLE_TERM.fullmatch(p))]
        ):
            key = key.strip()
            if 2 <= len(key) <= 26 and normalize(key) not in done:
                score[key] = score.get(key, 0) + 1
    return sorted(score, key=lambda x: (-score[x], len(x), x))


def source_inventory(config, work):
    registry = {
        "vip_public": lambda: VipPublic(config.get("vip", {})),
        "journal_shxyj_public": lambda: PublicJournal(config.get("public_journal", {})),
        "cnki_normal_selenium": lambda: CNKISource(
            config.get("browser", {}), work, SEEDS
        ),
    }
    enabled = config.get("sources", list(registry))
    if (
        not isinstance(enabled, list)
        or not enabled
        or len(set(enabled)) != len(enabled)
        or set(enabled) - registry.keys()
    ):
        raise ValueError("Invalid source registry selection")
    return [registry[key]() for key in enabled]


def identity_projection(observed):
    canonical = {}
    projected = {}
    for key, original in observed.items():
        row = dict(original, authors=author_names(original))
        doi = clean_doi(row.get("doi"))
        if doi and doi in canonical and resolve(canonical[doi], row) == "doi":
            first = canonical[doi]
            projected[key] = dict(row, title=first["title"], authors=first["authors"])
        else:
            projected[key] = row
            if doi and doi not in canonical and row["status"] == "valid_abstract":
                canonical[doi] = row
    return projected


def displayed(papers, groups):
    for paper in papers:
        variants = [
            item for item in paper["provenance"] if item["status"] == "valid_abstract"
        ]
        best = min(variants, key=lambda x: PRIORITY.get(x["provider"], 10))
        text = abstract_text(best["raw_abstract"], paper["title"])
        paper.update(
            source=best["provider"],
            source_url=best["url"],
            search_id=best["search_id"],
            raw_abstract=best["raw_abstract"],
            raw_hash=best["raw_hash"],
            abstract_text=text,
            abstract_hash=text_hash(text),
            locator=best["locator"],
            retrieved_at=best["retrieved_at"],
            abstract_variant_hashes=sorted({v["abstract_hash"] for v in variants}),
        )
        paper["relevance_status"], paper["relevance_matches"] = relevance(paper, groups)
    return papers


class SearchRun:
    def __init__(self, config, work, sources, seeds, resume):
        self.spec, self.work = prepare(config), work
        self.sources = {s.provider_id: s for s in sources}
        self.seeds = seeds
        self.file = work / "checkpoint.json"
        identity = digest([ENGINE, config, self.spec, list(self.sources), seeds])
        if resume:
            self.state = load(self.file)
            if (
                self.state.get("engine") != ENGINE
                or self.state.get("config_sha256") != identity
            ):
                raise ValueError(
                    "Wrong engine or changed configuration; keep the prior checkpoint"
                )
        else:
            if self.file.exists() or any(p.name != ".lock" for p in work.iterdir()):
                raise FileExistsError("Use a new work directory or resume")
            self.state = dict(
                engine=ENGINE,
                profile="abstract_only",
                schema_version=1,
                config_sha256=identity,
                collection_id="COL_"
                + digest([identity, str(work.resolve()), now()])[:24],
                spec=self.spec,
                status="running",
                searches={},
                observed={},
                details={},
                requests=[],
                source_failures={},
                resolutions=[],
                seed_results={},
                expansion=[],
                processed_queries=[],
                capabilities={
                    k: getattr(v, "capabilities", ("topic", "title", "abstract"))
                    for k, v in self.sources.items()
                },
            )
            self.save()

    def save(self):
        write(self.file, self.state)

    def request(self, source, action, key, callback, cost=1):
        requests = self.state["requests"]
        attempts = [r for r in requests if r["key"] == key]
        for item in attempts:
            if item["status"] == "started":
                item["status"] = "interrupted_unknown"
        for _ in range(max(0, self.spec["max_retries"] + 1 - len(attempts))):
            if (
                sum(r["budget_units"] for r in requests) + cost
                > self.spec["request_budget"]
            ):
                return None, "budget_exhausted"
            event = dict(
                source=source.provider_id,
                operation=action,
                key=key,
                at=now(),
                status="started",
                budget_units=cost,
            )
            requests.append(event)
            self.save()
            try:
                result = callback()
            except AccessStop as exc:
                event.update(status=exc.status, reason=str(exc))
                if exc.status in FAILURES and (
                    action == "search" or isinstance(source, CNKISource)
                ):
                    self.state["source_failures"][source.provider_id] = exc.status
                self.save()
                return None, exc.status
            except RETRY as exc:
                event.update(status="retryable_error", reason=type(exc).__name__)
                self.save()
                continue
            except Exception as exc:
                if not type(exc).__module__.startswith("selenium") and not isinstance(
                    exc, (ImportError, FileNotFoundError)
                ):
                    raise
                event.update(status="browser_unavailable", reason=type(exc).__name__)
                self.state["source_failures"][source.provider_id] = (
                    "browser_unavailable"
                )
                self.save()
                return None, event["status"]
            event["status"] = "received"
            return result, "received"
        return None, "retry_limit"

    def discovery(self, source, query, journal, year=None, kind="topic", page=1):
        provider = source.provider_id
        key = "S_" + digest([provider, query, journal, year, kind, page])[:24]
        saved = self.state["searches"].get(key)
        if saved:
            return saved
        if provider in self.state["source_failures"]:
            return None
        catalog = kind == "catalog" and hasattr(source, "catalog")
        if catalog:
            action = lambda: source.catalog(query, journal, year, page)
        elif provider == "vip_public":
            action = lambda: source.search(query, journal, year, page, kind=kind)
        else:
            action = lambda: source.search(query, journal, year, page)
        cost = (
            page
            if isinstance(source, CNKISource)
            and source.position != ((query, journal, year), page - 1)
            else 1
        )
        result, status = self.request(source, "search", key, action, cost)
        if status == "budget_exhausted":
            return None
        raw = (result or {}).get("records", [])
        rows = []
        for row in raw:
            if (
                not isinstance(row.get("title"), str)
                or not row["title"].strip()
                or not safe_url(row.get("url"))
            ):
                continue
            row = {
                k: row.get(k)
                for k in (
                    "title",
                    "authors",
                    "journal",
                    "issn",
                    "year",
                    "doi",
                    "url",
                    "source_record_id",
                    "request_url",
                )
            }
            row["journal"] = canonical_journal(row)
            row["doi"] = clean_doi(row["doi"])
            rows.append(
                dict(
                    row,
                    search_id=key,
                    provider=provider,
                    disposition="in_scope"
                    if row["journal"] == journal
                    else "other_or_unverified_journal",
                )
            )
        saved = dict(
            search_id=key,
            provider=provider,
            journal=journal,
            query=query,
            year=year,
            kind=kind,
            page=page,
            ran_at=now(),
            status="accessible" if result else status,
            records=rows,
            raw_count=(result or {}).get("raw_count", len(raw)),
            has_next=bool((result or {}).get("has_next")),
            source_url=(result or {}).get("url"),
            response_sha256=(result or {}).get("response_sha256"),
            pagination_status=(result or {}).get("pagination_status"),
        )
        self.state["searches"][key] = saved
        self.save()
        return saved

    def retrieval(self, source, record, *, observe=True):
        key = digest(
            [source.provider_id, record.get("source_record_id") or record["url"]]
        )
        if key in self.state["details"]:
            row = self.state["details"][key]
            if observe:
                self.state["observed"][key] = row
                self.save()
            return row
        if source.provider_id in self.state["source_failures"]:
            return None
        detail, status = self.request(
            source, "abstract", key, lambda: source.fetch_abstract(record)
        )
        if status == "budget_exhausted":
            return None
        if detail:
            detail["journal"] = canonical_journal(detail)
        result = article_observation(
            record, detail, source.provider_id, record["search_id"]
        )
        if status != "received":
            result["status"] = status
        result.update(
            response_sha256=(detail or {}).get("response_sha256"),
            keywords=(detail or {}).get("keywords", []),
        )
        self.state["details"][key] = result
        if observe:
            self.state["observed"][key] = result
        self.save()
        return result

    def resolve_on_page(self, anchor, page, source):
        candidates = (
            []
            if not page
            else [r for r in page["records"] if r["disposition"] == "in_scope"]
        )
        matches = [
            (r, resolve(anchor, r))
            for r in candidates
            if normalize(r["title"]) == normalize(anchor["title"])
            or clean_doi(anchor.get("doi"))
            and clean_doi(anchor.get("doi")) == r["doi"]
        ]
        checked = []
        for candidate, why in matches[:4]:
            if why == "author_year_unconfirmed":
                # An exact-title search can return a TOC item without authors/year.
                # Read its public detail once, but quarantine it until the identity agrees.
                detail = self.retrieval(source, candidate, observe=False)
                if detail:
                    why = resolve(anchor, detail)
            checked.append((candidate, why))
        agreed = [(r, why) for r, why in checked if why in ("doi", "bibliographic")]
        # A duplicate link can be collapsed. Distinct ambiguous identities cannot.
        unique = {r["source_record_id"] or r["url"]: (r, why) for r, why in agreed}
        return list(unique.values()), [
            {"url": r["url"], "decision": why} for r, why in checked
        ]

    def ordered(self, journal):
        return sorted(
            (s for s in self.sources.values() if journal in s.journals),
            key=lambda s: PRIORITY.get(s.provider_id, 10),
        )

    def trace(self, anchor, discover, source, decision, result=None):
        row = dict(
            anchor_title=anchor["title"],
            discovery_source=discover,
            abstract_source=source,
            resolution=decision,
            at=now(),
        )
        if result:
            row.update(
                abstract_status=result["status"],
                url=result["url"],
                hash=result.get("raw_hash"),
            )
        key = digest(
            [
                row.get(k)
                for k in (
                    "anchor_title",
                    "discovery_source",
                    "abstract_source",
                    "resolution",
                    "url",
                )
            ]
        )
        if not any(x["event_key"] == key for x in self.state["resolutions"]):
            self.state["resolutions"].append(dict(row, event_key=key))
            self.save()

    def article(self, anchor, origin=None):
        valid, attempted = [], []
        journal = anchor["journal"]
        if anchor.get("disposition") not in ("in_scope", None) or journal not in SEEDS:
            return valid, attempted
        for source in self.ordered(journal):
            provider = source.provider_id
            if provider in self.state["source_failures"]:
                attempted.append(
                    dict(
                        source=provider, status=self.state["source_failures"][provider]
                    )
                )
                continue
            if origin == provider:
                choices, rejected = [(anchor, "same_discovery_record")], []
            else:
                page = self.discovery(
                    source, anchor["title"], journal, anchor.get("year"), "title"
                )
                choices, rejected = self.resolve_on_page(anchor, page, source)
                if not choices and (anchor.get("authors") or []) and page:
                    first = anchor["authors"][0]
                    alternate = self.discovery(
                        source,
                        first + " " + anchor["title"],
                        journal,
                        anchor.get("year"),
                        "author_title",
                    )
                    choices, more = self.resolve_on_page(anchor, alternate, source)
                    rejected += more
                if not choices and anchor.get("year") and hasattr(source, "catalog"):
                    catalog = self.discovery(
                        source, anchor["title"], journal, anchor["year"], "catalog"
                    )
                    choices, more = self.resolve_on_page(anchor, catalog, source)
                    rejected += more
            if len(choices) != 1:
                status = (
                    "ambiguous"
                    if choices
                    else "identity_not_found"
                    if not rejected
                    else "identity_unconfirmed"
                )
                attempted.append(
                    dict(source=provider, status=status, candidates=rejected)
                )
                self.trace(anchor, origin or "historical_seed", provider, status)
                continue
            found, decision = choices[0]
            result = self.retrieval(source, found)
            status = result["status"] if result else "budget_or_access"
            attempted.append(
                dict(source=provider, status=status, match=decision, url=found["url"])
            )
            self.trace(anchor, origin or "historical_seed", provider, decision, result)
            if status == "valid_abstract":
                valid.append(result)
                # Preferred publisher plus an already-discovered alternate can both be
                # retained. Do not fetch unrelated third copies after success.
                if provider != "journal_shxyj_public" or origin in (None, provider):
                    break
        return valid, attempted

    def seed_checks(self):
        for i, seed in enumerate(self.seeds):
            key = str(i + 1)
            if key in self.state["seed_results"]:
                continue
            if seed["journal"] not in SEEDS:
                status, attempts = "out_of_scope", []
            else:
                valid, attempts = self.article(seed)
                if valid:
                    status = "recovered"
                elif any(a.get("match") for a in attempts):
                    status = "metadata_only"
                elif (
                    sum(r["budget_units"] for r in self.state["requests"])
                    >= self.spec["request_budget"]
                ):
                    status = "budget_exhausted"
                else:
                    status = "not_verified"
            self.state["seed_results"][key] = dict(
                seed=seed, status=status, attempts=attempts
            )
            self.save()

    def complete(self):
        rows, _ = build_articles(
            list(identity_projection(self.state["observed"]).values()),
            self.spec["relevance_groups"],
        )
        return sum(
            a["relevance_status"] == "relevant"
            for a in displayed(rows, self.spec["relevance_groups"])
        ) >= TARGET and set(SEEDS) <= {
            p["journal"]
            for p in self.state["searches"].values()
            if p["kind"] in ("topic", "catalog")
        }

    def page_candidates(self, page):
        if not page:
            return
        rows = [
            r
            for r in page["records"]
            if r["disposition"] == "in_scope"
            and (
                not page["year"]
                or not r.get("year")
                or str(r["year"]) >= str(page["year"])
            )
        ]
        # Cap per page, favor exact title match, then provider order without substituting query snippets.
        rows.sort(key=lambda r: normalize(page["query"]) not in normalize(r["title"]))
        for r in rows[:4]:
            marker = digest([r["provider"], r["source_record_id"] or r["url"]])
            if marker not in self.state["observed"]:
                self.article(r, r["provider"])
            if self.complete():
                return

    def execute(self):
        self.seed_checks()
        pending = [(q, "topic_base") for q in self.spec["queries"]]
        done = {normalize(q) for q in self.state["processed_queries"]}
        for _ in range(max(0, self.spec["max_queries"] - len(done))):
            adaptive = keywords(
                [
                    dict(a, url=a["source_url"])
                    for a in build_articles(
                        list(self.state["observed"].values()),
                        self.spec["relevance_groups"],
                    )[0]
                ],
                list(self.state["observed"].values()),
                done,
            )
            if len(done) and adaptive:
                pending.insert(0, (adaptive[0], "verified_article_term"))
            item = next(((q, r) for q, r in pending if normalize(q) not in done), None)
            if not item:
                break
            query, why = item
            year = self.spec["first_pass_from_year"] if not done else None
            pages = [
                (source, j, self.discovery(source, query, j, year))
                for j in SEEDS
                for source in self.ordered(j)
            ]
            # Every journal's first page is attempted before spending budgets on details.
            for source, j, first in pages:
                if self.complete():
                    break
                self.page_candidates(first)
                page = first
                for n in range(2, self.spec["max_pages"] + 1):
                    if not page or not page["has_next"] or self.complete():
                        break
                    new = self.discovery(source, query, j, year, page=n)
                    if not new or [r["url"] for r in new["records"]] == [
                        r["url"] for r in page["records"]
                    ]:
                        break
                    self.page_candidates(new)
                    page = new
            if not done and not any(
                p and any(r["disposition"] == "in_scope" for r in p["records"])
                for _, _, p in pages
            ):
                for source in self.ordered("社会学研究"):
                    if hasattr(source, "catalog"):
                        self.page_candidates(
                            self.discovery(source, query, "社会学研究", year, "catalog")
                        )
            done.add(normalize(query))
            self.state["processed_queries"].append(query)
            self.state["expansion"].append(dict(query=query, reason=why, at=now()))
            self.save()
            if self.complete():
                return "target_reached"
            if (
                sum(r["budget_units"] for r in self.state["requests"])
                >= self.spec["request_budget"]
            ):
                return "budget_exhausted"
        return "search_plan_exhausted"

    def export(self):
        projected = identity_projection(self.state["observed"])
        bundle = export_collection(dict(self.state, observed=projected), self.work)
        displayed(bundle["articles"], self.spec["relevance_groups"])
        details_by_url = {
            (r["provider"], r["url"]): r for r in self.state["observed"].values()
        }
        for paper in bundle["articles"]:
            for item in paper["provenance"]:
                row = details_by_url[(item["provider"], item["url"])]
                item.update(
                    source_title=row["title"],
                    source_authors=row["authors"],
                    source_doi=row["doi"],
                    response_sha256=row.get("response_sha256"),
                )
        bundle["counts"]["unique_relevant_abstracts"] = sum(
            a["relevance_status"] == "relevant" for a in bundle["articles"]
        )
        bundle["target_met"] = bundle["counts"]["unique_relevant_abstracts"] >= TARGET
        bundle.update(
            engine=ENGINE,
            capabilities=self.state["capabilities"],
            resolutions=self.state["resolutions"],
            expansion=self.state["expansion"],
        )
        write(self.work / "abstract_collection.json", bundle)
        write(
            self.work / "historical_regression.json",
            list(self.state["seed_results"].values()),
        )
        return bundle


class PublicJournal(JournalSource):
    capabilities = (
        "topic",
        "title",
        "author_title",
        "year",
        "catalog",
        "metadata",
        "abstract",
        "keywords",
    )

    def page(self, url):
        self.last_document, actual = super().page(url)
        return self.last_document, actual

    def fetch_abstract(self, record):
        detail = super().fetch_abstract(record)
        for tr in self.last_document.select("tr"):
            cells = tr.find_all("td", recursive=False)
            if (
                len(cells) == 2
                and cells[0].get_text(strip=True).strip("：: ") == "关键词"
            ):
                detail["keywords"] = [
                    x.strip()
                    for x in re.split(r"[；;，,]", cells[1].get_text(" ", strip=True))
                    if x.strip()
                ]
                break
        return detail

    def catalog(self, query, journal, year, page):
        if year is None:
            raise AccessStop(
                "catalog_year_required", "A historical catalog year is required"
            )
        # Same normal publisher search endpoint, constrained by its visible year field.
        from urllib.parse import urlencode

        url = "https://shxyj.ajcass.com/Magazine/?" + urlencode(
            {"Title": "", "Year": year, "Issue": "", "JChannelID": "", "page": page}
        )
        doc, actual = self.page(url)
        from abstract_sources import article_url, PUBLIC
        from urllib.parse import urljoin, parse_qs, urlsplit

        rows = []
        for a in doc.select("a[href]"):
            link = urljoin(actual, a["href"])
            if not article_url(link, "shxyj.ajcass.com", {"/magazine/show"}):
                continue
            ident = parse_qs(urlsplit(link).query).get("id", [""])[0]
            title = a.get_text(" ", strip=True)
            if ident.isdecimal() and title and normalize(query) in normalize(title):
                rows.append(
                    dict(
                        title=title,
                        journal=journal,
                        year=year,
                        source_record_id=ident,
                        url=PUBLIC + "/Magazine/Show?id=" + ident,
                    )
                )
        return dict(records=rows, has_next=False, url=url)


def collect(config, work, *, seeds=(), providers=None, resume=False):
    work = Path(work)
    if work.exists() and any(x.name != ".lock" for x in work.iterdir()) and not resume:
        raise FileExistsError("Use a new independent job directory")
    if resume and (
        not (work / "checkpoint.json").is_file()
        or load(work / "checkpoint.json").get("engine") != ENGINE
    ):
        raise ValueError("Refusing to resume a first-phase or foreign checkpoint")
    work.mkdir(parents=True, exist_ok=True)
    sources = providers if providers is not None else source_inventory(config, work)
    try:
        with job_lock(work):
            run = SearchRun(config, work, sources, list(seeds), resume)
            if run.state["status"] in ("running", "interrupted"):
                try:
                    run.state["status"] = run.execute()
                except KeyboardInterrupt:
                    run.state["status"] = "interrupted"
                run.save()
            return run.export()
    finally:
        if providers is None:
            for source in sources:
                source.close()
