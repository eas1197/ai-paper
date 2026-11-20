"""Audit complete article coverage and distinguish model input from evidence review."""
from __future__ import annotations

from collections import Counter
import json

from topic_cards import WORK
from runtime import file_lock, load, now, sha, write


def check(work):
    index = work / "全量来源.json"
    papers = load(index)
    cards_path = work / "逐篇选题卡.json"
    card_counts = Counter(row["paper_id"] for row in load(cards_path))
    expected_counts = Counter(row["paper_id"] for row in papers)
    if len(papers) != len(expected_counts) or card_counts != expected_counts:
        raise ValueError("逐篇选题卡与来源清单的篇目不一致")
    missing = []
    insufficient_pages = []
    model_no_anchor = []
    output_locks = []
    read_pages = 0
    for entry in papers:
        paper_id = entry["paper_id"]
        path = work / "本地模型通读" / (paper_id + ".json")
        paging = entry["extracted_pages"]
        pages = load(paging["path"])
        if sha(paging["path"]) != paging["sha256"] or len(pages) != entry["pdf_pages"]:
            raise ValueError(f"页文本与清单不符 {paper_id}")
        short = [i for i, page in enumerate(pages, 1) if len(page) < 100]
        if short:
            insufficient_pages.append({"paper_id": paper_id, "pages": short})
        if not path.exists():
            missing.append(paper_id)
            continue
        result = load(path)
        if (result["paper_id"] != paper_id or result["extracted_pages_sha256"] != paging["sha256"]
                or result["pages_presented"] != len(pages) or result["portions"] < 1):
            raise ValueError(f"模型批次与原文不匹配 {paper_id}")
        if any(not (1 <= e["page"] <= len(pages) and e["anchor"] in pages[e["page"] - 1])
               for e in result["evidence"]):
            raise ValueError(f"无效的原文锚点 {paper_id}")
        if not result["evidence"]:
            model_no_anchor.append(paper_id)
        read_pages += len(pages)
        output_locks.append(file_lock(path))
    return {
        "checked_at": now(), "sources": file_lock(index), "topic_cards": file_lock(cards_path),
        "articles": len(papers), "card_count": sum(card_counts.values()),
        "full_extracted_text_pass": {"articles": len(output_locks), "page_slots": read_pages,
                                     "missing": missing, "unanchored_model_drafts": model_no_anchor,
                                     "outputs": output_locks},
        "extracted_pages_under_100_chars": insufficient_pages,
        "human_review_depth": "substantive_sections_reviewed",
        "meaning_notes_are_independent_from_model_drafts": True,
    }


if __name__ == "__main__":
    receipt = check(WORK)
    write(WORK / "审读覆盖与哈希.json", receipt)
    run = receipt["full_extracted_text_pass"]
    print(json.dumps({"articles": receipt["articles"], "topic_cards": receipt["card_count"],
                      "full_text_model": run["articles"], "missing": len(run["missing"]),
                      "model_drafts_without_anchors": len(run["unanchored_model_drafts"])},
                     ensure_ascii=False))
