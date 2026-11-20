"""Per-attempt normalized SQLite index using module 10's contract."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from common06 import MODULE, ROOT, load, now, sha, value_hash
from runtime import registry_module


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def insert(db, table, row):
    fields = list(row)
    # Table/column names are internal literals, never external SQL.
    db.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [row[k] for k in fields])


def build(work, bundle, status):
    target = work / "knowledge.sqlite"
    if target.exists():
        raise FileExistsError("拒绝覆盖知识快照")
    upstream = bundle.get("upstream", {}).get("path")
    origin = Path(upstream).parent if upstream else None
    with closing(sqlite3.connect(target)) as db:
        if origin and (origin / "knowledge.sqlite").is_file():
            with closing(sqlite3.connect((origin / "knowledge.sqlite").resolve().as_uri() + "?mode=ro", uri=True)) as source:
                source.backup(db)
        else:
            db.executescript((registry_module("10") / "knowledge.sql").read_text(encoding="utf-8"))
        db.execute("PRAGMA foreign_keys=ON")
        with db:
            run_id = bundle["run_id"]
            if not db.execute("SELECT 1 FROM research_runs WHERE run_id=?", (run_id,)).fetchone():
                insert(db, "research_runs", dict(run_id=run_id, theme="unknown", issue=None, question=None,
                       config_sha256=value_hash(bundle["protocol"]), requirements_sha256=sha(ROOT / "基础要求.md"),
                       created_at=now(), status=status))
            db.execute("CREATE TABLE stage06_snapshot(run_id TEXT PRIMARY KEY, protocol_json TEXT NOT NULL, content_sha256 TEXT NOT NULL, status TEXT NOT NULL)")
            db.execute("INSERT INTO stage06_snapshot VALUES(?,?,?,?)", (run_id, encoded(bundle["protocol"]), value_hash(bundle), status))
            def source_doc(identity, kind, path, digest, access, date):
                sid, did = "S06_" + identity, "D06_" + identity
                insert(db, "sources", dict(source_id=sid, kind=kind, title=identity, url_or_path=str(path),
                       retrieved_at=date, sha256=digest, access_basis=access, share_scope="local_only", status="verified" if status == "passed" else "unverified"))
                insert(db, "documents", dict(document_id=did, source_id=sid, local_path=str(path), sha256=digest,
                       document_type=kind, fulltext_status="acquired", identity_verified=0))
                return sid, did
            # 05 keeps questionnaire evidence in JSON: bring it into the normalized index here.
            evidence_ids = set()
            if origin:
                up = load(origin / "bundle.json")
                doc_ids = set()
                for doc in up.get("metadata_documents", []):
                    sid, did = "S06_META_" + doc["document_id"], doc["document_id"]
                    if not db.execute("SELECT 1 FROM documents WHERE document_id=?", (did,)).fetchone():
                        insert(db, "sources", dict(source_id=sid, kind=doc["kind"], title=did,
                               url_or_path=str(origin / doc["path"]), retrieved_at=doc["retrieved_at"],
                               sha256=doc["sha256"], access_basis=doc["access_basis"], share_scope="local_only", status="unverified"))
                        insert(db, "documents", dict(document_id=did, source_id=sid, local_path=str(origin / doc["path"]),
                               sha256=doc["sha256"], document_type=doc["kind"], fulltext_status="acquired", identity_verified=0))
                    doc_ids.add(did)
                for ev in up.get("measurement_evidence", []):
                    if ev.get("document_id") in doc_ids:
                        if not db.execute("SELECT 1 FROM evidence WHERE evidence_id=?", (ev["evidence_id"],)).fetchone():
                            insert(db, "evidence", dict(evidence_id=ev["evidence_id"], paper_id=None, document_id=ev["document_id"],
                                   locator=ev["locator"], short_excerpt=ev.get("short_excerpt"), paraphrase=ev["paraphrase"],
                                   evidence_class=ev["evidence_class"], stance=ev["stance"], extraction_method=ev["extraction_method"],
                                   review_status=ev["review_status"], source_sha256=ev["source_sha256"]))
                        evidence_ids.add(ev["evidence_id"])
            # Only metadata-verified datasets/variables are indexed as candidate records.
            datasets = {}
            for dataset in bundle["protocol"].get("datasets", []):
                did = dataset["dataset_id"]
                if did not in bundle["metadata"]:
                    continue
                sid, _ = source_doc("DATA_" + did, "survey_data_reference", dataset["path"], dataset["sha256"],
                                    dataset["access_basis"], dataset["verified_at"])
                insert(db, "datasets", dict(dataset_id=did, name=dataset["name"], wave=str(dataset["wave"]), source_id=sid,
                       file_path=dataset["path"], file_sha256=dataset["sha256"], questionnaire_document_id=None,
                       raw_identity_status=dataset["identity_status"], access_conditions=dataset["access_basis"]))
                datasets[did] = dataset
            measurements = {v["variable_id"]: v for v in bundle["measurements"]}
            valid_variables = set()
            for variable in bundle["protocol"].get("variables", []):
                vid = variable["variable_id"]
                m = measurements.get(vid)
                if variable.get("dataset_id") not in datasets or not m:
                    continue
                insert(db, "variables", dict(variable_id=vid, run_id=run_id, dataset_id=variable["dataset_id"],
                       source_variable=variable["source_variable"], role=m["role"], concept=m["concept"], question_id=m["question_id"],
                       question_text=m["question_text"], questionnaire_locator=m["questionnaire_locator"],
                       variable_label=variable.get("expected_label", ""), value_labels_json=encoded(m["value_labels"]),
                       special_missing_json=encoded(m["special_missing"]), population=m["population"], measurement_time=m["measurement_time"],
                       construction=encoded(variable.get("transform", {"op": "identity"})), rationale=m["rationale"], review_status="verified" if status == "passed" else "unverified"))
                valid_variables.add(vid)
                for eid in m.get("evidence_ids", []):
                    if eid in evidence_ids:
                        insert(db, "variable_evidence", dict(variable_id=vid, evidence_id=eid, role="questionnaire_mapping"))
            from methods06 import catalog
            for method in catalog():
                insert(db, "methods", dict(method_id=method["method_id"], name=method["name"], category="method_model_design_or_inference",
                       assumptions_json=encoded(method["required_checks"]), reporting_json=encoded(method["reporting_focus"]), status="unverified"))
            for ref in bundle["method_references"]:
                pid = ref["paper_id"]
                existing = db.execute("SELECT title FROM papers WHERE paper_id=?", (pid,)).fetchone()
                if existing and existing[0] != ref["title"]:
                    raise ValueError("方法文献paper_id与上游题录冲突")
                if not existing:
                    digest = ref["pdf_sha256"]
                    library = Path(bundle["protocol"]["method_library"])
                    sid, did = source_doc("METHOD_" + value_hash(pid)[:20], "fulltext", library / ref["pdf_path"],
                                          digest, ref["access_basis"], ref["retrieved_at"])
                    insert(db, "papers", dict(paper_id=pid, title=ref["title"], authors_json=encoded(ref["authors"]),
                           year=int(ref["year"]), journal_name=ref.get("journal"), metadata_source_id=sid,
                           fulltext_document_id=did, fulltext_read_at=ref["read_at"], verification_status="verified"))
                insert(db, "method_references", dict(method_id=ref["method_id"], paper_id=pid, reference_role=ref["reference_role"],
                       method_locator=encoded(ref["method_evidence"]), table_locator=encoded(ref.get("table_evidence", [])),
                       extracted_rules_json=encoded(ref), review_status="verified"))
            output_models = {m["model_id"]: m for m in bundle["models"]}
            failed_models = {m["model_id"] for m in bundle["failures"]}
            code = MODULE / "tools/engines.py"
            _, output_doc = source_doc("OUTPUT_" + value_hash(str(work))[:20], "model_output", work / "model_outputs.json",
                                       sha(work / "model_outputs.json"), "project_generated_aggregate", bundle.get("actual_run_at") or now())
            for spec in bundle["protocol"].get("models", []):
                mid, output = spec["model_id"], output_models.get(spec["model_id"])
                hid = spec.get("hypothesis_id")
                if not db.execute("SELECT 1 FROM hypotheses WHERE hypothesis_id=?", (hid,)).fetchone():
                    continue
                insert(db, "models", dict(model_id=mid, run_id=run_id, hypothesis_id=hid, method_id=spec["method_id"],
                       sample_version=output["sample_version"] if output else "not_executed", specification_json=encoded(spec),
                       code_path=str(code), code_sha256=sha(code), engine_environment_json=encoded(bundle["environment"]),
                       seed=bundle["protocol"]["seed"], executed_at=bundle.get("actual_run_at"),
                       diagnostic_status="verified" if status == "passed" else "needs_review",
                       result_status="verified" if status == "passed" else "executed" if output else "failed" if mid in failed_models else "planned"))
                for vid in [spec["outcome"]] + spec["predictors"]:
                    if vid in valid_variables:
                        db.execute("INSERT OR IGNORE INTO model_variables VALUES(?,?)", (mid, vid))
            for row in bundle["results"]:
                if row.get("estimate") is None:
                    continue
                insert(db, "results", {**{k: row[k] for k in ("result_id", "model_id", "outcome", "term", "estimate", "scale", "std_error",
                       "ci_low", "ci_high", "ci_level", "p_value", "n_obs", "n_clusters")}, "output_document_id": output_doc,
                       "verification_status": "verified" if status == "passed" else "executed"})
            if db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("06 SQLite外键校验失败")
