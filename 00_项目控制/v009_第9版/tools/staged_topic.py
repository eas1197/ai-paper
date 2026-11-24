"""Two-stage evidence search and failure routing for the v3.2 candidate."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
VERSION = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "00_项目控制"
sys.path[:0] = [str(CONTROL / "v007_第7版/tools"),
                str(CONTROL / "v008_第8版/tools"),
                str(ROOT / "04_议题文献与现实/v012_第12版/tools")]
from native_library import registry
import run_mode
from topic32 import TASKS

REGISTRY = registry()
from abstract_acquisition import job_lock
from codex_literature import collect, evidence, group, url_event
from collect_common import digest, load, normalize, write
from native_receiving import receive
from method_paths import PATHS, select_method, verify_material_review
from event_protocol import OBSERVATION, validate_exchange
sys.path.append(str(CONTROL / "v012_第12版/tools"))
from review_gate_guard import require_original_review

POLICY = load(VERSION / "search_policy.json")
SCHEMA = ROOT / REGISTRY["modules"]["04"] / "templates/native_response.schema.json"
LIBRARY = ROOT / "潜在研究选题库.md"
ACADEMIC = {"concept": "S02", "value": "S03", "depth": "S06", "increment": "S05"}
REALITY_TASK = (
    "先用原生网页搜索观察日常社会生活。从新闻、公开讨论、采访、调查或文化现象比较线索；"
    "官方统计与政策用于核实，不以政策目标代替事实。标明个案、舆论、调查及可推广范围，"
    "提炼待解释的矛盾，再把探索线索交给学术初查。"
)
RESEARCH_TASK = (
    "用一个概念准确的问句提出核心问题。把研究情境、机制、假设或命题、实证设计分别陈述。"
    "从文献解释与理论反诘推导预期，说明作用条件、竞争解释、支持证据和反证。"
    "描述性或探索性研究可用命题或子问题。独立审查应核对现实来源、社会矛盾、问题单一性、"
    "推导是否成立、各项预期是否回答核心问题、数据是否实际可检验。"
)


def archive(case, library=LIBRARY):
    fields = {
        "core": "核心学术问题", "question": "具体研究问题", "value": "理论价值",
        "literature": "主要文献依据", "missing": "缺少数据", "access": "未来获取方式",
        "run": "运行编号", "review": "审查结论",
    }
    if any(not isinstance(case.get(key), str) or not case[key].strip() for key in fields):
        raise ValueError("Potential topic records require all archive fields")
    key = hashlib.sha256((normalize(case["core"]) + "|" + normalize(case["question"])).encode()).hexdigest()[:20]
    with job_lock(library.parent):
        current = library.read_text(encoding="utf-8") if library.exists() else "# 潜在研究选题库\n"
        marker = f"<!-- topic:{key} -->"
        if marker in current:
            return key
        section = [f"## {case['question']}", marker, ""]
        section.extend(f"- **{label}** {case[name]}" for name, label in fields.items())
        pending = library.with_suffix(".tmp")
        pending.write_text(current.rstrip() + "\n\n" + "\n".join(section) + "\n", encoding="utf-8")
        pending.replace(library)
    return key


def route(history, outcome):
    if outcome == "technical":
        return "retry_technical"
    if outcome == "materials_pending":
        return "materials_pending"
    if outcome == "missing_data":
        return "archived"
    if outcome in ACADEMIC:
        failures = sum(row["outcome"] in ACADEMIC for row in history)
        return "eliminated" if failures >= 2 else ACADEMIC[outcome]
    if outcome == "pass":
        return "passed"
    raise ValueError("Unknown outcome")


def init(run_id, mode, theme, *, full_paper=False):
    if mode == "dev":
        work = run_mode.start(run_id, theme, full_paper=full_paper)
        manifest = run_mode.verified_run(work)
        if sum(POLICY["dev"].values()) != manifest["workload"]["04"]["abstract_target"]:
            raise ValueError("Staged and global experimental totals differ")
    else:
        import re
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
            raise ValueError("Invalid run ID")
        work = VERSION / "runs_candidate" / run_id
        work.mkdir(parents=True, exist_ok=False)
    write(work / "staged_topic.json", {"run_id": run_id, "mode": mode, "theme": theme,
          "policy_sha256": digest(POLICY), "history": [], "status": "reality", "formal_eligible": False,
          "reality_first": True, "method_paths": True, "qual_search_receipts": True,
          "explanation_first": True, "issue_search": True})
    return work


def receipt(folder, journals=None):
    matrix = receive(folder, journals or POLICY["journals"])
    return matrix, load(folder / "checkpoint.json")


def issue_plan(work, state):
    plan = load(work / "issue_plan.json")
    if digest(plan) != state["issue_plan_sha256"]:
        raise ValueError("Sociological issue plan changed")
    return plan


def record_issue_plan(work, state, plan):
    if state["status"] != "issue_positioning":
        raise ValueError("Position the issue after the critical exchange")
    for key in ("issue", "why", "object_search", "issue_search", "theory_search"):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            raise ValueError("Explain issue placement and all three search layers")
    names = set(POLICY["journals"])
    for row in plan.get("specialist_journals", []):
        if (not all(isinstance(row.get(key), str) and row[key].strip()
                    for key in ("name", "publisher_url", "standing", "fit"))
                or not row["publisher_url"].startswith("https://") or row["name"] in names):
            raise ValueError("Added journals need separate standing, topical fit and official publisher evidence")
        names.add(row["name"])
    write_stage_once(work / "issue_plan.json", plan)
    state.update(status="initial", issue_plan_sha256=digest(plan))


def theories(folder, state):
    accepted = []
    for batch in state["batches"]:
        if batch["status"] != "completed":
            continue
        trace = evidence(folder / batch["batch"] / "events.jsonl")
        for note in batch["notes"]:
            parts = note.split("|", 3)
            if len(parts) == 4 and parts[0].strip() == "THEORY":
                _, title, url, claim = (s.strip() for s in parts)
                event = url_event(url, trace)
                if event and title and claim:
                    accepted.append({"title": title, "url": url, "claim": claim, "event_id": event})
    return accepted


def verify_automatic_event_inputs(work, state, *, comparison_required=True):
    """Read-only preflight for automation; retain pending facts, never promote them."""
    from event_protocol import (relative_receipt_path, validate_same_attempt,
                                build_source_receipts, compare_events)
    from codex_literature import web_url
    load_reality(work,state)
    if not comparison_required:
        return
    saved=load(work/"event_comparison.json")
    if saved.get("run_id")!=state["run_id"] or saved.get("reality_sha256")!=state["reality_sha256"]:
        raise ValueError("Original event comparison is bound to another run or reality")
    if state.get("event_comparison_sha256") and digest(saved)!=state["event_comparison_sha256"]:
        raise ValueError("Original pre-search evidence changed: event_comparison.json")
    execution=saved.get("execution_receipt",{})
    for key in ("response_path","events_path","response_sha256","events_sha256","thread_id"):
        if not execution.get(key):
            raise ValueError("Original event source receipts incomplete: "+key)
    response=work/execution["response_path"]
    events=work/execution["events_path"]
    relative_receipt_path(response,work)
    relative_receipt_path(events,work)
    validate_same_attempt(response,events)
    if (hashlib.sha256(response.read_bytes()).hexdigest()!=execution["response_sha256"]
            or hashlib.sha256(events.read_bytes()).hexdigest()!=execution["events_sha256"]):
        raise ValueError("Original event raw receipt changed")
    threads=[row.get("thread_id") for row in
             (json.loads(line) for line in events.read_text(encoding="utf-8-sig").splitlines())
             if row.get("type")=="thread.started"]
    if threads!=[execution["thread_id"]]:
        raise ValueError("Original event thread receipt changed")
    packet=load(response)
    if digest(packet)!=saved.get("input_sha256"):
        raise ValueError("Original event input digest changed")
    trace=evidence(events)
    receipts=build_source_receipts(packet,trace,work=work,events_path=events,response_path=response,
        thread_id=threads[0],url_event_fn=url_event,canonicalize=web_url)
    rebuilt=compare_events(packet,receipts,canonicalize=web_url,execution=execution)
    if any(saved.get(key)!=value for key,value in rebuilt.items()):
        raise ValueError("Original event comparison differs from raw receipts")
    if rebuilt["event_count"]<2 or rebuilt["source_verification_status"]!="verified":
        raise ValueError("Original event source receipts incomplete; stop automatic advancement")


def search(work, state, phase, resume, *, budget_migration=None):
    allowed = "initial" if phase == "initial" else "supplemental"
    if state["status"] != allowed:
        raise ValueError("Search not authorized in this state; reuse existing evidence during revisions")
    if state.get("issue_search"):
        verify_automatic_event_inputs(work,state)
        if digest(load(work/"explanation_exchange.json"))!=state.get("exchange_sha256"):
            raise ValueError("Original pre-search explanation or challenge changed")
    first = work / "initial"
    initial = load(first / "literature_matrix.json") if phase == "supplemental" else None
    folder = work / phase
    manifest = run_mode.verified_run(work) if state["mode"] == "dev" else None
    budget = manifest["workload"]["11"] if manifest else {}
    limit = POLICY[state["mode"]][phase]
    plan = issue_plan(work, state) if state.get("issue_search") else None
    journals = [*POLICY["journals"], *(row["name"] for row in plan.get("specialist_journals", []))] if plan else POLICY["journals"]
    theme = state.get("question", state["theme"]) if initial else state["theme"]
    if initial:
        theme = "补查：" + theme
    else:
        if state.get("reality_first"):
            observation = load_reality(work, state)
            theme += "；现实线索：" + observation["search_focus"]
        if state.get("explanation_first"):
            exchange = load(work / "explanation_exchange.json")
            if digest(exchange) != state["exchange_sha256"]:
                raise ValueError("Pre-search explanation or challenge changed")
            theme += "；比较候选解释与反诘提出的机制：" + exchange["search_focus"]
        theme = "初查：" + theme + "。同时单列经典理论与权威解释。"
    if plan:
        theme = state.get("question", state["theme"])
    config = {"theme": theme, "target": limit, "topic_search_phase": phase,
              "journals": journals, "max_batches": budget.get("max_batches", 3),
              "timeout_seconds": budget.get("timeout_seconds", 720),
              "excluded_titles": [row["title"] for row in initial["rows"]] if initial else []}
    if plan:
        config["search_guidance"] = {
            **plan, "candidate_question": load(work / "explanation_exchange.json")["candidate_question"],
        }
    if manifest:
        config.update(run_mode="dev", search_action_budget=budget["native_search_actions"],
                      workload_sha256=manifest["workload_sha256"], topic_batch_budget=True,
                      max_batches=run_mode.load(run_mode.CONTROL / "dev_profile.json")["11"]["topic_batches_per_phase"])
    original_rows = []
    if initial:
        initial, original = receipt(first, journals)
        if digest(initial) != state["initial_sha256"]:
            raise ValueError("Initial evidence changed after review")
        ids = {row["observation_id"] for paper in initial["rows"][:POLICY[state["mode"]]["initial"]]
               for row in paper["provenance"]}
        original_rows = [row for row in original["observations"] if row["observation_id"] in ids]
    bundle = collect(config, folder, VERSION / "search_prompt.txt", SCHEMA, resume=resume,
                     budget_migration=budget_migration,
                     initial_observations=original_rows if config.get("topic_batch_budget") else ())
    matrix, checkpoint = receipt(folder, journals)
    if plan:
        write(folder / "journal_tiers.json", {
            "core_nine": [row["article_id"] for row in matrix["rows"] if row["journal"] in POLICY["journals"]],
            "specialist": [row["article_id"] for row in matrix["rows"] if row["journal"] not in POLICY["journals"]],
        })
    if phase == "initial":
        theory_rows = theories(folder, checkpoint)
        write(folder / "theories.json", theory_rows)
        count = matrix["verified_rows"]
        ready = count >= limit and bool(theory_rows)
    else:
        # Two independent collectors reuse batch names; scope these IDs before cross-stage merging.
        scoped = [dict(row, observation_id="supplemental:" + row["observation_id"])
                  for row in checkpoint["observations"]]
        merged, conflicts = group([*original_rows, *scoped])
        count = len(merged)
        ready = count >= sum(POLICY[state["mode"]].values())
        if ready and bundle["status"] != "experimental_budget_exceeded":
            write(work / "merged_literature.json", {"rows": merged, "conflicts": conflicts,
                  "initial_sha256": digest(initial), "supplemental_sha256": digest(matrix)})
    if ready and bundle["status"] != "experimental_budget_exceeded":
        state["status"] = "preliminary_review" if phase == "initial" else "final_review"
    state["latest_search"] = {"phase": phase, "verified_count": count,
                              "collection_sha256": matrix["collection_sha256"]}
    return {"phase": phase, "count": count, "status": state["status"], "collection_status": bundle["status"]}


def literature_next(checkpoint, count, target):
    config = checkpoint["config"]
    skipped = set(checkpoint.get("login_preflight_only_batches", []))
    batches = [row for row in checkpoint["batches"] if row["batch"] not in skipped]
    remaining = max(0, config["max_batches"] - len(batches))
    events = sum(row.get("search_events", 0) for row in batches)
    budget = config.get("search_action_budget")
    exhausted = remaining == 0 or (not config.get("topic_batch_budget") and budget is not None and events >= budget)
    if count >= target:
        action = "verify"
    elif exhausted:
        action = "stop"
    else:
        action = "resume_deficit"
    return {"action": action, "count": count, "target": target, "deficit": max(0, target - count),
            "batch_limit": config["max_batches"], "used_batches": len(batches), "remaining_batches": remaining,
            "recorded_search_events": events, "search_action_budget": budget}


def advance(work, state):
    phase = state["status"]
    if phase == "literature_budget_exhausted":
        prior = state["stop_decision"]
        phase = prior["phase"]
        folder = work / phase
        checkpoint = load(folder / "checkpoint.json")
        limit = run_mode.load(run_mode.CONTROL / "dev_profile.json")["11"]["topic_batches_per_phase"]
        if state["mode"] != "dev" or checkpoint["config"]["max_batches"] >= limit:
            return {"action": "already_stopped", "status": state["status"], "decision": prior}
        matrix, _ = receipt(folder, checkpoint["config"]["journals"])
        if (digest(checkpoint) != prior["checkpoint_sha256"]
                or matrix["collection_sha256"] != prior["collection_sha256"]):
            raise ValueError("Prior checkpoint or verified literature differs from the stop record")
        state["status"] = phase
        state["budget_resume"] = {"phase": phase, "prior_stop": prior, "new_batch_limit": limit}
        write(work / "staged_topic.json", state)
    if phase not in {"initial", "supplemental"}:
        return {"action": "wait_for_stage_input", "status": phase}
    folder = work / phase
    checkpoint_path = folder / "checkpoint.json"
    if not checkpoint_path.exists():
        result = search(work, state, phase, False)
        if state["status"] != phase or state["mode"] != "dev":
            return result
    checkpoint = load(checkpoint_path)
    config = checkpoint["config"]
    if state["mode"] == "dev" and not config.get("topic_batch_budget"):
        migration = state.get("budget_resume", {}).get("prior_stop", {})
        if migration.get("checkpoint_sha256") != digest(checkpoint):
            raise ValueError("Legacy continuation requires the verified prior stop record")
        result = search(work, state, phase, True, budget_migration=digest(checkpoint))
        if state["status"] != phase:
            return result
        checkpoint = load(checkpoint_path)
        config = checkpoint["config"]
    result = load(folder / "abstract_collection.json")
    catalog, _ = receipt(folder, config["journals"])
    count = catalog["verified_rows"]
    assessed = state.get("latest_search", {})
    if (phase == "supplemental" and assessed.get("phase") == phase
            and assessed.get("collection_sha256") == catalog["collection_sha256"]):
        count = assessed["verified_count"] - POLICY[state["mode"]]["initial"]
    decision = literature_next(checkpoint, max(0, count), config["target"])
    decision.update(phase=phase, origin="controller", collection_id=result["collection_id"],
                    collection_sha256=catalog["collection_sha256"],
                    checkpoint_sha256=digest(checkpoint))
    if checkpoint["batches"] and checkpoint["batches"][-1]["status"] == "failed":
        decision.update(action="retry_technical", failure=checkpoint["batches"][-1]["failure"])
    elif result["status"] == "experimental_budget_exceeded":
        decision.update(action="stop", failure_kind="resource_limit",
                        reason="Recorded search events exceeded the experimental budget")
        state["status"] = "literature_budget_exhausted"
        state["stop_decision"] = decision
    elif decision["action"] == "verify" and phase == "initial" and not load(folder / "theories.json"):
        decision.update(action="wait_for_theory_evidence", failure_kind="unverified_evidence")
    elif decision["action"] == "stop":
        state["status"] = "literature_budget_exhausted"
        decision["failure_kind"] = "resource_limit"
        decision["reason"] = "Effective literature target not reached within the remaining batch and search limits"
        decision["unverified_count"] = len(result.get("unverified", []))
        state["stop_decision"] = decision
    elif decision["action"] == "resume_deficit":
        decision["collection"] = search(work, state, phase, True)
        if state["status"] == phase and state["mode"] == "dev":
            state.setdefault("autonomous_steps", []).append(decision)
            write(work / "staged_topic.json", state)
            return advance(work, state)
    state.setdefault("autonomous_steps", []).append(decision)
    return decision


def review(work, state, report, *, review_intake=None):
    require_original_review(work, intake=review_intake)
    if state["status"] not in {"preliminary_review", "design_review", "final_review", "materials_pending", *ACADEMIC.values()}:
        raise ValueError("No academic review is due")
    final = state["status"] == "final_review" or state.get("review_phase") == "final"
    source = work / ("merged_literature.json" if final else "initial/literature_matrix.json")
    theory = work / "initial/theories.json"
    if (report.get("model") != "gpt-6.2-sol" or not report.get("invocation_id")
            or report["evidence_sha256"] != evidence_hash(work, state, source, theory)
            or not report.get("reason") or not report.get("question")):
        raise ValueError("Review must bind evidence and state a substantive reason")
    if any(row["invocation_id"] == report["invocation_id"] for row in state["history"]):
        raise ValueError("Duplicate review invocation")
    outcome = report["outcome"]
    if outcome in {"pass", "academic_pass", "missing_data", "materials_pending"} and report.get("academic_value") != "pass":
        raise ValueError("An explicit academic value pass is required")
    if state.get("reality_first") and outcome in {"pass", "missing_data"}:
        packet = report.get("research_case", {})
        if (not isinstance(packet, dict) or packet.get("core_question") != report["question"]
                or not packet.get("context")):
            raise ValueError("Attach the reviewed question, context and theory-derived expectations")
        expectations = packet.get("hypotheses_or_propositions")
        if (not isinstance(expectations, list) or not expectations
                or not all(isinstance(item, str) and item.strip() for item in expectations)):
            raise ValueError("Attach nonempty hypotheses, propositions or research subquestions")
    if outcome == "pass" and report.get("data_feasibility") != "pass":
        raise ValueError("Data feasibility must pass before additional search or freeze")
    if outcome == "academic_pass":
        if final or state["status"] == "design_review":
            raise ValueError("Academic-only approval belongs to the initial topic review")
        state["history"].append(report)
        state["question"] = report["question"]
        state["status"] = "design_review"
        return
    method = None
    if state.get("method_paths") and outcome in {"pass", "missing_data", "materials_pending"}:
        method = select_method(report.get("method_assessment"), outcome)
        if state.get("qual_search_receipts"):
            paths = report["method_assessment"]["paths"]
            for path in ("secondary_interviews", "online_qualitative"):
                verify_material_review(work, path, paths[path], report["question"])
    if outcome == "missing_data":
        if report.get("data_feasibility") != "blocked":
            raise ValueError("Missing-data classification requires a data blocker")
        case = report["archive"]
        if case.get("run") != state["run_id"] or case.get("question") != report["question"]:
            raise ValueError("Archive must describe the reviewed question in this run")
        state["library_key"] = archive(case)
    result = route(state["history"], outcome)
    state["history"].append(report)
    state["review_phase"] = "final" if final else "initial"
    state["question"] = report["question"]
    if result == "passed":
        if method:
            state["research_method"] = method
        state["status"] = "s08_ready" if final else "supplemental"
        if not final:
            state["initial_sha256"] = digest(load(source))
    elif result != "retry_technical":
        state["status"] = result


def _reviewed_freeze_payload(work, state):
    """Single original source for the reviewed freeze payload."""
    evidence_sha = evidence_hash(work, state, work / "merged_literature.json",
                                 work / "initial/theories.json")
    history = state.get("history", [])
    final = history[-1] if history else {}
    if (state.get("review_phase") != "final" or final.get("outcome") != "pass"
            or final.get("academic_value") != "pass" or final.get("data_feasibility") != "pass"
            or final.get("model") != "gpt-6.2-sol" or not final.get("invocation_id")
            or not final.get("reason")):
        raise ValueError("S08 requires the original final positive independent review record")
    if final["evidence_sha256"] != evidence_sha or final["question"] != state["question"]:
        raise ValueError("Reviewed question or evidence changed")
    design = final.get("design")
    if not isinstance(design, str) or not design.strip():
        raise ValueError("S08 requires a reviewed study design")
    method = state.get("research_method")
    if state.get("method_paths") and method != select_method(final.get("method_assessment"), "pass"):
        raise ValueError("Reviewed design and method handoff do not match")
    if state.get("qual_search_receipts") and method["path"] != "quantitative":
        path = method["path"]
        verify_material_review(work, path, final["method_assessment"]["paths"][path], final["question"])
    return {"stage": "S08", "question": final["question"], "design": design,
          "research_case": final.get("research_case"),
          "research_method": method,
          "evidence_sha256": evidence_sha, "review_sha256": digest(final), "mode": state["mode"],
          "formal_eligible": False, "scope": "experimental" if state["mode"] == "dev" else "formal_candidate"}


def freeze(work, state):
    if state["status"] != "s08_ready":
        raise ValueError("A final positive independent review is required")
    write_stage_once(work / "s08_topic.json", _reviewed_freeze_payload(work, state))
    state["status"] = "frozen"


def verified_frozen_topic(work, state):
    """Read-only original freeze verification for the post-S08 handoff."""
    if state["status"] != "frozen":
        raise ValueError("Original S08 is not frozen")
    if state.get("run_id") != work.name or state.get("policy_sha256") != digest(POLICY):
        raise ValueError("Frozen run identity or policy changed")
    frozen = load(work / "s08_topic.json")
    if frozen != _reviewed_freeze_payload(work, state):
        raise ValueError("Original S08 frozen payload differs from reviewed inputs")
    method = frozen.get("research_method")
    if not isinstance(method, dict) or method.get("path") not in PATHS:
        raise ValueError("Frozen method missing or unsupported")
    return frozen


def load_reality(work, state):
    packet = load(work / "reality.json")
    if digest(packet) != state["reality_sha256"]:
        raise ValueError("Reality evidence changed")
    return packet


def write_stage_once(path, value):
    """Preserve an original single-stage product across interrupted state publication."""
    if path.exists():
        if path.is_symlink() or load(path)!=value:
            raise ValueError("Preserve existing original stage artifact: "+path.name)
    else:
        write(path,value)


def record_reality(work, state, packet):
    if state["status"] != "reality":
        raise ValueError("Reality evidence is already recorded for this run")
    if not packet.get("phenomenon") or not packet.get("search_focus") or not packet.get("sources"):
        raise ValueError("Supply a phenomenon, literature search focus and traceable reality sources")
    for source in packet["sources"]:
        if not all(source.get(key) for key in ("url", "kind", "supports", "limits")):
            raise ValueError("Record the source and its limits")
    write_stage_once(work / "reality.json", packet)
    state["reality_sha256"] = digest(packet)
    state["status"] = "explanation_exchange" if state.get("explanation_first") else "initial"


def evidence_hash(work, state, path, theory):
    evidence = {"papers": load(path), "theories": load(theory)}
    if state.get("reality_first"):
        evidence["reality"] = load_reality(work, state)
    if state.get("explanation_first"):
        exchange = load(work / "explanation_exchange.json")
        if digest(exchange) != state["exchange_sha256"]:
            raise ValueError("Pre-search explanation or challenge changed")
        evidence["explanation_exchange"] = exchange
    if state.get("issue_search"):
        evidence["issue_plan"] = issue_plan(work, state)
        comparison = load(work / "event_comparison.json")
        if digest(comparison) != state["event_comparison_sha256"]:
            raise ValueError("Pre-search event comparison changed")
        evidence["event_comparison"] = comparison
    return digest(evidence)


def prepare(work, state):
    status = state["status"]
    final = status == "final_review" or state.get("review_phase") == "final"
    path = work / ("merged_literature.json" if final else "initial/literature_matrix.json")
    theory = work / "initial/theories.json"
    task = {"status": status, "theme": state["theme"], "question": state.get("question"),
            "existing_v32_tasks": TASKS, "revision_uses_existing_evidence": True}
    task["review_scope"] = {
        "preliminary_review": "先审查问题的学术价值；证据可得性尚待检查时，可用 academic_pass 保留该判断，转入研究设计。命题是否成立留待经验分析。",
        "design_review": "审查能否取得真实、可核验且适用的证据；区分待查证据与确认不可得。",
        "final_review": "审查学术增量、经核实的可行性与设计，不要求经验解释已成立。",
    }.get(status, "经验阶段才检验解释成立与否；结论不得超出材料。")
    if state.get("reality_first"):
        task.update(reality_task=REALITY_TASK, research_and_review_task=RESEARCH_TASK)
        if status != "reality":
            task["reality"] = load_reality(work, state)
    if state.get("explanation_first"):
        task["observation_instruction"] = OBSERVATION
        task["critical_instruction"] = "反方质疑解释的前提、找反例与竞争机制，可以提出独立候选题。独立审查另做学术判断与放行。"
        if state.get("exchange_sha256"):
            task["exchange"] = load(work / "explanation_exchange.json")
            task["theory_dialogue_instruction"] = (
                "比较已读文献如何解释当前事件、自主解释与反方机制在何处一致或分歧、"
                "各自尚不能回答什么。再次提出解释与反诘，允许产生独立候选。"
                "说明选择何种社会学视角以及理由，把行动、结构或两者关系落实为可区分机制。"
                "指出何种证据能区分解释；零命中不能证明创新。沿用初查材料及原返修上限。"
            )
    if state.get("issue_search"):
        task["issue_positioning_instruction"] = (
            "先确定社会学议题与学术传统及归属理由；对象层定位近邻，议题层寻找可迁移机制，"
            "理论层查经典原著。新增专业刊说明地位、适配性及出版方，避免为数量扩刊。"
        )
        if state.get("issue_plan_sha256"):
            task["issue_plan"] = issue_plan(work, state)
    if state.get("method_paths"):
        task["research_method_options"] = PATHS
        task["research_method_instruction"] = (
            "先按问题选择方法，可直接选择定性。分别说明三条路径的适用性与材料状况。"
            "定性使用理论框架、命题、案例与材料设计；定量使用假设和统计设计。"
            "量化不可行时检查适用的访谈与网络材料。所有适用路径材料确实不足才归档。"
        )
    if path.is_file() and theory.is_file():
        task["evidence_sha256"] = evidence_hash(work, state, path, theory)
        task["papers"] = str(path)
        task["theories"] = str(theory)
    return task


def verify_stage_artifacts(work, state, operation, *, prior_stage=None):
    """Check actual native products before publishing an original stage transition.

    Integrity only: neither pending source receipts nor a technical result is a
    scholarly pass. Uses the original canonical digest and native receiver.
    """
    def checked(name, key):
        value=load(work/name)
        if digest(value)!=state.get(key):
            raise ValueError("Original stage artifact hash changed: "+name)
        return value
    if operation=="reality":
        checked("reality.json","reality_sha256")
        if state["status"]!=("explanation_exchange" if state.get("explanation_first") else "initial"):
            raise ValueError("Original reality transition inconsistent")
    elif operation=="exchange":
        checked("reality.json","reality_sha256")
        validate_exchange(checked("explanation_exchange.json","exchange_sha256"))
        if state.get("issue_search"):
            comparison=checked("event_comparison.json","event_comparison_sha256")
            if (comparison.get("run_id")!=work.name or comparison.get("reality_sha256")!=state["reality_sha256"]
                    or comparison.get("event_count",0)<2):
                raise ValueError("Original event comparison is inconsistent")
            for path_key,sha_key in (("input_path","response_sha256"),("events_path","events_sha256")):
                if comparison.get(sha_key) is not None:
                    raw=(work/comparison[path_key]).resolve(strict=True)
                    if not raw.is_relative_to(work.resolve()) or hashlib.sha256(raw.read_bytes()).hexdigest()!=comparison[sha_key]:
                        raise ValueError("Original event raw receipt changed")
        if state["status"]!=("issue_positioning" if state.get("issue_search") else "initial"):
            raise ValueError("Original exchange transition inconsistent")
    elif operation=="issue":
        issue_plan(work,state)
        if state["status"]!="initial":
            raise ValueError("Original issue transition inconsistent")
    elif operation in {"initial","supplemental","advance"}:
        phase=operation if operation!="advance" else prior_stage
        latest=state.get("latest_search",{})
        if phase=="literature_budget_exhausted":
            phase=latest.get("phase")
        if phase not in {"initial","supplemental"}:
            return
        if latest.get("phase")!=phase:
            raise ValueError("Original literature phase result missing or inconsistent")
        folder=work/phase
        checkpoint=load(folder/"checkpoint.json")
        matrix=receive(folder,checkpoint["config"]["journals"],persist=False)
        if (matrix!=load(folder/"literature_matrix.json")
                or matrix["collection_sha256"]!=latest.get("collection_sha256")):
            raise ValueError("Original literature matrix or collection changed")
        expected="preliminary_review" if phase=="initial" else "final_review"
        if state["status"] not in {phase,expected,"literature_budget_exhausted"}:
            raise ValueError("Original literature transition inconsistent")
        if phase=="initial":
            if load(folder/"theories.json")!=theories(folder,checkpoint):
                raise ValueError("Original theory receipt changed")
        if phase=="supplemental" and state["status"]==expected:
            initial_folder=work/"initial"
            initial=receive(initial_folder,checkpoint["config"]["journals"],persist=False)
            if (initial!=load(initial_folder/"literature_matrix.json") or digest(initial)!=state.get("initial_sha256")):
                raise ValueError("Original initial literature changed")
            original=load(initial_folder/"checkpoint.json")
            ids={row["observation_id"] for paper in initial["rows"][:POLICY[state["mode"]]["initial"]]
                 for row in paper["provenance"]}
            rows=[row for row in original["observations"] if row["observation_id"] in ids]
            scoped=[dict(row,observation_id="supplemental:"+row["observation_id"]) for row in checkpoint["observations"]]
            merged,conflicts=group([*rows,*scoped])
            expected_merged={"rows":merged,"conflicts":conflicts,"initial_sha256":digest(initial),
                             "supplemental_sha256":digest(matrix)}
            if load(work/"merged_literature.json")!=expected_merged:
                raise ValueError("Original merged literature changed")
    elif operation=="s08":
        verified_frozen_topic(work,state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "reality", "exchange", "issue", "initial", "supplemental", "advance", "review", "prepare", "status", "s08"))
    parser.add_argument("run_id")
    parser.add_argument("--mode", choices=("dev", "formal"), default="dev")
    parser.add_argument("--theme")
    parser.add_argument("--full-paper", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.full_paper and (args.command != "init" or args.mode != "dev"):
        parser.error("--full-paper is only accepted when initializing an experimental run")
    if args.command == "init":
        if not args.theme:
            parser.error("--theme is required")
        print(init(args.run_id, args.mode, args.theme, full_paper=args.full_paper))
        return
    base = run_mode.RUNS if args.mode == "dev" else VERSION / "runs_candidate"
    work = (base / args.run_id).resolve()
    if work.parent != base.resolve():
        raise ValueError("Run escapes its namespace")
    if args.mode == "dev":
        run_mode.verified_run(work)
    state_path = work / "staged_topic.json"
    with job_lock(work):
        state = load(state_path)
        if state["policy_sha256"] != digest(POLICY) or state["mode"] != args.mode or state["run_id"] != args.run_id:
            raise ValueError("Staged policy or run identity changed")
        prior_stage = state["status"]
        result = None
        if args.command in ("initial", "supplemental"):
            if state["mode"] == "dev" and state["status"] == args.command:
                result = advance(work, state)
            else:
                result = search(work, state, args.command, args.resume)
        elif args.command == "advance":
            result = advance(work, state)
        elif args.command == "review":
            review(work, state, load(args.report))
        elif args.command == "reality":
            record_reality(work, state, load(args.report))
        elif args.command == "exchange":
            if state["status"] != "explanation_exchange":
                raise ValueError("Record the exchange after reality and before literature")
            packet = load(args.report)
            validate_exchange(packet)
            if state.get("issue_search"):
                comparison = load(work / "event_comparison.json")
                if comparison["event_count"] < 2 or comparison["reality_sha256"] != state["reality_sha256"]:
                    raise ValueError("Compare independent events before generating candidate questions")
                state["event_comparison_sha256"] = digest(comparison)
            if not isinstance(packet.get("search_focus"), str) or not packet["search_focus"].strip():
                raise ValueError("State the literature search focus")
            write_stage_once(work / "explanation_exchange.json", packet)
            state["exchange_sha256"] = digest(packet)
            state["status"] = "issue_positioning" if state.get("issue_search") else "initial"
        elif args.command == "issue":
            record_issue_plan(work, state, load(args.report))
        elif args.command == "s08":
            freeze(work, state)
        elif args.command == "prepare":
            result = prepare(work, state)
        if args.command not in {"status", "prepare"}:
            verify_stage_artifacts(work,state,args.command,prior_stage=prior_stage)
            write(state_path, state)
    print(json.dumps(result or state, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
