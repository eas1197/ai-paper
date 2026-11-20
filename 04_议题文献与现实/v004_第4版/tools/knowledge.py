"""Per-attempt SQLite snapshots using module 10 DDL; never open a shared/original DB for writing."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing

from runtime import ROOT, load, registry_module, sha, value_hash


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def build04(work, bundle, report):
    target = work / "knowledge.sqlite"
    if target.exists():
        raise FileExistsError("拒绝覆盖知识快照")
    with closing(sqlite3.connect(target)) as db:
        db.executescript((registry_module("10") / "knowledge.sql").read_text(encoding="utf-8"))
        with db:
            sources = {}
            for p in bundle["papers"]:
                for r in p["provenance"]:
                    sources.setdefault(r["source_id"], (r["source_id"], "literature_export", r["source_id"],
                        r.get("metadata_origin_path") or r.get("url") or r["source_id"], r["retrieved_at"],
                        r["metadata_sha256"], r["access_basis"], r["share_scope"], "unverified"))
            for d in bundle["documents"]:
                sources.setdefault(d["source_id"], (d["source_id"], d["kind"], d["source_id"], d.get("url") or d["path"],
                    d["retrieved_at"], d["sha256"], d["access_basis"], d.get("share_scope", "local_only"), "unverified"))
            db.executemany("INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?)", sources.values())
            for d in bundle["documents"]:
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?)", (d["document_id"], d["source_id"], d["path"], d["sha256"], d["kind"],
                           "acquired" if d["kind"] == "fulltext" else "not_applicable", 0))
            abstract_ids = {p["paper_id"] for p in bundle.get("abstracts", [])}
            full_ids = set(report.get("valid_fulltext_ids", []))
            for p in bundle["papers"]:
                pid = p["paper_id"]
                year = int(p["year"]) if str(p.get("year", "")).isdigit() else None
                review = p.get("review", {})
                db.execute("INSERT INTO papers VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (pid, p["title"], encoded(p["authors"]), year,
                    p.get("journal"), None, p.get("doi"), p.get("source_record_id"), p.get("abstract"), p["source_id"],
                    review.get("abstract", {}).get("read_at") if pid in abstract_ids else None, p.get("fulltext_document_id"),
                    review.get("fulltext", {}).get("read_at") if pid in full_ids else None,
                    "conflict" if p.get("identity_status") == "conflict" else "verified" if pid in full_ids else "unverified"))
                if pid in full_ids:
                    db.execute("UPDATE documents SET identity_verified=1,fulltext_status='fulltext_read' WHERE document_id=?", (p.get("fulltext_document_id"),))
            for e in bundle["evidence"]:
                # Invalid references are retained in bundle/error report, not inserted as false foreign keys.
                if db.execute("SELECT 1 FROM documents WHERE document_id=?", (e.get("document_id"),)).fetchone() and (not e.get("paper_id") or db.execute("SELECT 1 FROM papers WHERE paper_id=?", (e["paper_id"],)).fetchone()):
                    if e.get("evidence_class") in ("direct", "synthesis", "inference") and e.get("stance") in ("support", "contradict", "qualify", "context"):
                        db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?)", (e["evidence_id"], e.get("paper_id"), e["document_id"], e.get("locator", "unknown"), e.get("short_excerpt"), e.get("paraphrase", "unknown"), e["evidence_class"], e["stance"], e.get("extraction_method", "unknown"), e.get("review_status", "unverified"), e.get("source_sha256", "unknown")))
            for r in bundle["relations"]:
                if not db.execute("SELECT 1 FROM papers WHERE paper_id=?", (r.get("paper_id"),)).fetchone():
                    continue
                db.execute("INSERT OR IGNORE INTO relations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (r["relation_id"], r["paper_id"], r.get("X", "unknown"), r.get("Y", "unknown"), r.get("M"), r.get("Z"), r.get("relation_type", "unknown"), r.get("direction", "unknown"), r.get("mechanism"), r.get("unit", "unknown"), encoded(r.get("scope", {})), r.get("claimed_strength", "unknown"), r.get("supported_strength", "unknown"), r.get("read_basis", "unknown"), r.get("review_status", "unverified")))
                for eid in r.get("evidence_ids", []):
                    if db.execute("SELECT 1 FROM evidence WHERE evidence_id=?", (eid,)).fetchone():
                        db.execute("INSERT OR IGNORE INTO relation_evidence VALUES(?,?)", (r["relation_id"], eid))
            for purpose, rows, requirement in (("abstract100", bundle.get("abstracts", []), "abstract_read"), ("core25", bundle["core"], "fulltext_read")):
                for row in rows:
                    if db.execute("SELECT 1 FROM papers WHERE paper_id=?", (row.get("paper_id"),)).fetchone():
                        db.execute("INSERT OR IGNORE INTO corpus_membership VALUES(?,?,?,?,?)", (bundle["run_id"] + ":" + purpose, row["paper_id"], purpose, row.get("selection_reason") or row.get("review", {}).get("abstract", {}).get("relevance", "unknown"), requirement))
            issue = next((c.get("issue") for c in bundle["topic_scope"].get("issue_candidates", []) if c.get("topic_id") == bundle["topic_scope"].get("selected_topic_id")), None)
            plan = load(work / "plan.json")
            db.execute("INSERT INTO research_runs VALUES(?,?,?,?,?,?,?,?)", (bundle["run_id"], bundle.get("theme") or "unknown", issue, None,
                       value_hash(plan["config"]), sha(ROOT / "基础要求.md"), bundle["as_of"], report["status"]))
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("SQLite外键校验失败")


def build05(work, upstream_work, bundle, report):
    target = work / "knowledge.sqlite"
    if target.exists():
        raise FileExistsError("拒绝覆盖知识快照")
    with closing(sqlite3.connect((upstream_work / "knowledge.sqlite").resolve().as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(target)) as db:
        source.backup(db)
        db.execute("PRAGMA foreign_keys=ON")
        with db:
            db.execute("DELETE FROM hypothesis_evidence")
            db.execute("DELETE FROM hypotheses")
            for h in bundle["hypotheses"]:
                candidate = next((c for c in bundle["candidates"] if c.get("candidate_id") == h.get("candidate_id")), {})
                gap = candidate.get("primary_advance")
                if gap not in ("reality_theory_tension", "same_level_gap", "scope_change", "relation_revision"):
                    continue
                checks = next((r.get("checks", {}) for r in bundle["same_level_reviews"] if r.get("candidate_id") == h.get("candidate_id")), {})
                db.execute("INSERT OR IGNORE INTO hypotheses VALUES(?,?,?,?,?,?,?,?,?)", (h["hypothesis_id"], bundle["run_id"], gap,
                    h.get("research_question", "unknown"), encoded(h), encoded(checks), h.get("falsification", "unknown"), h.get("causal_claim_level", "unknown"), h.get("review_status", "pending")))
                for eid in h.get("evidence_ids", []):
                    if db.execute("SELECT 1 FROM evidence WHERE evidence_id=?", (eid,)).fetchone():
                        db.execute("INSERT OR IGNORE INTO hypothesis_evidence VALUES(?,?,?)", (h["hypothesis_id"], eid, "theory_dialogue"))
            db.execute("CREATE TABLE stage05_design(run_id TEXT PRIMARY KEY, design_json TEXT NOT NULL, content_sha256 TEXT NOT NULL, status TEXT NOT NULL)")
            db.execute("INSERT INTO stage05_design VALUES(?,?,?,?)", (bundle["run_id"], encoded(bundle["analysis_design"]), value_hash(bundle["analysis_design"]), report["status"]))
            db.execute("UPDATE research_runs SET question=?,status=? WHERE run_id=?", (bundle["analysis_design"].get("question"), report["status"], bundle["run_id"]))
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("05 SQLite外键校验失败")
