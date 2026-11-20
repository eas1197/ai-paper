"""Offline three-condition writing trial with controlled evidence and blinded codes."""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

from build_pilot_index import MODULE as CORPUS, ROOT, compact, lock, read, write
from exemplars07 import read_index, select

MODULE = Path(__file__).resolve().parents[1]
OUT = MODULE / "outputs/论证范例试验_20261118_attempt001"
INDEX = ROOT / "03_学术语言学习/v004_第4版/outputs" / CORPUS / "writing_exemplars.json"
RESEARCH = ROOT / "00_项目控制/v002_第2版/runs/cgss23_digital_ties_20261118"
PLAN = RESEARCH / "分析前方案.md"
RESULTS = RESEARCH / "exploratory_analysis/results.csv"
GUIDES = [
    ROOT / "02_文章结构学习/v005_第5版/assets/写作架构/定量社会学论文写作架构.md",
    ROOT / "03_学术语言学习/v004_第4版/outputs/语言风格学习.md",
    MODULE / "templates/文字要求.md",
]
SEED = 20261118
MODES = ("manual", "topic", "function")
TASKS = {
    "question": {
        "title": "引言收束",
        "instruction": "写一个约120—190字的引言末段。承接老年人的线上使用与线下往来，收束到一个可回答的问题。可引用所给文献。",
        "facts": [
            "Tang等（2022，DOI 10.3389/fpsyg.2022.895141）区分朋友网络和家庭网络；原研究的网络指标与本研究的实际聚会不同。",
            "本项探索用CGSS 2023入户调查老年受访者，同一受访者在同一题组报告与朋友以及与非同住亲属的聚会频率。",
            "比较频繁上网者与其他受访者在两类聚会上达到同一频率阈值的概率差，进一步比较两个关联的大小。",
        ],
        "query": {"move": "question", "design": "cross_section",
                  "topic": "老年人 互联网 上网 社会网络 朋友关系 家庭亲属 线下聚会 社会联系 CGSS"},
    },
    "hypothesis": {
        "title": "假设推导",
        "instruction": "写一个约120—190字的理论段，将两项事前预期连到可观察的比较。理论渠道只作为预期，不写成已观察到的事实。",
        "facts": [
            "朋友见面通常需要在日常生活圈外联系和协调；非同住亲属的见面还可能由较稳定的家庭责任或安排维系。这两条是本题的理论预期。",
            "问卷测量一般上网频率与两类线下聚会，未测这次上网具体拿来做什么。",
            "H1：频繁上网与朋友聚会达到阈值正相关。H2：该关联的概率差大于与非同住亲属聚会的关联概率差。",
        ],
        "query": {"move": "hypothesis", "design": "cross_section", "subtask": "分项比较",
                  "topic": "老年人 互联网 上网 社会网络 朋友关系 家庭亲属 线下聚会 社会联系 CGSS"},
    },
    "results": {
        "title": "主结果首段",
        "instruction": "写一个约120—190字的结果首段。报告调整条件、两项估计与直接差值及其95%区间。用关联措辞。",
        "facts": [
            "使用同一批CGSS 2023入户完整案例。省固定效应模型还调整年龄及平方、性别、教育及居委/村委社区。",
            "比较经常或非常频繁上网与其余有效受访者，两项聚会均以每月数次及以上为阈值。",
        ],
        "query": {"move": "results", "design": "cross_section", "subtask": "直接比较",
                  "topic": "老年人 互联网 上网 社会网络 朋友关系 家庭亲属 线下聚会 社会联系 CGSS"},
    },
}
RESULT_IDS = {f"M2_{outcome}_internet_high" for outcome in ("friend", "kin", "difference")}


def prepare():
    index = read_index(INDEX, pilot=True)
    with RESULTS.open(encoding="utf-8-sig", newline="") as stream:
        estimates = {row["outcome"]: row for row in csv.DictReader(stream) if row["result_id"] in RESULT_IDS}
    if len(estimates) != 3 or len({(r["n"], r["clusters"]) for r in estimates.values()}) != 1:
        raise ValueError("实证比较缺少同样本结果")
    estimates = {name: {**{f: f"{100 * float(row[f]):.2f}" for f in ("estimate", "ci_low", "ci_high")},
                        "result_id": row["result_id"]} for name, row in estimates.items()}
    rng = random.Random(SEED)
    prompts, keys = {}, {}
    for task_id, task in TASKS.items():
        positions = list(MODES)
        rng.shuffle(positions)
        for i, mode in enumerate(positions, 1):
            code = f"{task_id.upper()}-{i}"
            keys[code] = {"task": task_id, "condition": mode}
            facts = list(task["facts"])
            if task_id == "results":
                facts.extend(f"{name} {r['estimate']}个百分点（95%区间 {r['ci_low']}—{r['ci_high']}），{r['result_id']}"
                             for name, r in estimates.items())
            prompts[code] = {
                "task": task["title"], "instruction": task["instruction"], "evidence": facts,
                "guide": "用具体对象、比较与证据推进，逐段围绕一个判断，讲清即收束，陈述强度贴合研究设计。",
                "examples": select(index, task["query"], mode),
                "usage": "示例只提供论证组织和语言处理。仅使用当前证据中的研究事实。输出单段正文。",
            }
    packet = {"schema_version": 1, "scope": "exploratory_writing_pilot", "seed": SEED,
              "inputs": [lock(p) for p in [*GUIDES, PLAN, RESULTS, INDEX, Path(__file__),
                                           MODULE / "tools/exemplars07.py"]],
              "writer": "当前Codex会话，同一模型", "exact_model_id": None,
              "tasks": prompts, "results": estimates}
    for name, data in (("同证据写作任务.json", packet), ("盲评揭盲键.json", keys)):
        path = OUT / name
        if path.exists():
            if read(path) != data:
                raise ValueError(f"冻结输入已变化，请新开试验attempt：{path.name}")
        else:
            write(path, data)
    return packet, keys


def review():
    packet, keys = prepare()
    drafts_path = OUT / "段落实写.json"
    drafts = read(drafts_path)
    if set(drafts) != set(keys) or len({compact(s) for s in drafts.values()}) != len(keys):
        raise ValueError("每个写作任务须有一段不同的正文")
    index = read_index(INDEX, pilot=True)
    passages = {}
    split = read(ROOT / index["split"]["path"])
    from build_pilot_index import PREVIOUS
    for source in split["train"]:
        key = source["paper_id"].removeprefix("zotero_")
        for page in read(PREVIOUS / "fulltext" / key / "pages.json"):
            passages[key, page["pdf_page"]] = compact(page["text"])
    evidence = []
    score_lines = []
    for code, excerpt in drafts.items():
        meta = keys[code]
        body = compact(excerpt)
        grams = {body[i:i + 14] for i in range(max(0, len(body) - 13))}
        long_matches = sorted({fragment for fragment in grams if any(fragment in text for text in passages.values())})
        if meta["task"] == "results":
            needed = {v for fields in packet["results"].values() for k, v in fields.items() if k != "result_id"}
            numbers = set(re.findall(r"[-−]?\d+\.\d+", excerpt.replace("−", "-")))
            errors = sorted(needed - numbers)
            extra = sorted(numbers - needed)
        else:
            errors, extra = [], sorted(set(re.findall(r"\d+(?:\.\d+)?", excerpt)) - {"2022", "2023"})
        score_lines.append({"code": code, "condition": meta["condition"], "task": meta["task"],
                            "characters": len(body), "missing_required_numbers": errors,
                            "unexpected_numbers": extra, "source_14_character_matches": long_matches})
    for task_id, task in TASKS.items():
        evidence.extend([f"## {task['title']}", "", task["instruction"], ""])
        evidence.extend(f"- {fact}" for fact in task["facts"])
        if task_id == "results":
            results = packet["results"]
            evidence.extend(f"- {name} {r['estimate']}个百分点，95%区间 {r['ci_low']}—{r['ci_high']}。"
                            for name, r in results.items())
        evidence.append("")
        for code in sorted(key for key in keys if keys[key]["task"] == task_id):
            evidence += [f"### {code}", "", drafts[code], ""]
    heading = [
        "# 写作段落盲评", "",
        "本页供独立读者比较，编号顺序已随机打乱。各题独立打分，每项0—2分。",
        "依次看任务是否完成、句间是否推进、期刊式表达是否自然、事实和推断是否贴合材料。"
        "0分表示缺失或有实质错误，1分表示已覆盖但松散或不完整，2分表示具体、连贯或准确。",
        "示例三种输入条件对应的编号另存，先评本页再看揭盲键。", "",
    ]
    report = {"schema_version": 1, "scope": "automated_text_and_number_checks",
              "inputs": [lock(drafts_path), lock(OUT / "同证据写作任务.json"), lock(Path(__file__))], "checks": score_lines}
    if any(r["missing_required_numbers"] or r["unexpected_numbers"] or r["source_14_character_matches"] for r in score_lines):
        report["status"] = "needs_review"
    else:
        report["status"] = "passed"
    packet_text = "\n".join([*heading, *evidence])
    report_path = OUT / "自动核对.json"
    packet_path = OUT / "盲评材料.md"
    if report_path.exists() or packet_path.exists():
        if read(report_path) != report or packet_path.read_text(encoding="utf-8") != packet_text:
            raise ValueError("现存核对产物与重新计算不同")
    else:
        write(report_path, report)
        packet_path.write_text(packet_text, encoding="utf-8")
    return {"status": report["status"], "paragraphs": len(drafts), "checks": score_lines}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "review"))
    args = parser.parse_args()
    if args.command == "prepare":
        packet, _ = prepare()
        result = packet["tasks"]
    else:
        result = review()
    print(json.dumps(result, ensure_ascii=False, indent=2))
