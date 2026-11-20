"""对照原文定位，给现有第7步范例检索生成候选资源。"""
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / "02_文章结构学习/v005_第5版/outputs/两刊全篇分析_20261118_attempt001/work/阅读输入"
STRUCTURE = ROOT / "02_文章结构学习/v005_第5版/outputs/两刊全篇分析_20261119_attempt002"
STAGE07 = ROOT / "07_三稿独立写作/v011_第11版/tools"
sys.path.insert(0, str(STAGE07))
from exemplars07 import MOVES, read_index, select


DESIGNS = {
    "SCCKUUS9": "对数线性", "6V7LJIWN": "两期调查回归", "3G222LKC": "逻辑回归",
    "V3CA3AZW": "结构方程", "89UP6KH7": "多结局回归", "Y8WNZ3AN": "多层回归",
    "FQ7RQ5NC": "二元逻辑回归", "MK385948": "因素分析",
    "NU3YY8ZA": "倾向得分匹配", "HLMCFMEQ": "一阶差分", "39ERQM27": "分部门交互",
    "2SKTAPLF": "描述与多指标回归", "J38BV4A5": "多元线性回归", "J5XDE43I": "转换矩阵",
    "Y32DRMKW": "多结果回归", "ZVEEAGSX": "两期调查比较", "DD4I5QA4": "分组与交互回归",
    "GUQJU4JA": "家庭及个人分层分析", "IFYBIRP2": "多层回归", "NUR2L8DP": "职业流动模型",
}
SUBTASKS = {
    "E04": ["分项比较"], "E08": ["并列估计"], "E09": ["单位转译"],
    "E12": ["直接比较"], "E15": ["单项关联"], "E16": ["分项比较"],
    "E21": ["并列估计"], "E23": ["并列估计"],
    "E25": ["直接比较"], "E26": ["并列估计"], "E33": ["并列估计"],
}


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def canon(text):
    return re.sub(r"\s+", "", text)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lock(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}


def produce():
    path = HERE / "原文定位范例.tsv"
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file, delimiter="\t"))
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("范例ID重复或资料为空")
    examples, papers, source_locks = [], {}, {}
    for row in rows:
        key = row["key"]
        paper_id = "zotero_" + key
        item = SOURCE / (paper_id + ".json")
        raw = json.loads(item.read_text(encoding="utf-8"))
        page = int(row["page"])
        body = {p["pdf_page"]: p["body_text"] for p in raw["pages"]}
        if row["anchor"] not in canon(body[page]):
            raise ValueError(f"{row['id']} 短锚无法定位到原页")
        original = canon(row["original"])
        if any(original[i:i+12] in canon(body[page]) for i in range(len(original) - 11)):
            raise ValueError(f"{row['id']} 试写与来源页面过度重合")
        if paper_id not in papers:
            pdf = Path(raw["pdf_path"])
            if sha(pdf) != raw["pdf_sha256"]:
                raise ValueError(f"{paper_id} 原PDF哈希已变化")
            source_locks[paper_id] = {"path": item.relative_to(ROOT).as_posix(), "sha256": sha(item)}
            papers[paper_id] = {"title": raw["title"], "journal": raw["journal"], "design": DESIGNS[key],
                                "pdf": str(pdf), "pdf_sha256": raw["pdf_sha256"]}
        examples.append(
            {"example_id": row["id"], "paper_id": paper_id, "move": row["move"], "section": row["section"],
             "pdf_page": page, "source_anchor": row["anchor"], "before": row["before"],
             "advance": row["advance"], "after": row["after"],
             "style": row["style"] + " 原创示例：" + row["original"],
             "original_example": row["original"], "anti_pattern": row["counterexample"],
             "conditions": row["conditions"], "subtasks": SUBTASKS.get(row["id"], []),
             "topic": raw["title"], "annotation": "nearby_original_pages_reviewed"}
        )

    index_path = HERE / "writing_exemplars.json"
    write(index_path, {"schema_version": 1, "status": "pilot", "papers": papers,
                       "held_out_paper_ids": [], "examples": examples})
    index = read_index(index_path, pilot=True)
    counts = Counter(x["move"] for x in examples)
    if counts.keys() != MOVES.keys() or min(counts.values()) < 2:
        raise ValueError("段落任务范例覆盖不足")

    type_samples = {
        "question": ("学校选择与入学差异", "", ""),
        "literature": ("家庭资源与儿童学校选择", "", ""),
        "hypothesis": ("家庭照料与相邻居住", "", "分项比较"),
        "design": ("学生与学校的嵌套关系", "多层回归", ""),
        "results": ("儿童学业成就的城乡差异", "结构方程", "并列估计"),
        "discussion": ("大学生学业与校园活动", "多结局回归", ""),
    }
    checked = {}
    for move, (topic, design, subtask) in type_samples.items():
        query = {"topic": topic, "design": design, "move": move, "subtask": subtask}
        selected = select(index, query)
        if (len(selected) != 2 or any(row["move"] != move or "原创示例：" not in row["style"] for row in selected)
                or any("source_anchor" in row for row in selected)):
            raise ValueError(f"现行写作模块返回错误: {move}")
        checked[move] = {"purpose": MOVES[move], "query": query, "examples": selected}
    expected_top = {"design": "E18", "results": "E08", "discussion": "E10"}
    for move, example_id in expected_top.items():
        if checked[move]["examples"][0]["example_id"] != example_id:
            raise ValueError(f"{move} 未优先返回预期的同设计或同功能范例")
    try:
        read_index(index_path)
    except ValueError:
        pass
    else:
        raise ValueError("试用索引不能进入正式入口")
    write(HERE / "第7步范例调用试跑.json", {
        "mode": "pilot", "source_index": lock(index_path), "router": lock(STAGE07/"exemplars07.py"),
        "tasks": checked,
    })
    write(HERE / "范例核验.json", {"checked_at": "2026-11-19", "readable_index": True,
                                 "formal_gate": "needs_review", "original_pdf_hashes": len(papers),
                                 "original_anchors": len(examples), "counts": counts, "sources": source_locks,
                                 "authored_source": {"path": path.name, "sha256": sha(path)},
                                 "router_trials": len(checked), "preferred_example_first": expected_top,
                                 "formal_entry_rejects_pilot": True})

    lines = ["# 两刊定量写作语言范例", "", "以下各项依据所列原文位置。试写和反例为项目原创，均用于演示表达。", ""]
    for kind, label in MOVES.items():
        lines.extend([f"## {label}", ""])
        for ex in (example for example in examples if example["move"] == kind):
            paper = papers[ex["paper_id"]]
            pdf = Path(paper["pdf"]).as_posix()
            lines.extend([
                f"### {ex['example_id']} {ex['style'].split(' 原创示例：', 1)[0]}", "",
                f"{ex['before']}{ex['advance']}{ex['after']}", "",
                f"- 可以用在　{ex['conditions']}",
                f"- 原创示例　{ex['original_example']}",
                f"- 反例　{ex['anti_pattern']}",
                f"- 原文　{paper['journal']}，{ex['section']}，PDF第{ex['pdf_page']}页。[《{paper['title']}》](<{pdf}>)",
                "",
            ])
    (HERE / "语言范例手册.md").write_text("\n".join(lines), encoding="utf-8")
    write(HERE / "第7步候选绑定.json", {
        "schema_version": 1, "status": "pilot", "use": "stage07_exemplar_pilot",
        "created_at": "2026-11-19", "source_module_versions": {"02": 5, "03": 5, "07": 11},
        "index": lock(index_path), "router": lock(STAGE07 / "exemplars07.py"),
        "files": [lock(STRUCTURE / "结构手册.md"), lock(STRUCTURE / "覆盖与验收.json"),
                  lock(HERE / "语言范例手册.md"), lock(HERE / "范例核验.json"), lock(HERE / "第7步范例调用试跑.json"),
                  lock(HERE / "第7步使用说明.md"), lock(HERE / "build_examples.py")],
    })
    print(f"{len(examples)}条范例、{len(papers)}篇原文、{len(checked)}项召回试跑")


if __name__ == "__main__":
    produce()
