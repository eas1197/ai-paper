"""专题正式语料的刊物准入。目录外检索结果留在候选库。"""
from providers import norm


DESIGNATED = ("社会", "社会学研究", "中国社会科学", "管理世界")
PENDING_ALIASES = {"经济学研究": "经济研究", "探索与证明": "探索与争鸣"}


def source_journals(bundle, evidence):
    approved = {norm(name) for name in DESIGNATED}
    for alias in bundle.get("journal_aliases", []):
        name = PENDING_ALIASES.get(alias.get("original"))
        if (name and alias.get("decision") == "confirmed"
                and alias.get("canonical_name") == name and any(
                    evidence.get(eid, {}).get("evidence_class") == "direct"
                    and evidence[eid].get("review_status") == "verified"
                    for eid in alias.get("evidence_ids", []))):
            approved.add(norm(name))
    return approved


def eligible_papers(bundle, evidence):
    approved = source_journals(bundle, evidence)
    return {paper["paper_id"] for paper in bundle["papers"] if norm(paper.get("journal")) in approved}
