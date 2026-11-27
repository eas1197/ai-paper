"""v3.2 topic candidate driven by the existing experimental run contract."""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CONTROL = ROOT / "00_项目控制"
sys.path[:0] = [str(CONTROL / version / "tools") for version in ("v007_第7版", "v006_第6版")]
import run_mode
import topic_run

TASKS = {
    "opportunity": ("S01–S02", "从可定位的社会现象出发。区分事实、政策意图与推测。先解释抽象概念及可能的关系，说明观测指标能支持到哪里。不预定数据、样本和模型。"),
    "question": ("S03", "从通过的概念化提出核心学术问题和有意义的具体情境。样本、变量、模型等在实证操作层单独记录，允许待定。允许描述、解释、理论及有独立价值的测量研究。"),
    "deepening": ("S04–S07", "检索并区分作者解释、证据、成立条件和自己的推断。反诘最强解释，允许补检与修正。说明新旧答案会改变哪项认识。仅改分组、范围、模型或测量的变化记作设计优化。独立审查学术价值、情境和可行性，再判断是否值得追加成本。"),
}


def check(stage, bundle, review):
    reasoning = bundle.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ValueError("Attach the stage's academic reasoning to the reviewed bundle")
    if stage == "deepening" and bundle.get("change_kind") not in {
        "academic", "design_only", "unresolved",
    }:
        raise ValueError("Classify the claimed change")
    if stage == "deepening" and review["verdict"] == "READY" and bundle["change_kind"] != "academic":
        raise ValueError("READY requires an academic change; record design-only changes without promotion")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("command", choices=("init", "prepare", "status", "record"))
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    work = run_mode.RUNS / args.run_id
    manifest = run_mode.verified_run(work)
    os.environ["AI_PAPER_DEV_RUN"] = str(work)
    marker = topic_run.run_path(args.run_id) / "topic_version.json"
    if args.command == "init":
        result = topic_run.initialize(args.run_id, {})
        topic_run.write_new(marker, {"topic_version": "3.2", "workload_sha256": manifest["workload_sha256"]})
    else:
        if topic_run.read(marker) != {"topic_version": "3.2", "workload_sha256": manifest["workload_sha256"]}:
            raise ValueError("This is not a v3.2 topic run")
        result = topic_run.status(args.run_id)
        stage = result["stage"]
        if args.command == "prepare":
            result = topic_run.prepare(ROOT, topic_run.read, result)
            result["stages"], result["instruction"] = TASKS[stage]
            result["abstract_target"] = manifest["workload"]["04"]["abstract_target"]
        elif args.command == "record":
            if len(args.paths) != 3:
                parser.error("Supply bundle, independent review and usage files")
            bundle, review, usage = map(topic_run.read, args.paths)
            check(stage, bundle, review)
            result = topic_run.record(args.run_id, bundle, review, usage)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
