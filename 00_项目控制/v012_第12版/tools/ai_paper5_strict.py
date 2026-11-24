"""ai-paper 5.0 strict v3.x heritage router and Chat-native literature audit.

Never use v010/v011 loose literature acceptance instead of the original 3.x
academic engine. Chat receipts are separately labelled, not forged Codex events.
"""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[3]
CONTROL = ROOT / "00_项目控制"
V32 = CONTROL / "v009_第9版"
V3_TOPIC = V32 / "tools/staged_topic.py"
V3_EVENTS = V32 / "tools/event_protocol.py"
V3_POLICY = V32 / "search_policy.json"
V3_SEARCH_PROMPT = V32 / "search_prompt.txt"
NATIVE_SEARCH = ROOT / "04_议题文献与现实/v012_第12版/tools/native_library.py"
NATIVE_COLLECTOR = ROOT / "11_文献采集适配/v007_第7版/tools/codex_literature.py"
NATIVE_PROMPT = ROOT / "04_议题文献与现实/v012_第12版/templates/search_prompt.txt"
NATIVE_SCHEMA = ROOT / "04_议题文献与现实/v012_第12版/templates/native_response.schema.json"
MATERIAL = ROOT / "06_数据方法与分析/v005_第5版/tools/qual_materials.py"
MATERIAL_REPAIR = ROOT / "06_数据方法与分析/v005_第5版/tools/repair_materials.py"
MATERIAL_ADEQUACY = V32 / "tools/material_adequacy.py"
REVISION = V32 / "tools/resume_writing.py"
V15 = ROOT / "07_三稿独立写作/v015_第15版/tools/writing_plan.py"
V16 = ROOT / "07_三稿独立写作/v016_第16版/tools/ai_writer4.py"
RUNS = CONTROL / "v007_第7版/runs_dev"
REQUIRED = {
    "topic_v32": V3_TOPIC, "event_comparison": V3_EVENTS,
    "policy_v32": V3_POLICY, "search_prompt_v32": V3_SEARCH_PROMPT,
    "native_search": NATIVE_SEARCH, "codex_receipts": NATIVE_COLLECTOR,
    "native_prompt": NATIVE_PROMPT, "native_schema": NATIVE_SCHEMA,
    "qualitative_materials": MATERIAL, "materials_repair": MATERIAL_REPAIR,
    "material_adequacy": MATERIAL_ADEQUACY, "revision": REVISION,
    "writing_v15": V15, "writing_v16": V16,
}
PHASES = {"initial", "supplemental"}
ORIGINAL_COMMANDS = {"init", "reality", "exchange", "issue",
                     "initial", "supplemental", "advance", "review",
                     "prepare", "status", "s08"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def doctor():
    missing = [name for name, path in REQUIRED.items() if not path.is_file()]
    if missing:
        raise RuntimeError("Missing original 3.x modules: " + ", ".join(missing))
    policy = read(V3_POLICY)
    if policy.get("dev") != {"initial": 5, "supplemental": 5} or policy.get("formal") != {"initial": 5, "supplemental": 35}:
        raise RuntimeError("Original v3.2 research quantity profile changed")
    if len(policy.get("journals", [])) != 9:
        raise RuntimeError("Original v3.2 9-journal source contract changed")
    schema = read(NATIVE_SCHEMA)
    required = set(schema["properties"]["papers"]["items"]["required"])
    fields = {"title", "authors", "journal", "year", "doi",
              "metadata_url", "abstract_url", "abstract_locator",
              "abstract_excerpt", "abstract_summary", "relevance", "relevance_reason"}
    if required != fields:
        raise RuntimeError("Original v3 native literature fields changed")
    return {"status": "original_v3_contracts_present",
            "journals": policy["journals"], "dev": policy["dev"], "formal": policy["formal"],
            "sha256": {name: sha(path) for name, path in REQUIRED.items()},
            "formal_eligible": False}


def run_id_guard(run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", str(run_id)):
        raise ValueError("Invalid v3.x run identity")
    return run_id


def original_command(action, run_id, *, theme=None, report=None):
    if action not in ORIGINAL_COMMANDS:
        raise ValueError("Original 3.x has no such command")
    cmd = [sys.executable, "-B", str(V3_TOPIC), action, run_id_guard(run_id), "--mode", "dev"]
    if theme:
        cmd += ["--theme", theme]
    if report:
        cmd += ["--report", str(Path(report).resolve())]
    return cmd


def original_call(cmd, *, timeout=3600):
    result = subprocess.run(cmd, cwd=ROOT, check=False, text=True,
                            capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("3.x component blocked (exit %d): %s" %
                           (result.returncode, (result.stderr or result.stdout)[-1500:]))
    return result.stdout


def state_of(run_id):
    state = read(RUNS / run_id_guard(run_id) / "staged_topic.json")
    if state.get("run_id") != run_id or state.get("mode") != "dev":
        raise ValueError("Not an original v3.2 experimental research run")
    return state


def status(run_id, *, progress=False):
    doctor()
    state = state_of(run_id)
    stage = state["status"]
    if stage in PHASES:
        if progress:
            # Dispatch to ORIGINAL v009, which owns original v012/11-v007
            # batches, deduplication, abstract provenance and source quota.
            task = codex_task(run_id, stage)
            output = original_call(original_command(stage, run_id))
            return {"action": "original_native_literature_search", "before": stage,
                    "after": state_of(run_id)["status"], "output": output[-1300:],
                    "task_snapshot": task["task_snapshot"]}
        return {"action": "original_native_literature_search", "stage": stage,
                "command": original_command(stage, run_id)}
    if stage == "s08_ready":
        if progress:
            original_call(original_command("s08", run_id))
            return {"action": "original_s08_freeze", "after": state_of(run_id)["status"]}
        return {"action": "original_s08_freeze", "command": original_command("s08", run_id)}
    if stage == "frozen":
        return {"action": "original_06_adequacy_then_v15_v16",
                "status": "awaiting_original_independent_material_and_writing_receipts",
                "modules": [str(MATERIAL), str(MATERIAL_REPAIR), str(MATERIAL_ADEQUACY),
                            str(REVISION), str(V15), str(V16)],
                "writer4_dispatch": (
                    "writer4 --action prepare --packet <reviewed V15 plan_input.json> "
                    "--workspace <new workspace> --mode exploratory"
                ),
                "writer4_formal_status": "blocked_until_original_independent_receipts"}
    return {"action": "original_v3_requires_staged_evidence_or_independent_review",
            "stage": stage,
            "prepare": original_command("prepare", run_id),
            "strict_gate": "no advance on unreviewed internal roleplay"}


def original_material_command(run_id, *, attempt="attempt_001",
                              conversion=None, review=None, matrix=None,
                              framework=None, framework_revision=None,
                              preliminary_attempt="attempt_001", event_focus=False):
    """Route without alteration to actual 06/v005 material collection/review/matrix."""
    work = RUNS / run_id_guard(run_id)
    if not all(re.fullmatch(r"attempt_[0-9]{3}", x)
               for x in (attempt, preliminary_attempt)):
        raise ValueError("Keep the original 06 numbered-attempt contract")
    modes = [conversion, review, matrix]
    if sum(x is not None for x in modes) != 1:
        raise ValueError("Original 06 requires exactly one conversion, review, or matrix")
    cmd=[sys.executable,"-B",str(MATERIAL),"--dev-run",str(work),
         "--attempt",attempt,"--preliminary-attempt",preliminary_attempt]
    for name,value in (("conversion",conversion),("review",review),("matrix",matrix),
                       ("framework",framework),("framework-revision",framework_revision)):
        if value is not None:
            cmd += ["--"+name,str(Path(value).resolve())]
    if event_focus:
        cmd.append("--event-focus")
    return cmd


def original_writing_command(run_id, *, attempt="attempt_001"):
    """Use the original independent matrix-to-writing revision controller."""
    if not re.fullmatch(r"attempt_[0-9]{3}", attempt):
        raise ValueError("Use original 06/07 attempt identity")
    return [sys.executable,"-B",str(REVISION),run_id_guard(run_id),
            "--attempt",attempt]


def original_writer4_command(action, *, packet, workspace=None, mode="exploratory",
                               manuscript=None, claims=None):
    """Dispatch directly to the original v016 writer; this adapter adds no writing rules."""
    if action not in {"route", "prepare", "submit"}:
        raise ValueError("Unknown original v016 writer action")
    cmd = [sys.executable, "-B", str(V16), action,
           "--packet", str(Path(packet).resolve())]
    if action == "route":
        if any(value is not None for value in (workspace, manuscript, claims)):
            raise ValueError("The original v016 route command accepts only a packet")
        return cmd
    if workspace is None:
        raise ValueError("The original v016 writer requires a workspace")
    cmd += ["--workspace", str(Path(workspace).resolve())]
    if action == "prepare":
        if manuscript is not None or claims is not None or mode not in {"exploratory", "formal"}:
            raise ValueError("Invalid original v016 prepare arguments")
        cmd += ["--mode", mode]
        return cmd
    if manuscript is None or claims is None:
        raise ValueError("The original v016 submit command requires manuscript and claims")
    cmd += ["--manuscript", str(Path(manuscript).resolve()),
            "--claims", str(Path(claims).resolve())]
    return cmd


def original_event_command(run_id, report):
    """Use the original v3.x fact-level event comparison contract."""
    return [sys.executable,"-B",str(V3_EVENTS),"--dev-run",
            str(RUNS/run_id_guard(run_id)),"--input",str(Path(report).resolve())]


def common_literature_task(run_id, phase):
    """Build a single frozen phase packet for both v012 executor routes.

    Original v009 prepare and workload stay authoritative. This function only
    packages inputs; it cannot execute search or grant an academic pass.
    """
    import task_packet as contract

    doctor()
    if phase not in PHASES or state_of(run_id)["status"] != phase:
        raise ValueError("Search not authorized by original v3.2 state")
    state = state_of(run_id)
    work = RUNS / run_id
    prepared = json.loads(original_call(original_command("prepare", run_id)))
    if prepared.get("status") != phase:
        raise ValueError("Original prepare returned another phase")
    manifest = contract.run_mode.verified_run(work)
    rules = read(V3_POLICY)
    journals = list(rules["journals"])
    plan = prepared.get("issue_plan")
    files = ["run_manifest.json"]
    for name in ("reality.json", "event_comparison.json", "explanation_exchange.json"):
        if (work / name).is_file():
            files.append(name)
    if state.get("issue_search") or plan is not None:
        if (not isinstance(plan, dict)
                or plan != read(work / "issue_plan.json")
                or not all(isinstance(plan.get(k), str) and plan[k].strip()
                           for k in ("issue", "why", "object_search", "issue_search", "theory_search"))):
            raise ValueError("Original object/issue/theory positioning is incomplete")
        files.append("issue_plan.json")
        for item in plan.get("specialist_journals", []):
            if not all(isinstance(item.get(k), str) and item[k].strip()
                       for k in ("name", "publisher_url", "standing", "fit")) or not item["publisher_url"].startswith("https://"):
                raise ValueError("Unverified specialist-journal addition")
            journals.append(item["name"])
    else:
        # Preserve the direct original legacy route. The existing Chat prompt
        # still requires the current three-layer issue plan.
        plan = None
    accepted = []
    if phase == "supplemental":
        matrix = "initial/literature_matrix.json"
        accepted = [row["title"] for row in read(work / matrix)["rows"]]
        files.append(matrix)
        if (work / "initial/theories.json").is_file():
            files.append("initial/theories.json")
    budget = manifest["workload"]["11"]
    current_profile = read(CONTROL / "v007_第7版/dev_profile.json")
    target = rules["dev"][phase]
    question = state.get("question") or state["theme"]
    def file_ref(path, root):
        return {"path": path.relative_to(root).as_posix(), "sha256": sha(path)}
    packet = {
        "schema_version": 1, "research_id": run_id, "stage_id": phase,
        "task_id": "original_v3_literature_" + phase,
        "purpose": "Original v3.2 literature phase: " + phase,
        "research_question": question,
        "search_levels": ["object", "issue", "theory"] if plan is not None else [],
        "input_files": [file_ref(work / name, work) for name in files],
        "source_scope": {
            "journals": journals,
            "source_types": ["journal_abstract", "separate_theory_note"],
            "policy_refs": [file_ref(path, ROOT) for path in (
                V3_POLICY, V3_SEARCH_PROMPT, NATIVE_PROMPT,
                CONTROL / "v007_第7版/dev_profile.json")],
        },
        "quantity_budget": {"target": target,
                            "max_batches": current_profile["11"]["topic_batches_per_phase"],
                            "native_search_actions": budget["native_search_actions"]},
        "time_budget_seconds": budget["timeout_seconds"],
        "output_schema": {"kind": "file", "file": file_ref(NATIVE_SCHEMA, ROOT)},
        "stop_conditions": [
            "Original v009 phase gate or sufficient eligible evidence",
            "Original v009 deficit/batch/action/timeout rules require stopping",
            "Input, policy or research identity changes",
        ],
        "notes": ["Time and native search action budgets are per original batch; "
                  "max_batches is per original phase. Original receiver controls eligibility."],
    }
    reference = contract.freeze_packet(packet, current_run_id=run_id)
    contract.verify_snapshot(reference, current_run_id=run_id)
    return {"task_packet": packet, "task_snapshot": reference,
            "plan": plan, "accepted": accepted}


def codex_task(run_id, phase):
    """Export the same frozen packet used for Chat; do not invoke Codex here."""
    shared = common_literature_task(run_id, phase)
    return {"task_packet": shared["task_packet"], "task_snapshot": shared["task_snapshot"]}


def chat_task(run_id, phase):
    """Existing Chat prompt plus the shared executor-neutral task contract."""
    shared = common_literature_task(run_id, phase)
    packet, plan = shared["task_packet"], shared["plan"]
    if plan is None:
        raise ValueError("Original object/issue/theory positioning is incomplete")
    work = RUNS / run_id
    journals = packet["source_scope"]["journals"]
    accepted = shared["accepted"]
    theme = packet["research_question"]
    if phase == "initial":
        theme += "; 现实: " + read(work / "reality.json")["search_focus"]
        theme += "; 反诘: " + read(work / "explanation_exchange.json")["search_focus"]
    else:
        theme = "补查: " + theme
    target = packet["quantity_budget"]["target"]
    prompt = NATIVE_PROMPT.read_text(encoding="utf-8-sig").format(
        theme=theme, desired=target,
        journals="、".join(journals), accepted=json.dumps(accepted, ensure_ascii=False))
    prompt += ("\n原v3.2议题三层定位和自适应搜索策略:\n"
               + json.dumps(plan, ensure_ascii=False)
               + "\n严格使用本对话的真实网页搜索和页面打开。逐篇阅读原摘要。"
               "请将每个题录和摘要URL与打开记录一起归档；Chat工具来源独立标识，"
               "不可标记为Codex原生工具事件或正式独立审查。")
    return {"run_id": run_id, "phase": phase, "source_mode": "chat_native_web",
            "profile": "original_v3.2", "policy_sha256": sha(V3_POLICY),
            "prompt_sha256": sha(NATIVE_PROMPT), "schema_sha256": sha(NATIVE_SCHEMA),
            "journals": journals, "accepted": accepted,
            "target": target, "prompt": prompt,
            "task_packet": packet, "task_snapshot": shared["task_snapshot"]}


def clean_title(text):
    return re.sub(r"[\W_]+", "", str(text)).casefold()


def valid_https(text):
    if not isinstance(text, str):
        return False
    url = urlsplit(text)
    return url.scheme == "https" and bool(url.netloc) and not url.username


def audit_chat(task, bundle):
    """No weaker than v3 source structural rules; cannot authenticate Chat tool events."""
    doctor()
    if task.get("profile") != "original_v3.2" or task.get("source_mode") != "chat_native_web":
        raise ValueError("Invalid Chat evidence mode")
    if any(task.get(key) != sha(path) for key, path in (
        ("policy_sha256", V3_POLICY), ("prompt_sha256", NATIVE_PROMPT),
        ("schema_sha256", NATIVE_SCHEMA))):
        raise ValueError("v3.x source rules have changed since task creation")
    if not isinstance(bundle, dict) or not all(isinstance(bundle.get(k), list)
                 for k in ("papers", "unverified", "search_notes")):
        raise ValueError("Only original v3 response contract accepted")
    fields = set(read(NATIVE_SCHEMA)["properties"]["papers"]["items"]["required"])
    allowed = set(task["journals"])
    prior = {clean_title(t) for t in task["accepted"]}
    seen = set()
    accepted, rejected = [], []
    for index, paper in enumerate(bundle["papers"], 1):
        try:
            if set(paper) != fields:
                raise ValueError("Not an original v3 paper schema")
            if paper["journal"] not in allowed:
                raise ValueError("Out-of-scope journal")
            if not isinstance(paper["authors"], list) or not paper["authors"] or not all(
                isinstance(x, str) and x.strip() for x in paper["authors"]):
                raise ValueError("Unverified author identity")
            if type(paper["year"]) is not int or not 1900 <= paper["year"] <= date.today().year + 1:
                raise ValueError("Invalid publication year")
            if not valid_https(paper["metadata_url"]) or not valid_https(paper["abstract_url"]):
                raise ValueError("No verified metadata/abstract HTTPS source")
            if not paper["title"].strip() or not paper["abstract_locator"].strip():
                raise ValueError("Missing title or actual abstract locator")
            if paper["relevance"] not in ("direct", "substantive") or not paper["relevance_reason"].strip():
                raise ValueError("Not a justified directly or substantively related paper")
            if not 8 <= len(paper["abstract_excerpt"].strip()) <= 90:
                raise ValueError("Original v3 excerpt length failed")
            if not 80 <= len(paper["abstract_summary"].strip()) <= 160:
                raise ValueError("Original v3 summary length failed")
            title = clean_title(paper["title"])
            key = paper["doi"].casefold().strip() if paper["doi"] else paper["journal"]+title+str(paper["year"])
            if title in prior or key in seen:
                raise ValueError("Duplicate prior/current paper")
            seen.add(key)
            accepted.append(paper)
        except (KeyError, ValueError, AttributeError, TypeError) as exc:
            rejected.append({"index": index, "title": str(paper.get("title",""))[:120],
                             "reason": str(exc)})
    return {"source_mode": "chat_native_web",
            "status": "pending_independent_url_and_abstract_provenance",
            "native_cli_receipt": False, "formal_eligible": False,
            "provisional_count": len(accepted), "target": task["target"],
            "deficit": max(0, task["target"]-len(accepted)),
            "rejected": rejected,
            "note": "Structure checked under original 3.x rules; self-reported Chat tools cannot substitute for native CLI URLs/events or independent academic review."}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="cmd",required=True)
    sub.add_parser("doctor")
    p=sub.add_parser("init"); p.add_argument("--run-id",required=True); p.add_argument("--theme",required=True)
    for action in ("status","advance"):
        p=sub.add_parser(action);p.add_argument("--run-id",required=True)
    for action in ("reality","exchange","issue","review"):
        p=sub.add_parser(action);p.add_argument("--run-id",required=True);p.add_argument("--report",type=Path,required=True)
    p=sub.add_parser("event-compare");p.add_argument("--run-id",required=True);p.add_argument("--report",type=Path,required=True)
    p=sub.add_parser("materials");p.add_argument("--run-id",required=True)
    p.add_argument("--attempt",default="attempt_001")
    for option in ("conversion","review","matrix","framework","framework-revision"):
        p.add_argument("--"+option,type=Path)
    p.add_argument("--preliminary-attempt",default="attempt_001")
    p.add_argument("--event-focus",action="store_true")
    p=sub.add_parser("resume-writing");p.add_argument("--run-id",required=True)
    p.add_argument("--attempt",default="attempt_001")
    p=sub.add_parser("writer4")
    p.add_argument("--action",choices=("route","prepare","submit"),required=True)
    p.add_argument("--packet",type=Path,required=True)
    p.add_argument("--workspace",type=Path)
    p.add_argument("--mode",choices=("exploratory","formal"),default="exploratory")
    p.add_argument("--manuscript",type=Path)
    p.add_argument("--claims",type=Path)
    for action in ("chat-task", "codex-task"):
        p=sub.add_parser(action);p.add_argument("--run-id",required=True)
        p.add_argument("--phase",choices=sorted(PHASES),required=True);p.add_argument("--output",type=Path,required=True)
    p=sub.add_parser("review-task");p.add_argument("--run-id",required=True);p.add_argument("--output",type=Path,required=True)
    p.add_argument("--review-object");p.add_argument("--packet");p.add_argument("--manuscript");p.add_argument("--claims")
    p.add_argument("--prior-report");p.add_argument("--revision-record")
    p=sub.add_parser("chat-audit");p.add_argument("--task",type=Path,required=True)
    p.add_argument("--response",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    p=sub.add_parser("chat-receive");p.add_argument("--run-id",required=True)
    p.add_argument("--task",type=Path,required=True);p.add_argument("--result",required=True)
    p.add_argument("--execution-binding",type=Path);p.add_argument("--observed-actions",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p=sub.add_parser("codex-receive");p.add_argument("--run-id",required=True)
    p.add_argument("--task",type=Path,required=True);p.add_argument("--result",required=True)
    p.add_argument("--execution-binding",type=Path);p.add_argument("--output",type=Path,required=True)
    p=sub.add_parser("literature-receive");p.add_argument("--run-id",required=True)
    p.add_argument("--task",type=Path,required=True);p.add_argument("--result",required=True)
    p.add_argument("--execution-binding",type=Path);p.add_argument("--observed-actions",type=Path)
    p.add_argument("--output",type=Path,required=True)
    p=sub.add_parser("merge-results");p.add_argument("--run-id",required=True)
    p.add_argument("--task",type=Path,required=True);p.add_argument("--selection",type=Path,required=True)
    p.add_argument("--aliases",type=Path);p.add_argument("--output",required=True)
    args=parser.parse_args(argv)
    try:
        if args.cmd=="doctor": result=doctor()
        elif args.cmd=="init":
            doctor(); result={"original_output":original_call(original_command("init",args.run_id,theme=args.theme))}
        elif args.cmd in ("status","advance"): result=status(args.run_id,progress=args.cmd=="advance")
        elif args.cmd=="event-compare":
            doctor();result={"original_output":original_call(original_event_command(args.run_id,args.report))}
        elif args.cmd=="materials":
            doctor();result={"original_output":original_call(original_material_command(
                args.run_id,attempt=args.attempt,conversion=args.conversion,review=args.review,
                matrix=args.matrix,framework=args.framework,framework_revision=args.framework_revision,
                preliminary_attempt=args.preliminary_attempt,event_focus=args.event_focus))}
        elif args.cmd=="resume-writing":
            doctor();result={"original_output":original_call(original_writing_command(
                args.run_id,attempt=args.attempt))}
        elif args.cmd=="writer4":
            doctor()
            command=original_writer4_command(
                args.action,packet=args.packet,workspace=args.workspace,mode=args.mode,
                manuscript=args.manuscript,claims=args.claims)
            result={"original_output":original_call(command),"module":str(V16),
                    "action":args.action,"formal_eligible":False}
        elif args.cmd in ("chat-task", "codex-task"):
            generator=chat_task if args.cmd=="chat-task" else codex_task
            result=generator(args.run_id,args.phase);write(args.output,result)
        elif args.cmd=="review-task":
            if args.review_object:
                from review_artifact_task import prepare_artifact_review_task
                result=prepare_artifact_review_task(args.run_id,args.review_object,packet_path=args.packet,
                    manuscript_path=args.manuscript,claims_path=args.claims,prior_report=args.prior_report,revision_record=args.revision_record)
            else:
                if any((args.packet,args.manuscript,args.claims)):
                    raise ValueError("Select the original review object before draft inputs")
                from review_task import prepare_review_task
                result=prepare_review_task(args.run_id,prior_report=args.prior_report,revision_record=args.revision_record)
            write(args.output,result)
        elif args.cmd=="merge-results":
            from result_merge import merge_result_bundles, write_merge_index
            task=read(args.task)
            result=merge_result_bundles(read(args.selection),current_run_id=args.run_id,
                expected_reference=task["task_snapshot"],
                reviewed_report_aliases=read(args.aliases) if args.aliases else None)
            write_merge_index(result,current_run_id=args.run_id,output=args.output)
        elif args.cmd=="literature-receive":
            from original_literature_gate import audit_unified_literature
            task=read(args.task)
            result=audit_unified_literature(args.result,current_run_id=args.run_id,
                expected_reference=task["task_snapshot"],
                expected_execution=read(args.execution_binding) if args.execution_binding else None,
                observed_actions=read(args.observed_actions) if args.observed_actions else None)
            write(args.output,result)
        elif args.cmd=="codex-receive":
            from codex_receiving import audit_codex_records
            task=read(args.task)
            if task.get("source_mode") == "chat_native_web":
                raise ValueError("Expected independently selected Codex task")
            result=audit_codex_records(args.result,current_run_id=args.run_id,
                expected_reference=task["task_snapshot"],
                expected_execution=read(args.execution_binding) if args.execution_binding else None)
            write(args.output,result)
        elif args.cmd=="chat-receive":
            from chat_receiving import audit_chat_records
            task=read(args.task)
            if task.get("source_mode") != "chat_native_web":
                raise ValueError("Expected an independently selected Chat task")
            result=audit_chat_records(args.result,current_run_id=args.run_id,
                expected_reference=task["task_snapshot"],
                expected_execution=read(args.execution_binding) if args.execution_binding else None,
                observed_actions=read(args.observed_actions) if args.observed_actions else None)
            write(args.output,result)
        elif args.cmd=="chat-audit":
            result=audit_chat(read(args.task),read(args.response));write(args.output,result)
        else:
            doctor();result={"original_output":original_call(original_command(args.cmd,args.run_id,report=args.report)),
                             "stage":state_of(args.run_id)["status"]}
        print(json.dumps({"status":"ok","result":result},ensure_ascii=False,indent=2))
        return 0
    except (ValueError,KeyError,TypeError,RuntimeError,OSError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status":"blocked","reason":str(exc)},ensure_ascii=False))
        return 2


if __name__=="__main__":
    sys.exit(main())
