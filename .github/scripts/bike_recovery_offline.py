"""Read-only recovery probe for the archived bike-parking qualitative run.

Outputs are provisional. This script never edits run evidence, calls models, or
changes academic review outcomes. It does NOT call writing_plan.produce().
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "00_项目控制/v007_第7版/runs_dev/bike_parking_20261122"
FOLDER = RUN / "qualitative_framework/requirements_570aa82a9f24d0"
MATRIX_FILE = FOLDER / "analysis_matrix_rebuilt_e3161a4acbc9ad42.json"

sys.path.insert(0, str(ROOT / "00_项目控制/v007_第7版/tools"))
sys.path.insert(0, str(ROOT / "00_项目控制/v009_第9版/tools"))
sys.path.insert(0, str(ROOT / "07_三稿独立写作/v015_第15版/tools"))
from question_binding import evidence_digest
from writing_plan import render


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def raw_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence_refs(row, materials):
    refs = []
    for item in row["evidence"]:
        ref = "E-" + item["material_id"]
        if item["material_id"] in materials and ref not in refs:
            refs.append(ref)
    return refs


def section(title, task, argument, evidence_use, refs, paragraphs):
    return dict(title=title, task=task, argument=argument,
                evidence_use=evidence_use, source_ids=refs, paragraphs=paragraphs)


def chapter(identifier, title, task, bridge, sections):
    return dict(id=identifier, title=title, task=task, bridge=bridge, sections=sections)


def build_plan(frozen, framework, matrix, receipt):
    materials = {row["material_id"]: row for row in receipt["materials"]}
    all_refs = ["E-" + key for key in materials]
    sources = {
        "T-ABSTRACT": {
            "kind": "theory",
            "label": "Rahman与Valentine等机制文献线索（仅据原框架中的摘要级梳理，非全文核验）",
            "locator": "qualitative_framework/requirements_570aa82a9f24d0/framework.json:nearest_study/existing_explanation；正式引用需核对原文",
        }
    }
    for identifier, material in materials.items():
        sources["E-" + identifier] = dict(
            kind="empirical",
            label="来源回执中的" + str(material.get("kind", "公开报道")) + "，材料" + identifier,
            locator=str(material.get("locator", "未提供行号")) +
                    "；来源URL：" + str(material.get("url", "未记录")),
        )
    first = all_refs[:2]
    chapters = [
        chapter("problem", "问题的提出",
                "区分可核对的现场停车线—应用判定冲突与其他还车困难，提出研究问题",
                "将现场例子转化为可比较的研究条件，而非先验地认定平台造成损害",
                [section("冲突与额外补救工作",
                         "记录现场标线、应用判定、操作与结果的可证实事实",
                         frozen["question"],
                         "使用两项公开报道作问题引入，不把二手陈述等同记者实测",
                         first,
                         ["定义单次事件和观察起点", "区分已知事实、当事人陈述与制度解释", "说明不能由少量案例估计普遍发生率"])]),
        chapter("framework", "文献综述与分析框架",
                "在摘要级文献对话基础上阐明补救工作及处置权限的解释路径",
                "推导四个相互衔接而不互相混同的比较维度",
                [section("冲突后的修复与组织可见性",
                         "总结已有理论能解释的部分和现有材料不能验证的部分",
                         framework["existing_explanation"],
                         "理论材料目前仅来自冻结框架中的摘要级记录，不能冒充已核全文",
                         ["T-ABSTRACT", *first],
                         ["梳理既有解释及其适用对象", "说明转用于共享单车情境的条件", "提出竞争解释和理论增量待核项"])]),
        chapter("case", "案例介绍",
                "交代案例筛选、来源类型和证据分级方法",
                "依照观察时序进入D1冲突识别",
                [section("案例界限与二手访谈材料",
                         "说明公开报道中的记者实测、当事人陈述和事后费争的不同地位",
                         framework["choice"],
                         "严格保留回执中标线、关锁、应用关单与费用的未知项",
                         first,
                         ["列出来源回执中可定位的事件", "区分独立事件与同一订单后续", "声明尚无完整对照组及后台日志"])]),
    ]
    for row in matrix["rows"]:
        refs = evidence_refs(row, materials)
        if not refs:
            raise ValueError("Dimension " + row["id"] + " lacks traceable receipt material")
        unresolved = row["unresolved"]
        if row["id"] == "D1" and "当前问题绑定" in unresolved:
            unresolved = unresolved.split("当前问题绑定")[0].rstrip("；。") + "。"
        links = ["T-ABSTRACT", *refs]
        chapters.append(chapter(
            row["id"], row["name"],
            "检查待检验命题：" + row["proposition"],
            row["relationship"],
            [section(
                "机制命题与可核对的事件条件",
                "由理论框架推导区分条件，并核对本维度材料是否真正满足条件",
                row["deduction"],
                row["needed_material"],
                links,
                ["交代本维度的比较条件，不把观察时序误认为因果", "逐项标识来源类型和对应事件", "在未核实适用边界时保留候选而非正式纳入"]),
             section(
                "过程对照、竞争解释及证据缺口",
                "比较已记录操作，审查竞争解释，并清楚列出不能下结论之处",
                "已有矩阵暂定判断（独立复审尚未通过）：" + row["conclusion"],
                "分析边界：" + row["boundary"] +
                "；竞争解释：" + row["alternatives"] +
                "；尚未核实：" + unresolved,
                links,
                ["按同一次事件的时间顺序陈述原始记录", "将已观察动作与解释性推断分开", "比较相近事件并明确替代机制", "结尾说明不足和可检验预期"])]))
    last = all_refs[-2:]
    chapters.append(chapter(
        "conclusion", "结论与讨论",
        "综合四维度对补救工作的分配过程提出有限结论",
        "区分已有案例可支持的过程描述与无法检验的因果命题",
        [section("可追踪的行动过程与后续证据需求",
                 "在不夸大机制效果的前提下回应核心问题",
                 framework["proposed_increment"],
                 "重点说明D3复核权限和关单确认缺少完整过程证据",
                 ["T-ABSTRACT", *last],
                 ["总结可核实的移动、重试、求助和关单线索", "明确尚未证实的机制及外推限制", "列出标线适用、后台关单和减免到账的补充证据需求"])]))
    return {
        "method": "secondary_interviews",
        "core_question": framework["core_question"],
        "specific_question": frozen["question"],
        "answer_strategy": framework["integration"],
        "sources": sources,
        "framework": {
            "prior_explanation": framework["existing_explanation"],
            "gap": framework["limitation"],
            "theory_choice": framework["nearest_study"],
            "deduction": framework["choice"],
            "increment": framework["proposed_increment"],
            "integration": framework["integration"],
            "dimensions": [{"id": row["id"], "title": row["name"],
                            "deduction": row["deduction"]} for row in matrix["rows"]],
        },
        "case": {
            "background": frozen["research_case"]["context"],
            "selection": framework["choice"],
            "materials": "来源回执中 " + str(len(materials)) +
                         " 条材料；独立事件和后续报道按原矩阵区分，未确认的现场记录不得补造",
            "method": frozen["design"],
        },
        "chapters": chapters,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    frozen = read(RUN / "s08_topic.json")
    framework = read(FOLDER / "framework.json")
    receipt = read(FOLDER / "material_receipt.json")
    matrix = read(MATRIX_FILE)
    status = read(RUN / "autonomous_writing_status.json")
    latest_review = read(RUN / "autonomous_writing/rebuilt_matrix_review_e3161a4acbc9ad42/attempt_001/validated.json")
    lineage = read(RUN / "autonomous_writing/artifact_lineage_verified.json")
    needed = [
        RUN / "run_manifest.json",
        RUN / "staged_topic.json",
        RUN / "merged_literature.json",
        RUN / "initial/theories.json",
        FOLDER / "events.jsonl",
        FOLDER / "response.json",
    ]
    missing = [p.relative_to(ROOT).as_posix() for p in needed if not p.is_file()]
    listed = next((entry for entry in lineage
                   if entry["framework_path"] == "qualitative_framework/requirements_570aa82a9f24d0/framework.json"), None)
    matrix_ids = {e["material_id"] for r in matrix["rows"] for e in r["evidence"]}
    receipt_ids = {m["material_id"] for m in receipt["materials"]}
    checks = {
        "matrix_framework_canonical_digest_matches": matrix.get("framework_sha256") == evidence_digest(framework),
        "matrix_collection_digest_matches_receipt": matrix.get("collection_sha256") == evidence_digest(receipt),
        "receipt_framework_canonical_digest_matches": receipt.get("framework_sha256") == evidence_digest(framework),
        "lineage_framework_file_sha256_matches": listed is not None and listed.get("framework_file_sha256") == raw_sha(FOLDER / "framework.json"),
        "lineage_receipt_file_sha256_matches": listed is not None and listed.get("receipt_file_sha256") == raw_sha(FOLDER / "material_receipt.json"),
        "matrix_material_ids_all_in_receipt": matrix_ids <= receipt_ids,
        "freeze_method_matches_framework": frozen.get("research_method", {}).get("path") == "secondary_interviews",
        "review_still_requests_revision": latest_review.get("answer", {}).get("decision") == "revise",
        "status_local_revision_limit": status.get("status") == "local_revision_limit",
        "old_hash_in_D1_unresolved": any("哈希" in row.get("unresolved", "") for row in matrix["rows"] if row["id"] == "D1"),
    }
    packet = build_plan(frozen, framework, matrix, receipt)
    plan = render(packet)
    header = (
        "# 共享单车研究 · 真实材料候选写作方案（未经独立审查）\n\n"
        "> 此文件来自 GitHub 存档矩阵与材料回执的离线复用，不是通过学术门禁的论文计划。"
        "矩阵状态为 pending_independent_review，独立复审要求 revise，且局部返修额度已耗尽。"
        "以下任务仅作为下一轮独立审查的候选输入，不能视为正式定稿。\n\n"
        "> 所有材料保留二手来源、未知锁态、未知关单、因果不能识别等证据界限。"
        "历史版本哈希问题属于制品元数据整改，并未因此被判定解决。\n\n"
    )
    (args.out / "候选论文写作方案_未经学术审查.md").write_text(header + plan, encoding="utf-8")
    (args.out / "candidate_packet.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Prepare a *preview*, never mutate the reviewed matrix or reset revision budgets.
    # Only move the recorded legacy hash comparison out of empirical D1.unresolved.
    candidate_matrix = json.loads(json.dumps(matrix, ensure_ascii=False))
    d1 = next(row for row in candidate_matrix["rows"] if row["id"] == "D1")
    marker = "当前问题绑定"
    if marker not in d1["unresolved"]:
        raise ValueError("Cannot move an absent legacy hash comment")
    empirical, legacy_hash_note = d1["unresolved"].split(marker, 1)
    d1["unresolved"] = empirical.rstrip("；。") + "。"
    if any(not (
        hashlib.sha256(file.read_bytes().replace(b"\n", b"\r\n")).hexdigest()
        == listed.get(field) if listed else False
    ) for file, field in (
        (FOLDER / "framework.json", "framework_file_sha256"),
        (FOLDER / "material_receipt.json", "receipt_file_sha256")
    )):
        raise ValueError("Raw hash lineage cannot be explained by line endings")
    candidate_matrix["artifact_version_metadata"] = {
        "preview_status": "unreviewed_technical_repair_not_a_formal_revision",
        "basis_matrix_file_sha256_in_git": raw_sha(MATRIX_FILE),
        "historical_version_chain": lineage,
        "moved_from": "D1.unresolved",
        "legacy_hash_note": marker + legacy_hash_note,
        "algorithm": {
            "file_sha256": "sha256(original local raw bytes; historical sources use CRLF)",
            "git_sha256": "sha256(GitHub checkout raw bytes; repository snapshot uses LF)",
            "canonical_json_sha256": "sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8'))",
            "newline_reconciliation": "SHA256(GitHub snapshot LF bytes converted to CRLF) matches historical local SHA256 for current framework and receipt",
        },
        "coverage": "Framework and receipt bytes reconciled; events.jsonl, response.json and full parent artifacts absent, not independently recomputed",
        "review_gate": "pending_independent_review",
        "academic_approval": False,
    }
    assert all(candidate_matrix["rows"][i] == matrix["rows"][i]
               for i in range(1, len(matrix["rows"])))
    assert all(d1[key] == matrix["rows"][0][key]
               for key in matrix["rows"][0] if key != "unresolved")
    (args.out / "候选矩阵_仅版本元数据返修_未经复审.json").write_text(
        json.dumps(candidate_matrix, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    report = {
        "scope": "offline_repository_snapshot_only",
        "repository_run": RUN.relative_to(ROOT).as_posix(),
        "research_theme": "共享单车停车线与应用还车判定冲突",
        "academic_approval": False,
        "formal_eligible": False,
        "academic_gate": "blocked",
        "archived_status": status,
        "latest_review_decision": latest_review.get("answer", {}).get("decision"),
        "matrix_status": matrix.get("status"),
        "matrix_sha256": raw_sha(MATRIX_FILE),
        "snapshot_hash_comparison": {
            label: {
                "git_snapshot_raw_sha256": raw_sha(file),
                "recorded_runtime_raw_sha256": listed.get(field) if listed else None,
                "git_snapshot_bytes": len(file.read_bytes()),
                "matches_if_lf_to_crlf": (
                    hashlib.sha256(file.read_bytes().replace(b"\n", b"\r\n")).hexdigest()
                    == listed.get(field) if listed else False),
                "matches_if_trim_final_lf": (
                    hashlib.sha256(file.read_bytes().rstrip(b"\r\n")).hexdigest()
                    == listed.get(field) if listed else False),
            } for label, file, field in (
                ("framework", FOLDER / "framework.json", "framework_file_sha256"),
                ("receipt", FOLDER / "material_receipt.json", "receipt_file_sha256")
            )
        },
        "missing_runtime_files": missing,
        "checks": checks,
        "dimensions": [{"id": r["id"], "status": r.get("status"), "evidence_count": len(r["evidence"])} for r in matrix["rows"]],
        "receipt_materials": len(receipt["materials"]),
        "candidate_document": "候选论文写作方案_未经学术审查.md",
        "candidate_status": "rendered_unreviewed",
        "candidate_matrix": "候选矩阵_仅版本元数据返修_未经复审.json",
        "next_gate": "recover runtime artifacts + version-metadata repair + authorized independent re-review",
        "paid_model_calls": 0,
    }
    (args.out / "恢复诊断.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    assert all(checks[key] for key in (
        "matrix_framework_canonical_digest_matches",
        "matrix_collection_digest_matches_receipt",
        "receipt_framework_canonical_digest_matches",
        "matrix_material_ids_all_in_receipt",
        "freeze_method_matches_framework",
    )), "Archived source and matrix integrity inconsistent"
    assert missing and status["status"] == "local_revision_limit"
    assert "D3" in [row["id"] for row in matrix["rows"]]
    assert "论文写作方案" in plan and "### " in plan


if __name__ == "__main__":
    main()
