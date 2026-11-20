"""Resumable metadata -> abstracts -> actual PDF acquisition. Default single worker."""
from __future__ import annotations
import os
import re
import shutil
from pathlib import Path
from typing import Protocol

from collect_common import AccessStop, article_id, contained, digest, load, normalize, now, sha, write
from cnki import SeleniumCNKI, verify_pdf

SEEDS = ["社会", "社会学研究", "中国社会科学", "管理世界", "经济学研究", "探索与证明"]
PROPOSED_ALIASES = {"经济学研究": "经济研究", "探索与证明": "探索与争鸣"}

class LiteratureProvider(Protocol):
    def search(self, query: str, cursor=None) -> dict: ...
    def fetch_abstract(self, record: dict) -> dict: ...
    def resolve_fulltext(self, record: dict) -> list[dict]: ...
    def download(self, record: dict, destination: Path) -> dict: ...
    def close(self): ...

def plan(config):
    if config.get("abstract_target", 100) < 100 or config.get("core_target", 25) < 25:
        raise ValueError("不得降低100摘要/25核心目标；初扫用phase=scan单独记账")
    if not config.get("access_basis"):
        raise ValueError("需说明正常授权/开放访问依据，不将有链接当成有下载权限")
    phase = config.get("phase", "focused")
    if phase not in ("scan", "focused"):
        raise ValueError("phase须scan/focused")
    if phase == "focused" and not config.get("issue"):
        raise ValueError("聚焦检索需要暂定议题；先scan比较议题，不要求预先锁定具体问题")
    queries = config.get("queries") or [config.get("issue") or config.get("theme")]
    if not queries or not all(isinstance(q, str) and q.strip() for q in queries):
        raise ValueError("至少提供一个有效主题/议题查询式")
    aliases = config.get("journal_aliases", {})
    journals, pending = [], []
    for original in config.get("journals", SEEDS):
        if original in PROPOSED_ALIASES:
            a = aliases.get(original, {})
            if a.get("confirmed") is True and a.get("evidence_url") and a.get("verified_at") and a.get("canonical_name"):
                journals.append(a["canonical_name"])
            else:
                pending.append({"original": original, "proposed": PROPOSED_ALIASES[original], "status": "needs_confirmation"})
        else:
            journals.append(original)
    if not journals:
        raise ValueError("没有已确认可用的来源期刊")
    result = {"schema_version": 1, "phase": phase, "theme": config.get("theme"), "issue": config.get("issue"),
              "queries": queries, "journals": sorted(set(journals)), "pending_aliases": pending,
              "abstract_target": config.get("abstract_target", 100), "core_target": config.get("core_target", 25),
              "max_pages_per_query": min(int(config.get("max_pages_per_query", 30)), 200),
              "max_records": int(config.get("max_records", 250)),
              "scan_limit": int(config.get("scan_limit", 20)), "download_scope": config.get("download_scope", "all_related"),
              "config_sha256": digest(config)}
    if result["download_scope"] not in ("all_related", "core_only", "none"):
        raise ValueError("download_scope须all_related/core_only/none")
    for field in ("max_pages_per_query", "max_records", "scan_limit"):
        if result[field] < 1: raise ValueError(f"{field}必须大于零")
    return result

def record_key(record):
    if record.get("doi"): return ("doi", record["doi"].lower().removeprefix("https://doi.org/"))
    if record.get("source_record_id"): return ("cnki", record["source_record_id"])
    return ("bibliographic", normalize(record.get("title")), tuple(sorted(normalize(a) for a in record.get("authors", []))), str(record.get("year")))

def read_checkpoint(work):
    path = work / "checkpoint.json"
    return load(path) if path.exists() else None

def collect(config, work, provider=None, *, resume=False, selection=None, pdf_reader=None):
    work = Path(work).resolve(); spec = plan(config)
    if work.exists() and any(p.name not in ("_private", ".gitignore") for p in work.iterdir()) and not resume:
        raise FileExistsError("采集目录已存在；使用resume保留旧文件，不覆盖")
    work.mkdir(parents=True, exist_ok=True)
    (work / ".gitignore").write_text("_private/\n.acquisition.lock\n", encoding="utf-8")
    checkpoint = read_checkpoint(work)
    if checkpoint and checkpoint["config_sha256"] != spec["config_sha256"]:
        raise ValueError("采集配置已变化，请新建采集目录/资源版本")
    lock = work / ".acquisition.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.close(fd)
    state = checkpoint or {"schema_version": 1, "config_sha256": spec["config_sha256"], "records": [], "searches": [], "errors": [], "created_at": now()}
    state["status"] = "running"
    write(work / "plan.json", spec)
    supplied_provider = provider is not None
    try:
        provider = provider or SeleniumCNKI(config.get("browser", {}), work)
        # Verify old receipts before treating a download as complete on resume.
        for record in state["records"]:
            receipt = record.get("fulltext", {})
            if receipt.get("status") == "downloaded_verified":
                p = contained(work, receipt["path"])
                if not p.is_file() or sha(p) != receipt.get("sha256"):
                    receipt.update(status="stale", reason="已有全文缺失/哈希变化，拒绝复用")
        def save():
            state["updated_at"] = now(); write(work / "checkpoint.json", state)
            export_records(work, state, config)
        save()
        seen = {record_key(r): r for r in state["records"]}
        # Pagination restarts from normal query entry on resume; dedup makes it idempotent.
        # No cursor replay from a detail tab or hidden endpoint.
        def enough():
            if spec["phase"] == "scan": return len(state["records"]) >= spec["scan_limit"]
            return sum(bool(r.get("abstract")) for r in state["records"]) >= spec["abstract_target"]
        if selection is None and not enough():
            for query in spec["queries"]:
                page_fingerprints = set()
                for page_number in range(1, spec["max_pages_per_query"] + 1):
                    page = provider.search(query, cursor=page_number if page_number > 1 else None)
                    signature = digest([record_key(r) for r in page["records"]])
                    if signature in page_fingerprints:
                        state["errors"].append({"kind": "repeated_page", "query": query, "page": page_number}); break
                    page_fingerprints.add(signature)
                    if not page["records"] and not page.get("empty_confirmed"):
                        raise AccessStop("layout_changed", "检索结果为空且未识别到无结果提示；不能当成检索完成")
                    log = {"search_id": "SEARCH_" + digest([query, page_number, now()])[:16], "provider": getattr(provider, "provider_id", "custom"),
                           "query": query, "page_or_cursor": page_number, "searched_at": now(), "journals": spec["journals"], "hits_raw": len(page["records"]),
                           "inclusion_rule": "已确认权威来源+议题查询；内容相关性待摘要复核", "exclusion_rule": "非目标来源/超年份/明确排除词", "access_status": "accessible", "coverage_limit": "当前查询式、来源、页数上限；不代表穷尽"}
                    state["searches"].append(log)
                    for candidate in page["records"]:
                        if candidate.get("journal") and candidate["journal"] not in spec["journals"]: continue
                        if record_key(candidate) in seen: continue
                        record = dict(candidate)
                        try:
                            detail = provider.fetch_abstract(record)
                            record.update({k: v for k, v in detail.items() if v not in (None, [], "")})
                        except AccessStop:
                            # Keep metadata found before the access challenge.
                            record.update(paper_id=article_id(record), acquisition_status="requires_user_access", abstract_read_status="not_read", fulltext_read_status="not_read", retrieved_at=now())
                            state["records"].append(record); save(); raise
                        except Exception as exc:
                            state["errors"].append({"kind": "abstract_failed", "url": record.get("url"), "error": type(exc).__name__})
                        if record.get("journal") not in spec["journals"]: continue
                        years = config.get("years")
                        if years and str(record.get("year")) not in {str(y) for y in years}: continue
                        if any(normalize(k) in normalize((record.get("title") or "") + (record.get("abstract") or "")) for k in config.get("exclude_terms", [])): continue
                        key = record_key(record)
                        if key in seen: continue
                        record.update(paper_id=article_id(record), source_id="S_CNKI", access_basis=config["access_basis"], share_scope="local_only", retrieved_at=now(),
                                      acquisition_status="abstract_available" if record.get("abstract") else "metadata_found", abstract_read_status="not_read", fulltext_read_status="not_read")
                        state["records"].append(record); seen[key] = record; save()
                        if enough() or len(state["records"]) >= spec["max_records"]: break
                    log["hits_unique"] = len(state["records"])
                    save()
                    if enough() or len(state["records"]) >= spec["max_records"] or not page.get("has_next"): break
                if enough() or len(state["records"]) >= spec["max_records"]: break
        # Re-fetch missing abstracts left by a previous access stop, independent of PDF state.
        if resume:
            for record in state["records"]:
                if record.get("abstract"): continue
                try:
                    record.update(provider.fetch_abstract(record))
                    if record.get("abstract"): record["acquisition_status"] = "abstract_available"
                except AccessStop: save(); raise
                except Exception as exc: state["errors"].append({"kind": "abstract_failed", "paper_id": record["paper_id"], "error": type(exc).__name__})
                save()
        to_download = []
        if selection is not None:
            requested = {s["paper_id"] for s in selection}
            available = {r["paper_id"] for r in state["records"]}
            if not requested.issubset(available): raise ValueError("核心选择含未检索到的文献ID")
            if len(requested) < spec["core_target"]: raise ValueError("核心选择不足25篇；保留缺口，不自动凑数")
            write(work / "core_selection.json", selection)
            to_download = [r for r in state["records"] if r["paper_id"] in requested]
        elif spec["phase"] != "scan" and spec["download_scope"] == "all_related":
            to_download = list(state["records"])
        for record in to_download:
            if record.get("fulltext", {}).get("status") == "downloaded_verified": continue
            if record.get("fulltext", {}).get("status") == "stale":
                # Never overwrite a changed old file; new receipt has a distinct filename.
                suffix = "_retry_" + digest(now())[:8]
            else: suffix = "" if not record.get("fulltext") else "_retry_" + digest(now())[:8]
            dest = work / "literature/fulltext" / (record["paper_id"] + suffix + ".pdf")
            try:
                response = provider.download(record, dest)
                if response.get("status") == "file_received":
                    receipt = verify_pdf(dest, record, pdf_reader)
                    receipt["path"] = str(dest.relative_to(work)).replace("\\", "/")
                    receipt["retrieved_at"] = now()
                    record["fulltext"] = receipt
                else: record["fulltext"] = response
            except AccessStop as exc:
                record["fulltext"] = {"status": exc.status, "reason": str(exc)}; save(); raise
            except Exception as exc:
                record["fulltext"] = {"status": "verification_or_download_failed", "reason": f"{type(exc).__name__}: {exc}"}
            save()
        state["status"] = "collected" if enough() else "needs_more_sources"
        if any(r.get("fulltext", {}).get("status") != "downloaded_verified" for r in to_download): state["status"] = "needs_fulltext"
        save()
    except AccessStop as exc:
        state["status"] = exc.status; state["errors"].append({"kind": exc.status, "message": str(exc), "at": now()})
        write(work / "checkpoint.json", state); export_records(work, state, config)
    except Exception as exc:
        state["status"] = "failed"; state["errors"].append({"kind": type(exc).__name__, "message": str(exc), "at": now()})
        write(work / "checkpoint.json", state); export_records(work, state, config)
        raise
    finally:
        try:
            if provider is not None and not supplied_provider: provider.close()
        finally: lock.unlink(missing_ok=True)
    return report(work, state, spec)

def export_records(work, state, config):
    rows = []
    for r in state["records"]:
        public_fields = {"paper_id", "title", "authors", "journal", "year", "doi", "source_record_id", "abstract", "url",
                         "source_id", "access_basis", "share_scope", "retrieved_at", "acquisition_status", "abstract_read_status", "fulltext_read_status", "fulltext"}
        row = {k: v for k, v in r.items() if k in public_fields}
        receipt = r.get("fulltext", {})
        if receipt.get("status") == "downloaded_verified":
            path = contained(work, receipt["path"])
            if path.is_file() and sha(path) == receipt["sha256"]:
                row["fulltext_path"] = str(path)
        rows.append(row)
    write(work / "literature/metadata/papers.json", rows)
    write(work / "search_log.json", state["searches"])
    write(work / "downloads.json", [{"paper_id": r["paper_id"], "title": r.get("title"), **r.get("fulltext", {"status": "not_requested"})} for r in state["records"]])

def report(work, state, spec):
    counts = {"metadata": len(state["records"]), "abstracts_available": sum(bool(r.get("abstract")) for r in state["records"]),
              "fulltexts_verified": sum(r.get("fulltext", {}).get("status") == "downloaded_verified" for r in state["records"]), "abstracts_read": 0, "fulltexts_read": 0}
    value = {"status": state["status"], "counts": counts, "targets": {"abstracts": spec["abstract_target"], "core": spec["core_target"]},
             "pending_aliases": spec["pending_aliases"], "phase": spec["phase"], "metadata_path": str(work / "literature/metadata/papers.json"),
             "queries_not_executed": [q for q in spec["queries"] if q not in {s["query"] for s in state["searches"]}],
             "work": str(work), "business_gate_passed": False, "downloads_do_not_mean_read": True}
    write(work / "collection_report.json", value)
    return value
