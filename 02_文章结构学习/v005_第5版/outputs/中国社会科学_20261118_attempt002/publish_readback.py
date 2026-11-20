"""Validate the added reading notes against their sources and publish current coverage."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

OUT = Path(__file__).resolve().parent
PREVIOUS = OUT.with_name("中国社会科学_20261118_attempt001")
SOCIAL_SECURITY = "逐篇解析/02_制度的力量_第二至四节及结论.md"
MOBILITY = "逐篇解析/03_当代中国的代际流动模式及其变迁_摘要至第三节.md"
SECTION_HEAD = re.compile(r"^### ((?:P\d{3}|(?:A|I{1,3})\d{2})) ·", re.M)
SENTENCE_ROW = re.compile(r"^\| ((?:P\d{3}|(?:A|I{1,3})\d{2})S\d{2}) \| ([^|]+) \| ([^|]+) \|$", re.M)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def annotations(report):
    raw = (OUT / report).read_text(encoding="utf-8")
    paragraphs = SECTION_HEAD.findall(raw)
    entries = SENTENCE_ROW.findall(raw)
    sentence_ids = [entry[0] for entry in entries]
    if len(set(paragraphs)) != len(paragraphs) or len(set(sentence_ids)) != len(sentence_ids):
        raise ValueError(f"编号重复：{report}")
    if list(dict.fromkeys(identifier.split("S")[0] for identifier in sentence_ids)) != paragraphs:
        raise ValueError(f"段落和句子未按来源顺序对应：{report}")
    for paragraph in paragraphs:
        section = raw.split(f"### {paragraph} ·", 1)[1].split("\n### ", 1)[0]
        if "**段落作用及衔接**" not in section:
            raise ValueError(f"缺少段落关系：{report} {paragraph}")
    return raw, paragraphs, sentence_ids


def validate_links(source, raw):
    for match in re.finditer(r"\]\((<[^>]+>|[^)]+)\)", raw):
        target = Path(unquote(match.group(1).strip("<>")))
        if not (source.parent / target).is_file():
            raise FileNotFoundError(f"{source.name}: {target}")


def main():
    prev_manifest = PREVIOUS / "run_manifest.json"
    old = load(prev_manifest)
    for file, expected in old["output_sha256"].items():
        if digest(PREVIOUS / file) != expected:
            raise ValueError(f"上次产物已变化：{file}")

    inventory = load(PREVIOUS / "馆藏清单.json")
    article_by_key = {article["attachment_key"]: article for article in inventory["articles"]}
    keys = ["6V7LJIWN", "SCCKUUS9"]
    for key in keys:
        article = article_by_key[key]
        if digest(Path(article["pdf_path"])) != article["sha256"]:
            raise ValueError(f"原始PDF已变化：{key}")

    security_text, security_paragraphs, security_sentences = annotations(SOCIAL_SECURITY)
    security_index = load(PREVIOUS / "定位索引/zotero_6V7LJIWN.json")
    # The printed PDF identifies these candidate blocks as table and note material.
    non_body_blocks = {19, 27, *range(34, 46), *range(48, 59), *range(60, 71), *range(75, 80), *range(82, 86)}
    non_body_tails = {"P026S07", "P033S07", "P047S06", "P059S06", "P074S05", "P081S05"}
    remaining = [para for para in security_index["blocks"]
                 if int(para["id"][1:]) >= 16 and int(para["id"][1:]) not in non_body_blocks]
    expected = [s["id"] for para in remaining for s in para["sentences"] if s["id"] not in non_body_tails]
    if security_sentences != expected or security_paragraphs != [para["id"] for para in remaining]:
        raise ValueError("《制度的力量》正文覆盖须与校订后的索引相符")
    english = re.findall(r"^\| (E\d{2}) \|", security_text, re.M)
    if english != [f"E{i:02}" for i in range(1, 7)]:
        raise ValueError("《制度的力量》英文摘要须含六句")

    mobility_text, mobility_paragraphs, mobility_sentences = annotations(MOBILITY)
    # Printed paragraphs, counted after treating the numbered subheads as labels.
    groups = {"A": [4], "I": [5, 3], "II": [1, 3, 5, 4, 5, 2, 4, 4, 1],
              "III": [3, 4, 4, 7, 2, 2, 3, 8, 6, 8, 4, 2]}
    expected = [f"{group}{p:02}S{s:02}" for group, paragraphs in groups.items()
                for p, count in enumerate(paragraphs, 1) for s in range(1, count + 1)]
    if expected != mobility_sentences:
        raise ValueError("《当代中国的代际流动模式及其变迁》句编号与版面核对记录不符")
    for report, raw in [(SOCIAL_SECURITY, security_text), (MOBILITY, mobility_text)]:
        validate_links(OUT / report, raw)

    source_catalog = PREVIOUS / "阅读总目录.md"
    original = source_catalog.read_text(encoding="utf-8")
    old_name = PREVIOUS.name
    prior_security = old["annotation_coverage"]["6V7LJIWN"]
    prior_short = old["annotation_coverage"]["WPWDXCNN"]
    sec_coverage = (prior_security["paragraphs"] + len(security_paragraphs),
                    prior_security["sentences"] + len(security_sentences))
    total_paragraphs = prior_short["paragraphs"] + sec_coverage[0] + len(mobility_paragraphs)
    total_sentences = prior_short["sentences"] + sec_coverage[1] + len(mobility_sentences)
    prior_security_link = f"../{old_name}/{prior_security['file']}"
    prior_short_link = f"../{old_name}/{prior_short['file']}"
    lines = [
        "# Zotero《中国社会科学》逐篇解析总目录",
        "",
        f"馆藏58条题录，去重后55篇。本轮累计**完成全文解析2篇，完成部分章节1篇**。"
        f"已逐句核对中文段落{total_paragraphs}段、{total_sentences}句，另核1则英文摘要6句。",
        "",
        f"- [《“第二个结合”与文化主体性重建》全文]({prior_short_link})，正文10段45句。",
        f"- 《制度的力量》全文，中文44段245句、英文摘要6句。"
        f"[摘要、引言与第一节]({prior_security_link}) · [第二至四节、结论及英文摘要]({SOCIAL_SECURITY})。",
        f"- [《当代中国的代际流动模式及其变迁》摘要至第三节]({MOBILITY})，24段94句。"
        "已核至刊页47，下一位置是刊页48第四节。",
        "- 另52篇已有章节路线初读和段句候选定位，待核实句意、段落作用及衔接关系。",
        "",
        "下表的定位索引来自首次馆藏盘点。待逐句的候选位置可能包含脚注、表头及跨页片段。"
        "已精读的勘误、段句编号和图表作用见各篇报告。",
        "",
    ]
    table = original[original.index("| 序号 |"):original.index("\n## 重复题录")]
    table = table.replace("](%E5%AE%9A", f"](../{old_name}/%E5%AE%9A")
    table = table.replace(f"](<{prior_short['file']}>)", f"](<{prior_short_link}>)")
    table = table.replace(
        f"[已逐句分析摘要、引言与第一节](<{prior_security['file']}>)",
        f"全文 · [上卷]({prior_security_link}) · [下卷]({SOCIAL_SECURITY})",
    )
    table_lines = table.splitlines()
    for i, row in enumerate(table_lines):
        if "zotero_SCCKUUS9.json" in row:
            table_lines[i] = row.replace("待逐句逐段", f"[已精读摘要至第三节]({MOBILITY})")
    if sum(1 for row in table_lines if re.match(r"^\| \d+ \|", row)) != 55:
        raise ValueError("馆藏表逐篇数量发生变化")
    if not all(any(target in row for row in table_lines) for target in (SOCIAL_SECURITY, MOBILITY, prior_short_link)):
        raise ValueError("馆藏表未反映全部精读记录")
    lines.extend(table_lines)
    lines.extend([
        "",
        f"[原馆藏盘点及重复题录](../{old_name}/阅读总目录.md) · [本轮校验与接续记录](run_manifest.json)",
        "",
    ])
    catalog = OUT / "阅读总目录.md"
    catalog_content = "\n".join(lines)
    catalog.write_text(catalog_content, encoding="utf-8")

    manifest = {
        "run_id": OUT.name, "stage_id": "02", "module_version": 5, "attempt": 2,
        "schema_version": 1, "status": "needs_review",
        "checked_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "previous_snapshot": {"path": f"../{old_name}/run_manifest.json", "sha256": digest(prev_manifest)},
        "sources": {key: {"pdf": article_by_key[key]["pdf_path"], "sha256": article_by_key[key]["sha256"]}
                    for key in keys},
        "config": {"reuse_inventory": True, "split_by_printed_paragraphs": True,
                   "count_subheads_tables_and_notes_as_prose": False, "random_seed": None},
        "new_coverage": {"articles_completed": 1, "articles_started": 1,
                         "chinese_paragraphs": len(security_paragraphs) + len(mobility_paragraphs),
                         "chinese_sentences": len(security_sentences) + len(mobility_sentences),
                         "english_abstracts": 1, "english_sentences": len(english)},
        "corpus_coverage": {"articles": 55, "full": 2, "partial": 1, "section_overview_only": 52,
                            "chinese_paragraphs": total_paragraphs, "chinese_sentences": total_sentences},
        "readback": {
            "6V7LJIWN": {"note": SOCIAL_SECURITY, "chinese_pdf_pages": [6, 20], "english_pdf_page": 21,
                         "chinese_body_paragraphs_added": len(security_paragraphs),
                         "chinese_body_sentences_added": len(security_sentences),
                         "non_body_blocks_in_prior_index": sorted(non_body_blocks),
                         "non_body_tails_in_prior_index": sorted(non_body_tails), "status": "full"},
            "SCCKUUS9": {"note": MOBILITY, "chinese_pdf_pages": [1, 8], "paragraphs": len(mobility_paragraphs),
                         "sentences": len(mobility_sentences), "sentence_counts_by_printed_paragraph": groups,
                         "status": "partial", "next_pdf_page": 9, "next_journal_page": 48, "next_section": "四、研究模型"},
        },
        "output_sha256": {file: digest(OUT / file) for file in (catalog.name, SOCIAL_SECURITY, MOBILITY)},
        "code_sha256": digest(Path(__file__)),
        "root_requirements_sha256": {name: digest(OUT.parents[3] / name)
                                     for name in ("AGENTS.md", "基础要求.md", "项目架构.md")},
    }
    manifest["config_sha256"] = hashlib.sha256(
        json.dumps(manifest["config"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_links(catalog, catalog_content)
    print(json.dumps(manifest["corpus_coverage"], ensure_ascii=False))


if __name__ == "__main__":
    main()
