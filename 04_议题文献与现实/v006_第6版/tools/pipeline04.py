"""Operational bridge: issue selection -> acquisition -> abstract screening -> core25 -> 04/05."""
from __future__ import annotations
import importlib
import json
import re
import sys
from pathlib import Path

from runtime import ROOT, input_path, load, now, registry_module, run_directory, sha, value_hash, write

def collectors():
    location = registry_module("11") / "tools"
    if str(location) not in sys.path: sys.path.insert(0, str(location))
    return importlib.import_module("acquisition")

def source_inputs(file, run_id):
    file = Path(file).resolve(); data = load(file); raw = dict(data.get("collection", {}))
    stage = data.get("04", {})
    if not raw.get("theme"): raw["theme"] = stage.get("theme")
    if stage.get("annotations"):
        annotations = load(input_path(file.parent, stage["annotations"]))
        scope = annotations.get("topic_scope", {})
        selected = next((c for c in scope.get("issue_candidates", []) if c.get("topic_id") == scope.get("selected_topic_id")), None)
        if selected and not raw.get("issue"): raw["issue"] = selected.get("issue")
    for name in ("screening_file", "selection_file", "context_sources"):
        if raw.get(name): raw[name] = str(input_path(file.parent, raw[name]))
    return data, raw

def acquisition_work(run_id, config):
    # Stable job directory for resume; changing the query/config creates a different job.
    key = value_hash({k: v for k, v in config.items() if k not in ("screening_file", "selection_file", "context_sources")})[:16]
    return run_directory(run_id) / "acquisition" / ("cnki_" + key)

def acquire(file, run_id, *, action="collect", provider=None, context_provider=None, pdf_reader=None):
    _, config = source_inputs(file, run_id)
    module = collectors(); work = acquisition_work(run_id, config)
    if action == "context":
        from context_web import collect_context
        topic = config.get("issue") or (config.get("theme") if config.get("phase") == "scan" else None)
        if not topic: raise ValueError("初扫至少提供主题，聚焦检索需暂定议题")
        result = collect_context(topic, work / "context", provider=context_provider,
                                 sources=load(config["context_sources"]) if config.get("context_sources") else None,
                                 as_of=load(file).get("config", {}).get("as_of"))
        result["scope"] = "issue" if config.get("issue") else "broad_theme_scan"
        return result
    if action == "plan": return dict(module.plan(config), work=str(work))
    if action == "rank": return rank_core(work, config)
    if action == "bridge": return bridge(file, run_id, work, config)
    if action == "login":
        from cnki import SeleniumCNKI
        browser = SeleniumCNKI(config.get("browser", {}), work)
        try:
            browser.login(); input("在浏览器正常登录/核实机构权限后按Enter保存会话：")
        finally: browser.close()
        return {"status": "session_saved_locally", "work": str(work)}
    selected = None
    if action == "core":
        path = config.get("selection_file") or str(work / "core_selection_proposal.json")
        selection = load(path)
        selected = selection.get("selected", []) if isinstance(selection, dict) else selection
    return module.collect(config, work, provider, resume=action in ("resume", "core"), selection=selected, pdf_reader=pdf_reader)

def rank_core(work, config):
    work = Path(work); state = load(work / "checkpoint.json")
    supplied = load(config["screening_file"]) if config.get("screening_file") else []
    reviews = {r["paper_id"]: r for r in supplied}
    terms = config.get("relevance_terms") or [config.get("issue") or ""]
    rows = []
    for paper in state["records"]:
        if not paper.get("abstract"): continue
        review = reviews.get(paper["paper_id"], {})
        if review.get("decision") == "excluded": continue
        text = str(paper.get("title", "")) + str(paper.get("abstract", ""))
        lexical = sum(1 for term in terms if term and term in text) / max(len(terms), 1)
        scores = review.get("scores", {})
        reviewed = review.get("review_status") == "verified" and bool(review.get("reviewer")) and bool(review.get("read_at")) and bool(review.get("reason"))
        if reviewed:
            fields = ("relevance", "theory_authority", "design_quality", "journal_authority", "recency")
            if any(type(scores.get(k)) not in (int, float) or not 0 <= scores[k] <= 5 for k in fields):
                raise ValueError("摘要筛选评分须0—5并覆盖相关性/理论/设计/来源/时效")
            if scores["relevance"] == 0: continue
            score = sum(scores[k] * w for k, w in zip(fields, (.55, .20, .15, .05, .05)))
        else:
            scores = {"relevance": lexical, "theory_authority": None, "design_quality": None, "journal_authority": None, "recency": None}
            score = lexical
        rows.append({"paper_id": paper["paper_id"], "title": paper["title"], "scores": scores, "score": score,
                     "screening_status": "abstract_reviewed" if reviewed else "lexical_proposal_only", "perspective_tags": review.get("perspective_tags", []),
                     "selection_reason": review.get("reason") or "仅据查询词命中的检索优先级，尚未评价理论权威/设计质量；不能称最权威25篇",
                     "review": review})
    rows.sort(key=lambda r: (r["screening_status"] == "abstract_reviewed", r["scores"]["relevance"], r["score"]), reverse=True)
    target = max(25, config.get("core_target", 25)); chosen = []
    # Diversity is a proposal based on documented perspective tags, never invented from titles.
    for tag in ("classic", "recent", "counterevidence"):
        candidate = next((r for r in rows if tag in r["perspective_tags"] and r not in chosen and r["screening_status"] == "abstract_reviewed"), None)
        if candidate: chosen.append(candidate)
    chosen += [r for r in rows if r not in chosen][:max(0, target - len(chosen))]
    result = {"status": "proposal_requires_fulltext_review", "target": target, "selected": chosen,
              "ranked": rows, "shortfall": max(0, target - len(chosen)),
              "selection_criteria": "相关性优先，其次理论代表性/设计、权威来源、时效；经典/近年/反证需据摘要标注，非被引数排序",
              "confirmed_core_count": 0}
    write(work / "core_selection_proposal.json", result)
    return {"status": "needs_review", "selected": len(chosen), "shortfall": result["shortfall"], "path": str(work / "core_selection_proposal.json")}

def bridge(file, run_id, work, config):
    file, work = Path(file).resolve(), Path(work)
    state = load(work / "checkpoint.json"); raw = load(file)
    folder = work / "handoff_inputs"; folder.mkdir(exist_ok=True)
    number = max([int(p.name[8:]) for p in folder.glob("attempt_*")], default=0) + 1
    dest = folder / f"attempt_{number:03d}"; dest.mkdir()
    from providers import LocalLiteratureProvider
    metadata = work / "literature/metadata/papers.json"
    source_spec = {"path": str(metadata), "source_id": "S_CNKI", "format": "json", "retrieved_at": state.get("updated_at", now()),
                   "access_basis": config["access_basis"], "share_scope": "local_only"}
    imported = LocalLiteratureProvider().read(source_spec)
    annotation_path = raw.get("04", {}).get("annotations")
    annotations = load(input_path(file.parent, annotation_path)) if annotation_path else load(registry_module("04") / "templates/annotations04.json")
    for doc in annotations.get("documents", []):
        if doc.get("path"): doc["path"] = str(input_path(file.parent, doc["path"]))
    for entry in annotations.get("paper_reviews", {}).values():
        full = entry.get("fulltext", {})
        if full.get("path"): full["path"] = str(input_path(file.parent, full["path"]))
    annotations.setdefault("paper_reviews", {})
    for paper, record in zip(imported, state["records"]):
        pid = record["paper_id"]; entry = annotations["paper_reviews"].setdefault(pid, {})
        # Availability and proposed reading tasks, never fabricate abstract_read/fulltext_read.
        entry.setdefault("abstract", {"status": "not_read", "abstract_sha256": __import__("hashlib").sha256((paper.get("abstract") or "").encode()).hexdigest(), "reader": None, "read_at": None, "notes": None, "inclusion_status": "pending"})
        if record.get("fulltext", {}).get("status") == "downloaded_verified":
            entry.setdefault("fulltext", {"path": str(work / record["fulltext"]["path"]), "status": "not_read", "sha256": record["fulltext"]["sha256"],
                    "identity_verified": True, "identity_basis": record["fulltext"]["identity_basis"], "complete": False, "page_spans": [], "reader": None, "read_at": None, "notes": None})
    # Build core bibliography candidates; never claim all 25 are already read/citable.
    proposal_path = work / "core_selection.json"
    proposal = load(proposal_path) if proposal_path.exists() else load(work / "core_selection_proposal.json").get("selected", []) if (work / "core_selection_proposal.json").exists() else []
    lookup = {r["paper_id"]: r for r in state["records"]}
    selected = []
    for item in proposal:
        record = lookup.get(item["paper_id"], {}); receipt = record.get("fulltext", {})
        if receipt.get("status") == "downloaded_verified":
            selected.append(dict(record, citation_status="fulltext_read_and_claim_check_pending"))
    write(dest / "reference_candidates.json", selected)
    write_bibliography(dest, selected)
    annotations.setdefault("searches", []).extend(s for s in state["searches"] if s["search_id"] not in {x.get("search_id") for x in annotations.get("searches", [])})
    annotations["abstract_gap"] = {"available": sum(bool(r.get("abstract")) for r in state["records"]), "target": config.get("abstract_target", 100), "collection_status": state["status"], "coverage_limit": "现有查询、期刊与页数；获取不等于阅读"}
    context_file = work / "context/context_candidates.json"
    if context_file.exists():
        for candidate in load(context_file):
            cid = candidate["context_id"]; did = "DOC_" + cid
            if not any(d.get("document_id") == did for d in annotations.setdefault("documents", [])):
                annotations["documents"].append({"document_id": did, "source_id": "S_" + cid, "path": candidate["snapshot_path"],
                     "url": candidate["primary_url"], "retrieved_at": candidate["retrieved_at"], "access_basis": "公开原始网页正常访问", "share_scope": "local_only", "kind": candidate["type"]})
            if not any(c.get("context_id") == cid for c in annotations.setdefault("contexts", [])):
                annotations["contexts"].append(candidate)
    write(dest / "annotations04.json", annotations)
    workflow = json.loads(json.dumps(raw))
    previous_sources = []
    for s in workflow.get("04", {}).get("literature", []):
        old = dict(s); old["path"] = str(input_path(file.parent, old["path"])); previous_sources.append(old)
    workflow.setdefault("04", {}).update(literature=previous_sources + [source_spec], annotations=str(dest / "annotations04.json"), quality_review=None)
    workflow["collection"] = config
    workflow.setdefault("05", {})
    for key in ("annotations", "quality_review"):
        if workflow["05"].get(key): workflow["05"][key] = str(input_path(file.parent, workflow["05"][key]))
    workflow.setdefault("config", {})["archive_all_fulltexts"] = True
    write(dest / "workflow_collected.json", workflow)
    tasks = [{"phase": "abstract", "paper_id": r["paper_id"], "title": r.get("title"), "abstract": r.get("abstract"), "status": "not_read",
              "extract": ["X", "Y", "M", "Z", "relation_type", "direction", "scope", "design", "unknowns"], "output": "paper_reviews+evidence+relations"} for r in state["records"]]
    tasks += [{"phase": "core_fulltext", "paper_id": r["paper_id"], "pdf_path": str(work / r["fulltext"]["path"]), "status": "not_read", "output": "25核心全文对话、证据页码和实际拟引用位置"} for r in selected]
    write(dest / "reading_tasks.json", tasks)
    return {"status": "needs_review", "workflow_input": str(dest / "workflow_collected.json"), "reading_tasks": len(tasks), "reference_candidates": len(selected), "notice": "补读、复核、冻结后才通过G4/G5；不将25篇候选硬塞正文"}

def write_bibliography(dest, records):
    def escape(value):
        return str(value or "").replace("\\", "\\textbackslash{}") .replace("{", "\\{").replace("}", "\\}").replace("%", "\\%").replace("&", "\\&").replace("_", "\\_")
    bib, ris = [], []
    for r in records:
        bib.append("@article{" + re.sub(r"[^A-Za-z0-9_]", "_", r["paper_id"]) + ",\n" + ",\n".join(f"  {k} = {{{escape(v)}}}" for k, v in [("title", r.get("title")), ("author", " and ".join(r.get("authors", []))), ("journal", r.get("journal")), ("year", r.get("year")), ("doi", r.get("doi"))] if v) + "\n}")
        ris += ["TY  - JOUR", "TI  - " + str(r.get("title", "")), *["AU  - " + a for a in r.get("authors", [])], "JO  - " + str(r.get("journal") or ""), "PY  - " + str(r.get("year") or ""), "ER  -", ""]
    (dest / "reference_candidates.bib").write_text("\n\n".join(bib), encoding="utf-8")
    (dest / "reference_candidates.ris").write_text("\n".join(ris), encoding="utf-8")
