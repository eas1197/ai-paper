"""Validate the literature-to-control decision log before freezing G5."""
from runtime import indexed, present, require_fields

BASELINE = ("age", "sex", "education", "marital_status", "residence", "hukou", "employment", "economic_resources")
DECISIONS = {"primary", "sensitivity_only", "focal", "exclude", "unavailable"}
RISK_POSITIONS = {"mediator", "collider", "post_exposure", "outcome_proxy"}


def audit_control_plan(design, measurements, evidence, documents, errors):
    plan = design.get("control_plan") or {}
    require_fields(plan, ("unit", "unit_rationale"), "控制变量台账", errors)
    if plan.get("unit") not in {"individual", "household", "aggregate", "other"}:
        errors.append("控制变量台账须声明分析单位")
    decisions = indexed(plan.get("decisions", []), "concept", errors)
    models = plan.get("literature_models", [])
    if not models:
        errors.append("控制变量台账须回查同类定量全文的模型表或变量说明")
    if plan.get("unit") == "individual":
        errors.extend(f"人口学候选缺少逐项审查: {key}" for key in BASELINE if key not in decisions)
    for model in models:
        require_fields(model, ("paper_id", "evidence_id", "table_or_section", "comparability", "controls"), "同类模型", errors)
        anchor = evidence.get(model.get("evidence_id"), {})
        if (anchor.get("paper_id") != model.get("paper_id")
                or anchor.get("evidence_class") != "direct"
                or documents.get(anchor.get("document_id"), {}).get("kind") != "fulltext"):
            errors.append("同类模型须绑定该篇全文中的直接证据")
        for concept in model.get("controls", []):
            if concept not in decisions:
                errors.append(f"文献控制候选尚无处置: {concept}")
    allocated = set()
    for concept, row in decisions.items():
        require_fields(row, ("label", "decision", "causal_position", "reason"), concept, errors)
        decision, variable = row.get("decision"), row.get("variable_id")
        if decision not in DECISIONS:
            errors.append(f"{concept}: 控制候选处置无效")
        if decision in {"primary", "sensitivity_only", "focal"}:
            measurement = measurements.get(variable, {})
            allowed = {"X", "Y", "M", "Z"} if decision == "focal" else {"control"}
            if measurement.get("role") not in allowed:
                errors.append(f"{concept}: 缺少已核问卷映射或变量角色冲突")
        if decision in {"primary", "sensitivity_only"}:
            allocated.add(variable)
        if decision == "primary" and row.get("causal_position") in RISK_POSITIONS:
            errors.append(f"{concept}: 该变量的因果位置与主控制集冲突")
        if concept in {"age", "sex"} and plan.get("unit") == "individual":
            if decision in {"exclude", "unavailable", "sensitivity_only"} and not present(row.get("baseline_exception")):
                errors.append(f"{concept}: 个体模型未纳入基本人口学变量，须说明具体例外")
    if allocated != {key for key, row in measurements.items() if row.get("role") == "control"}:
        errors.append("已冻结控制变量与台账纳入项不一致")
