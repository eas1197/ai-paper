"""Offline integrity checks for the Codex candidate and an abstract-only evidence matrix."""

from codex_literature import ENGINE, evidence, group, observation, web_url
from collect_common import digest, load, normalize, sha, write


def receive(work, journals):
    state = load(work / "checkpoint.json")
    bundle = load(work / "abstract_collection.json")
    if (bundle.get("engine"), bundle.get("schema_version"), bundle.get("journals")) != (
        ENGINE, 2, journals,
    ) or state.get("collection_id") != bundle["collection_id"]:
        raise ValueError("Wrong Codex abstract collection")
    batch_traces = {}
    for batch in bundle["batches"]:
        if batch["status"] != "completed":
            continue
        folder = work / batch["batch"]
        raw, answer = folder / "events.jsonl", folder / "response.json"
        if (batch["event_sha256"] != sha(raw) or batch["response_sha256"] != sha(answer)
                or load(folder / "login_status.json") != {"chatgpt": True}):
            raise ValueError("CLI receipt, output, or authentication record is inconsistent")
        batch_traces[batch["batch"]] = (evidence(raw), load(answer)["papers"])

    observations = []
    for old in state["observations"]:
        batch = old["batch"]
        trace, source_rows = batch_traces[batch]
        position = int(old["observation_id"].split(":")[-1])
        restored = observation(source_rows[position - 1], trace, journals, batch, position)
        restored["searched_at"] = old["searched_at"]
        if restored != old:
            raise ValueError("Observation no longer matches the native tool receipt")
        observations.append(restored)
    papers, conflicts = group(observations)
    if papers != bundle["articles"] or conflicts != bundle["conflicts"] or len(papers) != bundle["count"]:
        raise ValueError("Identity groups or counts differ")

    rows = []
    for paper in papers:
        trace, _ = batch_traces[paper["batch"]]
        original = normalize(paper["abstract_excerpt"])
        snippets = [
            result.get("snippet", "") for event in trace for result in event.get("results", [])
            if web_url(result.get("url")) == web_url(paper["abstract_url"])
        ]
        snippet_confirmed = bool(original) and any(original in normalize(s) for s in snippets)
        rows.append(dict(
            paper, evidence_id="E_" + digest([paper["article_id"], paper["abstract_hash"]])[:24],
            excerpt_visible_in_logged_result=snippet_confirmed, analysis_status="not_analyzed",
        ))
    matrix = {
        "schema_version": 2, "mode": "abstract_only", "engine": ENGINE,
        "collection_id": bundle["collection_id"], "collection_sha256": digest(bundle),
        "theme": bundle["theme"], "journals": journals, "verified_rows": len(rows),
        "excerpt_visible_count": sum(row["excerpt_visible_in_logged_result"] for row in rows),
        "rows": rows, "conflicts": conflicts,
    }
    if bundle.get("run_mode") == "dev":
        matrix.update(run_mode="dev", formal_eligible=False,
                      workload_sha256=bundle["workload_sha256"])
    write(work / "literature_matrix.json", matrix)
    return matrix


def receive_direct(rows, trace, journals):
    """Apply the same article checks to separately recorded direct-search evidence."""
    accepted = []
    for position, row in enumerate(rows, 1):
        item = observation(row, trace, journals, "direct_web", position)
        excerpt = normalize(row["abstract_excerpt"])
        if not any(web_url(source.get("url")) == web_url(row["abstract_url"])
                   and excerpt in normalize(source.get("snippet") or "")
                   for event in trace for source in event.get("results", [])):
            raise ValueError("Direct-search abstract excerpt must be visible in its saved source receipt")
        accepted.append(dict(item, provider="codex_direct_web", intake="manual_supplement"))
    articles, conflicts = group(accepted)
    return {"intake": "manual_supplement", "automated_count": 0, "count": len(articles),
            "articles": articles, "conflicts": conflicts, "source_receipt_sha256": digest(trace)}
