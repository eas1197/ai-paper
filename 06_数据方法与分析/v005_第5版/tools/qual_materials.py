"""Bounded discovery of qualitative materials using the existing Codex native CLI."""

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "04_议题文献与现实/v012_第12版/tools"),
                str(ROOT / "00_项目控制/v007_第7版/tools"),
                str(ROOT / "00_项目控制/v009_第9版/tools")]
from method_paths import select_method, verify_material_review
from native_library import registry
from run_mode import verified_run

registry()
from codex_literature import cli_executable, evidence, invoke, url_event
from collect_common import digest, load, sha, write
from abstract_acquisition import job_lock
from framework import analysis_matrix, validate_framework

KINDS = {"actor_statement", "reporter_account", "official_rule", "documented_action", "researcher_inference"}
PATHS = {"secondary_interviews", "online_qualitative"}
FIELDS = ("url", "date", "subject", "context", "kind", "path", "locator", "relation", "limits", "access")


def schema():
    item = {"type": "object", "required": list(FIELDS), "additionalProperties": False,
            "properties": {key: {"type": "string"} for key in FIELDS}}
    item["properties"]["kind"]["enum"] = sorted(KINDS - {"researcher_inference"})
    item["properties"]["path"]["enum"] = sorted(PATHS)
    return {"type": "object", "required": ["materials", "search_notes", "gaps"],
            "additionalProperties": False, "properties": {
                "materials": {"type": "array", "items": item},
                "search_notes": {"type": "array", "items": {"type": "string"}},
                "gaps": {"type": "array", "items": {"type": "string"}},
            }}


def validate_conversion(packet):
    keys = ("core_question", "prior_question", "new_question", "theoretical_concern",
            "reason_for_conversion", "framework", "literature", "context")
    if any(not isinstance(packet.get(key), str) or not packet[key].strip() for key in keys):
        raise ValueError("Record continuity of the question, theory, framework and prior literature")
    if packet["prior_question"].strip() == packet["new_question"].strip():
        raise ValueError("State the method-specific qualitative question")


def read_materials(folder, budget):
    events = folder / "events.jsonl"
    trace = evidence(events)
    if not trace or len(trace) > budget:
        raise ValueError("Missing native search receipts or event budget exceeded")
    result = load(folder / "response.json")
    candidates, excluded = [], []
    for row in result["materials"]:
        event = url_event(row["url"], trace)
        if (not event or row.get("kind") not in KINDS - {"researcher_inference"}
                or row.get("path") not in PATHS
                or any(not row.get(key, "").strip() for key in FIELDS)):
            excluded.append({"url": row.get("url"), "reason": "receipt or context incomplete"})
            continue
        candidates.append(dict(row, event_id=event, material_id=digest(row)[:16]))
    return {"status": "pending_independent_review", "events_sha256": sha(events),
            "response_sha256": sha(folder / "response.json"), "tool_events": len(trace),
            "materials": candidates, "excluded": excluded, "notes": result["search_notes"], "gaps": result["gaps"]}


def record_review(work, folder, report):
    packet = load(folder / "conversion.json")
    if (report.get("model") != "gpt-6.2-sol" or not report.get("invocation_id")
            or not report.get("reason") or report.get("conversion_sha256") != digest(packet)
            or report.get("academic_value") != "pass"):
        raise ValueError("An independent review must bind and support the converted question")
    outcome = report["outcome"]
    if outcome not in {"pass", "missing_data", "materials_pending"}:
        raise ValueError("Record academic revisions in S07")
    assessment = report["method_assessment"]
    path = select_method(assessment, outcome)
    question = report.get("reviewed_question", packet["new_question"])
    if outcome == "pass" and (not path or path["path"] not in PATHS or not question.strip()
                              or not report.get("review_scope")):
        raise ValueError("A qualitative approval must state its reviewed question and inference scope")
    for name in sorted(PATHS):
        decision = assessment["paths"][name]
        if decision["status"] in {"ready", "missing"} and decision.get("search_attempt") != folder.name:
            raise ValueError("Companion review must match this attempt")
        verify_material_review(work, name, decision, question if decision["status"] == "ready"
                               else packet["new_question"])
    status = {"pass": "qualitative_design_ready", "missing_data": "materials_insufficient",
              "materials_pending": "materials_pending"}[outcome]
    output = folder / "review.json"
    if output.exists():
        raise FileExistsError("Keep the recorded independent review")
    write(output, {**report, "status": status, "selected_method": path, "core_question": packet["core_question"],
                   "formal_eligible": False})
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-run", type=Path, required=True)
    parser.add_argument("--attempt", required=True)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--conversion", type=Path)
    operation.add_argument("--review", type=Path)
    operation.add_argument("--matrix", type=Path)
    parser.add_argument("--framework", type=Path)
    parser.add_argument("--event-focus", action="store_true")
    parser.add_argument("--preliminary-attempt", default="attempt_001")
    parser.add_argument("--framework-revision", type=Path,
                        help="Build a revised matrix from existing material; supply framework and reason")
    args = parser.parse_args()
    if (args.framework and not args.conversion) or (args.framework_revision and not args.matrix):
        parser.error("Framework collection requires --conversion; revision requires --matrix")
    manifest = verified_run(args.dev_run)
    if not all(re.fullmatch(r"attempt_[0-9]{3}", value)
               for value in (args.attempt, args.preliminary_attempt)):
        parser.error("Use a numbered qualitative search attempt")
    area = args.dev_run / ("qualitative_framework" if args.framework or args.matrix else "qualitative")
    folder = area / args.attempt
    if args.matrix:
        framework = load(folder / "framework.json")
        receipt = load(folder / "material_receipt.json")
        if (sha(folder / "events.jsonl") != receipt["events_sha256"]
                or sha(folder / "response.json") != receipt["response_sha256"]):
            raise ValueError("Original collection receipts changed")
        suffix = ""
        if args.framework_revision:
            if len(list(folder.glob("analysis_matrix_*.json"))) >= 2:
                raise ValueError("Framework revision limit reached")
            revision = load(args.framework_revision)
            revised = revision["framework"]
            if (revision.get("prior_framework_sha256") != receipt["framework_sha256"]
                    or not isinstance(revision.get("reason"), str) or not revision["reason"].strip()
                    or revised.get("core_question") != framework["core_question"]):
                raise ValueError("Bind the revision to the source framework and explain the material-led change")
            suffix = f"_{digest(revised)[:12]}"
            result = analysis_matrix(revised, dict(receipt, framework_sha256=digest(revised)), load(args.matrix))
            result.update(prior_framework_sha256=digest(framework), revision_reason=revision["reason"],
                          collection_sha256=digest(receipt))
        else:
            result = analysis_matrix(framework, receipt, load(args.matrix))
        out = folder / f"analysis_matrix{suffix}.json"
        if out.exists():
            raise FileExistsError("Preserve the existing matrix")
        if args.framework_revision:
            write(folder / f"framework{suffix}.json", revised)
        write(out, result)
        print(out)
        return
    if args.review:
        with job_lock(area):
            print(record_review(args.dev_run, folder, load(args.review)))
        return
    packet = load(args.conversion)
    validate_conversion(packet)
    framework = load(args.framework) if args.framework else None
    if framework:
        validate_framework(framework)
        first = args.dev_run / "qualitative" / args.preliminary_attempt
        initial = load(first / "material_receipt.json")
        if (initial.get("status") != "pending_independent_review"
                or sha(first / "events.jsonl") != initial.get("events_sha256")
                or sha(first / "response.json") != initial.get("response_sha256")
                or not initial.get("tool_events") or not initial.get("materials")
                or initial.get("run_id") != manifest["run_id"]
                or initial.get("conversion_sha256") != digest(packet)
                or framework["core_question"] != packet["core_question"]):
            raise ValueError("Framework collection requires an actual preliminary search for the same question")
    area.mkdir(exist_ok=True)
    budget = manifest["workload"]["11"]
    with job_lock(area):
        # An interrupted login before any CLI search does not consume a real search batch.
        used = sum(not (existing / "login_status.json").is_file()
                   or load(existing / "login_status.json").get("chatgpt") is not False
                   or (existing / "events.jsonl").exists()
                   for existing in area.glob("attempt_[0-9][0-9][0-9]") if existing.is_dir())
        if used >= budget["max_batches"]:
            raise ValueError("Experimental qualitative search batch budget exhausted")
        folder.mkdir(exist_ok=False)
    write(folder / "conversion.json", packet)
    if framework:
        write(folder / "framework.json", framework)
    write(folder / "response.schema.json", schema())
    prompt = (
        "只使用原生实时网页搜索和打开，不用命令、文件、账户登录或爬虫。"
        f"核心问题：{packet['core_question']}。定性问题：{packet['new_question']}。"
        f"场域：{packet['context']}。最多 {budget['native_search_actions']} 次工具动作。"
        "分别检索公开深度报道与二手访谈、公开网络互动及可核验的制度和事件资料。"
        "优先查行动过程并找反例，记录访问边界。报道中的行动者陈述、记者转述、规则和实际行为分开。"
        "仅概述公开内容，不提供个人姓名、账号或可识别未成年人的信息；不抄写原文。"
        "不把规则或研究者推测当行为。说明不符合预期、来源差异和缺失。"
        "输出最多八条材料，区分可公开阅览和研究用途许可尚待核实。记录两路径的搜索词、"
        "核过的来源及失败，不将网页阅读称作民族志。"
    )
    if framework:
        needs = [f"{item['name']}：{item['needed_material']}" for item in framework["dimensions"]]
        prompt += (f"本轮是框架形成后的定向材料收集。核心概念：{framework['core_concept']}。"
                   f"各维度所需材料：{'；'.join(needs)}。优先找反例与竞争机制，不限于初查材料。")
    if args.event_focus:
        prompt += ("优先在豆瓣、小红书、知乎、百度贴吧、小黑盒和微博寻找公开亲历事件，"
                   "按主题选择平台，在检索备注中写下实际查询、命中和访问失败。逐项区分自述、证实事实、"
                   "矛盾和推断；记录互动、决策、理由及结果，缺失写明。同一事件的转述合并。"
                   "官方材料只核实背景，除非研究问题本身针对制度设计。")
    try:
        code = invoke(cli_executable(), folder, prompt, folder / "response.schema.json",
                      timeout=budget["timeout_seconds"])
        if code:
            raise RuntimeError(f"Codex CLI returned {code}")
        result = read_materials(folder, budget["native_search_actions"])
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        write(folder / "material_receipt.json", {"status": "search_incomplete", "reason": str(exc)})
        raise
    result.update(run_id=manifest["run_id"], conversion_sha256=digest(packet),
                  formal_eligible=False, material_kind="qualitative_empirical")
    if framework:
        result.update(phase="framework_collection", framework_sha256=digest(framework),
                      preliminary_sha256=digest(initial))
    write(folder / "material_receipt.json", result)
    print(len(result["materials"]))


if __name__ == "__main__":
    main()
