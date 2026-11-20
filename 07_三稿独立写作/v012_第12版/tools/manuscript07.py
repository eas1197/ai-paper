"""检查 Markdown 稿件、论证任务、证据台账及研究者复核。"""
import csv
import re
from decimal import Decimal, InvalidOperation

from runtime import indexed, present, refs, signoff


HEADING = re.compile(r"^(#{1,6}) +(.+?) *$", re.MULTILINE)
STAT_FIELDS = {"estimate", "std_error", "p_value", "ci_low", "ci_high", "ci_level", "n_obs", "n_clusters"}


def body_count(text):
    """架构2.1计数口径。标题、表格、图注、引用链接地址均不计入。"""
    text = re.sub(r"(?m)^ *(?:#|\||!\[|\[\^|(?:表|图)\s*[A-Z]?\d+|注[：:]).*$", "", text)
    text = re.sub(r"!?(\[([^\]]+)\])\([^)]*\)", r"\2", text)
    return len(re.sub(r"[\s*_\x60]", "", text))


def parse_structure(text, structure, profile, errors):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    headings = list(HEADING.finditer(text))
    main = [h for h in headings if len(h[1]) <= 2]
    if not main or main[0][1] != "#" or text[:main[0].start()].strip() or sum(h[1] == "#" for h in main) != 1:
        errors.append("须从一个明确的论文标题开始")
    if re.search(r"【[^】]+】|\b(?:TODO|TBD)\b|待补充|占位符|拟补入", text):
        errors.append("正文仍含模板占位语")
    sections = {h[2]: text[h.end():main[i + 1].start() if i + 1 < len(main) else len(text)].strip()
                for i, h in enumerate(main) if h[1] == "##"}
    if len(sections) != sum(h[1] == "##" for h in main):
        errors.append("二级标题不得重复")
    default = [{"heading": f"{n}、{s['title']}", "functions": [s["id"]]}
               for n, s in zip("一二三四五六", profile["sections"])]
    structure = structure or default
    expected_functions = [s["id"] for s in profile["sections"]]
    if [k for row in structure for k in row["functions"]] != expected_functions or any(
            not row["functions"] for row in structure):
        errors.append("须按照架构顺序完成六项论证任务；合并时仍须逐项列出")
    if structure != default and any(len(row["functions"]) > 1 and not present(row.get("reason")) for row in structure):
        errors.append("合并章节须在写作计划中记录理由")
    expected = ["摘要"] + [row["heading"] for row in structure] + ["参考文献"]
    actual = list(sections)
    if actual[:len(expected)] != expected or any(not h.startswith("附录") for h in actual[len(expected):]):
        errors.append("标题顺序与计划不符，须有摘要、六项正文任务和参考文献；附录置于文末")
    abstract = sections.get("摘要", "")
    keywords = re.search(r"(?m)^\s*(?:\*\*)?关键词(?:\*\*)?[：:](?:\*\*)?\s*(.+)$", abstract)
    if not keywords or not 4 <= len([k for k in re.split(r"[；;、，,]", keywords[1]) if k.strip()]) <= 6:
        errors.append("摘要后须列4—6个关键词")
    abstract_text = abstract[:keywords.start()] if keywords else abstract
    if not body_count(abstract_text) or not sections.get("参考文献"):
        errors.append("摘要正文或参考文献为空")
    counts = {row["heading"]: body_count(sections.get(row["heading"], "")) for row in structure}
    if any(count == 0 for count in counts.values()):
        errors.append("正文任务缺少实际段落")
    return sections, structure, counts, body_count(abstract_text)


def decimal(value):
    result = Decimal(str(value).replace("−", "-"))
    if not result.is_finite():
        raise ValueError("数值须为有限数")
    return result


def reported_value(item, row, anchor):
    token = item["display"]
    field = item["field"]
    if (not isinstance(token, str) or field not in STAT_FIELDS or field not in row
            or not re.search(r"(?<![\d.+−-])" + re.escape(token) + r"(?![\d.]|%)", anchor)):
        return False
    try:
        displayed = decimal(token.rstrip("%"))
        source = decimal(row[field]) * (100 if token.endswith("%") else 1)
        if field in {"n_obs", "n_clusters"}:
            return source == displayed and "%" not in token
        half_unit = Decimal("0.5").scaleb(displayed.as_tuple().exponent)
        return abs(source - displayed) <= half_unit
    except (InvalidOperation, ValueError):
        return False


def audit(draft, text, profile, bundles, checklist, errors, eligible_literature=None):
    sections, structure, counts, abstract_count = parse_structure(text, draft.get("structure"), profile, errors)
    budgets = profile["length_profiles"].get(draft.get("length_profile", "standard"))
    if budgets is None:
        budgets = draft.get("section_budgets", [])
        if (draft.get("length_profile") != "custom" or len(budgets) != len(profile["sections"])
                or not all(type(n) is int and n > 0 for n in budgets) or not present(draft.get("length_reason"))):
            errors.append("篇幅使用标准/短/长计划；定制时记录六项预算与调整理由")
            budgets = []
    literature, theory, analysis = (bundles[mid] for mid in ("04", "05", "06"))
    papers = indexed(literature["papers"], "paper_id", errors)
    documents = indexed(literature["documents"] + theory["metadata_documents"], "document_id", errors)
    evidence = indexed(literature["evidence"] + theory["measurement_evidence"], "evidence_id", errors)
    results = indexed(analysis["results"], "result_id", errors)
    references = indexed(draft.get("references", []), "reference_id", errors)
    approved_papers = set(eligible_literature) if eligible_literature is not None else set(papers)
    bibliography = sections.get("参考文献", "")
    used_refs, result_sections, table_rows, ref_entries = set(), set(), [], set()
    for ref_id, ref in references.items():
        marker, entry = ref.get("marker"), ref.get("entry")
        if (not isinstance(marker, str) or not marker.strip() or not isinstance(entry, str)
                or len(entry.strip()) <= len(marker) or entry not in bibliography or entry in ref_entries):
            errors.append(f"{ref_id} 缺唯一且与正文标记对应的参考文献条目")
        if isinstance(entry, str):
            ref_entries.add(entry)
        if ref_id not in papers and ref_id not in documents:
            errors.append(f"{ref_id} 参考文献未绑定冻结题录或原文")
        cited_paper = ref_id if ref_id in papers else documents.get(ref_id, {}).get("paper_id")
        if cited_paper in papers and cited_paper not in approved_papers:
            errors.append(f"{ref_id} 来自指定文献库之外的候选记录")
    if {line.strip() for line in bibliography.splitlines() if line.strip()} != ref_entries:
        errors.append("参考文献每一条须单独一行并登记对应来源")
    claims = indexed(draft.get("claims", []), "claim_id", errors)
    for identity, claim in claims.items():
        heading, anchor = claim["section"], claim["text"]
        if not anchor.strip() or anchor not in sections.get(heading, "") or heading == "参考文献":
            errors.append(f"{identity} 无法在指定正文位置定位")
        kind = claim.get("claim_type")
        if kind not in ("direct", "synthesis", "inference", "result"):
            errors.append(f"{identity} 须区分直接证据、综合、推断与实证结果")
        source_ids, result_ids = claim.get("evidence_ids", []), claim.get("result_ids", [])
        sources = refs(source_ids, evidence, identity, errors, required=kind != "result")
        refs(result_ids, results, identity, errors, required=kind == "result")
        cited_ids = claim.get("reference_ids", [])
        refs(cited_ids, references, identity, errors, required=False)
        source_refs = {row.get("document_id") for row in sources} | {row.get("paper_id") for row in sources}
        source_refs |= {documents.get(ref, {}).get("paper_id") for ref in source_refs}
        for ref_id in cited_ids:
            used_refs.add(ref_id)
            marker = references.get(ref_id, {}).get("marker")
            if ref_id not in source_refs or not isinstance(marker, str) or marker not in anchor:
                errors.append(f"{identity} 引文标记与冻结证据不对应: {ref_id}")
        if result_ids:
            result_sections.add(heading)
        for item in claim.get("statistics", []):
            result_id = item["result_id"]
            if result_id not in result_ids or not reported_value(item, results.get(result_id, {}), anchor):
                errors.append(f"{identity} 数字不在正文定位内或无法由锁定结果复算: {item.get('display')}")
        table_rows.append({"claim_id": identity, "sentence_id": heading, "claim_text": anchor,
                           "claim_type": kind, "paper_ids": [ref for ref in cited_ids if ref in papers],
                           "evidence_ids": source_ids, "result_ids": result_ids,
                           "scope_limit": claim.get("scope_limit"), "verification_status": "pending_review",
                           "paragraph_id": claim.get("paragraph_id")})
    if not used_refs or used_refs != set(references):
        errors.append("正文引文与参考文献台账须逐条对应")
    need_results = {"摘要"} | {row["heading"] for row in structure if {"R", "C"}.intersection(row["functions"])}
    if not need_results <= result_sections:
        errors.append("摘要、实证结果、结论均须绑定实际结果")
    if not any(row.get("statistics") for row in claims.values()):
        errors.append("缺少可与锁定模型输出复算的实证数字")
    checks = draft.get("checks", {})
    for entry in checklist:
        check = checks.get(entry["check_id"], {})
        if check.get("status") != "passed" or not present(check.get("evidence_or_note")):
            errors.append(f"{entry['check_id']} 未提交逐项复核依据: {entry['criterion']}")
    return {"abstract_characters": abstract_count, "body_characters": sum(counts.values()),
            "section_characters": counts, "target_by_function": dict(zip((s["id"] for s in profile["sections"]), budgets)),
            "structure": structure}, table_rows


def read_checklist(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def review(draft_subject, signoff_record, errors):
    return signoff(draft_subject, signoff_record, errors)
