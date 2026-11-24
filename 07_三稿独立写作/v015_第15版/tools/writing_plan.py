"""Build a method-aware writing plan from reviewed tasks and traceable sources."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "00_项目控制/v007_第7版/tools"))
from run_mode import digest, load, verified_run, write, writing_policy
sys.path.insert(0, str(ROOT / "00_项目控制/v009_第9版/tools"))
from question_binding import binding

QUALITATIVE = {"secondary_interviews", "online_qualitative"}
QUALITATIVE_FIXED = {
    "problem": "问题的提出",
    "framework": "文献综述与分析框架",
    "case": "案例介绍",
    "conclusion": "结论与讨论",
}
FRAMEWORK_FIELDS = {
    "prior_explanation": "已有文献及解释",
    "gap": "已有解释的不足",
    "theory_choice": "适用理论及选择理由",
    "deduction": "结合问题的理论推演",
    "increment": "相对已有解释的增量",
    "integration": "维度如何合答问题并与理论对话",
}
CASE_FIELDS = {"background": "案例背景", "selection": "案例选择",
               "materials": "资料来源", "method": "研究方法"}
REVIEW_CRITERIA = [
    "各章和各节承担可执行的论证任务，材料定位可回查。",
    "证据范围与计划提出的主张相符，跨章节衔接最终回答核心问题。",
    "定性维度由理论推演，逐章结合经验材料和理论解释，结论整合各维度并回应既有理论。",
    "定量方案遵循本项目的正式设计及结果口径，写作方案的结构检查不构成正式稿件验收。",
]


def prose(value, subject):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing writing task detail: {subject}")
    return value.strip()


def qualitative_order(packet):
    framework = packet["framework"]
    for key in FRAMEWORK_FIELDS:
        prose(framework.get(key), key)
    for key in CASE_FIELDS:
        prose(packet.get("case", {}).get(key), key)
    dimensions = framework["dimensions"]
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("The theoretical framework requires analysis dimensions")
    titles = dict(QUALITATIVE_FIXED)
    for dimension in dimensions:
        key = prose(dimension.get("id"), "dimension ID")
        title = prose(dimension.get("title"), "dimension title")
        prose(dimension.get("deduction"), "dimension deduction")
        if key in titles or title in {*titles.values(), "经验分析", "理论讨论"}:
            raise ValueError("Each dimension needs its own distinct analytic chapter")
        titles[key] = title
    order = ["problem", "framework", "case", *(row["id"] for row in dimensions), "conclusion"]
    return order, titles


def render(packet):
    method = packet["method"]
    if method not in {*QUALITATIVE, "quantitative"}:
        raise ValueError("Unknown research path")
    core = prose(packet.get("core_question"), "core question")
    synthesis = prose(packet.get("answer_strategy"), "how the paper answers the question")
    sources = packet["sources"]
    for identifier, source in sources.items():
        prose(identifier, "source identifier")
        prose(source.get("label"), "source label")
        prose(source.get("locator"), "source locator")
        if source.get("kind") not in {"theory", "literature", "empirical"}:
            raise ValueError("Specify theory, literature or empirical for each source")
    chapters = packet["chapters"]
    order = [chapter["id"] for chapter in chapters]
    if not chapters or len(order) != len(set(order)):
        raise ValueError("A complete plan needs distinct chapters")
    lines = ["# 论文写作方案", "", f"**核心问题** {core}", f"**回答路径** {synthesis}", ""]
    titles = {}
    analytic = set()
    if method in QUALITATIVE:
        required, titles = qualitative_order(packet)
        if order != required:
            raise ValueError("Qualitative chapters must match the framework dimensions in order")
        framework = packet["framework"]
        analytic = {row["id"] for row in framework["dimensions"]}
        lines.extend(["## 分析框架的形成", ""])
        lines.extend(f"- **{label}** {framework[key]}" for key, label in FRAMEWORK_FIELDS.items())
        lines.extend(f"- **{row['title']}** {row['deduction']}" for row in framework["dimensions"])
        lines.extend(["", "## 案例与材料设计", ""])
        lines.extend(f"- **{label}** {packet['case'][key]}" for key, label in CASE_FIELDS.items())
        lines.append("")
    lines.extend(["## 正文章节及分节任务", ""])
    for chapter in chapters:
        key = chapter["id"]
        title = titles[key] if key in titles else prose(chapter.get("title"), "chapter title")
        lines.extend([f"### {title}", "", f"**章节任务** {prose(chapter.get('task'), title)}",
                      f"**章节衔接** {prose(chapter.get('bridge'), title)}", ""])
        sections = chapter["sections"]
        if not isinstance(sections, list) or not sections:
            raise ValueError(f"{title} requires section-level tasks")
        used_kinds = set()
        for section in sections:
            section_title = prose(section.get("title"), "section title")
            refs = section.get("source_ids")
            if not isinstance(refs, list) or not refs or any(ref not in sources for ref in refs):
                raise ValueError(f"Missing or unknown materials for {section_title}")
            used_kinds.update(sources[ref]["kind"] for ref in refs)
            lines.extend([f"#### {section_title}", "",
                          f"- **任务** {prose(section.get('task'), section_title)}",
                          f"- **拟论证** {prose(section.get('argument'), section_title)}",
                          f"- **材料与用途** {prose(section.get('evidence_use'), section_title)}"
                          f"（{ '、'.join(refs) }）", ""])
            if "paragraphs" in section:
                paragraphs = section["paragraphs"]
                if not isinstance(paragraphs, list) or not paragraphs:
                    raise ValueError("Supply paragraph-level writing tasks")
                for number, paragraph in enumerate(paragraphs, 1):
                    lines.append(f"- 第 {number} 段 {prose(paragraph, section_title)}")
                lines.append("")
        if key in analytic and not {"empirical", "theory"} <= used_kinds:
            raise ValueError(f"{title} must integrate a theory source and empirical material")
    lines.extend(["## 材料索引", ""])
    lines.extend(f"- **{identifier}** {source['label']}，{source['locator']}"
                 for identifier, source in sources.items())
    return "\n".join(lines) + "\n"


def reviewed_dimension_sources(packet, matrix, approved):
    """Restrict empirical chapter references to their reviewed matrix dimension.

    Non-analytic chapters may synthesize across dimensions, but all empirical
    IDs must still pass the original material admission gate.
    """
    rows = matrix["rows"]
    ids = [row["dimension_id"] for row in rows]
    dimensions = packet["framework"]["dimensions"]
    if len(set(ids)) != len(ids) or ids != [row["id"] for row in dimensions]:
        raise ValueError("Writing dimensions differ from reviewed matrix")
    scope = {row["dimension_id"]: {item["material_id"] for item in row["evidence"]} & set(approved)
             for row in rows}
    order = ["problem", "framework", "case", *ids, "conclusion"]
    if [chapter["id"] for chapter in packet["chapters"]] != order:
        raise ValueError("Writing chapters differ from reviewed matrix dimensions")
    chapter_sources = {}
    for chapter in packet["chapters"]:
        key = chapter["id"]
        refs = {ref for section in chapter["sections"] for ref in section["source_ids"]
                if packet["sources"][ref]["kind"] == "empirical"}
        permitted = scope[key] if key in scope else set(approved)
        if not refs <= permitted:
            raise ValueError("Empirical chapter source is outside its reviewed matrix dimension")
        if key in scope and not refs:
            raise ValueError("Analytic chapter has no admitted matrix evidence")
        chapter_sources[key] = sorted(refs)
    return chapter_sources


def reviewed_material_admission(work, packet, review):
    """Recheck the original reviewed route; this is not an independent review.

    Only the native resume controller supplies its already-accepted review.
    The standalone CLI does not grant this admission from packet fields.
    """
    if not isinstance(review, dict) or review.get("decision") != "pass":
        raise ValueError("Reviewed V15 requires original matrix review pass")
    reference = packet.get("analysis_matrix")
    if not isinstance(reference, str):
        raise ValueError("Reviewed V15 requires the original reviewed matrix")
    path = (work / reference).resolve()
    if (path.name != "analysis_matrix_reviewed.json"
            or path.parent.parent != (work / "qualitative_framework").resolve()):
        raise ValueError("Reviewed V15 requires the original reviewed matrix")
    contract = binding(work, path.parent)
    matrix, receipt = load(path), load(path.parent / "material_receipt.json")
    from material_adequacy import approved_matrix_materials, validate_reviewed_plan_sources
    from question_binding import evidence_digest, file_hash
    if (matrix.get("question_binding") != contract
            or matrix.get("collection_sha256") != evidence_digest(receipt)
            or matrix.get("framework_sha256") != receipt.get("framework_sha256")):
        raise ValueError("Reviewed V15 matrix binding differs")
    approved = approved_matrix_materials(review.get("material_adequacy"), receipt, matrix)
    validate_reviewed_plan_sources(packet, contract, receipt, approved)
    chapter_sources = reviewed_dimension_sources(packet, matrix, approved)
    return {"mode": "native_reviewed", "matrix_sha256": file_hash(path),
            "receipt_sha256": contract["receipt_sha256"],
            "review_sha256": evidence_digest(review),
            "eligible_material_ids": sorted(approved),
            "chapter_empirical_source_ids": chapter_sources,
            "question_binding": contract}


def produce(work, packet, manifest, *, output=None, material_review=None):
    admission = (reviewed_material_admission(work, packet, material_review)
                 if material_review is not None else {"mode": "exploratory_unverified"})
    frozen_path = work / "s08_topic.json"
    question_binding = packet.get("question_binding")
    if frozen_path.is_file():
        frozen = load(frozen_path)
        method = frozen.get("research_method") or {}
        if ((method and method.get("path") != packet["method"])
                or frozen["question"] != (packet.get("specific_question") if question_binding
                                           else packet["core_question"])):
            raise ValueError("Writing plan must match the frozen method and question")
    matrix_path = None
    matrix_reference = packet.get("analysis_matrix")
    if matrix_reference:
        matrix_path = (work / matrix_reference).resolve()
        if not matrix_path.is_relative_to((work / "qualitative_framework").resolve()):
            raise ValueError("Use this run's framework analysis matrix")
        matrix = load(matrix_path)
        if question_binding and question_binding != binding(work, matrix_path.parent):
            raise ValueError("Research question binding changed")
        if question_binding and (packet["core_question"] != question_binding["core_question"]
                                 or matrix.get("question_binding") != question_binding
                                 or matrix.get("collection_sha256") != hashlib.sha256(
                                     json.dumps(load(matrix_path.parent / "material_receipt.json"),
                                                sort_keys=True, ensure_ascii=False,
                                                separators=(",", ":")).encode()).hexdigest()):
            raise ValueError("Matrix is not bound to this question and receipt")
        analytical = packet["framework"]["dimensions"]
        if [row["dimension_id"] for row in matrix["rows"]] != [row["id"] for row in analytical]:
            raise ValueError("Writing plan must preserve the matrix dimensions")
        framework_name = ("framework.json" if question_binding else
                          matrix_path.name.replace("analysis_matrix", "framework", 1))
        frozen_framework = load(matrix_path.with_name(framework_name))
        framework_bytes = json.dumps(frozen_framework, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()
        if (matrix["framework_sha256"] != hashlib.sha256(framework_bytes).hexdigest()
                or frozen_framework["core_question"] != packet["core_question"]
                or frozen_framework["core_concept"] != packet["framework"].get("core_concept")):
            raise ValueError("Analysis matrix and writing framework differ")
    text = render(packet)
    mode = writing_policy(manifest)["deliverable"]
    output = output or work / "writing"
    output.mkdir(exist_ok=False)
    plan = output / "论文写作方案.md"
    # The renderer owns the exact input consumed; publish the review request only after it exists.
    write(output / "plan_input.json", packet)
    plan.write_text(text, encoding="utf-8")
    write(output / "writing_plan_review_request.json", {
        "run_id": manifest["run_id"], "run_mode": "dev", "formal_eligible": False,
        "method": packet["method"], "requested_deliverable": mode, "status": "plan_prepared",
        "input_sha256": digest(packet), "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "topic_sha256": hashlib.sha256(frozen_path.read_bytes()).hexdigest() if frozen_path.is_file() else None,
        "analysis_matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest() if matrix_path else None,
        "review_criteria": REVIEW_CRITERIA, "review_status": "pending",
        "question_binding": question_binding, "material_admission": admission,
        "full_draft_entry": ("existing_quantitative_with_upstream_gates"
                             if mode == "full" and packet["method"] == "quantitative"
                             else "planned" if mode == "full" else "not_requested"),
    })
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-run", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    manifest = verified_run(args.dev_run)
    print(produce(args.dev_run, load(args.input), manifest))


if __name__ == "__main__":
    main()
