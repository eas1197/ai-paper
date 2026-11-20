"""Select traceable writing examples by topic or rhetorical task."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from hashlib import sha256
from math import sqrt
from pathlib import Path

MOVES = {
    "question": "收束研究问题",
    "literature": "比较既有解释",
    "hypothesis": "从解释推出可检验预期",
    "design": "让测量或模型对应研究问题",
    "results": "用结果回答具体比较",
    "discussion": "将发现放回开篇问题和理论",
}


def read_index(path: Path, *, pilot: bool = False) -> dict:
    index = json.loads(path.read_text(encoding="utf-8-sig"))
    if index["schema_version"] != 1 or index["status"] != ("pilot" if pilot else "passed"):
        raise ValueError("写作范例库的版本或验收状态不适用")
    papers = index["papers"]
    held_out = set(index.get("held_out_paper_ids", []))
    examples = index["examples"]
    if len({item["example_id"] for item in examples}) != len(examples):
        raise ValueError("写作范例编号重复")
    for item in examples:
        paper_id = item["paper_id"]
        if (paper_id in held_out or paper_id not in papers or item["move"] not in MOVES
                or not isinstance(item["pdf_page"], int) or item["pdf_page"] < 1
                or not item["section"] or not item["source_anchor"]
                or not item["before"] or not item["advance"] or not item["after"]
                or not item["style"] or not item["conditions"]):
            raise ValueError(f"范例缺少定位或论证标注，或来自留出集：{item['example_id']}")
    return index


def tokens(text: str) -> Counter:
    parts = re.findall(r"[\u3400-\u9fff]+|[a-z0-9]+", unicodedata.normalize("NFKC", text).lower())
    return Counter(t for part in parts for t in
                   ([part] if len(part) < 2 or part.isascii() else
                    [part[i:i + 2] for i in range(len(part) - 1)]))


def similarity(left: Counter, right: Counter) -> float:
    denominator = sqrt(sum(v * v for v in left.values()) * sum(v * v for v in right.values()))
    return sum(v * right[t] for t, v in left.items()) / denominator if denominator else 0.0


def select(index: dict, query: dict, mode: str = "function", limit: int = 2) -> list[dict]:
    if mode not in {"manual", "topic", "function"} or query["move"] not in MOVES or limit < 1:
        raise ValueError("范例检索参数无效")
    if mode == "manual":
        return []
    terms = tokens(query.get("topic", ""))
    candidates = []
    for item in index["examples"]:
        if mode == "function" and item["move"] != query["move"]:
            continue
        paper = index["papers"][item["paper_id"]]
        topic = similarity(terms, tokens(item["topic"]))
        if mode == "topic" and not topic:
            continue
        design = int(bool(query.get("design")) and query["design"] == paper["design"])
        journal = int(bool(query.get("journal")) and query["journal"] == paper["journal"])
        rank = (-topic,) if mode == "topic" else (-design, -journal, -topic)
        subtask = query.get("subtask")
        if mode == "function" and subtask:
            rank = (-int(subtask in item.get("subtasks", [])), *rank)
        candidates.append((rank, item["example_id"], item, paper, topic))
    selected, seen = [], set()
    for _, _, item, paper, topic in sorted(candidates, key=lambda candidate: candidate[:2]):
        if item["paper_id"] in seen:
            continue
        seen.add(item["paper_id"])
        selected.append({key: item[key] for key in (
            "example_id", "paper_id", "move", "section", "pdf_page", "before", "advance", "after",
            "style", "conditions"
        )} | {"journal": paper["journal"], "title": paper["title"], "topic_score": round(topic, 6)})
        if len(selected) == limit:
            break
    return selected


def writing_examples(binding: dict | None, root: Path) -> dict:
    if binding is None:
        return {"status": "unavailable", "reason": "本次绑定的G3资源未发布已验收的范例索引"}
    path = Path(binding["path"])
    path = (root / path).resolve()
    if not path.is_relative_to(root.resolve()) or sha256(path.read_bytes()).hexdigest() != binding["sha256"]:
        raise ValueError("写作范例索引已变化或超出项目目录")
    index = read_index(path)
    return {"status": "available", "index": binding,
            "tasks": {key: {"purpose": MOVES[key], "examples": select(index, query)}
                      for key, query in binding["queries"].items()}}
