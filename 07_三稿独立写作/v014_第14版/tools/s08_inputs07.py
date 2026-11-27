"""Offline intake of a historical S08 and the analysis it authorizes."""
import re
import sys
from pathlib import Path

from runtime import ROOT, file_lock, inside, load, sha, value_hash, verify_locks

CONTROL = ROOT / "00_项目控制"
METHOD06 = ROOT / "06_数据方法与分析/v005_第5版"
CONFIG = CONTROL / "v005_第5版/project_config.json"
sys.path.extend([str(CONTROL / "v009_第9版/tools"), str(METHOD06 / "tools")])
import staged_topic
import qual_materials
from framework import analysis_matrix
from method_paths import select_method, verify_material_review


def frozen_source(directory):
    run = Path(directory).resolve()
    names = ("s08_topic.json", "staged_topic.json", "merged_literature.json", "initial/theories.json",
             "reality.json", "event_comparison.json", "explanation_exchange.json", "issue_plan.json")
    freeze, state, literature, theories = (load(inside(run, name)) for name in names[:4])
    final = state["history"][-1]
    method = select_method(final["method_assessment"], final["outcome"])
    evidence_hash = staged_topic.evidence_hash(run, state, inside(run, names[2]), inside(run, names[3]))
    if (state["run_id"] != run.name or state["status"] != "frozen" or freeze.get("stage") != "S08"
            or freeze["mode"] != state["mode"] or freeze.get("formal_eligible") is not False
            or freeze.get("scope") != {"dev": "experimental", "formal": "formal_candidate"}[state["mode"]]
            or final["outcome"] != "pass" or final["academic_value"] != "pass"
            or final["data_feasibility"] != "pass" or final["model"] != "gpt-6.2-sol"
            or not final["invocation_id"] or final["invocation_id"] in
            {review["invocation_id"] for review in state["history"][:-1]}
            or freeze["evidence_sha256"] != final["evidence_sha256"] or evidence_hash != freeze["evidence_sha256"]
            or freeze["review_sha256"] != staged_topic.digest(final)
            or any(freeze[key] != final[key] for key in ("question", "design", "research_case"))
            or freeze["question"] != state["question"] or method != freeze["research_method"]
            or method != state["research_method"]):
        raise ValueError("S08、终审或原始证据绑定不一致")
    locks = [file_lock(inside(run, name)) for name in names if inside(run, name).is_file()]
    if method["path"] != "quantitative":
        decision = final["method_assessment"]["paths"][method["path"]]
        verify_material_review(run, method["path"], decision, freeze["question"])
        preliminary = inside(run, Path("qualitative") / decision["search_attempt"])
        locks.extend(file_lock(inside(preliminary, name)) for name in
                     ("conversion.json", "material_receipt.json", "events.jsonl", "response.json"))
        budget_file = inside(run, "run_manifest.json")
        budget = load(budget_file)["workload"]["11"]["native_search_actions"]
        receipt = load(inside(preliminary, "material_receipt.json"))
        replay = qual_materials.read_materials(preliminary, budget)
        if any(receipt[key] != value for key, value in replay.items()):
            raise ValueError("原 06 初步材料与原生检索记录不一致")
        locks.append(file_lock(budget_file))
    if verify_locks(locks):
        raise ValueError("读取期间 S08 证据发生变化")
    return run, freeze, final, literature, theories, locks


def main_language():
    config = load(CONFIG)
    writing = config["writing"]
    profile_path = inside(ROOT, writing["language_style"]["profile_path"])
    profile = load(profile_path)
    resource = inside(ROOT, config["shared_resources"]["resource_manifests"]["03"])
    snapshot = load(resource)
    registered = {inside(ROOT, row["path"]): row["sha256"] for row in snapshot["files"]}
    resources = {"profile": {"path": str(profile_path), "sha256": writing["language_style"]["profile_sha256"]},
                 **{name: profile[name] for name in ("guide", "examples", "application")}}
    locks = [file_lock(resource), file_lock(CONFIG)]
    for item in resources.values():
        path = inside(ROOT, item["path"])
        if sha(path) != item["sha256"] or registered.get(path) != item["sha256"]:
            raise ValueError(f"main 语言资源哈希校验失败：{path.name}")
        locks.append(file_lock(path))
    return {"profile_id": profile["profile_id"], "resources": resources, "style_ids": profile["style_ids"],
            "snapshot_status": snapshot["status"]}, locks


def qualitative(source, attempt):
    run, freeze, final, literature, theories, locks = source
    if freeze["scope"] != "experimental":
        raise ValueError("当前定性入口仅支持实验运行")
    if not re.fullmatch(r"attempt_[0-9]{3}", attempt):
        raise ValueError("分析批次必须为 attempt_NNN")
    method = freeze["research_method"]["path"]
    decision = final["method_assessment"]["paths"][method]
    preliminary = load(inside(run, f"qualitative/{decision['search_attempt']}/material_receipt.json"))
    conversion = load(inside(run, f"qualitative/{decision['search_attempt']}/conversion.json"))
    folder = inside(run, f"qualitative_framework/{attempt}")
    required = ("framework.json", "conversion.json", "material_receipt.json", "events.jsonl",
                "response.json", "analysis_matrix.json", "matrix_review.json")
    files = {name: inside(folder, name) for name in required}
    missing = [name for name, path in files.items() if not path.is_file()]
    base = {"run_id": run.name, "method": method, "scope": freeze["scope"], "formal_eligible": False,
            "material_count": len(preliminary["materials"]), "analysis_directory": str(folder)}
    if missing:
        return dict(base, status="needs_review", missing=missing), None
    framework, directed_conversion, receipt, matrix, review = (
        load(files[name]) for name in ("framework.json", "conversion.json", "material_receipt.json",
                                       "analysis_matrix.json", "matrix_review.json"))
    budget = load(inside(run, "run_manifest.json"))["workload"]["11"]["native_search_actions"]
    replay = qual_materials.read_materials(folder, budget)
    if (directed_conversion != conversion or framework["core_question"] != conversion["core_question"]
            or receipt["run_id"] != run.name or receipt["conversion_sha256"] != staged_topic.digest(conversion)
            or receipt["preliminary_sha256"] != staged_topic.digest(preliminary)
            or receipt.get("formal_eligible") is not False
            or any(receipt[key] != value for key, value in replay.items())
            or matrix != analysis_matrix(framework, receipt, matrix["rows"])):
        raise ValueError("原 06 矩阵、框架或采集凭证不一致")
    findings = [row for row in matrix["rows"] if row["status"] == "tentative"
                and any(ref["relation"] != "context" for ref in row["evidence"])]
    if not findings:
        raise ValueError("矩阵缺少可定位经验材料支持的主要发现")
    if (review["decision"] != "pass" or review["reviewer"] != "gpt-6.2-sol"
            or not review["invocation_id"] or review["invocation_id"] in
            {row["invocation_id"] for row in load(run / "staged_topic.json")["history"]}
            or review["matrix_sha256"] != sha(files["analysis_matrix.json"])
            or not review["reason"].strip()):
        raise ValueError("矩阵缺少独立通过记录或记录未绑定当前矩阵")
    language, language_locks = main_language()
    writing_policy = load(inside(run, "run_manifest.json")).get("workload", {}).get("07", {})
    requirements = Path(__file__).resolve().parents[1] / "templates/文字要求.md"
    language_locks.append(file_lock(requirements))
    task = dict(base, research_question=freeze["question"], design=freeze["design"],
                research_case=freeze["research_case"], language_style=language, matrix=matrix,
                framework=framework, writing_requirements=requirements.read_text(encoding="utf-8-sig"),
                writing_budget=writing_policy,
                findings=findings, materials=receipt["materials"], matrix_review=review,
                prior_invocations=[r["invocation_id"] for r in load(run / "staged_topic.json")["history"]],
                literature=literature, theories=theories,
                front_matter={"title": "明确研究对象与核心关系", "abstract": "问题、资料方法、发现和理论意义与正文一致", "keywords": "4—6个"},
                sections=[
                    {"section": "问题的提出", "task": "从真实事件与问题出发，明确研究对象和核心问题。"},
                    {"section": "文献回顾", "task": "比较近邻研究解释、差异和未回答的问题，区分摘要与全文证据。"},
                    {"section": "理论分析框架", "task": "使用冻结框架，说明核心概念、维度推演与命题，区分理论主张和经验发现。"},
                    {"section": "资料与方法", "task": "说明文本选取、比较单位、编码维度、来源和访问边界。"},
                    {"section": "经验发现", "task": "按矩阵维度展开比较。每项主张引用材料 ID 并保留定位，呈现反例和其他解释。"},
                    {"section": "讨论与结论", "task": "回应命题，说明适用边界、未解决问题和替代解释。区分规则文本与实际行为。"},
                ],
                end_matter={"references": "仅列正文实际使用且可核验的来源", "appendix": "材料定位、编码与主张证据台账"},
                input_files=locks + language_locks + [file_lock(path) for path in files.values()]
                + [file_lock(Path(__file__)),
                   file_lock(Path(__file__).with_name("qualitative07.py")),
                   file_lock(Path(__file__).with_name("stage07.py"))])
    if verify_locks(task["input_files"]):
        raise ValueError("准备期间定性写作输入发生变化")
    return dict(base, status="ready", pack_id=value_hash(task)), task
