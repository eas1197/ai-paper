"""Prepare stage inputs from the existing project registry and research resources."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


CONTROL = "00_项目控制/v005_第5版"
MODEL_TASKS = {
    "opportunity": "从理论、现实、文献找范围不同的社会现象。逐一定位原始来源，写出社会过程和后续疑问。已有主题时保持在其范围内。",
    "question": "只从通过审查的机会提问。参考选题卡的构造办法，明确人群、并列比较、核心概念以及不同答案的用途。",
    "deepening": "围绕通过的问题查找最相近的文献。把作者主张、机制、实际支持、范围和推论分开。只对有据可查的缺口提出下一问。",
}


def existing_module(root, read, module_id):
    records = read(root / CONTROL / "module_registry.json")["modules"]
    return root / next(row["path"] for row in records if row["module_id"] == module_id)


def prepare(root, read, state, context_sources=()):
    stage = state["stage"]
    if stage not in MODEL_TASKS:
        raise ValueError(f"No exploratory work at {stage}")
    theme = state["config"]["theme"]
    stage04 = existing_module(root, read, "04")
    stage05 = existing_module(root, read, "05")
    stage11 = existing_module(root, read, "11")
    task = {"run_id": state["config"]["run_id"], "stage": stage, "theme": theme,
            "instruction": MODEL_TASKS[stage], "approved_ids": state.get("approved_ids", []),
            "sources": {"stage04": str(stage04 / "tools/research.py"), "stage11": str(stage11),
                        "question_skill": str(stage05 / "skills/social-science-topic-selection/SKILL.md")}}
    if state["last_round"]:
        last = read(state["last_round"])
        task["previous_review"] = last["review"]
        task["previous_round"] = state["last_round"]

    known = set()
    task["reality_sources"] = []
    for source_index in context_sources:
        source_index = Path(source_index).resolve()
        if not source_index.is_relative_to(root):
            raise ValueError("Context source index is outside the project")
        for item in read(source_index):
            path = Path(item["snapshot_path"]).resolve()
            digest = item["snapshot_sha256"]
            if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Unverified context archive: {item['context_id']}")
            if digest not in known:
                task["reality_sources"].append({"source_id": item["context_id"], "path": str(path), "sha256": digest,
                                                "url": item["primary_url"], "title": item.get("title"),
                                                "retrieved_at": item.get("retrieved_at"), "status": "requires_reading"})
                known.add(digest)
    if stage == "question":
        query = theme or " ".join(row["social_process"] for row in last["bundle"]["opportunities"]
                                  if row["opportunity_id"] in task["approved_ids"])
        task["question_cards"] = []
        if query:
            proc = subprocess.run([sys.executable, "-B", str(stage05 / "tools/topic_cards.py"), "retrieve", "--theme", query],
                                  cwd=root, capture_output=True, encoding="utf-8", timeout=30, check=True)
            task["question_cards"] = json.loads(proc.stdout)
    return task
