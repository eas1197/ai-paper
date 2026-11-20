"""Build the pilot from its locked Zotero split and reviewed source anchors."""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from hashlib import sha256
from pathlib import Path

from exemplars07 import MOVES, read_index

ROOT = Path(__file__).resolve().parents[2].parent
MODULE = "论证语料试验_20261118_attempt001"
PREVIOUS = ROOT / "02_文章结构学习/v002_第2版/outputs/资源建设_20261114_attempt002"
DESIGN = {
    "6V7LJIWN": "repeated_cross_section", "SCCKUUS9": "pooled_cross_section",
    "J38BV4A5": "cross_section", "89UP6KH7": "panel",
    "DD4I5QA4": "cross_section", "NLVHWHF6": "couple_cohort",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def lock(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}


def compact(text):
    return re.sub(r"[^a-z0-9\u3400-\u9fff]", "", unicodedata.normalize("NFKC", text).lower())


def write(path, obj):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def csv_read(path, delimiter=","):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def build(split_path, annotated_path, routes_path, index_path, *, verify_only=False):
    split = read(split_path)
    training, holdout = split["train"], split["holdout"]
    papers = {row["paper_id"]: row for row in training}
    withheld = {row["paper_id"] for row in holdout}
    all_rows = training + holdout
    if (len(papers) != len(training) or len(withheld) != len(holdout)
            or papers.keys() & withheld or len({compact(r["title"]) for r in all_rows}) != len(all_rows)
            or len({r["sha256"] for r in all_rows}) != len(all_rows)):
        raise ValueError("语料划分重复")
    if any(digest(Path(r["pdf_path"])) != r["sha256"] for r in all_rows):
        raise ValueError("Zotero 文件已变化")
    legacy = ROOT / split["legacy_corpus"]["path"]
    if digest(legacy) != split["legacy_corpus"]["sha256"]:
        raise ValueError("既有语料登记已变化")
    if withheld & {r["paper_id"] for r in csv_read(legacy)}:
        raise ValueError("留出文章已在既有风格资源中")
    section_file = PREVIOUS / "structure_moves.csv"
    previous = csv_read(legacy)
    section_records = csv_read(section_file)
    example_rows = csv_read(annotated_path, "\t")
    examples, routes = [], []
    for paper_id, paper in papers.items():
        key = paper_id.removeprefix("zotero_")
        page_file = PREVIOUS / "fulltext" / key / "pages.json"
        source = read(page_file.parent / "source.json")
        old = next(r for r in previous if r["paper_id"] == paper_id)
        if source["pdf_sha256"] != paper["sha256"] or old["pdf_sha256"] != paper["sha256"]:
            raise ValueError(f"旧文字层未绑定当前PDF {paper_id}")
        pages = read(page_file)
        annotations = [r for r in example_rows if r["key"] == key]
        for row in annotations:
            page = int(row["page"])
            if not 1 <= page <= len(pages) or compact(row["anchor"]) not in compact(pages[page - 1]["text"]):
                raise ValueError(f"未在正文页文字层定位：{key} PDF第{page}页 {row['anchor']}")
            examples.append({
                "example_id": f"{key}-{row['move']}-{page}", "paper_id": paper_id,
                "move": row["move"], "pdf_page": page, "source_anchor": row["anchor"],
                "section": row["section"], "topic": row["topic"],
                "subtasks": [part for part in row["subtasks"].split("|") if part],
                **{name: row[name] for name in ("before", "advance", "after", "style", "conditions")},
            })
        sections = [{name: r[name] for name in ("section_title", "page_start", "page_end",
                                               "first_says", "next_says", "ends_with", "relationship")}
                    for r in section_records if r["paper_id"] == paper_id and r["level"] == "section"]
        routes.append({
            "paper_id": paper_id, "title": paper["title"], "journal": paper["journal"],
            "pdf_sha256": paper["sha256"], "pdf_pages": len(pages),
            "text_pages": sum(bool(compact(p["text"])) for p in pages),
            "chapter_routes": sections, "stage": "chapter_routes_and_selected_paragraphs",
            "paragraphs_coded_this_pilot": len(annotations), "source_text": lock(page_file),
        })
    if len(examples) != len(example_rows) or set(MOVES) != {e["move"] for e in examples}:
        raise ValueError("存在未分配的标注或缺失的写作任务")
    route_data = {"scope": "pilot", "status": "needs_review", "split": lock(split_path),
                  "previous_section_annotations": lock(section_file), "papers": routes}
    index = {"schema_version": 1, "status": "pilot", "split": lock(split_path),
             "annotation": lock(annotated_path),
             "papers": {paper_id: {k: paper[k] for k in ("title", "journal", "sha256")}
                        | {"design": DESIGN[paper_id.removeprefix("zotero_")]}
                        for paper_id, paper in papers.items()},
             "held_out_paper_ids": sorted(withheld), "examples": examples}
    if verify_only:
        if read(routes_path) != route_data or read_index(index_path, pilot=True) != index:
            raise ValueError("现有产物与重新构建结果不一致")
    else:
        if routes_path.exists() or index_path.exists():
            raise FileExistsError("已有产物。如需核对请使用 --verify")
        write(routes_path, route_data)
        write(index_path, index)
        read_index(index_path, pilot=True)
    return {"articles": len(routes), "holdout": len(holdout), "examples": len(examples),
            "pdf_pages": sum(r["pdf_pages"] for r in routes), "moves": dict(Counter(e["move"] for e in examples))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    structure = ROOT / "02_文章结构学习/v005_第5版/outputs" / MODULE
    language = ROOT / "03_学术语言学习/v004_第4版/outputs" / MODULE
    print(json.dumps(build(structure / "split.json", language / "段落标注.tsv",
                           structure / "章节推进.json", language / "writing_exemplars.json",
                           verify_only=args.verify), ensure_ascii=False))
