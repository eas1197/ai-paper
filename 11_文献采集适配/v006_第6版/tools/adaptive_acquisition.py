"""Bounded adaptive search using the registered phase-two source adapters."""

from collections import Counter
from pathlib import Path
from urllib.error import URLError

from abstract_acquisition import (
    MODE, SEEDS, TARGET, article_observation, job_lock,
)
from abstract_sources import CNKISource
from collect_common import AccessStop, digest, load, normalize, now, write
from multi_acquisition import SearchRun, canonical_journal, displayed, source_inventory
from search_decision import ProviderError, WebIndex, ZhipuDecider, validate_decision
from verified_identity import MATCH, group_verified, resolve
from vip_public import VipPublic


ENGINE = "adaptive_v1"
USER_ACCESS = {"requires_user_access", "requires_purchase", "access_denied"}
TEMPORARY = {"layout_changed", "browser_unavailable", "source_error", "retry_limit"}
PAUSED = {
    "running", "interrupted", "paused", "budget_exhausted",
    "model_failed", "history_partial", "source_deferred",
}


class PauseRun(Exception):
    pass


def validate_record(record):
    if not isinstance(record, dict):
        raise ValueError("Malformed source record")
    for key in ("authors", "keywords"):
        if record.get(key) is not None and (
            not isinstance(record[key], list)
            or any(not isinstance(value, str) for value in record[key])
        ):
            raise ValueError("Malformed source contributor or keyword list")
    if record.get("source_record_id") is not None and not isinstance(
        record["source_record_id"], (str, int)
    ):
        raise ValueError("Malformed source identifier")


def registered_sources(config, work):
    enabled = config.get("sources", ["vip_public", "journal_shxyj_public", "cnki_normal_selenium"])
    if not isinstance(enabled, list) or not enabled or len(set(enabled)) != len(enabled):
        raise ValueError("Invalid source selection")
    previous = [name for name in enabled if name != "zhipu_web_index"]
    sources = {
        source.provider_id: source for source in source_inventory(dict(config, sources=previous), work)
    } if previous else {}
    if "vip_public" in sources:
        settings = config.get("vip", {})
        sources["vip_public"] = VipPublic(dict(
            settings, interval_seconds=max(20, float(settings.get("interval_seconds", 20))),
        ))
    sources["zhipu_web_index"] = WebIndex(SEEDS)
    return [sources[name] for name in enabled]


class AdaptiveRun(SearchRun):
    def __init__(self, config, work, sources, seeds, resume, decider, session, extension):
        self.decider, self.session = decider, session
        self.round_limit = config.get("model_rounds", 8)
        if type(self.round_limit) is not int or not 2 <= self.round_limit <= 20:
            raise ValueError("model_rounds must be 2–20")
        self.config = config
        self.sources = {source.provider_id: source for source in sources}
        self.work, self.seeds = work, list(seeds)
        self.file = work / "checkpoint.json"
        self.clock = 0
        self.active_journal = self.anchor = None
        identity = digest([
            ENGINE, config, list(self.sources), self.seeds,
            decider.provider_id if decider else None, getattr(decider, "model", None),
        ])
        if resume:
            self.state = load(self.file)
            if (self.state["engine"], self.state["config_sha256"]) != (ENGINE, identity):
                raise ValueError("Different engine, sources, model or frozen config")
            self.spec = self.state["spec"]
        else:
            if any(p.name != ".lock" for p in work.iterdir()):
                raise FileExistsError("Use a new run directory")
            # Reuse the v005 initialization and original relevance rules.
            super().__init__(config, work, sources, self.seeds, False)
            self.state.update(
                engine=ENGINE, config_sha256=identity, decisions=[],
                budgets=[], session=0, checked={}, web_hints={}, coverage_sweeps={},
            )
        if self.state["status"] not in PAUSED:
            if extension:
                raise ValueError("Cannot extend a completed run")
            return
        self.state.setdefault("coverage_sweeps", {})
        self.state["session"] += 1
        self.clock = self.state["session"]
        self.session_start = len(self.state["requests"])
        self.limit = self.spec["request_budget"] + sum(
            event["additional_units"] for event in self.state["budgets"]
        )
        if extension:
            if not resume or self.limit + extension > 2000:
                raise ValueError("Budget extension is for resume, total at most 2000")
            self.limit += extension
            self.state["budgets"].append({"at": now(), "additional_units": extension})
        for source, state in list(self.state["source_failures"].items()):
            if state in TEMPORARY:
                del self.state["source_failures"][source]
        self.save()

    def units(self):
        return sum(r["budget_units"] for r in self.state["requests"])

    def request(self, source, action, key, callback, cost=1):
        events = self.state["requests"]
        for event in events:
            if event["status"] == "started":
                event["status"] = "interrupted_unknown"
        attempts = [r for r in events if r["key"] == key and r["session"] == self.clock]
        for _ in range(max(0, self.spec["max_retries"] + 1 - len(attempts))):
            if self.units() + cost > self.limit:
                raise PauseRun("budget_exhausted")
            if self.session is not None and len(events) - self.session_start >= self.session:
                raise PauseRun("paused")
            event = dict(
                source=source.provider_id, operation=action, key=key, at=now(),
                status="started", budget_units=cost, session=self.clock,
                journal=self.active_journal,
            )
            events.append(event)
            self.save()
            try:
                result = callback()
                if not isinstance(result, dict):
                    raise ValueError("Provider result is not an object")
                if action == "search":
                    if not isinstance(result.get("records"), list):
                        raise ValueError("Provider result has malformed records")
                    for record in result["records"]:
                        validate_record(record)
                else:
                    validate_record(result)
            except AccessStop as exc:
                event.update(status=exc.status, reason=str(exc))
            except (TimeoutError, ConnectionError, URLError):
                event.update(status="retryable_error")
                self.save()
                continue
            except Exception as exc:
                event.update(status="source_error", reason=type(exc).__name__)
            else:
                event["status"] = "received"
                event["provider_request_id"] = result.get("request_id")
                if source.provider_id == "zhipu_web_index":
                    self.state["web_hints"][key] = result["index_leads"]
                return result, "received"
            state = event["status"]
            if (action == "search" or isinstance(source, CNKISource)) and (
                state in USER_ACCESS or state in TEMPORARY
            ):
                self.state["source_failures"][source.provider_id] = state
            self.save()
            return None, state
        return None, "retry_limit"

    def discovery(self, source, query, journal, year=None, kind="topic", page=1):
        self.active_journal = journal
        key = "S_" + digest([source.provider_id, query, journal, year, kind, page])[:24]
        saved = self.state["searches"].get(key)
        if saved and saved["status"] in TEMPORARY and saved.get("session") != self.clock:
            if source.provider_id not in self.state["source_failures"]:
                del self.state["searches"][key]
                self.state.setdefault("search_attempts", []).append(saved)
        result = super().discovery(source, query, journal, year, kind, page)
        if result and "session" not in result:
            result["session"] = self.clock
            self.save()
        return result

    def retrieval(self, source, record, *, observe=True):
        marker = record.get("source_record_id") or record["url"]
        key = digest([source.provider_id, marker])
        cached = self.state["details"].get(key)
        if cached is None or cached["status"] in TEMPORARY and cached["session"] != self.clock:
            if source.provider_id in self.state["source_failures"]:
                return None
            detail, status = self.request(
                source, "abstract", key, lambda: source.fetch_abstract(record)
            )
            cached = {"detail": detail, "status": status, "session": self.clock}
            self.state["details"][key] = cached
        detail, status = cached["detail"], cached["status"]
        decision = None
        if detail:
            detail = dict(detail, journal=canonical_journal(detail))
            detail_id = detail.get("source_record_id")
            record_id = record.get("source_record_id")
            if detail_id and record_id and str(detail_id) != str(record_id):
                decision = "source_record_conflict"
            else:
                linked = detail.get("url") == record["url"] or bool(detail_id and record_id)
                decision = resolve(record, detail, linked=linked)
        result = article_observation(
            dict(record, title=detail["title"]) if decision in MATCH else record,
            detail if decision in MATCH else None, source.provider_id, record["search_id"],
        )
        if status != "received":
            result["status"] = status
        elif decision not in MATCH:
            result["status"] = "identity_mismatch"
        result.update(
            identity_decision=decision,
            response_sha256=(detail or {}).get("response_sha256"),
            keywords=(detail or {}).get("keywords") or [],
        )
        if observe and self.anchor and result["status"] == "valid_abstract":
            if self.anchor is not record and resolve(self.anchor, result) not in MATCH:
                result["status"] = "anchor_mismatch"
        if observe:
            observation = digest([key, record["search_id"], record.get("authors")])
            self.state["observed"][observation] = result
        self.save()
        return result

    def article(self, anchor, origin=None):
        self.anchor = anchor
        try:
            return super().article(anchor, origin)
        finally:
            self.anchor = None

    def ordered(self, journal):
        return [
            source for source in super().ordered(journal)
            if source.provider_id != "zhipu_web_index"
        ]

    def resolve_on_page(self, anchor, page, source):
        if not page:
            return [], []
        candidates, rejected = {}, []
        for row in page["records"]:
            if row["disposition"] != "in_scope":
                continue
            if normalize(row["title"]) != normalize(anchor["title"]) and (
                not anchor.get("doi") or anchor["doi"] != row.get("doi")
            ):
                continue
            decision = resolve(anchor, row)
            if decision == "author_year_unconfirmed":
                detail = self.retrieval(source, row, observe=False)
                if detail and detail["status"] in ("valid_abstract", "missing_abstract", "invalid_abstract"):
                    decision = resolve(anchor, detail)
            if decision in MATCH:
                candidates[row["source_record_id"] or row["url"]] = (row, decision)
            rejected.append({"url": row["url"], "decision": decision})
        return list(candidates.values()), rejected

    def snapshot(self):
        papers, conflicts = group_verified(
            self.state["observed"].values(), self.spec["relevance_groups"]
        )
        return displayed(papers, self.spec["relevance_groups"]), conflicts

    def stats(self, papers):
        rows = list(self.state["observed"].values())
        pages = list(self.state["searches"].values())
        searches = {p["search_id"]: p["journal"] for p in pages}
        journal_counts = {}
        for journal in SEEDS:
            scoped = [p for p in pages if p["journal"] == journal]
            candidates = {r["url"] for p in scoped for r in p["records"]
                          if r["disposition"] == "in_scope"}
            verified = [r for r in rows if r["journal"] == journal
                        and r.get("identity_decision") in MATCH
                        and r["status"] not in ("identity_mismatch", "anchor_mismatch")]
            unique = [p for p in papers if p["journal"] == journal]
            journal_counts[journal] = {
                "search_calls": sum(
                    event["operation"] == "search" and (
                        event.get("journal") or searches.get(event["key"])
                    ) == journal for event in self.state["requests"]
                ),
                "accessible_topic_pages": sum(
                    p["kind"] == "topic" and p["status"] == "accessible"
                    and p["provider"] != "zhipu_web_index" for p in scoped
                ),
                "candidate_urls": len(candidates),
                "verified_urls": len({r["url"] for r in verified}),
                "valid_abstract_urls": len({r["url"] for r in verified if r["status"] == "valid_abstract"}),
                "unique_valid": len(unique),
                "unique_relevant": sum(p["relevance_status"] == "relevant" for p in unique),
            }
        return journal_counts

    def complete(self):
        papers, _ = self.snapshot()
        return sum(p["relevance_status"] == "relevant" for p in papers) >= TARGET and all(
            row["accessible_topic_pages"] for row in self.stats(papers).values()
        )

    def page_candidates(self, page):
        if not page:
            return
        query = normalize(page["query"])
        rows = [r for r in page["records"] if r["disposition"] == "in_scope"]
        rows.sort(key=lambda r: query not in normalize(r["title"]))
        for row in rows[:4]:
            key = digest([row["provider"], row["source_record_id"] or row["url"]])
            if self.state["checked"].get(key) in ("valid", self.clock):
                continue
            # A verified discovery source is cheap and sufficient. Cross-source
            # searches are reserved for missing abstracts or weak identity.
            source = self.sources[row["provider"]]
            result = self.retrieval(source, row)
            self.trace(row, row["provider"], row["provider"], "discovery_detail", result)
            success = result and result["status"] == "valid_abstract"
            if not success:
                valid, _ = self.article(row, row["provider"])
                success = bool(valid)
            self.state["checked"][key] = "valid" if success else self.clock
            self.save()
            if self.complete():
                return

    def search_action(self, action):
        source = self.sources[action["source"]]
        journal, query, page_no = action["journal"], action["query"], action["page"]
        primary = self.discovery(source, query, journal, page=page_no)
        self.page_candidates(primary)
        if page_no > 1 or source.provider_id == "zhipu_web_index" or self.complete():
            return primary, None
        if primary and any(r["disposition"] == "in_scope" for r in primary["records"]):
            return primary, None
        # Use one alternate evidence source after an empty or blocked result.
        backup = next((
            item for item in self.ordered(journal)
            if item is not source and item.provider_id not in self.state["source_failures"]
            and not isinstance(item, CNKISource)
        ), None)
        fallback = self.discovery(backup, query, journal) if backup else None
        self.page_candidates(fallback)
        return primary, fallback

    def cover_unsearched(self):
        if not self.config.get("complete_coverage", True):
            return
        covered = self.stats([])
        # Reserve an independent initial search only for missing journals.
        # This support path never creates model actions or contributes a fake pass.
        query = self.spec["queries"][0]
        for journal, counts in covered.items():
            if counts["accessible_topic_pages"]:
                continue
            source = next((
                item for item in self.ordered(journal)
                if item.provider_id not in self.state["source_failures"]
                and not isinstance(item, CNKISource)
            ), None)
            if source is None:
                continue
            page = self.discovery(source, query, journal)
            self.page_candidates(page)
            if page:
                self.state["coverage_sweeps"][journal] = page["search_id"]
                self.save()

    def context(self):
        papers, _ = self.snapshot()
        pages = list(self.state["searches"].values())
        histories = [d for d in self.state["decisions"] if d["status"] in ("received", "done")]
        valid = [p for p in papers if p["relevance_status"] == "relevant"]
        sample = (valid + [p for p in papers if p not in valid])[-15:]
        observations = {row["url"]: row for row in self.state["observed"].values()}
        recent = [p for p in pages if p["kind"] == "topic"][-12:]
        return {
            "theme": self.spec["theme"], "target": TARGET,
            "budget_remaining": self.limit - self.units(),
            "coverage": self.stats(papers),
            "sources": {key: list(value.journals) for key, value in self.sources.items()
                        if key not in self.state["source_failures"]},
            "unavailable_sources": self.state["source_failures"],
            "used": [[p["provider"], p["journal"], normalize(p["query"]), p["page"]]
                     for p in pages if p["kind"] == "topic" and
                     (p["status"] not in TEMPORARY or p.get("session") == self.clock)],
            "recent_queries": [{
                "source": p["provider"], "journal": p["journal"], "query": p["query"],
                "status": p["status"], "raw_count": p["raw_count"],
                "candidate_titles": [r["title"][:110] for r in p["records"]
                                     if r["disposition"] == "in_scope"][:5],
            } for p in recent],
            "next_pages": [{
                "source": p["provider"], "journal": p["journal"], "query": p["query"],
                "page": p["page"] + 1,
            } for p in recent if p["has_next"] and p["page"] < self.spec["max_pages"]],
            "previous_decision": histories[-1].get("reason") if histories else None,
            "latest_index_leads": [
                {"id": p["search_id"], "title": hint["title"]}
                for p in recent[-5:] for hint in self.state["web_hints"].get(p["search_id"], [])[:3]
            ],
            "leads": [{
                "id": p["article_id"], "title": p["title"], "journal": p["journal"],
                "relevance": p["relevance_status"],
                "keywords": [str(word)[:70] for word in
                             observations.get(p["source_url"], {}).get("keywords", [])[:8]],
            } for p in sample],
        }

    def execute(self):
        if self.seeds:
            # Identified regression articles are never mixed into blind jobs.
            if self.state["status"] != "running":
                self.state["seed_results"] = {
                    key: value for key, value in self.state["seed_results"].items()
                    if value["status"] in ("recovered", "out_of_scope")
                }
            self.seed_checks()
            return "history_completed" if all(
                row["status"] in ("recovered", "out_of_scope")
                for row in self.state["seed_results"].values()
            ) else "history_partial"
        decisions = self.state["decisions"]
        for item in decisions:
            if item["status"] == "started":
                item["status"] = "interrupted_unknown"
        while True:
            if self.complete():
                return "target_reached"
            if self.units() >= self.limit:
                return "budget_exhausted"
            pending = next((d for d in decisions if d["status"] == "received"), None)
            if pending is None:
                if len(decisions) >= self.round_limit:
                    self.cover_unsearched()
                    return "target_reached" if self.complete() else "model_round_limit"
                context = self.context()
                pending = dict(at=now(), status="started", context=context,
                               context_sha256=digest(context), provider=self.decider.provider_id)
                decisions.append(pending)
                self.save()
                try:
                    raw, receipt = self.decider.decide(context)
                    pending["receipt"] = receipt
                    why, actions, rejected = validate_decision(raw, context)
                except (ProviderError, URLError, TimeoutError, ValueError) as exc:
                    pending.update(status="failed", failure=type(exc).__name__,
                                   reason=str(exc)[:120] if isinstance(exc, ProviderError) else None)
                    return "model_failed"
                pending.update(status="received", reason=why,
                               actions=actions, rejected=rejected, cursor=0, results=[])
                self.save()
            for action in pending["actions"][pending["cursor"]:]:
                journal = action["journal"]
                result, fallback = self.search_action(action)
                papers, _ = self.snapshot()
                pending["results"].append({
                    "search_id": (result or {}).get("search_id"),
                    "status": (result or {}).get("status", "source_unavailable"),
                    "fallback_search_id": (fallback or {}).get("search_id"),
                    "coverage": self.stats(papers)[journal],
                })
                pending["cursor"] += 1
                self.save()
                if self.complete():
                    return "target_reached"
            pending["status"] = "done"
            self.save()
            if not pending["actions"] and not pending["rejected"]:
                if TEMPORARY.intersection(self.state["source_failures"].values()):
                    return "source_deferred"
                self.cover_unsearched()
                return "target_reached" if self.complete() else "model_stopped"

    def export(self):
        rows, conflicts = self.snapshot()
        counts = Counter(row["status"] for row in self.state["observed"].values())
        searches = list(self.state["searches"].values())
        origins = {(r["provider"], r["url"], r["search_id"]): r
                   for r in self.state["observed"].values() if r["status"] == "valid_abstract"}
        for paper in rows:
            for item in paper["provenance"]:
                row = origins[item["provider"], item["url"], item["search_id"]]
                item.update(source_title=row["title"], source_authors=row["authors"],
                            source_doi=row["doi"], response_sha256=row["response_sha256"])
        attempted = {event["journal"] for event in self.state["requests"]
                     if event["operation"] == "search" and event.get("journal")}
        relevant = sum(r["relevance_status"] == "relevant" for r in rows)
        bundle = dict(
            schema_version=1, acquisition_mode=MODE,
            collection_id=self.state["collection_id"], theme=self.spec["theme"],
            relevance_groups=self.spec["relevance_groups"], status=self.state["status"],
            target=TARGET, searches=searches, source_failures=self.state["source_failures"],
            attempted_journals=sorted(attempted),
            unattempted_journals=[j for j in SEEDS if j not in attempted],
            engine=ENGINE, articles=rows, conflicts=conflicts,
            counts={
                "retrieved_records": sum(s["raw_count"] for s in searches),
                "valid_source_abstracts": len({
                    (r["provider"], r["url"]) for r in self.state["observed"].values()
                    if r["status"] == "valid_abstract"
                }),
                "unique_valid_abstracts": len(rows),
                "unique_relevant_abstracts": relevant,
            },
            target_met=relevant >= TARGET,
            observation_status_counts=dict(counts), coverage=self.stats(rows),
            resolutions=self.state["resolutions"], decisions=self.state["decisions"],
            web_hints=self.state.get("web_hints", {}),
            coverage_sweeps=self.state.get("coverage_sweeps", {}),
            usage={
                "search_calls": sum(r["operation"] == "search" for r in self.state["requests"]),
                "abstract_calls": sum(r["operation"] == "abstract" for r in self.state["requests"]),
                "budget_units": self.units(), "fulltext_requests": 0, "pdf_requests": 0,
                "provider_actual_cost": None, "cost_unknown_reason": "无服务商实收费用凭证",
            },
        )
        receipts = [event.get("receipt") or {} for event in self.state["decisions"]]
        usage = [receipt["usage"] for receipt in receipts if isinstance(receipt.get("usage"), dict)]
        bundle["usage"].update(
            model_calls=len(receipts),
            model_confirmed_responses=sum(bool(r.get("request_id")) for r in receipts),
            model_reported_usage_count=len(usage),
            model_reported_tokens={
                key: sum(item.get(key) or 0 for item in usage)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            } if usage else None,
            model_actual_cost=None,
        )
        write(self.work / "historical_regression.json", list(self.state["seed_results"].values()))
        write(self.work / "abstract_collection.json", bundle)
        return bundle


def collect(config, work, *, seeds=(), providers=None, decider=None, resume=False,
            session_requests=None, add_budget=0):
    work = Path(work)
    if session_requests is not None and not 1 <= session_requests <= 2000:
        raise ValueError("Invalid session request count")
    if not 0 <= add_budget <= 2000:
        raise ValueError("Invalid extra budget")
    work.mkdir(parents=True, exist_ok=True)
    sources = providers if providers is not None else registered_sources(config, work)
    model = None if seeds else decider or ZhipuDecider(config.get("model", "glm-4-flash"))
    try:
        with job_lock(work):
            run = AdaptiveRun(config, work, sources, seeds, resume, model,
                              session_requests, add_budget)
            if run.state["status"] in PAUSED:
                try:
                    run.state["status"] = run.execute()
                except PauseRun as exc:
                    run.state["status"] = str(exc)
                except KeyboardInterrupt:
                    run.state["status"] = "interrupted"
                run.save()
            return run.export()
    finally:
        if providers is None:
            for source in sources:
                source.close()
