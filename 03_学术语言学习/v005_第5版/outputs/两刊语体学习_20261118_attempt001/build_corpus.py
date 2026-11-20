"""Build the two-journal writing study from frozen, read-only Zotero inputs."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

from pypdfium2 import PdfDocument


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
STRUCTURE = ROOT / "02_文章结构学习/v005_第5版/outputs"
CSS_PRIOR = STRUCTURE / "中国社会科学_20261118_attempt001"
SOCI = STRUCTURE / "社会学研究_20261118_attempt001"
CSS = HERE / "work/css"
sys.path.insert(0, str(ROOT / "07_三稿独立写作/v011_第11版/tools"))
from exemplars07 import MOVES, read_index, select


HEADINGS = {
    "question": r"问题|引言|导[论言]|缘起|背景",
    "literature": r"综述|回顾|评述|述评|研究进展|文献|争论|辨析",
    "hypothesis": r"假[设说]|理论|框架|机制|路径",
    "design": r"研究设计|数据|测量|分析策略|方法|模型|案例选择",
    "results": r"结果|发现|描述|实证分析|估计|检验|比较",
    "discussion": r"结[论语]|讨论|小结|余论|启示|总结|结语",
}
BODY_CUES = {
    "question": r"本文|本研究|何以|为什么|有必要|问题",
    "literature": r"既有|已有|以往|文献|一方面|另一方面|视角",
    "hypothesis": r"假设|预期|机制|据此|基于|理论|如果|随着",
    "design": r"数据|指标|测量|变量|样本|调查|模型|方法",
    "results": r"估计|结果|表\d|图\d|关联|差异|系数|显著",
    "discussion": r"结论|讨论|贡献|启示|本研究|本文|发现",
}
BORDERS = {
    "question": "先交代读者已经知道的现实变化或理论现象。",
    "literature": "先指出各解释共同面对的对象或结果。",
    "hypothesis": "将前文已有理论落实到可区分的概念与关系。",
    "design": "先交代设计需要回答的具体比较。",
    "results": "沿用设计中已说明的结局、分组和口径。",
    "discussion": "从实证结果中选出能回答开篇问题的发现。",
}
NEXT = {
    "question": "接着交代将比较什么以及用什么材料回答。",
    "literature": "说明已有解释之间的区别怎样限定本文问题。",
    "hypothesis": "把预期交给下一节的变量和观测设计。",
    "design": "交代这种设定将产生什么可对照的结果。",
    "results": "按研究问题进入下一步比较或解释。",
    "discussion": "将判断落实到证据覆盖的对象和条件。",
}
HOLDOUT = {
    "Y8WNZ3AN", "J38BV4A5", "6V7LJIWN", "2SKTAPLF",
    "DD4I5QA4", "GTUTSZDI", "FQ7RQ5NC", "GZFRXXPL",
}
ELIGIBLE = {"定量", "定量描述", "实验", "混合"}
BOUND_ABSTRACTS = {
    "MK385948": ("本文试图使用实证分析", "一、研究目的"),
    "S823QAM2": ("本文运用推拉理论模型", "关键词"),
    "2SKTAPLF": ("基于文献考察和经验观察", "关键词"),
}
NO_CHINESE_ABSTRACT = {
    "X88U69EU": "首页附英文摘要，中文写作范例仅取正文。",
    "8B575M9S": "首页题名后直接进入前言。",
    "7YINUFQE": "首页题名后直接进入正文。",
    "VTLX3U9G": "首页题名后直接进入正文。",
    "TWLELHMQ": "首页题名后直接进入正文。",
    "CX9UWVCX": "笔谈编者按之后是本文题名与正文。",
    "7A7CYZHB": "首页题名后直接进入正文。",
    "G5HIFZKQ": "首页题名后直接进入正文。",
    "WPWDXCNN": "研讨会发言，编者按后的本文题名下直接进入正文。",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def clean(text):
    text = unicodedata.normalize("NFKC", text.replace("\x82", "，"))
    return re.sub(r"[\s\ud800-\udfff\ue000-\uf8ff]", "", text)


def abstract_moves(article, blocks):
    key = article["attachment_key"]
    if key in BOUND_ABSTRACTS:
        start, end = BOUND_ABSTRACTS[key]
        with PdfDocument(article["pdf_path"]) as doc, closing(doc[0]) as page, closing(page.get_textpage()) as text_page:
            text = clean(text_page.get_text_range())
        start_at = text.index(start)
        segment = text[start_at:text.index(end, start_at)]
        sentences = re.findall(r"[^。！？!?]+[。！？!?]?", segment)
        abstract = {"start_page": 1, "text": segment, "sentences": []}
        cursor = 0
        for i, sentence in enumerate(sentences, 1):
            abstract["sentences"].append({"id": f"A{i:02d}", "start": cursor, "end": cursor + len(sentence)})
            cursor += len(sentence)
        status = "首页定位已复核，无显式摘要标签"
    else:
        abstract = next((b for b in blocks if b["section"] == "摘要"), None)
        status = "已取得中文摘要候选"
    if abstract is None:
        return [], NO_CHINESE_ABSTRACT[key]
    result = []
    for sent in abstract["sentences"]:
        text = abstract["text"][sent["start"]:sent["end"]]
        tags = []
        for tag, pattern in (
            ("结果", r"发现|结果(表明|显示)|结果如下|显著|不显著"),
            ("目的", r"本文.{0,16}(考察|研究|试图|旨在|讨论|探讨|分析|检验)|本研究旨在"),
            ("数据或方法", r"数据|调查|模型|基于|采用|通过|测量"),
            ("缺口或问题", r"缺乏|尚[无未待]|较少|然而|问题|未能|不足"),
            ("含义或应用", r"启示|意义|提供.{0,7}(参考|视角|依据)|有助于|未来"),
        ):
            if re.search(pattern, text):
                tags.append(tag)
        if not tags and not result and re.search(r"[\u3400-\u9fff]", text):
            tags = ["背景或起始判断"]
        result.append({"id": sent["id"], "pdf_page": abstract["start_page"], "anchor": text[:12],
                       "role_candidates": tags or ["语义待确认"]})
    return result, status


def select_block(blocks, move, page=None):
    candidates = [b for b in blocks if b["section"] != "摘要" and len(b["text"]) >= 45]
    if page is not None:
        on_page = [b for b in candidates if b["start_page"] <= page <= b["end_page"]]
        if not on_page:
            raise ValueError(f"标注页{page}缺正文定位")
        candidates = on_page
    if not candidates:
        raise ValueError("没有可定位的正文候选")
    def rank(block):
        title = block["section"]
        # Rank within a reviewed page, or among matching sections for prior outlines.
        return (bool(re.search(HEADINGS[move], title)),
                min(5, len(re.findall(BODY_CUES[move], block["text"]))),
                -block["start_page"])
    return max(candidates, key=rank)


def style_cards():
    sources = [
        (SOCI, {r["附件键"]: r for r in rows(HERE / "社会学研究逐篇观察.tsv")}),
        (CSS, {r["附件键"]: r for r in rows(HERE / "中国社会科学范例定位.tsv")}),
    ]
    css_routes = {r["附件键"]: r["章节关系初读"] for r in rows(CSS_PRIOR / "章节路线.tsv")}
    for folder, labels in sources:
        inventory = load(folder / "馆藏清单.json")
        papers = [a for a in inventory["articles"] if a.get("pdf_path")]
        if {a["attachment_key"] for a in papers} != labels.keys():
            raise ValueError(f"馆藏和逐篇标注未逐条对应: {inventory['selection']}")
        for article in papers:
            label = labels[article["attachment_key"]]
            source = load(folder / "work" / f"{article['paper_id']}.json")
            blocks = source["blocks"]
            if not blocks or article["extraction_status"] == "failed":
                raise ValueError(f"读取得到空正文: {article['title']}")
            note = label.get("逐篇观察") or css_routes[article["attachment_key"]]
            confirmed_page = int(label["定位PDF页"]) if label.get("定位PDF页") else None
            move = label["功能"]
            block = select_block(blocks, move, confirmed_page)
            spans = defaultdict(lambda: dict(paragraphs=0, sentences=0, chinese_characters=0, pdf_pages=set()))
            for item in blocks:
                section = spans[item["section"]]
                section["paragraphs"] += 1
                section["sentences"] += len(item["sentences"])
                section["chinese_characters"] += len(re.findall(r"[\u3400-\u9fff]", item["text"]))
                section["pdf_pages"].update(range(item["start_page"], item["end_page"] + 1))
            sections = [{"section": k, **v, "pdf_pages": sorted(v["pdf_pages"])} for k, v in spans.items()]
            cite_page = confirmed_page or block["start_page"]
            abstract, abstract_status = abstract_moves(article, blocks)
            yield {
                "paper_id": article["paper_id"], "attachment_key": article["attachment_key"],
                "title": article["title"], "journal": inventory["selection"], "year": article["year"],
                "issue": article["issue"], "pdf": article["pdf_path"], "sha256": article["sha256"],
                "pdf_pages": article["pdf_pages"], "study_type": label["研究类型"], "note": note, "move": move,
                "section_heads": article["section_heading_candidates"], "sections": sections,
                "abstract_sentences": abstract, "abstract_status": abstract_status, "flags": article["flags"],
                "reviewed_location": bool(confirmed_page), "pdf_page": cite_page,
                "section": block["section"], "block_id": block["id"], "source_anchor": block["text"][:12],
                "block_page_span": [block["start_page"], block["end_page"]],
                "locator_index": str((folder / "定位索引" / f"{article['paper_id']}.json").relative_to(ROOT)),
                "source_snapshot": str((folder / "馆藏清单.json").relative_to(ROOT)),
                "working_text": str((folder / "work" / f"{article['paper_id']}.json").relative_to(ROOT)),
            }


def exemplar_index(cards):
    papers = {
        c["paper_id"]: {k: c[k] for k in ("title", "journal", "pdf", "sha256")}
        | {"design": c["study_type"]}
        for c in cards if c["study_type"] in ELIGIBLE
    }
    held = [c["paper_id"] for c in cards if c["attachment_key"] in HOLDOUT]
    examples = []
    for c in cards:
        pid, move = c["paper_id"], c["move"]
        if pid not in papers or pid in held:
            continue
        examples.append({
            "example_id": f"{pid}_{move}", "paper_id": pid, "move": move,
            "section": c["section"], "pdf_page": c["pdf_page"], "source_anchor": c["source_anchor"],
            "topic": c["title"], "before": BORDERS[move], "advance": c["note"],
            "after": NEXT[move], "style": MOVES[move],
            "conditions": f"原载文章类型为{c['study_type']}。模仿行文时，用当前研究锁定的比较、变量和证据。",
            "annotation_status": "paper_reading_with_page" if c["reviewed_location"] else "outline_with_candidate_page",
            "source_block_id": c["block_id"],
        })
    by_key = {c["attachment_key"]: c for c in cards}
    for row in rows(HERE / "重点段落补读.tsv"):
        c = by_key[row["附件键"]]
        pid, move, number = c["paper_id"], row["功能"], int(row["PDF页"])
        if pid not in papers or pid in held:
            raise ValueError(f"补读范例来源不在建库集: {pid}")
        block = next(b for b in load(ROOT / c["working_text"])["blocks"] if b["id"] == row["段落候选号"])
        if not block["start_page"] <= number <= block["end_page"]:
            raise ValueError(f"补读范例定位不符: {pid} {number}")
        examples.append({
            "example_id": f"{pid}_{move}_{block['id']}", "paper_id": pid, "move": move,
            "section": block["section"], "pdf_page": number, "source_anchor": block["text"][:12],
            "topic": c["title"], "before": row["承接"], "advance": row["本段推进"],
            "after": row["下一步"], "style": row["语言写法"],
            "conditions": "写作时以当次研究可复核的材料、比较条件和结果为准。",
            "annotation_status": "paragraph_reviewed", "source_block_id": block["id"],
        })
    return {"schema_version": 1, "status": "pilot", "papers": papers,
            "held_out_paper_ids": held, "examples": examples}


def evaluate(index, cards):
    scores = []
    for c in cards:
        if c["paper_id"] not in index["held_out_paper_ids"]:
            continue
        query = {"move": c["move"], "topic": c["title"], "design": c["study_type"], "journal": c["journal"]}
        for mode in ("manual", "topic", "function"):
            found = select(index, query, mode, 2)
            scores.append({"paper_id": c["paper_id"], "move": c["move"], "mode": mode,
                           "examples": [i["example_id"] for i in found],
                           "right_function": sum(i["move"] == c["move"] for i in found),
                           "same_journal": sum(i["journal"] == c["journal"] for i in found)})
    return scores


def write_index(cards):
    header = [
        "# 两刊逐篇语体学习与范例定位",
        "",
        "学术语体学习使用本地两刊论文。逐篇记录论证路线、一个重点观察、可回看的正文位置、摘要句和章节候选统计。各行资料用于行文。研究结论和数据仍取当次论文的证据。",
        "",
        "《社会学研究》观察来自本轮逐篇读到的摘要、正文位置和章节路线。《中国社会科学》复用前期逐篇章节研读，新增功能标签和自动段落定位。自动标注、抽取的节长及部分页段仍按候选记录。",
        "",
    ]
    for journal in ("中国社会科学", "社会学研究"):
        journal_cards = [c for c in cards if c["journal"] == journal]
        header.extend((f"## {journal}（{len(journal_cards)}篇）", "",
                       "| 文章 | 写作功能 | 重点读法 |",
                       "|---|---|---|"))
        for c in journal_cards:
            original = Path(c["pdf"]).as_posix()
            title = c["title"].replace("|", "｜")
            note = c["note"].replace("|", "｜")
            source_link = (ROOT / c["locator_index"]).as_posix()
            mark = "候选" if not c["reviewed_location"] else "定位"
            header.append(f"| [{title}](<{original}>) · {c['year']}年第{c['issue']}期 | {MOVES[c['move']]} | {note} [PDF第{c['pdf_page']}页的{mark}](<{source_link}>)。 |")
        header.append("")
    (HERE / "阅读总目录.md").write_text("\n".join(header) + "\n", encoding="utf-8")


def main():
    cards = list(style_cards())
    expected = {"中国社会科学": 55, "社会学研究": 80}
    assert Counter(c["journal"] for c in cards) == expected
    assert len({c["paper_id"] for c in cards}) == len(cards)
    for c in cards:
        if digest(Path(c["pdf"])) != c["sha256"]:
            raise ValueError(f"PDF在读取后变更: {c['title']}")
        first, last = c["block_page_span"]
        if not 1 <= first <= c["pdf_page"] <= last <= c["pdf_pages"]:
            raise ValueError(f"PDF页码无法回定位: {c['title']}")
    write("逐篇结构与语言.json", cards)
    write_index(cards)
    write("writing_exemplars.json", exemplar_index(cards))
    index = read_index(HERE / "writing_exemplars.json", pilot=True)
    scores = evaluate(index, cards)
    write("范例检索对照.json", scores)
    write("核验.json", {
        "checked_at": "2026-11-18",
        "distinct_local_pdfs": len(cards), "by_journal": expected,
        "pdf_pages": sum(c["pdf_pages"] for c in cards), "hashes_rechecked": len(cards),
        "abstracts_with_extracted_sentences": sum(bool(c["abstract_sentences"]) for c in cards),
        "abstract_sentence_candidates": sum(len(c["abstract_sentences"]) for c in cards),
        "abstract_status_counts": Counter(c["abstract_status"] for c in cards),
        "body_paragraph_candidates": sum(s["paragraphs"] for c in cards for s in c["sections"] if s["section"] != "摘要"),
        "study_type_counts": Counter(c["study_type"] for c in cards),
        "exemplar_count": len(index["examples"]),
        "functions": Counter(e["move"] for e in index["examples"]),
        "supplementally_reviewed_paragraphs": sum(e["annotation_status"] == "paragraph_reviewed" for e in index["examples"]),
        "holdout_count": len(index["held_out_paper_ids"]),
        "min_function_examples": min(Counter(e["move"] for e in index["examples"]).values()),
        "retrieval": {mode: dict(queries=sum(r["mode"] == mode for r in scores),
                                returned=sum(len(r["examples"]) for r in scores if r["mode"] == mode),
                                function_hits=sum(r["right_function"] for r in scores if r["mode"] == mode))
                      for mode in ("manual", "topic", "function")},
        "gate_suggestion": "pilot",
    })


if __name__ == "__main__":
    main()
