"""Require a source-linked critique of why each proposed question matters."""
from __future__ import annotations

from runtime import indexed, present, refs, require_fields, valid_date
from providers import norm

DIMENSIONS = {
    "reality": ("population", "observation", "baseline", "scope"),
    "theory": ("existing_explanation", "unresolved_prediction", "contribution"),
    "practice": ("user", "decision", "consequence"),
    "policy": ("policy_objective", "implementation_problem", "decision", "boundary"),
}
PROMPT = (
    "候选形成后，逐题反问。现实意义：哪群人在何时何地遇到什么，依据、比较基线和后果是什么？"
    "理论意义：就哪条既有解释，哪两种答案可改变结论？实际意义：哪个人或机构会据此改变哪项判断或行动？"
    "政策意义：对应什么政策目标、执行矛盾和取舍？仅在缺直接政策用途且实事求是说明边界时填bounded。"
    "进一步检验用途：与较简单的对照题相比，这道题带来什么额外信息？"
    "分别说明哪类证据支持预期答案、支持竞争答案，以及区间表明差异可忽略或证据不足时各怎么判断。"
    "把学刊范例的发问动作改写到本研究，用04的证据论证；范例本身只用于学习。"
    "答不出、无需区分就能预知或只有泛泛口号时退回重构；允许零题合格。"
)


def audit(bundle, candidates, up_bundle, evidence, errors, feedback):
    selection = bundle.get("question_selection", {})
    examples = {r["paper_id"] for r in selection.get("examples", [])}
    examples.update(r["paper_id"] for r in selection.get("topic_cards", []))
    if not examples:
        errors.append("G5缺少锁定的五刊提问学习资源")
    reviews = indexed(bundle.get("significance_reviews", []), "candidate_id", errors)
    if set(reviews) - set(candidates):
        errors.append("意义审查包含无对应候选的问题")
    policy_ids = {eid for row in up_bundle["contexts"] if row.get("type") == "policy"
                  for eid in row.get("evidence_ids", [])}
    status_counts = {"pass": 0, "revise": 0, "reject": 0, "missing": 0}
    expected = {"accepted": "pass", "needs_evidence": "revise", "rejected": "reject"}
    for cid, candidate in candidates.items():
        start = len(errors)
        label = f"{cid} 选题意义审查"
        review = reviews.get(cid, {})
        decision = review.get("decision")
        if decision not in ("pass", "revise", "reject") or decision != expected.get(candidate.get("status")):
            errors.append(f"{label}: 必须记录与候选处置一致的pass、revise或reject")
        require_fields(review, ("reason", "reviewer"), label, errors)
        if not valid_date(review.get("reviewed_at")):
            errors.append(f"{label}: 缺少有效审查日期")
        checks = review.get("dimensions", {})
        for dimension, fields in DIMENSIONS.items():
            item = checks.get(dimension, {})
            name = f"{label}/{dimension}"
            policy_bound = dimension == "policy" and item.get("status") == "bounded"
            if item.get("status") not in ("supported", "insufficient", "bounded") or (item.get("status") == "bounded" and not policy_bound):
                errors.append(f"{name}: 缺少有效的逐项判断")
            require_fields(item, ("assessment",), name, errors)
            if candidate.get("status") != "accepted":
                continue
            if policy_bound:
                require_fields(item, ("boundary",), name, errors)
                refs(item.get("evidence_ids", []), evidence, name, errors, required=False)
                continue
            if item.get("status") != "supported":
                errors.append(f"{name}: 拟接受的问题需要具体且有证据的判断")
                continue
            require_fields(item, fields, name, errors)
            linked = refs(item.get("evidence_ids"), evidence, name, errors)
            if not any(e.get("evidence_class") == "direct" for e in linked):
                errors.append(f"{name}: 缺少直接证据锚点")
            if dimension == "policy" and not any(e.get("evidence_id") in policy_ids for e in linked):
                errors.append(f"{name}: 政策判断须回到04的政策原文证据")
        if candidate.get("status") == "accepted":
            use = review.get("answer_use", {})
            require_fields(use, ("simpler_question", "added_information", "evidence_needed", "expected_answer",
                                 "if_expected", "competing_answer", "if_competing",
                                 "if_negligible", "if_inconclusive"), label + "/用途", errors)
            if any(present(use.get(a)) and norm(use.get(a)) == norm(use.get(b)) for a, b in (
                ("if_expected", "if_competing"), ("expected_answer", "competing_answer"),
                ("if_negligible", "if_inconclusive")
            )):
                errors.append(f"{label}: 必须区分两种答案的用途，以及可忽略差异与证据不足")
            transfers = review.get("example_transfers", [])
            if not transfers:
                errors.append(f"{label}: 缺少五刊范例的发问动作及迁移说明")
            for transfer in transfers:
                require_fields(transfer, ("paper_id", "borrowed_move", "adaptation", "scope_limit"), label, errors)
                if transfer.get("paper_id") not in examples:
                    errors.append(f"{label}: 范例须来自本轮已核选题范例")
            if len(errors) == start:
                status_counts["pass"] += 1
        elif decision == "revise":
            require_fields(review, ("next_step",), label, errors)
            feedback.append({"kind": "question_significance", "candidate_id": cid,
                             "request": review.get("next_step") or "补齐选题意义与用途依据", "evidence_ids": []})
        if decision in ("revise", "reject"):
            status_counts[decision] += 1
        if not review or len(errors) > start:
            status_counts["missing"] += 1
    return status_counts
