"""核对原PDF、正文输入和初读笔记的逐篇覆盖，生成可查页的总目录。"""

from collections import Counter
from hashlib import sha256
from pathlib import Path
import re
from urllib.parse import quote

from fulltext import HERE, WORK, load, write


VISUAL_PAGES = {
    "zotero_39ERQM27": {17},
    "zotero_3G222LKC": {10},
    "zotero_DD4I5QA4": {19},
    "zotero_V3CA3AZW": {20},
    "zotero_89UP6KH7": {17},
}


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def check_note(note):
    text = note["analysis"].strip()
    fields = ("承接", "推进", "写法")
    headers = re.findall(r"(?m)^\s*(?:\*\*)?(承接|推进|写法)(?:\*\*)?(?=[ |｜:：\r\n])", text)
    flags = []
    if tuple(headers) != fields:
        flags.append("字段缺失、顺序错误或重复")
    if any(template in text for template in ("前文交代了什么", "这几页依次做了什么", "指出这种推进的具体表达技巧")):
        flags.append("复述指令")
    if not text.endswith(("。", "！", "？", "”", "）", ".", "!", "?")):
        flags.append("可能截断")
    return flags


def main():
    inputs = load(HERE / "全篇阅读输入清单.json")
    outputs = HERE / "逐篇全文分析"
    expected = {p["paper_id"] for p in inputs}
    actual = {p.stem for p in outputs.glob("*.json")}
    if expected != actual or len(expected) != 135:
        raise ValueError(f"阅读清单与产物不一致: {expected ^ actual}")

    totals = Counter()
    journals = Counter()
    page_types = Counter()
    paper_results = []
    for row in inputs:
        paper_id = row["paper_id"]
        source = HERE / row["input"]
        output = outputs / f"{paper_id}.json"
        reading = load(source)
        annotated = load(output)
        if reading["paper_id"] != paper_id or annotated["paper_id"] != paper_id:
            raise ValueError(f"篇目ID不一致: {paper_id}")
        if file_hash(source) != row["input_sha256"] or annotated["input_sha256"] != row["input_sha256"]:
            raise ValueError(f"正文输入已改变: {paper_id}")
        if annotated["pdf_sha256"] != reading["pdf_sha256"] or file_hash(Path(reading["pdf_path"])) != reading["pdf_sha256"]:
            raise ValueError(f"PDF哈希不一致: {paper_id}")
        pages = reading["pages"]
        notes = annotated["passage_analysis"]
        if [p["pdf_page"] for p in pages] != list(range(1, row["pages"] + 1)):
            raise ValueError(f"物理页序错误: {paper_id}")
        with_text = {p["pdf_page"] for p in pages if p["body_text"]}
        covered = {page for note in notes for page in note["pdf_pages"]}
        if with_text != covered or with_text != set(row["pages_with_body"]):
            raise ValueError(f"正文输入与模型覆盖不一致: {paper_id}")
        checked = {p["pdf_page"] for p in pages if p["scope"] == "正文文字层不足，保留页面复查"}
        if checked != VISUAL_PAGES.get(paper_id, set()):
            raise ValueError(f"待看版面页与核查记录不一致: {paper_id}")
        if annotated["paragraphs"] != reading["paragraphs"]:
            raise ValueError(f"段落索引变化: {paper_id}")
        flags = []
        for note in notes:
            issues = check_note(note)
            if issues:
                flags.append({"pdf_pages": note["pdf_pages"], "issues": issues})
        paper_results.append({
            "paper_id": paper_id, "title": row["title"], "journal": row["journal"],
            "physical_pages": len(pages), "text_pages": sorted(covered),
            "visual_pages": sorted(checked), "groups": len(notes), "flags": flags,
            "no_paragraph_index": row["body_pages_without_paragraphs"],
            "output_sha256": file_hash(output), "pdf_sha256": reading["pdf_sha256"],
        })
        journals[row["journal"]] += 1
        page_types.update(p["scope"] for p in pages)
        totals.update({
            "physical_pages": len(pages), "text_pages": len(covered), "visual_pages": len(checked),
            "groups": len(notes), "flagged_groups": len(flags),
            "body_paragraph_candidates": len(annotated["paragraphs"]),
            "body_pages_without_paragraph_index": len(row["body_pages_without_paragraphs"]),
        })

    write(HERE / "核验报告.json", {
        "checked_at": "2026-11-19 Asia/Shanghai",
        "status": "needs_review", "journals": dict(journals), "totals": dict(totals),
        "page_types": dict(page_types), "papers": paper_results,
        "coverage_verified": True, "semantic_fulltext_review_passed": False,
        "settings": {
            "batch": 7, "max_input_tokens_per_group": 4600, "max_generated_tokens": 145,
            "decoding": "greedy", "inference_local": True,
            "reading_script_sha256": file_hash(HERE / "fulltext.py"),
            "checks_script_sha256": file_hash(Path(__file__)),
            "model_files_manifest_sha256": file_hash(WORK / "qwen2.5-1.5b-instruct" / "weights_manifest.json"),
        },
    })

    lines = [
        "# 两刊全篇初读总目录", "",
        "2026-11-19以本地 Zotero PDF 核对篇目、物理页、正文输入和原件哈希。", "",
        f"共{len(paper_results)}篇、{totals['physical_pages']}个物理页。"
        f"模型初读覆盖{totals['text_pages']}个有正文输入的页位，"
        f"另回看{totals['visual_pages']}个无正文文字层的表页。"
        f"{totals['groups']}组初读记录中有{totals['flagged_groups']}组存在格式、回显提示或疑似截断问题。"
        "所有组的语义仍须结合原文复核。", "",
        "逐篇文件保留每组的页码和每个候选段落的前段编号、节名、逻辑词及页码。"
        "来源PDF路径与SHA-256见各篇文件。PDF的页号和原刊页码可能不同。", "",
        "[版面补读](版面补读.md)　[逐篇覆盖核验](核验报告.json)　"
        "[定量论文精读示例](MK385948_逐节与段落精读.md)　"
        "[理论与经验论述精读示例](X88U69EU_逐节与段落精读.md)　"
        "[《中国社会科学》定量论文续读](SCCKUUS9_第四节至结论续读.md)", "",
        "| 期刊 | 篇名 | 正文页位 | 版面回看 | 初读组 | 格式疑点组 |",
        "|---|---|---|---|---:|---:|",
    ]
    for item in paper_results:
        text_pages = item["text_pages"]
        page_range = f"PDF {min(text_pages)}–{max(text_pages)}（{len(text_pages)}页位）"
        visual = ", ".join(str(p) for p in item["visual_pages"]) or "—"
        link = quote(f"逐篇全文分析/{item['paper_id']}.json")
        title = item["title"].replace("|", r"\|").replace("[", "［").replace("]", "］")
        lines.append(f"| {item['journal']} | [{title}]({link}) | {page_range} | {visual} | "
                     f"{item['groups']} | {len(item['flags'])} |")
    (HERE / "全文分析总目录.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(dict(totals), dict(journals))


if __name__ == "__main__":
    main()
