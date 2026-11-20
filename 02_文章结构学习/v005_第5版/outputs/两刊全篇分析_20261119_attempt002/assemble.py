"""核对两刊原文页、模型记录、节/段/句索引，并生成可查的资源清单。"""
import argparse
from collections import Counter, defaultdict
import csv
from pathlib import Path
import re
import statistics
import unicodedata
from urllib.parse import quote

from review import (
    ENGINE, HERE, MODEL, PREVIOUS, ROOT, STUDY, TARGETS,
    canonical, check_anchor, digest as hash_text, file_hash, load, load_sources, read_pages, save,
)


def table(name, header, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)


def candidate_sections(source, raw):
    if raw is not None:
        heads = raw["heading_candidates"]
    else:
        heads = source["heading_candidates"]
    indexed = [h for h in heads if isinstance(h, dict) and h.get("pdf_page") and h.get("heading")]
    supplemental = {
        "zotero_Y32DRMKW": [(3, "数据、变量和方法"), (5, "户口因素在社会分层中的作用"),
                            (9, "户口因素对社会流动的影响"), (13, "结论与讨论")],
        "zotero_SCCKUUS9": [(1, "一、问题的提出")],
        "zotero_6V7LJIWN": [(19, "结论")],
        "zotero_J5XDE43I": [(19, "总结")],
        "zotero_89UP6KH7": [(4, "二、理论比较:文化再生产、文化抵制与文化流动"), (14, "五、结果分析")],
    }
    indexed.extend({"pdf_page": page, "heading": heading, "level": 1}
                   for page, heading in supplemental.get(source["paper_id"], []))
    return sorted(indexed, key=lambda h: h["pdf_page"])


def text_key(text):
    return canonical(unicodedata.normalize("NFKC", text))


def paragraph_scope(text):
    if re.match(r"^(?:续|附)?[表图]\s*[A-Za-z]?\d+", text):
        return "图表起始，核对是否兼有正文"
    if re.match(r"^(?:注[：:]|①|②|③|④)", text):
        return "脚注或表注起始，核对边界"
    if len(re.findall(r"[\u3400-\u9fff]", text)) < 8:
        return "短段或数字片段"
    if re.match(r"^(?:研究)?假设\s*\d+\w*\s*[:：]", text):
        return "有显式假设编号"
    return "正文候选"


def punctuation_insensitive_locator(block, pages):
    body = "".join(re.findall(r"[\u3400-\u9fff]", block["text"]))
    if len(body) < 12:
        return None
    starts = list(dict.fromkeys([0, max(0, len(body)//2 - 6), len(body)-12]))
    probes = [body[i:i+12] for i in starts if len(set(body[i:i+12])) >= 5]
    for page in range(block["start_page"], block["end_page"] + 1):
        source = "".join(re.findall(r"[\u3400-\u9fff]", pages.get(page, "")))
        matches = [probe for probe in probes if source.count(probe) == 1]
        if matches:
            return {"pdf_page": page, "han_sequence": matches[0]}
    return None


def section_sizes(heads, pages):
    pages = {page: text_key(value) for page, value in pages.items()}
    offsets, size = {}, 0
    for page, value in pages.items():
        offsets[page], size = size, size + len(value)
    body = "".join(pages.values())
    positions = [(0, None, "首个已定位节标题前")]
    for h in heads:
        if h["level"] != 1:
            continue
        page = h["pdf_page"]
        heading = h["heading"]
        at = pages.get(page, "").find(text_key(heading))
        if at >= 0:
            positions.append((offsets[page] + at, page, heading))
    positions.sort(key=lambda item: item[0])
    han = re.compile(r"[\u3400-\u9fff]")
    for i, (begin, page, heading) in enumerate(positions):
        end = positions[i+1][0] if i+1 < len(positions) else len(body)
        if end > begin:
            yield heading, page, len(han.findall(body[begin:end]))


def main(require_all=False):
    cases = {r["paper_id"]: r for r in load(STUDY / "逐篇结构与语言.json")}
    sources = load_sources()
    initial = load(PREVIOUS / "核验报告.json")
    first_round = {r["paper_id"]: r for r in initial["papers"]}
    verified_abstract_path = HERE / "摘要逐句原文复核.tsv"
    with verified_abstract_path.open(encoding="utf-8-sig", newline="") as file:
        verified_abstract = {f"zotero_{r['key']}": r["moves"].split("|") for r in csv.DictReader(file, delimiter="\t")}
    if set(verified_abstract) != TARGETS:
        raise ValueError("摘要复核清单应与20篇定量样本完全匹配")
    verified_sections_path = HERE / "二十篇分节复核.tsv"
    with verified_sections_path.open(encoding="utf-8-sig", newline="") as file:
        verified_sections = {f"zotero_{r['key']}": r["sequence"].split("|") for r in csv.DictReader(file, delimiter="\t")}
    if set(verified_sections) != TARGETS:
        raise ValueError("分节复核清单应与20篇定量样本完全匹配")
    paragraph_samples_path = HERE / "逐段校对样例.tsv"
    with paragraph_samples_path.open(encoding="utf-8-sig", newline="") as file:
        paragraph_samples = {(row["paper_id"], row["paragraph"]): row for row in csv.DictReader(file, delimiter="\t")}
    paragraph_samples_used = set()
    manual_fallback = HERE / "无锚点补核.md"
    manually_located = {"zotero_" + key for key in re.findall(r"馆藏号\s+([A-Z0-9]{8})",
                                                             manual_fallback.read_text(encoding="utf-8"))}
    layout_review_path = HERE / "段落排版补核.tsv"
    with layout_review_path.open(encoding="utf-8-sig", newline="") as file:
        layout_samples = {(f"zotero_{row['key']}", item): row["scope"]
                          for row in csv.DictReader(file, delimiter="\t") for item in row["ids"].split()}
    layout_samples_used = set()
    results, section_rows, paragraph_rows, abstract_rows, model_rows = [], [], [], [], []
    paragraph_review_rows = []
    sizes = []
    paragraph_counts = Counter()
    spans = defaultdict(list)
    section_report = ["# 二十篇定量论文分节阅读", "",
                      "这里记录各篇由开头至结尾的推进。数字是PDF物理页。跨节共用一页时，两个页段可重叠。", ""]
    all_notes = ["# 两刊逐篇论证笔记", "",
                 "各篇正文整批读入后生成候选。正文短语可定位的条目列在这里，逐篇文件保留全部组和源页。"
                 "回查原文时以判断和数据的上下文为准。定量样本优先阅读分节复核文件。", ""]
    for source in sources:
        paper = source["paper_id"]
        pages = read_pages(source)
        local_pdf = source["origin"] == "zotero_pdf"
        raw = load(Path(source["source"])) if local_pdf else None
        if local_pdf and file_hash(Path(source["pdf"])) != source["pdf_sha256"]:
            raise ValueError(f"{paper}: 原PDF已变化")
        heads = candidate_sections(source, raw)
        title = source["title"]
        if paper in TARGETS:
            sizes.extend((paper, title, source["journal"], *size) for size in section_sizes(heads, pages))
            section_report.extend([f"## 《{title}》", "", f"{source['journal']} · {paper}", ""])
            checked_pages = set()
            for move in verified_sections[paper]:
                loc, text = move.split(" ", 1)
                beginning, ending = (int(x) for x in loc.split("–"))
                if not text or beginning < min(pages) or ending > max(pages):
                    raise ValueError(f"{paper}: 节范围不符 {move}")
                checked_pages.update(range(beginning, ending + 1))
                section_report.append(f"- PDF {loc}。{text}。")
            if set(pages) - checked_pages:
                raise ValueError(f"{paper}: 分节复核尚有页范围缺失 {set(pages) - checked_pages}")
            section_report.extend(["", f"[核对原PDF](<{Path(source['pdf']).as_posix()}>)", ""])
            main_pages = [h["pdf_page"] for h in heads if h.get("level") == 1]
            for i, start in enumerate(main_pages):
                end = main_pages[i + 1] if i + 1 < len(main_pages) else max(pages)
                spans[source["journal"]].append(end - start)
            for h in heads:
                page = h["pdf_page"]
                on_page = text_key(h["heading"]) in text_key(pages.get(page, ""))
                section_rows.append((paper, title, source["journal"], h["level"], page, h["heading"], on_page))
            for p in raw["paragraphs"]:
                paragraph_rows.append((paper, p["id"], *p["pdf_span"], p["section"], p["previous_id"],
                                       p["sentences"], p["opener"], p["explicit_link"], "；".join(p["function_candidates"]),
                                       p["review_status"], p["text_sha256"]))
            para_file = HERE / "逐段复核候选" / f"{paper}.json"
            if para_file.exists():
                para_review = load(para_file)
                if para_review["reference_pages_sha256"] != source["source_sha256"]:
                    raise ValueError(f"{paper}: 逐段候选使用的原文页已变化")
                working = Path(para_review["working_text"])
                if file_hash(working) != para_review["working_text_sha256"]:
                    raise ValueError(f"{paper}: 逐段候选的段落底稿已变化")
                block_lookup = {b["id"]: b for b in load(working)["blocks"]}
                if [p["id"] for p in raw["paragraphs"]] != [p["paragraph_id"] for p in para_review["paragraphs"]]:
                    raise ValueError(f"{paper}: 候选段编号与复核记录不一致")
                paragraph_counts["paper_count"] += 1
                for p, match in zip(raw["paragraphs"], para_review["paragraphs"]):
                    if p["text_sha256"] != match["source_text_sha256"]:
                        raise ValueError(f"{paper}: {p['id']} 原段哈希已变化")
                    for anchor in match["anchors"]:
                        original = canonical(pages[anchor["page"]])
                        if not all(anchor[key] in original for key in ("first_anchor", "last_anchor")):
                            raise ValueError(f"{paper}: {p['id']} 原段锚点失效")
                    label, alternate = match["labels"]
                    function = para_review["function_labels"]
                    block = block_lookup[p["id"]]
                    scope = paragraph_scope(block["text"])
                    sample_key = (paper, p["id"])
                    if sample_key in layout_samples:
                        scope = layout_samples[sample_key]
                        layout_samples_used.add(sample_key)
                    supplemental = punctuation_insensitive_locator(block, pages) if not match["anchors"] else None
                    paragraph_counts["matched_anchors"] += bool(match["anchors"])
                    paragraph_counts["punctuation_normalized_anchors"] += bool(supplemental)
                    paragraph_counts["prose_candidates_without_locators"] += (
                        scope == "正文候选" and not (match["anchors"] or supplemental)
                    )
                    paragraph_counts["paragraphs"] += 1
                    reviewed = paragraph_samples.get(sample_key, {})
                    if reviewed:
                        paragraph_samples_used.add(sample_key)
                    paragraph_review_rows.append((paper, p["id"], *p["pdf_span"], p["section"], p["previous_id"],
                                                  function[label["code"]], function[alternate["code"]],
                                                  label["relative_model_weight"], match["status"], scope,
                                                  "；".join(f"{a['page']} {a['first_anchor']}" for a in match["anchors"]),
                                                  f"{supplemental['pdf_page']} {supplemental['han_sequence']}" if supplemental else "",
                                                  reviewed.get("role"), reviewed.get("notes")))
            abstract = cases[paper]["abstract_sentences"]
            coded_sentences = verified_abstract[paper]
            if len(abstract) != len(coded_sentences):
                raise ValueError(f"{paper}: 摘要定位与复核句数不符")
            for pos, a in enumerate(abstract, 1):
                anchor = a["anchor"]
                if paper == "zotero_SCCKUUS9" and pos == 3:
                    anchor = "随着社会经济体制的转型"
                present = text_key(anchor) in text_key(pages.get(a["pdf_page"], ""))
                if not present:
                    raise ValueError(f"{paper}: 摘要核读位置不匹配 {pos}")
                role, detail = coded_sentences[pos-1].split("：", 1)
                abstract_rows.append((paper, pos, a["id"], a["pdf_page"], anchor, role, detail, present))
        path = HERE / "逐篇复读" / f"{paper}.json"
        annotations, digest = [], None
        if path.exists():
            card = load(path)
            if card["source"]["source_sha256"] != source["source_sha256"] or card["input_pages"] != list(pages):
                raise ValueError(f"{paper}: 复读卡输入不一致")
            if [p for group in card["parts"] for p in group["pages"]] != list(pages):
                raise ValueError(f"{paper}: 复读缺页")
            for group in card["parts"]:
                sampled = {p: pages[p] for p in group["pages"]}
                fragment = "\n\n".join(f"【PDF页{p}】\n{text}" for p, text in sampled.items())
                if group["source_fragment_sha256"] != hash_text(fragment):
                    raise ValueError(f"{paper}: 复读分块原文哈希不符")
                for row in group["sequence"]:
                    if (row["anchor_status"] == "matched") != (check_anchor(row, sampled) is not None):
                        raise ValueError(f"{paper}: 锚点核对状态变化")
                    annotations.append(row)
                    if paper in TARGETS:
                        model_rows.append((paper, source["journal"], row["page"], row["anchor_status"], row["anchor"],
                                           row["move"], row["before"], row["advance"], row["after"], row["style"]))
            digest = file_hash(path)
            located = [item for item in annotations if item["anchor_status"] == "matched"]
            all_notes.extend([f"## 《{title}》", "", f"{source['journal']} · {paper}", ""])
            for item in sorted(located, key=lambda x: x["page"]):
                page = item["page"]
                position = f"PDF第{page}页" if local_pdf else f"刊页{source['first_printed_page'] + page - 1}"
                all_notes.extend([
                    f"- {position}。承接　{item['before']}　推进　{item['advance']}　接续　{item['after']}　写法　{item['style']}"
                ])
            if not located:
                if paper in manually_located:
                    all_notes.append("- 自动短锚未匹配。已回原页，见[补核](无锚点补核.md)。")
                else:
                    all_notes.append("- 本篇候选笔记尚没有匹配上的原文字面锚点。")
            article_link = quote(f"逐篇复读/{paper}.json")
            all_notes.extend(["", f"[原页位置与全文笔记]({article_link})", ""])
        old = first_round.get(paper, {})
        results.append({
            "paper_id": paper, "journal": source["journal"], "title": title, "origin": source["origin"],
            "study_type": source["study_type"], "sample20": paper in TARGETS,
            "input_pages": list(pages), "body_page_count": len(pages), "physical_page_count": len(raw["pages"]) if raw else len(pages),
            "visual_pages": old.get("visual_pages", []), "source": source["source"], "source_sha256": source["source_sha256"],
            "initial_pass": bool(old), "initial_note_groups_to_recheck": len(old.get("flags", [])),
            "second_pass": digest is not None, "second_pass_sha256": digest,
            "notes": len(annotations), "located_notes": sum(a["anchor_status"] == "matched" for a in annotations),
        })

    if set(paragraph_samples) != paragraph_samples_used:
        raise ValueError("逐段校对样例找不到对应原始段落记录")
    if set(layout_samples) != layout_samples_used:
        raise ValueError("段落排版补核记录找不到对应原始候选段")
    matrix = [r for r in results if r["sample20"]]
    day = "2026-11-19 Asia/Shanghai"
    counts = {
        "articles": len(results), "journals": Counter(r["journal"] for r in results),
        "physical_pages": sum(r["physical_page_count"] for r in results),
        "local_pdf_papers": sum(bool(r["initial_pass"]) for r in results),
        "second_pass_papers": sum(r["second_pass"] for r in results),
        "body_or_publisher_page_positions": sum(r["body_page_count"] for r in results),
        "second_pass_original_page_positions": sum(r["body_page_count"] for r in results if r["second_pass"]),
        "second_pass_notes": sum(r["notes"] for r in results),
        "second_pass_located_notes": sum(r["located_notes"] for r in results),
        "sample20": len(matrix), "sample20_by_journal": Counter(r["journal"] for r in matrix),
        "sample20_second_pass": sum(r["second_pass"] for r in matrix),
        "sample20_section_candidates": len(section_rows), "sample20_body_paragraph_candidates": len(paragraph_rows),
        "sample20_reviewed_abstract_sentences": len(abstract_rows),
        "sample20_paragraph_model_output": dict(paragraph_counts),
        "reviewed_paragraph_audit_examples": len(paragraph_samples_used),
        "layout_fragments_checked": len(layout_samples_used),
    }
    missing = [r["paper_id"] for r in results if not r["second_pass"]]
    no_anchor = [r["paper_id"] for r in results if r["second_pass"] and r["located_notes"] == 0]
    fallback_needed = sorted(set(no_anchor) - manually_located)
    if require_all and (missing or paragraph_counts["paper_count"] != len(TARGETS)):
        raise ValueError(f"部分语料尚未输出完整：{missing}")
    if require_all and fallback_needed:
        raise ValueError(f"以下篇目自动锚点全未匹配，应补核原文：{fallback_needed}")
    table("corpus20.csv", ("paper_id", "journal", "title", "type", "physical_pages", "input_pages",
                          "second_pass", "source_sha256", "state"),
          ((r["paper_id"], r["journal"], r["title"], r["study_type"], r["physical_page_count"],
            len(r["input_pages"]), r["second_pass"], r["source_sha256"], "needs_content_review") for r in matrix))
    table("section_headings.csv", ("paper_id", "title", "journal", "level", "pdf_page", "heading", "anchor_match"), section_rows)
    table("paragraph_candidates.csv", ("paper_id", "paragraph", "first_pdf_page", "last_pdf_page", "section",
                                       "previous_paragraph", "sentence_count", "start_anchor", "cue", "function_candidates",
                                       "status", "text_sha256"), paragraph_rows)
    table("abstract_sentences.csv", ("paper_id", "order", "sentence_id", "pdf_page", "anchor", "role", "advance", "anchor_match"),
          abstract_rows)
    table("structure_moves.csv", ("paper_id", "journal", "pdf_page", "anchor_status", "anchor",
                                   "move", "before", "advance", "after", "style"), model_rows)
    table("paragraph_review_queue.csv", ("paper_id", "paragraph", "first_pdf_page", "last_pdf_page",
                                          "section", "previous_paragraph", "model_role", "alternate_role",
                                          "relative_weight", "evidence_status", "scope", "anchors",
                                          "normalized_han_locator", "source_checked_role",
                                          "source_checked_notes"), paragraph_review_rows)
    totals = Counter()
    for paper, _, _, _, _, han in sizes:
        totals[paper] += han
    table("section_space.csv", ("paper_id", "title", "journal", "heading", "first_pdf_page", "han_in_extracted_text", "share"),
          ((*row, round(row[-1] / totals[row[0]], 5)) for row in sizes if totals[row[0]]))

    (HERE / "二十篇分节阅读.md").write_text("\n".join(section_report), encoding="utf-8")
    (HERE / "两刊逐篇论证笔记.md").write_text("\n".join(all_notes), encoding="utf-8")
    tables = ("corpus20.csv", "section_headings.csv", "paragraph_candidates.csv", "abstract_sentences.csv", "structure_moves.csv",
              "二十篇分节阅读.md", "paragraph_review_queue.csv", "section_space.csv", "两刊逐篇论证笔记.md")
    save(HERE / "覆盖与验收.json", {
        "date": day, "status": "needs_review", "gate": "G2", "counts": counts,
        "paper_notes": results, "stage07_activation": "pilot_only",
        "all_whole_text_inputs_submitted": not missing,
        "missing_model_cards": missing,
        "zero_exact_anchor_among_generated_notes": no_anchor,
        "articles_with_manual_no_anchor_readback": sorted(set(no_anchor) & manually_located),
        "certification": "表格的切分、功能及模型判断有待逐篇精校。锚点匹配只验证引用位置。",
        "scripts": {name: file_hash(HERE / name) for name in ("review.py", "assemble.py", "paragraph_read.py")},
        "files": {name: file_hash(HERE / name) for name in
                  (*tables, verified_abstract_path.name, verified_sections_path.name, paragraph_samples_path.name,
                   layout_review_path.name, "结构手册.md", "验收与复现.md", "无锚点补核.md")},
        "model_engine_sha256": file_hash(ENGINE),
        "model_weights_sha256": file_hash(MODEL),
        "baseline_report_sha256": file_hash(PREVIOUS / "核验报告.json"),
        "locked_paragraph_cards": {
            path.stem: file_hash(path) for path in sorted((HERE / "逐段复核候选").glob("*.json"))
        },
        "root_requirements_sha256": file_hash(ROOT / "基础要求.md"),
    })
    note_summary = [
        f"两刊共{len(results)}篇，135篇本地PDF和2篇官网文本，"
        f"共{counts['physical_pages']}个文件或刊页位置。"
        f"第二轮记录已落盘{counts['second_pass_papers']}篇，核对过{counts['second_pass_original_page_positions']}个输入页位置。"
        f"{counts['second_pass_notes']}条模型笔记中，{counts['second_pass_located_notes']}条短语能回原页，仍需逐条核对释义。",
        f"本轮选择20篇定量论文做逐段精校准备，其中《中国社会科学》{counts['sample20_by_journal']['中国社会科学']}篇，"
        f"《社会学研究》{counts['sample20_by_journal']['社会学研究']}篇。"
        f"定位到{len(section_rows)}个节标题、{len(paragraph_rows)}个正文段落候选，逐句复核{len(abstract_rows)}个摘要句的功能。",
    ]
    for journal, lengths in spans.items():
        note_summary.append(f"{journal}定向样本的一级节标题之间，PDF页差中位数为{statistics.median(lengths):g}。"
                            "这个页差包含跨页边界，反映本样本定位，章节字数和正文占比须据复核的段界计算。")
    lines = ["# 两刊全文阅读与结构索引", "", *[line for s in note_summary for line in (s, "")],
             "[两刊逐篇论证笔记](两刊逐篇论证笔记.md)　"
             "[二十篇语料](corpus20.csv)　[分节阅读](二十篇分节阅读.md)　[节标题](section_headings.csv)　[段落](paragraph_candidates.csv)　"
             "[章节篇幅](section_space.csv)　[摘要逐句](abstract_sentences.csv)　[推进笔记](structure_moves.csv)　"
             "[逐段复核队列](paragraph_review_queue.csv)　[覆盖与验收](覆盖与验收.json)　[验收与复现说明](验收与复现.md)", "",
             "正文页按文件物理页定位。两篇官网逐行回收文本另有原刊始页，可按逐篇记录换算。",
             "章节篇幅按已定位一级标题之间的提取汉字计算。首页题录、脚注、表注可能随正文计入，"
             "整页图像表格计为版面证据。用于比较文章如何分配篇幅。", "",
             "135篇原件中的整页图表、引文表与卷末附页另有页级状态，见首轮核验。", "",
             "| 期刊 | 论文 | 输入页 | 二次阅读 | 匹配锚点 |",
             "|---|---|---:|---|---:|"]
    for r in results:
        title = r["title"].replace("|", "｜").replace("[", "［").replace("]", "］")
        first = quote(f"../{PREVIOUS.name}/逐篇全文分析/{r['paper_id']}.json")
        second = quote(f"逐篇复读/{r['paper_id']}.json")
        locator = f"[分节笔记]({second})" if r["second_pass"] else (f"[首轮全文记录]({first})" if r["initial_pass"] else "待读")
        lines.append(f"| {r['journal']} | {title} | {r['body_page_count']} | {locator} | {r['located_notes']}/{r['notes']} |")
    (HERE / "全文与结构索引.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(counts)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-all", action="store_true")
    args = parser.parse_args()
    main(args.require_all)
