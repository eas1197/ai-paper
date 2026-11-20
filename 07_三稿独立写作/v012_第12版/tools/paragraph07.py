"""Compile a writer's outline into paragraph tasks and match the submitted draft to them."""
from __future__ import annotations

import re

from exemplars07 import read_index, select
from manuscript07 import HEADING
from runtime import ROOT, inside, load, verify_locks

SECTION_ORDER = ("A", "I", "L", "T", "D", "R", "C")
MOVES_BY_SECTION = dict(zip(SECTION_ORDER[1:], ("question", "literature", "hypothesis",
                                              "design", "results", "discussion")))
PLAN_ID = re.compile(r"[0-9a-f]{64}")
PARAGRAPH_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def style_resource(binding, architecture, style_ids):
    """Follow the two G3 file locks and check the link to the 02 profile."""
    files = {key: inside(ROOT, binding[key]["path"]) for key in ("mapping", "rules")}
    if verify_locks([dict(binding[key], path=str(path)) for key, path in files.items()]):
        raise ValueError("03 逐段写法的映射或风格规则哈希已变化")
    mapping, rules = load(files["mapping"]), load(files["rules"])
    if (mapping["schema_version"] != 1 or mapping["architecture_profile_id"] != architecture["profile_id"]
            or mapping["architecture_profile_version"] != architecture["profile_version"]):
        raise ValueError("03 逐段写法与本次锁定的02写作架构不兼容")
    by_id = {rule["id"]: rule for rule in rules}
    if set(by_id) != set(style_ids) or len(by_id) != len(rules):
        raise ValueError("03 逐段写法与语言手册的规则编号不一致")
    units = mapping["units"]
    if set(row["section"] for row in units.values()) != set(SECTION_ORDER):
        raise ValueError("03 逐段写法须覆盖摘要和六项正文任务")
    for unit_id, unit in units.items():
        if not unit["purpose"].strip() or not unit["style_ids"] or not set(unit["style_ids"]) <= by_id.keys():
            raise ValueError(f"03 {unit_id} 缺少有效的论证任务或规则")
    return units, by_id


def research_catalog(bundles, eligible_literature):
    literature, theory, analysis = (bundles[mid] for mid in ("04", "05", "06"))
    protocol = analysis.get("protocol", {})
    eligible = set(eligible_literature)
    papers = {row["paper_id"] for row in literature["papers"]}
    document_fields = ("document_id", "title", "source_id", "paper_id", "kind", "path", "sha256")
    documents = {row["document_id"]: {field: row[field] for field in document_fields if field in row}
                                    | {"stage": stage}
                 for stage, rows in (("04", literature["documents"]), ("05", theory["metadata_documents"]))
                 for row in rows}

    def allowed(row):
        paper_id = row.get("paper_id") or documents.get(row.get("document_id"), {}).get("paper_id")
        return not paper_id or paper_id in eligible or paper_id not in papers

    def entries(rows, key, columns=None):
        return {row[key]: row if columns is None else {field: row[field] for field in columns if field in row}
                for row in rows}

    evidence = (dict(row, source_document=documents.get(row.get("document_id")))
                for row in literature["evidence"] + theory["measurement_evidence"] if allowed(row))
    return {
        "evidence_ids": entries(evidence, "evidence_id"),
        "document_ids": entries((row for row in documents.values() if allowed(row)), "document_id"),
        "hypothesis_ids": entries((row for row in theory.get("hypotheses", [])
                                  if row.get("review_status") == "accepted"), "hypothesis_id"),
        "result_ids": entries(analysis["results"], "result_id"),
        "dataset_ids": entries(protocol.get("datasets", []), "dataset_id", ("dataset_id", "name", "wave")),
        "variable_ids": entries(analysis.get("measurements", []), "variable_id"),
        "model_ids": entries(protocol.get("models", []), "model_id"),
    }


def compile_plan(outline, pack_id, labels, units, rules, catalog, exemplar_binding=None):
    if outline.get("schema_version") != 1 or outline.get("pack_id") != pack_id or outline.get("label") not in labels:
        raise ValueError("段落提纲须使用当前证据包、草稿标签和提纲格式")
    records = outline.get("paragraphs")
    if not isinstance(records, list) or not records:
        raise ValueError("段落提纲缺少 paragraphs")
    exemplars = None
    if exemplar_binding:
        path = inside(ROOT, exemplar_binding["path"])
        if verify_locks([dict(exemplar_binding, path=str(path))]):
            raise ValueError("写作范例索引已变化，须重新准备写作任务")
        exemplars = read_index(path)
    tasks, seen = [], set()
    for row in records:
        identity = row["paragraph_id"]
        if not isinstance(identity, str) or not PARAGRAPH_ID.fullmatch(identity) or identity in seen:
            raise ValueError(f"段落编号不合法或重复: {identity}")
        seen.add(identity)
        unit_ids = row["units"]
        if not isinstance(unit_ids, list) or not unit_ids or len(set(unit_ids)) != len(unit_ids):
            raise ValueError(f"{identity} 须提供不重复的02功能单元")
        unknown = set(unit_ids) - units.keys()
        if unknown:
            raise ValueError(f"{identity} 未知的02功能单元: {', '.join(sorted(unknown))}")
        parts = [units[key] for key in unit_ids]
        section = parts[0]["section"]
        if any(part["section"] != section for part in parts):
            raise ValueError(f"{identity} 同一段的功能单元须属于同一项正文任务")
        if any(not isinstance(row.get(key), str) or not row[key].strip()
               for key in ("heading", "continues", "purpose")):
            raise ValueError(f"{identity} 缺少标题、承接内容或本段推进")
        if (section == "A") != (row["heading"] == "摘要"):
            raise ValueError(f"{identity} 摘要功能须与摘要标题对应")
        allowed = list(dict.fromkeys(style for part in parts for style in part["style_ids"]))
        style_ids = row.get("style_ids", allowed)
        if (not isinstance(style_ids, list) or not style_ids or len(set(style_ids)) != len(style_ids)
                or not set(style_ids) <= set(allowed)):
            raise ValueError(f"{identity} 请选择本段功能对应的风格规则")
        sources = row.get("sources", {})
        if not isinstance(sources, dict) or not sources.keys() <= catalog.keys():
            raise ValueError(f"{identity} 证据字段无效")
        for field, ids in sources.items():
            if not isinstance(ids, list) or len(set(ids)) != len(ids) or not set(ids) <= catalog[field].keys():
                raise ValueError(f"{identity} 的 {field} 含重复编号或未绑定冻结材料")
        move = MOVES_BY_SECTION.get(section)
        examples = []
        if exemplars and move:
            query = exemplar_binding["queries"][move]
            subtask = next((part["subtask"] for part in parts if part.get("subtask")), None)
            examples = select(exemplars, dict(query, subtask=subtask) if subtask else query)
        tasks.append({
            "paragraph_id": identity, "heading": row["heading"], "section": section,
            "units": unit_ids, "unit_purposes": [part["purpose"] for part in parts],
            "continues": row["continues"], "purpose": row["purpose"],
            "sources": sources,
            "source_material": {field: [catalog[field][key] for key in ids] for field, ids in sources.items()},
            "style_rules": [{field: rules[key][field] for field in
                             ("id", "name", "how_to_write", "condition", "anti_pattern", "after")}
                            for key in style_ids],
            "examples": examples,
        })
    sequence = list(dict.fromkeys(task["section"] for task in tasks))
    ranks = [SECTION_ORDER.index(task["section"]) for task in tasks]
    if sequence != list(SECTION_ORDER) or ranks != sorted(ranks):
        raise ValueError("段落提纲须按架构覆盖摘要和六项正文任务")
    for section in ("A", "R", "C"):
        if not any(task["sources"].get("result_ids") for task in tasks if task["section"] == section):
            raise ValueError(f"{section}须在至少一项段落任务中绑定本研究的冻结结果")
    for i, task in enumerate(tasks):
        if i + 1 < len(tasks):
            following = tasks[i + 1]
            task["next"] = {key: following[key] for key in ("paragraph_id", "purpose")}
        else:
            task["next"] = None
    return {"schema_version": 1, "pack_id": pack_id, "label": outline["label"], "paragraphs": tasks}


NON_PROSE = re.compile(r"^(?:\||!\[|\[\^.+?\]:|(?:\*\*)?关键词(?:\*\*)?[：:]|"
                       r"(?:表|图)\s*[A-Za-z]?\d+(?:\s|[：:])|注[：:]|>)")


def prose_paragraphs(text):
    """Number only draftable paragraphs. Headings, tables, figures and notes stay in their ledgers."""
    heading = None
    headings = list(HEADING.finditer(text))
    for index, marker in enumerate(headings):
        if marker[1] == "##":
            heading = marker[2].strip()
            if heading == "参考文献" or heading.startswith("附录"):
                return
        if heading:
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            lines = text[marker.end():end].splitlines()
            block = []
            for line in [*lines, ""]:
                item = line.strip()
                if not item or NON_PROSE.match(item):
                    if block:
                        yield heading, " ".join(block)
                        block.clear()
                else:
                    block.append(item)


def check_paragraphs(compiled, records, text, structure, claims, errors):
    tasks = compiled["paragraphs"]
    if not isinstance(records, dict) or set(records) != {task["paragraph_id"] for task in tasks}:
        errors.append("交稿须按已准备的段落任务逐项登记写法")
        return
    sections = {"摘要": ["A"], **{row["heading"]: row["functions"] for row in structure}}
    actual = list(prose_paragraphs(text))
    if len(actual) != len(tasks):
        errors.append(f"正文及摘要共有{len(actual)}段，预先准备的任务有{len(tasks)}项。合并或拆分后重新准备计划")
        return
    for task, (heading, paragraph) in zip(tasks, actual):
        identity = task["paragraph_id"]
        if task["heading"] != heading or task["section"] not in sections.get(heading, []):
            errors.append(f"{identity} 的正文位置与预先准备的任务不一致")
            continue
        note = records[identity]
        if not isinstance(note, dict):
            errors.append(f"{identity} 缺有效的风格应用记录")
            continue
        anchor, applied, explanation = (note.get(key) for key in ("text", "style_ids", "application"))
        allowed = {row["id"] for row in task["style_rules"]}
        if (not isinstance(anchor, str) or not anchor.strip() or " ".join(anchor.split()) not in paragraph
                or not isinstance(applied, list) or not applied or not set(applied) <= allowed
                or not isinstance(explanation, str) or not explanation.strip()):
            errors.append(f"{identity} 须定位本段原句并说明如何运用任务中已选的风格规则")
    for claim in claims:
        anchor = " ".join(claim["claim_text"].split())
        paragraph_id = claim.get("paragraph_id")
        matches = [task for task, (heading, paragraph) in zip(tasks, actual)
                   if anchor and claim["sentence_id"] == heading and anchor in paragraph
                   and (paragraph_id is None or task["paragraph_id"] == paragraph_id)]
        if len(matches) > 1 or (paragraph_id is not None and not matches):
            errors.append(f"主张 {claim['claim_id']} 须按实际位置指定唯一的 paragraph_id")
        elif matches:
            task = matches[0]
            for field in ("evidence_ids", "result_ids"):
                if not set(claim[field]) <= set(task["sources"].get(field, [])):
                    errors.append(f"{task['paragraph_id']} 的主张 {claim['claim_id']} 使用了未分配到本段的 {field}")
