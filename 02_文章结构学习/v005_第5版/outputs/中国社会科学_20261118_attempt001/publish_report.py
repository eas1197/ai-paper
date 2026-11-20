"""Cross-check the inventory, reading notes and source hashes, then write the catalog."""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

from build_index import OUT, json_write, sha

ROOT = OUT.parents[3]
ANNOTATIONS = {
    "WPWDXCNN": ("逐篇解析/01_第二个结合与文化主体性重建.md", 10, 45, "正文逐句逐段完成"),
    "6V7LJIWN": ("逐篇解析/02_制度的力量_摘要引言与第一节.md", 14, 70, "已逐句分析摘要、引言与第一节"),
}
FOOTNOTE_FRAGMENTS = {"6V7LJIWN": {"P008"}}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def markdown_link(label, target):
    return f"[{label}](<{target}>)"


def check_annotations(row, locator, route, paragraph_count, sentence_count):
    text = (OUT / route).read_text(encoding="utf-8")
    documented_paragraphs = re.findall(r"(?m)^## (P\d{3})\b", text)
    documented_sentences = re.findall(r"(?m)^\| (P\d{3}S\d{2,}) \|", text)
    excluded = FOOTNOTE_FRAGMENTS.get(row["attachment_key"], set())
    covered = [block for block in locator["blocks"] if block["id"] not in excluded][:paragraph_count]
    expected_p = [block["id"] for block in covered]
    expected_s = [s["id"] for block in covered for s in block["sentences"]]
    if (expected_p != documented_paragraphs or expected_s != documented_sentences
            or len(expected_s) != sentence_count):
        raise ValueError(f"逐句编码与原文定位不一致：{row['title']}")


def main():
    path = OUT / "馆藏清单.json"
    data = load(path)
    articles = data["articles"]
    with (OUT / "章节路线.tsv").open(encoding="utf-8", newline="") as stream:
        readings = {row["附件键"]: row["章节关系初读"] for row in csv.DictReader(stream, delimiter="\t")}
    if len(articles) != len(readings) or set(readings) != {row["attachment_key"] for row in articles}:
        raise ValueError("章节初读与馆藏清单不完全对应")
    if len({row["paper_id"] for row in articles}) != len(articles):
        raise ValueError("paper_id重复")
    raw_pdfs = [pdf for row in articles for pdf in row["equivalents"]]
    if len(raw_pdfs) != data["records"] or len({pdf["attachment_key"] for pdf in raw_pdfs}) != data["records"]:
        raise ValueError("附件清单与原始 Zotero 记录数不一致")
    for pdf in raw_pdfs:
        if sha(Path(pdf["pdf_path"])) != pdf["sha256"]:
            raise ValueError(f"附件哈希已变化：{pdf['attachment_key']}")

    counts = dict(
        zotero_records=len(raw_pdfs),
        unique_articles=len(articles),
        direct_pdf_files_sha256_checked=len(raw_pdfs),
        pdf_pages_of_canonical_attachments=sum(row["pdf_pages"] for row in articles),
        indexed_paragraph_candidates=sum(row["paragraph_candidates"] for row in articles),
        indexed_sentence_candidates=sum(row["sentence_candidates"] for row in articles),
        articles_with_section_overview=len(readings),
        articles_with_full_annotation=1,
        articles_with_partial_annotation=1,
        articles_with_section_overview_only=len(readings) - len(ANNOTATIONS),
        close_reading_paragraphs=sum(v[1] for v in ANNOTATIONS.values()),
        close_reading_sentences=sum(v[2] for v in ANNOTATIONS.values()),
    )
    lines = [
        "# Zotero《中国社会科学》逐篇解析总目录",
        "",
        f"2026-11-18 按 Zotero 的规范刊名筛出 **{counts['zotero_records']} 条题录和 PDF、{counts['unique_articles']} 篇独立文章**。"
        "馆藏范围包括实证论文、理论论文、述评与研讨会发言。"
        "重复以规范化题名、年份、期号和刊页组合识别，两份附件的记录和哈希均保留。",
        "",
        "- **全文逐句逐段 1 篇**　[《“第二个结合”与文化主体性重建》](逐篇解析/01_第二个结合与文化主体性重建.md)，正文10段45句。",
        "- **逐句完成部分章节 1 篇**　[《制度的力量》摘要、引言与第一节](逐篇解析/02_制度的力量_摘要引言与第一节.md)，共14段70句。",
        f"- **章节关系初读 {counts['articles_with_section_overview']} 篇**　下表可查。其余 "
        f"{counts['articles_with_section_overview_only']} 篇有章间路线初读，全文句意、段落任务和细部关系待逐条回读。",
        f"- **自动定位**　定位索引含{counts['indexed_paragraph_candidates']}个候选段、"
        f"{counts['indexed_sentence_candidates']}个候选句。候选编号连接PDF页和短定位词。"
        "脚注、跨页、图表、多栏和引文可能使候选切分偏离版面，实际段句数量以逐篇核对为准。",
        "",
        "章节路线主要据原 PDF 的摘要、章节标题、开头与收束处做初读。箭头是对原文章节怎样推进的理解。"
        "表内页码是刊印页，索引里的页码从 PDF 文件第一页开始计。",
        "",
        "| 序号 | 文章与刊页 | 章节关系初读 | 进度与定位 |",
        "|---:|---|---|---|",
    ]
    for n, row in enumerate(articles, 1):
        key = row["attachment_key"]
        locator_path = f"定位索引/{row['paper_id']}.json"
        locator = load(OUT / locator_path)
        if locator["sha256"] != row["sha256"]:
            raise ValueError(f"索引来源不一致：{key}")
        if len(locator["blocks"]) != row["paragraph_candidates"] or (
            sum(len(b["sentences"]) for b in locator["blocks"]) != row["sentence_candidates"]
        ):
            raise ValueError(f"索引段句计数不一致：{key}")
        for b in locator["blocks"]:
            if not 1 <= b["start_page"] <= b["end_page"] <= row["pdf_pages"]:
                raise ValueError(f"段落坐标超出PDF范围：{key} {b['id']}")
        if key in ANNOTATIONS:
            note, paragraph_count, sentence_count, status = ANNOTATIONS[key]
            check_annotations(row, locator, note, paragraph_count, sentence_count)
            status = markdown_link(status, note)
        else:
            status = "待逐句逐段"
        source = Path(row["pdf_path"]).as_posix()
        article = markdown_link(f"《{row['title']}》", source)
        lines.append(f"| {n} | {article}（{row['year']}年第{row['issue']}期，{row['pages']}） "
                     f"| {readings[key]} | {status} · [定位索引]({quote(locator_path)}) |")
    lines += ["", "## 重复题录", ""]
    for row in articles:
        if len(row["equivalents"]) > 1:
            keys = "、".join(f"`{r['attachment_key']}`" for r in row["equivalents"])
            lines.append(f"- 《{row['title']}》对应 {keys}，采用 `{row['attachment_key']}` 定位。")
    lines.extend([
        "",
        "[馆藏记录、Zotero路径、页码及原附件SHA-256](馆藏清单.json) · [本次校验与版本记录](run_manifest.json)",
        "",
    ])
    catalog = OUT / "阅读总目录.md"
    catalog.write_text("\n".join(lines), encoding="utf-8")
    files = [path, catalog, OUT / "章节路线.tsv", *(OUT / v[0] for v in ANNOTATIONS.values()),
             *sorted((OUT / "定位索引").glob("*.json"))]
    if len(files) != len(articles) + 5:
        raise ValueError("定位索引文件数量不一致")
    code = [OUT / "build_index.py", OUT / "publish_report.py"]
    policy_files = [ROOT / filename for filename in ("AGENTS.md", "基础要求.md", "项目架构.md")]
    manifest = {
        "run_id": OUT.name,
        "stage_id": "02",
        "attempt": 1,
        "module_version": 5,
        "schema_version": 1,
        "status": "needs_review",
        "audit_status": "attachment_hashes_index_and_annotation_coverage_checked",
        "checked_at": data["checked_at"],
        "coverage": counts,
        "source_snapshot": {"zotero_query_export": path.name, "sha256": sha(path)},
        "config": {
            "publicationTitle": "中国社会科学",
            "deleted": False,
            "attachment_type": "application/pdf",
            "dedup_fields": ["normalized_title", "year", "issue", "pages"],
            "selection": "use available stored PDF; select duplicate with fuller Zotero text cache unless reused identified source",
        },
        "random_seed": None,
        "runtime": {"python": sys.version.split()[0]},
        "code_sha256": {p.name: sha(p) for p in code},
        "root_requirements_sha256": {p.name: sha(p) for p in policy_files},
        "output_sha256": {p.relative_to(OUT).as_posix(): sha(p) for p in files},
        "annotation_coverage": {key: {"file": file, "paragraphs": paragraphs, "sentences": sentences, "status": status}
                                for key, (file, paragraphs, sentences, status) in ANNOTATIONS.items()},
        "verified_footnote_fragments": {key: sorted(v) for key, v in FOOTNOTE_FRAGMENTS.items()},
        "pdf_extraction_flags": {row["paper_id"]: row["flags"] for row in articles if row["flags"]},
        "limits": ["All 55 section maps are preliminary readings. Full annotation only in the recorded scope.",
                   "Existing shared resource gate G2/G3 is unaffected; candidate index counts are not annotation counts."],
    }
    config_bytes = json.dumps(manifest["config"], ensure_ascii=False, sort_keys=True).encode()
    manifest["config_sha256"] = hashlib.sha256(config_bytes).hexdigest()
    json_write(OUT / "run_manifest.json", manifest)
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
