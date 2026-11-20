"""Read the local Zotero library and make a page-addressed reading index."""
import hashlib
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

import pypdfium2 as pdfium
from pypdfium2 import raw

OUT = Path(__file__).resolve().parent
JOURNAL = "中国社会科学"
MAIN = re.compile(r"^[一二三四五六七八九十]+[、.]")
SUB = re.compile(r"^\([一二三四五六七八九十]+\)")
END = re.compile(r"^[\[〔【(]?(?:责任编辑|责任编校|\s*ABSTRACTS\b|参考文献[:：]?$)", re.I)
HAN = re.compile(r"[\u3400-\u9fff]")
NOTE = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩❋●＊*]+")
FOOTER = re.compile(r"^[·.‧•?]*\d{1,4}[·.‧•?]*$")
TERMINAL = set("。！？!?")
CLOSER = set("”’」』）)]】①②③④⑤⑥⑦⑧⑨⑩")
NOTE_NUMBERS = set("①②③④⑤⑥⑦⑧⑨⑩")


def compact(s):
    s = "".join(ch if ch in NOTE_NUMBERS else unicodedata.normalize("NFKC", ch)
                for ch in s.replace("\x82", "，"))
    return re.sub(r"[\s\u200b\u00ad\ufeff\ue000-\uf8ff]", "", s)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def json_write(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def inventory(database):
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("pragma query_only = on")
        rows = db.execute("""
            with fields_by_item as (
                select d.itemID,
                       max(case when f.fieldName='publicationTitle' then v.value end) journal,
                       max(case when f.fieldName='title' then v.value end) title,
                       max(case when f.fieldName='date' then v.value end) date,
                       max(case when f.fieldName='issue' then v.value end) issue,
                       max(case when f.fieldName='pages' then v.value end) pages,
                       max(case when f.fieldName='DOI' then v.value end) doi
                from itemData d join fields f using(fieldID) join itemDataValues v using(valueID)
                group by d.itemID
            )
            select i.key item_key, ai.key attachment_key, a.path attachment_path,
                   a.contentType media_type, b.title, b.date, b.issue, b.pages, b.doi
            from fields_by_item b join items i on i.itemID=b.itemID
            left join itemAttachments a on a.parentItemID=i.itemID
                  and a.itemID not in (select itemID from deletedItems)
                  and a.contentType='application/pdf'
            left join items ai on ai.itemID=a.itemID
            where b.journal=? and i.itemID not in (select itemID from deletedItems)
            order by b.date desc, b.issue, i.key
        """, (JOURNAL,)).fetchall()
    return [dict(row) for row in rows]


def page_lines(page):
    tp = page.get_textpage()
    result = []
    line = []
    try:
        for i in range(tp.count_chars() + 1):
            char = chr(raw.FPDFText_GetUnicode(tp.raw, i)) if i < tp.count_chars() else "\n"
            if char == "\n":
                if line:
                    text = compact("".join(x[0] for x in line))
                    if text and any(x[1] for x in line):
                        boxes = [x[1] for x in line if x[1]]
                        result.append(dict(text=text, x=boxes[0][0], end=boxes[-1][2],
                                           y=median(b[1] for b in boxes), size=median(x[2] for x in line if x[1])))
                line.clear()
            elif char != "\r":
                box = tp.get_charbox(i) if HAN.fullmatch(char) or char.isalnum() else None
                line.append((char, box, raw.FPDFText_GetFontSize(tp.raw, i) if box else 0))
    finally:
        tp.close()
    return result


def join_fragments(lines):
    lines = sorted(lines, key=lambda line: -line["y"])
    result = []
    for line in lines:
        if result and abs(result[-1]["y"] - line["y"]) < 4 and result[-1]["end"] <= line["x"] + 2:
            result[-1]["text"] += line["text"]
            result[-1]["end"] = max(result[-1]["end"], line["end"])
        else:
            result.append(line.copy())
    return result


def sentence_spans(paragraph):
    start = pos = 0
    spans = []
    while pos < len(paragraph):
        if paragraph[pos] in TERMINAL:
            pos += 1
            while pos < len(paragraph) and paragraph[pos] in CLOSER | TERMINAL:
                pos += 1
            spans.append((start, pos))
            start = pos
        else:
            pos += 1
    if start < len(paragraph):
        spans.append((start, len(paragraph)))
    return spans


def key_title(title):
    return "".join(ch.lower() for ch in compact(title) if ch.isalnum())


def extract(row, keep_pages=False):
    with pdfium.PdfDocument(row["pdf_path"]) as doc:
        pages = []
        for i in range(len(doc)):
            page = doc[i]
            try:
                lines = page_lines(page)
                pages.append(dict(pdf_page=i + 1, width=page.get_width(), height=page.get_height(), lines=lines))
            finally:
                page.close()
    title = key_title(row["title"])
    title_aliases = {title}
    if row["attachment_key"] == "ETXRUCCP":
        # Printed title verified on PDF page 1. Its text layer maps 入 to 人.
        title_aliases.add(title.replace("介入", "介人"))
    running_titles = {title, key_title(re.split(r"[—–]{2,}|[:：]", row["title"], maxsplit=1)[0])}
    location = None
    for page in pages[:2]:
        lines = page["lines"]
        for i in range(min(15, len(lines))):
            for end in range(i + 1, min(i + 4, len(lines)) + 1):
                if key_title("".join(line["text"] for line in lines[i:end])) in title_aliases:
                    location = (page["pdf_page"], end)
                    break
            if location:
                break
        if location:
            break
    range_match = re.match(r"^(\d+)\s*[-—–]\s*(\d+)", row["pages"] or "")
    journal_first, journal_last = map(int, range_match.groups()) if range_match else (None, None)
    start_page = location[0] if location else 1
    planned_end = start_page + journal_last - journal_first if journal_last else len(pages)
    article_end = min(planned_end, len(pages))
    flags = []
    if not location:
        flags.append("题名需回看首页")
    if planned_end > len(pages):
        flags.append("题录页数超过附件页数")
    if not range_match:
        flags.append("题录缺有效起止页")
    middle = [page for page in pages[start_page:article_end-1]] or pages[start_page-1:article_end]
    line_samples = [line for page in middle for line in page["lines"]
                    if len(HAN.findall(line["text"])) >= 15 and page["height"]*.15 < line["y"] < page["height"]*.92]
    if not line_samples:
        flags.append("可提取正文过少")
    margins = Counter(round(line["x"] / 3) * 3 for line in line_samples)
    left = margins.most_common(1)[0][0] if margins else 0
    double_column = row["attachment_key"] == "8B575M9S"
    if double_column:
        flags.append("双栏及缺字页需回看原版")
    article_pages = pages[start_page-1:article_end]
    blocks = []
    block = None
    section = "正文开头（未编号）"
    front = True
    closed = False
    section_headings = []
    abstract = []
    for page in article_pages:
        pn, height = page["pdf_page"], page["height"]
        lines = page["lines"]
        if pn == start_page and location:
            lines = lines[location[1]:]
        if double_column:
            mid = page["width"] * .49
            grouped = [join_fragments([line for line in lines if line["x"] < mid]),
                       join_fragments([line for line in lines if line["x"] >= mid])]
        else:
            grouped = [join_fragments(lines)]
        in_abstract = False
        for col_idx, stream in enumerate(grouped):
            local_left = (10 if col_idx == 0 else 240) if double_column else left
            last_line = None
            in_notes = False
            body_started = not front
            for line in stream:
                t = line["text"]
                hz = len(HAN.findall(t))
                px, y = line["x"], line["y"]
                if not t or FOOTER.fullmatch(t) or re.match(r"^(?:中国知网|https?://|中国社会科学\d{4}年|“建设中华民族现代文明”研讨会发言摘登|“习近平文化思想研究”笔谈$)", t):
                    continue
                if y > height * .907 and pn > start_page and len(t) < 60:
                    continue
                if pn > start_page and y > height*.86 and key_title(t) in running_titles:
                    continue
                if END.match(t):
                    closed = True
                    break
                if y < height * (.042 if double_column else .055):
                    continue
                if pn == start_page and front:
                    if re.match(r"^摘要[:：]?", t):
                        abstract.append((pn, re.sub(r"^摘要[:：]?", "", t)))
                        in_abstract = True
                        continue
                    if re.match(r"^关键词[:：]?", t):
                        in_abstract = False
                        continue
                    if re.match(r"^作者.{2,30}[，,、]", t) and len(t) < 120:
                        in_abstract = False
                        continue
                    if in_abstract:
                        abstract.append((pn, t))
                        continue
                    if hz < 9 and not MAIN.match(t):
                        continue
                if NOTE.match(t) and (y < height*.40 or not body_started):
                    in_notes = True
                if in_notes:
                    break
                if hz < 3 and not re.search(r"[。？！!?]", t):
                    continue
                first_on_stream = last_line is None
                front = False
                body_started = True
                gap = last_line["y"] - y if last_line else 0
                heading = (MAIN.match(t) or SUB.match(t)) and len(t) <= 49 and not TERMINAL.intersection(t)
                if heading:
                    if MAIN.match(t):
                        section = t
                    section_headings.append({"heading": t, "pdf_page": pn, "level": 1 if MAIN.match(t) else 2})
                    block = None
                    last_line = line
                    continue
                indented = local_left + 12 <= px <= local_left + 38 and hz >= 4
                page_continuation = first_on_stream and not indented and block is not None
                if block is None or indented or (gap > 29 and not page_continuation):
                    block = dict(section=section, start_page=pn, end_page=pn, text="")
                    blocks.append(block)
                block["text"] += t
                block["end_page"] = pn
                last_line = line
            if closed:
                break
        if closed:
            break
    if abstract:
        blocks.insert(0, dict(section="摘要", start_page=abstract[0][0], end_page=abstract[-1][0],
                              text="".join(text for _, text in abstract)))
    if not blocks:
        flags.append("没有得到正文候选段")
    if any(len(block["text"]) > 2500 for block in blocks):
        flags.append("有超长候选段，需核对缩进、脚注或表格")
    if abstract and len(blocks[0]["text"]) > 700:
        flags.append("摘要终点需核对")
    uncovered = sorted(set(range(start_page, article_end + 1)) -
                       {pn for b in blocks for pn in range(b["start_page"], b["end_page"] + 1)})
    if uncovered:
        flags.append("候选正文未定位全部题录页，须核对末页或图表")
    for n, block in enumerate(blocks, 1):
        text = block["text"]
        block["id"] = f"P{n:03d}"
        block["sentences"] = [dict(id=f"P{n:03d}S{s:02d}", start=a, end=b)
                              for s, (a, b) in enumerate(sentence_spans(text), 1)]
    meta = dict(pdf_pages=len(pages), first_article_pdf_page=start_page,
                last_chinese_pdf_page=article_end, journal_first_page=journal_first,
                journal_last_page=journal_last, title_identity="text_match" if location else "needs_review",
                flags=flags, pages_without_body_candidate=uncovered, section_heading_candidates=section_headings,
                paragraph_candidates=len(blocks), sentence_candidates=sum(len(b["sentences"]) for b in blocks))
    return meta, blocks, article_pages if keep_pages else None


def main(database, scratch):
    rows = inventory(database)
    groups = defaultdict(list)
    checked = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    for row in rows:
        if row["attachment_path"] and row["attachment_path"].startswith("storage:"):
            filename = row["attachment_path"][len("storage:"):]
            path = database.parent / "storage" / row["attachment_key"] / filename
            if path.is_file():
                row.update(pdf_path=str(path), sha256=sha(path), file_bytes=path.stat().st_size)
        year = re.search(r"\b(?:19|20)\d\d\b", row["date"] or "")
        row["year"] = int(year.group()) if year else None
        groups[(key_title(row["title"]), row["year"], row["issue"], row["pages"])].append(row)
    order = sorted(groups.values(), key=lambda g: (g[0]["year"] or 0, int(g[0]["issue"] or 0), g[0]["pages"] or "", g[0]["title"]))
    summary = []
    for group in order:
        def attachment_rank(row):
            cache = database.parent / "storage" / (row["attachment_key"] or "-") / ".zotero-ft-cache"
            return (row.get("file_bytes", 0) > 0, cache.stat().st_size if cache.exists() else 0, row.get("file_bytes", 0))

        choices = sorted(group, key=attachment_rank, reverse=True)
        row = choices[0].copy()
        if row["title"] == "影响中国城乡流动人口的推力与拉力因素分析":
            row = next((entry.copy() for entry in choices if entry["attachment_key"] == "S823QAM2"), row)
        paper_id = "zotero_" + (row["attachment_key"] or row["item_key"])
        row.update(paper_id=paper_id, journal=JOURNAL, checked_at=checked, equivalents=choices)
        try:
            if not row.get("pdf_path"):
                raise FileNotFoundError("Zotero 未找到本地 PDF")
            meta, blocks, pages = extract(row, keep_pages=row["attachment_key"] == "WPWDXCNN")
            row.update(meta, extraction_status="segmented_needs_review")
            json_write(scratch / f"{paper_id}.json", {"source": row, "blocks": blocks, "pages": pages})
        except Exception as exc:
            row.update(extraction_status="failed", error=f"{type(exc).__name__}: {exc}")
        summary.append(row)
        print(paper_id, row["title"], row.get("pdf_pages"), row.get("paragraph_candidates"),
              row.get("sentence_candidates"), row.get("flags", row.get("error", "")), flush=True)
    json_write(OUT / "馆藏清单.json", {"checked_at": checked, "database": str(database), "selection": JOURNAL,
                                        "records": len(rows), "unique_articles": len(summary), "articles": summary})
    for row in summary:
        source = scratch / f'{row["paper_id"]}.json'
        if row["extraction_status"] == "failed" or not source.is_file():
            continue
        blocks = json.loads(source.read_text(encoding="utf-8"))["blocks"]
        target = OUT / "定位索引" / f'{row["paper_id"]}.json'
        target.parent.mkdir(exist_ok=True)
        json_write(target, {"paper_id": row["paper_id"], "pdf": row["pdf_path"], "sha256": row["sha256"],
                            "status": "geometry_candidates_needs_review",
                            "blocks": [{**{k: v for k, v in block.items() if k not in ("text", "sentences")},
                                        "anchor": block["text"][:14],
                                        "sentences": [{"id": s["id"], "anchor": block["text"][s["start"]:min(s["start"]+9, s["end"])]}
                                                      for s in block["sentences"]]} for block in blocks]})


if __name__ == "__main__":
    scratch = Path(sys.argv[1]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    main(Path.home() / "Zotero" / "zotero.sqlite", scratch)
