"""Check what the existing paper workflow can receive without granting research credit."""

from collect_common import digest, load, sha, write


def check(work, matrix):
    if matrix.get("run_mode") == "dev" or matrix.get("formal_eligible") is False:
        raise ValueError("Experimental literature cannot be exported by the regular handoff")
    from providers import LocalLiteratureProvider
    from literature_sources import DESIGNATED, online_record

    review_file = work / "pilot_review.json"
    review = load(review_file)
    eligible = set(review["article_ids"])
    if (review.get("decision") != "accepted_20"
            or review["collection_sha256"] != matrix["collection_sha256"]
            or len(eligible) < 20
            or not eligible <= {row["article_id"] for row in matrix["rows"]}):
        raise ValueError("Handoff requires a valid source review bound to this collection")
    rows = [row for row in matrix["rows"] if row["article_id"] in eligible]
    dest = work / "handoff_preflight"
    dest.mkdir(exist_ok=True)
    records = [
        dict(
            title=row["title"], authors=row["authors"], year=row["year"], doi=row["doi"],
            journal=row["journal"], url=row["abstract_url"], paper_id=row["article_id"],
            source_record_id=row["article_id"], abstract=None,
        )
        for row in rows
    ]
    metadata = dest / "candidate_metadata.json"
    write(metadata, records)
    spec = {
        "path": str(metadata), "source_id": "S_CODEX_NATIVE_CANDIDATE", "format": "json",
        "retrieved_at": max((row["searched_at"] for row in rows), default=None),
        "access_basis": "Codex 原生网页检索，逐条来源见证据矩阵",
        "share_scope": "local_only", "origin": "native_candidate",
    }
    imported = LocalLiteratureProvider().read(spec)
    input_ids = {row["paper_id"] for row in records}
    expected = {row["original_paper_id"] for row in imported}
    if len(imported) != len(rows) or input_ids != expected:
        raise ValueError("Legacy metadata preflight lost candidate papers")
    reading_tasks = [
        {
            "article_id": source["article_id"], "evidence_id": source["evidence_id"],
            "abstract_url": source["abstract_url"], "locator": source["abstract_locator"],
            "summary": source["abstract_summary"], "status": "source_reading_pending",
        }
        for source in rows
    ]
    write(dest / "abstract_reading_tasks.json", reading_tasks)
    # Preserve the full lineage for the receiving stage while keeping the
    # legacy metadata importer independent of the new abstract contract.
    batches = {b["batch"]: b for b in load(work / "abstract_collection.json")["batches"]}
    evidence_pack = {
        "schema_version": 1,
        "collection_sha256": matrix["collection_sha256"],
        "source_review_sha256": sha(review_file),
        "metadata_sha256": sha(metadata),
        "journals": matrix["journals"],
        "candidate_count": len(rows),
        "papers": [
            dict(
                task, journal=row["journal"], metadata_url=row["metadata_url"],
                metadata_event_id=row["metadata_event_id"],
                abstract_event_id=row["abstract_event_id"],
                excerpt=row["abstract_excerpt"], excerpt_sha256=row["excerpt_sha256"],
                summary_sha256=row["abstract_hash"], relevance_reason=row["relevance_reason"],
                native_receipt_sha256=batches[row["batch"]]["event_sha256"],
            )
            for task, row in zip(reading_tasks, rows)
        ],
    }
    write(dest / "native_abstract_handoff.json", evidence_pack)
    result = {
        "status": "metadata_import_compatible_formal_g4_pending",
        "source_collection_sha256": matrix["collection_sha256"],
        "metadata_imported": len(imported),
        "native_evidence_rows": len(evidence_pack["papers"]),
        "native_handoff_sha256": digest(evidence_pack),
        "legacy_journals": list(DESIGNATED),
        "new_journal_rows": sum(row["journal"] not in DESIGNATED for row in imported),
        "production_eligible_abstracts": sum(
            online_record(row, {}, row["retrieved_at"][:10]) for row in imported
        ),
        "source_abstracts_reviewed_in_pilot": len(eligible),
        "fulltext_read": 0, "formal_gate_executed": False,
        "remaining": [
            "生产 G4 的六刊范围及原生检索凭证适配",
            "原摘要、实读状态、逐篇证据和关系的正式接收",
            "25 篇核心全文、理论对话和现实材料验收",
        ],
    }
    write(dest / "report.json", result)
    return result
