"""Read the five-journal Zotero collection and build a local question library."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import re
import shutil
import sqlite3
import sys
import tempfile
import unicodedata
from collections import Counter
from contextlib import closing
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[2]
CONTROL = ROOT / "00_项目控制/v004_第4版"
SHARED = ROOT / next(
    item["path"] for item in json.loads((CONTROL / "module_registry.json").read_text(encoding="utf-8"))["modules"]
    if item["module_id"] == "04"
) / "tools"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))
from runtime import file_lock, inside, load, now, sha, verify_locks, write
from providers import doi, norm

JOURNALS = ("中国社会科学", "社会", "社会学研究", "中国青年研究", "探索与争鸣")
VERSION = "05-question-library-v1"
PATTERNS = {
    "现实反常": r"悖论|反常|出乎意料|何以|缘何|为什么|如何解释|令人困惑",
    "解释竞争": r"相反|相互矛盾|竞争性解释|两种.{0,12}(解释|观点|假设)|争论|存在分歧|截然不同",
    "解释不足": r"未能解释|无法解释|有待解释|未能揭示|忽视了|有待深入|鲜有研究|尚缺乏|尚未回答",
    "过程机制": r"如何形成|如何发生|如何实现|如何影响|如何运作|如何转化|作用机制|形成过程|通过何种",
    "差异边界": r"是否存在差异|有何差异|何种条件|何种情境|在什么情况下|异质性|是否适用",
    "变化比较": r"发生了怎样|如何变化|如何变迁|有什么变化|如何演变|怎样演变|何种变化|趋势如何",
    "概念辨析": r"何谓|何为|如何理解|概念界定|理论命题|何以可能",
}
QUESTION = re.compile(r"本文.{0,8}(旨在|试图|尝试|考察|探讨|检验|分析|聚焦|研究|回答)|"
                      r"本研究.{0,8}(考察|探讨|检验|分析|关注|旨在)|"
                      r"核心问题|研究问题|本文关注|问题是|[？?]")
SPLIT = re.compile(r"[^。！？!?；;]+[。！？!?；;]?")
# OCR or multi-column exceptions reviewed on the actual first page. Both
# fragments must be present before opening text can enter the source index.
CHECKED_TITLES = {
    "84YD2G38": ("资本介人文化生产的耦合效应", "胡潇"),
    "9AFZNVZ4": ("从嫉妒到怨恨", "论中国社会情绪氛围的一个侧面"),
    "TSVM4QCW": ("中国高等教育中的自主招生人才选拔", "吴晓刚李忠路"),
    "ZBEUMV5I": ("当代大学生婚恋价值观研究", "1019633jcnki112579d201105011"),
}


def compact(value):
    value = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"[\s\u200b\ufeff\ue000-\uf8ff]", "", value)


def read_items(path):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        rows = db.execute("""
            SELECT i.itemID, i.key, v.value FROM items i JOIN itemTypes t USING(itemTypeID)
            JOIN itemData d USING(itemID) JOIN fields f USING(fieldID)
            JOIN itemDataValues v USING(valueID)
            WHERE t.typeName='journalArticle' AND f.fieldName='publicationTitle'
                  AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
            ORDER BY i.key
        """).fetchall()
        result = []
        for item, key, journal in rows:
            journal = compact(journal).strip("《》")
            if journal not in JOURNALS:
                continue
            fields = dict(db.execute("""
                SELECT f.fieldName, v.value FROM itemData d JOIN fields f USING(fieldID)
                JOIN itemDataValues v USING(valueID) WHERE itemID=?
            """, (item,)))
            authors = ["".join((last or "", first or "")) for last, first in db.execute("""
                SELECT c.lastName, c.firstName FROM itemCreators ic JOIN creators c USING(creatorID)
                JOIN creatorTypes ct USING(creatorTypeID) WHERE ic.itemID=? AND ct.creatorType='author'
                ORDER BY ic.orderIndex
            """, (item,))]
            attachments = db.execute("""
                SELECT i.key,a.path FROM itemAttachments a JOIN items i USING(itemID)
                WHERE a.parentItemID=? AND (a.contentType='application/pdf' OR lower(a.path) LIKE '%.pdf')
                    AND a.itemID NOT IN (SELECT itemID FROM deletedItems) ORDER BY i.key
            """, (item,)).fetchall()
            result.append(dict(key=key, journal=journal, title=fields.get("title", ""),
                               date=fields.get("date", ""), issue=fields.get("issue", ""),
                               pages=fields.get("pages", ""), doi=doi(fields.get("DOI")),
                               authors=authors, abstract=fields.get("abstractNote", ""), attachments=attachments))
    return result


def snapshot_items(database):
    try:
        return read_items(database), "sqlite_read_transaction"
    except sqlite3.OperationalError as exc:
        if "locked" not in str(exc).lower() and "readonly" not in str(exc).lower():
            raise
    # A live database can reject mode=ro with exclusive locking. Freeze DB + WAL
    # into temporary storage and accept only a byte-stable source across the copy.
    with tempfile.TemporaryDirectory(prefix="topic_zotero_") as temp:
        for _ in range(3):
            paths = [database, database.with_name(database.name + "-wal")]
            sources = {p: sha(p) if p.is_file() else None for p in paths}
            try:
                for path, digest in sources.items():
                    dest = Path(temp) / path.name
                    if digest is None:
                        dest.unlink(missing_ok=True)
                    else:
                        shutil.copyfile(path, dest)
                if all((sha(p) if p.is_file() else None) == h
                       and (sha(Path(temp) / p.name) if (Path(temp) / p.name).is_file() else None) == h
                       for p, h in sources.items()):
                    return read_items(Path(temp) / database.name), "stable_db_and_wal_copy"
            except FileNotFoundError:
                continue
    raise ValueError("Zotero数据库正在变化，无法锁定只读快照，请重试")


def groups(items):
    # Group only on DOI or matching title and publication identity inside a journal.
    grouped = []
    for item in items:
        item["year"] = next(iter(re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", item["date"])), "")
        def same(other):
            if item["journal"] != other["journal"]:
                return False
            if item["doi"] and other["doi"]:
                return item["doi"] == other["doi"]
            same_bibliography = (item["year"] == other["year"] and item["issue"] == other["issue"]
                                 and item["pages"] == other["pages"] and bool(item["year"] and item["pages"]))
            same_author = (item["authors"] and item["authors"] == other["authors"]
                           and item["year"] == other["year"] and bool(item["year"]))
            return bool(item["title"] and norm(item["title"]) == norm(other["title"])
                        and (same_bibliography or same_author))

        match = next((group for group in grouped if any(same(other) for other in group)
                      and len({r["doi"] for r in group + [item] if r["doi"]}) < 2), None)
        if match is None:
            grouped.append([item])
        else:
            match.append(item)
    return grouped


def page_text(doc, index):
    page = doc[index]
    try:
        text = page.get_textpage()
        try:
            return compact(text.get_text_bounded())
        finally:
            text.close()
    finally:
        page.close()


def find_passages(value, location, seed=0):
    hits = []
    for match in SPLIT.finditer(value):
        sentence = match.group()
        if len(re.findall(r"[\u3400-\u9fff]", sentence)) < 8 or "@" in sentence:
            continue
        # Locator evidence is centered on the actual question or argumentative cue.
        cues = [(name, found) for name, regex in PATTERNS.items() if (found := re.search(regex, sentence))]
        question = QUESTION.search(sentence)
        if not cues and not question:
            continue
        term = question or cues[0][1]
        start = max(0, term.start() - 24) if len(sentence) > 72 else 0
        hits.append((seed + 3 * bool(question) + 2 * len(cues) + (1 if re.search(r"本文|本研究", sentence) else 0),
                     {"location": location, "excerpt": sentence[start:start+72],
                      "cues": [name for name, _ in cues]}))
    return hits


def locate_article(database, group):
    import pypdfium2 as pdfium
    candidates = []
    seen = set()
    for item in group:
        for key, raw in item["attachments"]:
            if not raw:
                continue
            path = (database.parent / "storage" / key / raw[8:] if raw.startswith("storage:") else Path(raw))
            if not path.is_absolute() or path in seen:
                continue
            seen.add(path)
            info = {"attachment_key": key, "path": str(path), "status": "missing"}
            candidates.append(info)
            if not path.is_file():
                continue
            try:
                digest = sha(path)
                with pdfium.PdfDocument(str(path)) as doc:
                    pages = [page_text(doc, i) for i in range(min(len(doc), 5))]
                    title = norm(item["title"])
                    matched_page = next((i for i, page in enumerate(pages) if title and title in norm(page)), 0)
                    identity = bool(title) and title in norm("".join(pages[:2]))
                    checked = CHECKED_TITLES.get(item["key"])
                    overridden = bool(checked and all(norm(part) in norm(pages[0]) for part in checked))
                    identity = identity or overridden
                    info.update(sha256=digest, page_count=len(doc), pages_scanned=list(range(1, len(pages)+1)),
                                status="title_matched" if identity else "title_unconfirmed",
                                identity_method="reviewed_opening_fragments" if overridden else "normalized_title")
                if not identity or sha(path) != digest:
                    continue
                # Some magazine bundles contain several articles. Start at the
                # matched heading and stop at the bibliographic span when known.
                span = re.fullmatch(r"(\d+)-(\d+)", compact(item["pages"]))
                stop = min(len(pages), matched_page + int(span[2]) - int(span[1]) + 1) if span else len(pages)
                sections = []
                for i in range(matched_page, stop):
                    value = pages[i]
                    if i == matched_page:
                        cut = re.search(r"关键词[:：].{0,130}?(?=\[|【|一[、.]|摘要|引言|提要)", value)
                        if cut:
                            value = value[cut.end():]
                    sections.append((i + 1, value))
                return info, sections, candidates
            except (OSError, ValueError, pdfium.PdfiumError) as exc:
                info.update(status="read_error", error=str(exc))
    return None, [], candidates


def paper_record(database, group):
    main = next((r for r in group if r["abstract"]), group[0])
    attachment, pages, attempts = locate_article(database, group)
    abstract = compact(main["abstract"])
    abstract_location = {"kind": "zotero_abstract", "item_key": main["key"], "field": "abstractNote"}
    hits = find_passages(abstract, abstract_location, seed=1)
    for number, page in pages:
        hits.extend(find_passages(page, {"kind": "pdf_opening", "page": number}, seed=3 if number <= 2 else 0))
    passages = []
    for _, hit in sorted(hits, key=lambda pair: -pair[0]):
        if any(hit["excerpt"] == prior["excerpt"] for prior in passages):
            continue
        passages.append(hit)
        if len(passages) == 4:
            break
    if not passages and abstract:
        passages.append({"location": abstract_location, "excerpt": abstract[:72], "cues": []})
    if not passages and pages:
        number, page = pages[0]
        passages.append({"location": {"kind": "pdf_opening", "page": number}, "excerpt": page[:72], "cues": []})
    return dict(paper_id="zotero_" + group[0]["key"], item_keys=[r["key"] for r in group],
                **{k: main[k] for k in ("journal", "title", "authors", "year", "issue", "pages", "doi")},
                abstract_available=bool(abstract), attachment=attachment, attachment_attempts=attempts,
                evidence_level="opening_indexed" if attachment else ("abstract_indexed" if abstract else "title_only"),
                candidate_cues=sorted({cue for passage in passages for cue in passage["cues"]}), passages=passages)


def scan(database, output):
    items, provenance = snapshot_items(database)
    if not items:
        raise ValueError("五刊没有命中，请核对Zotero题录与数据库位置")
    output.mkdir(parents=True, exist_ok=False)
    rows = [paper_record(database, group) for group in groups(items)]
    write(output / "inventory.json", rows)
    return write_summary(output, database, provenance, items, rows)


def write_summary(output, database, provenance, items, rows):
    summary = {journal: {"zotero_items": sum(r["journal"] == journal for r in items),
                         "unique_articles": sum(r["journal"] == journal for r in rows),
                         **{level: sum(r["journal"] == journal and r["evidence_level"] == level for r in rows)
                            for level in ("opening_indexed", "abstract_indexed", "title_only")}}
               for journal in JOURNALS}
    write(output / "scan_manifest.json", {"schema_version": 1, "started_from": str(database),
          "database_read_method": provenance, "verified_at": now(), "pdfium_version": importlib.metadata.version("pypdfium2"),
          "journal_counts": summary, "code": file_lock(__file__), "inventory": file_lock(output / "inventory.json")})
    return summary


def publish(output, annotations):
    inventory_lock = load(output / "scan_manifest.json")["inventory"]
    if verify_locks([inventory_lock]):
        raise ValueError("逐篇索引哈希与扫描清单不一致")
    papers = {row["paper_id"]: row for row in load(output / "inventory.json")}
    review = load(annotations)
    cases = []
    for case in review["cases"]:
        paper = papers[case["paper_id"]]
        attachment = paper["attachment"]
        pages = case["pdf_pages"]
        if not attachment or not pages or any(p < 1 or p > attachment["page_count"] for p in pages):
            raise ValueError(f"范例无有效原PDF页码 {case['paper_id']}")
        if sha(Path(attachment["path"])) != attachment["sha256"]:
            raise ValueError(f"范例与阅读时的PDF已变化 {case['paper_id']}")
        cases.append(dict(case, journal=paper["journal"], title=paper["title"], year=paper["year"],
                          pdf_sha256=attachment["sha256"], pdf_path=attachment["path"]))
    if {r["journal"] for r in cases} != set(JOURNALS) or len({r["paper_id"] for r in cases}) != len(cases):
        raise ValueError("例库须覆盖五刊且每个paper_id仅出现一次")
    snapshot = output / "question_library.json"
    if snapshot.exists():
        raise FileExistsError("资源已发布，增补须另建资源目录")
    write(snapshot, {"schema_version": 1, "resource_version": VERSION, "created_at": now(),
                     "scan_manifest": file_lock(output / "scan_manifest.json"), "inventory": inventory_lock,
                     "annotations": file_lock(annotations), "reviewer": review["reviewer"], "reviewed_at": review["reviewed_at"],
                     "patterns": review["patterns"], "cases": cases})
    return file_lock(snapshot)


def terms(value):
    clean = norm(value)
    return {clean[i:i+2] for i in range(len(clean)-1)}


def rank(rows, text_for, topic):
    query = terms(topic)
    vocab = [terms(text_for(row)) for row in rows]
    freq = Counter(term for bag in vocab for term in bag)
    matches = [(row, sum(math.log1p(len(rows) / freq[t]) for t in sorted(query & bag)))
               for row, bag in zip(rows, vocab)]
    return sorted(matches, key=lambda pair: (-pair[1], pair[0]["paper_id"]))


def retrieve(resource, topic, limit=6):
    ranked = rank(resource["cases"], lambda c: " ".join([c["title"], c["theme"], c["question"]]), topic)
    selected = [case for case, _ in ranked[:2]]
    seen = {case["journal"] for case in selected}
    for case, _ in ranked:
        if case["journal"] not in seen and len(selected) < limit:
            selected.append(case)
            seen.add(case["journal"])
    additional = [case for case, _ in ranked if case not in selected]
    return (selected + additional)[:limit]


def retrieve_openings(resource, topic, exclude, limit=4):
    rows = [r for r in load(resource["inventory"]["path"]) if r["paper_id"] not in exclude and r["passages"]]
    ranked = rank(rows, lambda r: r["title"] + " ".join(p["excerpt"] for p in r["passages"]), topic)
    return [{k: row[k] for k in ("paper_id", "title", "journal", "year", "evidence_level", "passages")}
            for row, score in ranked[:limit] if score > 0]


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("scan")
    build.add_argument("--output", required=True)
    build.add_argument("--database", default=str(Path.home() / "Zotero/zotero.sqlite"))
    publish_parser = commands.add_parser("publish")
    publish_parser.add_argument("--output", required=True)
    publish_parser.add_argument("--annotations", required=True)
    find = commands.add_parser("retrieve")
    find.add_argument("--library", required=True)
    find.add_argument("--topic", required=True)
    args = parser.parse_args(argv)
    if args.command == "scan":
        result = scan(Path(args.database).resolve(strict=True), inside(ROOT, args.output))
    elif args.command == "publish":
        result = publish(inside(ROOT, args.output), inside(ROOT, args.annotations))
    else:
        resource = load(args.library)
        if verify_locks([resource["inventory"], resource["scan_manifest"], resource["annotations"]]):
            raise ValueError("学习资源文件已变化")
        examples = retrieve(resource, args.topic)
        result = {"patterns": resource["patterns"], "examples": examples,
                  "opening_candidates": retrieve_openings(resource, args.topic, {c["paper_id"] for c in examples})}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
