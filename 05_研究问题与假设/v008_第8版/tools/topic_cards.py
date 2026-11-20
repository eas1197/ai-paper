"""Assemble the full Zotero reading ledger and retrieve cards for a research question."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from question_library import rank
from runtime import file_lock, load, now, write

MODULE = Path(__file__).resolve().parents[1]
WORK = MODULE.parent / "v006_第6版/outputs/五刊逐篇审读_20261118_attempt001"
JOURNALS = {"中国社会科学": 55, "社会学研究": 82, "社会": 9, "中国青年研究": 18, "探索与争鸣": 23}
SKILL = MODULE / "skills/social-science-topic-selection/SKILL.md"
FIELDS = ("question", "significance", "answer", "lesson", "locator")


def assemble(work):
    source = work / "全量来源.json"
    papers = load(source)
    if Counter(row["journal"] for row in papers) != JOURNALS:
        raise ValueError("五刊来源与锁定的187篇范围不一致")
    files = sorted((work / "审读笔记").glob("*.json"))
    by_id = {}
    for path in files:
        for note in load(path):
            paper_id = note["paper_id"]
            if paper_id in by_id or any(not note.get(key, "").strip() for key in FIELDS):
                raise ValueError(f"重复或缺少逐篇分析字段 {paper_id}")
            by_id[paper_id] = note
    if len(papers) != len(by_id) or {row["paper_id"] for row in papers} != set(by_id):
        raise ValueError("语料和逐篇笔记未对齐")
    cards = []
    for paper in papers:
        meta = {k: paper[k] for k in ("title", "authors", "journal", "year", "origin", "doi")}
        cards.append(dict(by_id[paper["paper_id"]], **meta))
    root = work / "逐篇选题卡.json"
    write(root, cards)
    report = ["# 五刊 187 篇论文的选题与意义", "",
              "逐篇笔记依据原文的重点章节。问题、回答和研究意义均为归纳；‘可借鉴’为本项目的迁移判断。"
              "涉及专题合辑按馆藏条目汇总，具体观点回原小节。全文页文本通读另见运行记录。", ""]
    for journal, count in JOURNALS.items():
        report += [f"## 《{journal}》· {count} 篇", ""]
        for row in [r for r in cards if r["journal"] == journal]:
            authors = "、".join(row["authors"]) if isinstance(row["authors"], list) else row["authors"]
            report += [f"### {row['title']}", "", f"{authors or '作者见原文'} · {row['year'] or '年份见原文'} · `{row['paper_id']}`", "",
                       f"- **问什么**　{row['question']}", f"- **为什么问**　{row['significance']}",
                       f"- **怎样回答**　{row['answer']}", f"- **可借鉴**　{row['lesson']}",
                       f"- **原文位置**　{row['locator']}", ""]
    (work / "187篇选题及意义.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    write(work / "逐篇卡来源锁.json", {"published_at": now(), "sources": file_lock(source),
                                "notes": [file_lock(path) for path in files], "cards": file_lock(root)})
    return root


def retrieve_cards(cards, theme, limit=8):
    ranked = rank(cards, lambda row: " ".join(row[k] for k in ("title", "question", "significance")), theme)
    return [{"score": score, **row} for row, score in ranked[:limit] if score > 0]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("assemble")
    retrieve = actions.add_parser("retrieve")
    retrieve.add_argument("--theme", required=True)
    args = parser.parse_args()
    if args.action == "assemble":
        print(assemble(WORK))
    else:
        print(json.dumps(retrieve_cards(load(WORK / "逐篇选题卡.json"), args.theme), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
