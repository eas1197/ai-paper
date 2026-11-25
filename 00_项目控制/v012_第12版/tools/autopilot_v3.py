"""AI wake layer for the ORIGINAL v3.2 staged-topic controller.

It can autonomously collect reality, compare events, run an isolated critical
exchange, position an issue, and trigger the ORIGINAL 3.x Codex literature
collector. It MUST halt at genuine independent academic/materials review.
Never constructs a fake v3 review id or accepts loose v011 literature JSON.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_paper5_strict as heritage
from run_observation import OriginalBudgetExhausted, classify_failure, failure_evidence


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_checksum(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def schema(fields):
    return {"type":"object","properties":fields,
            "required":list(fields),"additionalProperties":False}


def string():
    return {"type":"string"}


def array_of(value):
    return {"type":"array","items":value}


SOURCE = schema({"url":string(),"kind":string(),"supports":string(),"limits":string()})
FACT = schema({"source_id":string(),"statement":string(),"use":string(),
               "key":{"type":"boolean"},
               "status":{"type":"string","enum":["corroborated","single_account",
                       "unverified","contradicted","inference"]}})
EVENT = schema({"identity":string(),"facts":array_of(FACT)})
SCHEMAS = {
    "reality":schema({"phenomenon":string(),"search_focus":string(),
                      "sources":array_of(SOURCE)}),
    "events":schema({"sources":{"type":"object","additionalProperties":string()},
                     "events":array_of(EVENT),"sensitivity":string()}),
    "research_exchange":schema({"expectation":string(),"observation":string(),
                               "initial_explanation":string(),"candidate_question":string(),
                               "search_focus":string()}),
    "critical_exchange":schema({"challenge":string()}),
    "issue":schema({"issue":string(),"why":string(),"object_search":string(),
                    "issue_search":string(),"theory_search":string(),
                    "specialist_journals":array_of(schema({
                         "name":string(),"publisher_url":string(),
                         "standing":string(),"fit":string()}))}),
}


def native_modules():
    """Use the original 11/v007 Codex login, sandbox, provenance and safe output."""
    lib = heritage.ROOT / "04_议题文献与现实/v012_第12版/tools"
    sys.path.insert(0,str(lib))
    from native_library import registry
    registry()
    from codex_literature import cli_executable, invoke, evidence, url_event
    return cli_executable, invoke, evidence, url_event


def transcript_session(path):
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        try:
            e=json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type")=="thread.started" and e.get("thread_id"):
            return e["thread_id"]
    raise RuntimeError("Codex session has no authentic thread.started id")


def execution_task_id(work, stage, attempt, task_sha256):
    """Native attempt identity; separate from the stable C04 logical task slot."""
    return text_checksum(json.dumps([Path(work).name, stage, attempt, task_sha256],
                                    ensure_ascii=False, separators=(",", ":")))


def completed_call(work, stage, task, *, exclude_thread_id=None):
    """Reuse only a completed call whose exact task and raw receipts still match."""
    history=work/"v5_native_calls.json"
    if not history.is_file():
        return None
    ledger=heritage.read(history)
    candidates=[row for row in ledger.get("records", [])
                if row.get("stage")==stage and row.get("status")=="completed"]
    if not candidates:
        return None
    _,_,evidence,url_event=native_modules()
    for record in reversed(candidates):
        try:
            attempt=int(record["attempt"])
            folder=work/"v5_native"/stage/("attempt_%03d"%attempt)
            saved_task=heritage.read(folder/"task.json")
            raw=folder/"events.jsonl"
            response=folder/"response.json"
            if saved_task.get("instruction") != task or saved_task.get("stage") != stage:
                continue
            if "execution_task_id" in record or "task_sha256" in record:
                task_sha = checksum(folder/"task.json")
                if (record.get("task_sha256") != task_sha
                        or record.get("execution_task_id") != execution_task_id(work,stage,attempt,task_sha)):
                    continue
            if not raw.is_file() or not response.is_file():
                continue
            if (record.get("events_sha256") != checksum(raw)
                    or record.get("response_sha256") != checksum(response)):
                continue
            session=transcript_session(raw)
            if session != record.get("thread_id") or session == exclude_thread_id:
                continue
            trace=evidence(raw)
            return heritage.read(response),folder,session,trace,url_event
        except (OSError,RuntimeError,ValueError,KeyError,TypeError):
            continue
    return None


def require_no_unresolved_attempt(records, stage):
    """A prior attempt may be reused by completed_call, but never silently rerun."""
    previous = [row for row in records if row.get("stage") == stage]
    if any(row.get("status") == "completed" for row in previous):
        raise ValueError("Preserve completed call: exact task or original receipt no longer matches")
    if previous:
        raise RuntimeError("Prior native attempt requires explicit recovery; automatic retry is disabled")


def call_once(engine,work,stage,task,*,must_search=False,exclude_thread_id=None):
    """Recover a completed original call; never spend a second reservation on it."""
    result=completed_call(work,stage,task,exclude_thread_id=exclude_thread_id)
    if result is not None:
        if must_search and not result[3]:
            raise ValueError("Completed call lacks required original search provenance")
        return result
    history=work/"v5_native_calls.json"
    if history.is_file():
        require_no_unresolved_attempt(heritage.read(history).get("records",[]),stage)
    return engine.call(work,stage,task,**({"must_search":True} if must_search else {}))


def saved_critical_input(work):
    """Load a saved critic task only when its embedded snapshots match this run."""
    candidates=[work/"critical_input.txt",
                heritage.ROOT/"handoff_runs"/work.name/"critical_input.txt"]
    for source in candidates:
        if not source.is_file():
            continue
        content=source.read_text(encoding="utf-8-sig")
        if not content.strip():
            raise ValueError("Saved critical task is empty")
        start=content.find("{")
        if start < 0:
            raise ValueError("Saved critical task has no frozen context")
        decoder=json.JSONDecoder()
        try:
            reality,end=decoder.raw_decode(content,start)
            comparison_start=end
            while comparison_start < len(content) and content[comparison_start].isspace():
                comparison_start += 1
            comparison,_=decoder.raw_decode(content,comparison_start)
        except json.JSONDecodeError as exc:
            raise ValueError("Saved critical task has malformed frozen context") from exc
        current_reality=heritage.read(work/"reality.json")
        current_comparison=heritage.read(work/"event_comparison.json")
        state=heritage.read(work/"staged_topic.json")
        if reality != current_reality or comparison != current_comparison:
            raise ValueError("Saved critical task does not match this run's frozen reality/event comparison")
        if (comparison.get("run_id") != work.name
                or comparison.get("reality_sha256") != state.get("reality_sha256")):
            raise ValueError("Saved critical task is bound to another run or reality snapshot")
        return content,source
    return None,None


def source_proof(packet, trace, url_event):
    for index,source in enumerate(packet["sources"],1):
        url=source.get("url")
        if not heritage.valid_https(url) or not url_event(url,trace):
            raise ValueError("Reality source %d not bound to an actual original native web event"%index)


def write_native_ledger(history, ledger):
    """Atomically publish a full reservation/receipt update on the same filesystem."""
    history = Path(history)
    if history.is_symlink():
        raise ValueError("Original native ledger cannot be a symbolic link")
    fd, name = tempfile.mkstemp(prefix=".native-ledger-", dir=history.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(ledger, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, history)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Executor:
    def __init__(self, *, timeout=900, model=None):
        self.timeout,self.model=timeout,model

    def call(self, work, stage, task, *, must_search=False):
        # An interrupted process may leave this lock. Do not assume its call
        # did not launch or automatically reclaim its reservation.
        lock = work / ".native-call.lock"
        try:
            with lock.open("x", encoding="utf-8") as stream:
                stream.write(str(os.getpid()) + "\n")
        except FileExistsError as exc:
            raise RuntimeError("Prior native dispatch lock requires explicit recovery") from exc
        try:
            return self._call_locked(work, stage, task, must_search=must_search)
        finally:
            lock.unlink()

    def _call_locked(self, work, stage, task, *, must_search=False):
        history=work/"v5_native_calls.json"
        ledger=heritage.read(history) if history.is_file() else {"records":[],"budget":6}
        profile=heritage.read(heritage.CONTROL/"v007_第7版/dev_profile.json")
        ledger["budget"]=profile["00"]["model_calls"]
        if type(self.timeout) is not int or self.timeout<=0:
            raise ValueError("Positive original native timeout required")
        timeout=min(self.timeout,profile["00"]["timeout_seconds"])
        if len(ledger["records"])>=ledger["budget"]:
            raise OriginalBudgetExhausted("Original 3.x global model-call allowance exhausted")
        require_no_unresolved_attempt(ledger["records"],stage)
        cli,invoke,evidence,url_event=native_modules()
        attempt=sum(1 for row in ledger["records"] if row["stage"]==stage)+1
        folder=work/"v5_native"/stage/("attempt_%03d"%attempt)
        folder.mkdir(parents=True,exist_ok=False)
        task_json=folder/"schema.json"
        heritage.write(task_json,SCHEMAS[stage])
        heritage.write(folder/"task.json",{"stage":stage,"instruction":task})
        # Keep a durable call reservation before trying Codex. Never erase failed calls.
        task_sha=checksum(folder/"task.json")
        record={"stage":stage,"attempt":attempt,"status":"started",
                "task_sha256":task_sha, "executor":"codex_cli",
                "execution_task_id":execution_task_id(work,stage,attempt,task_sha),
                "model_call_reserved":1,"remaining_model_calls":ledger["budget"]-len(ledger["records"])-1,
                "web_actions":None,"web_action_observation":"not_yet_observed"}
        ledger["records"].append(record);write_native_ledger(history,ledger)
        prompt=(task+"\nRead 3.x project rules; use native live web ONLY for needed "
                "observations. Avoid shell/MCP/browser/plugins and never invent a source, "
                "actor action, DOI, review identity or evidence. "
                "Return JSON according to output schema; distinguish reported claims "
                "from empirical outcomes and preserve uncertainty.")
        raw=folder/"events.jsonl"
        response=folder/"response.json"
        def observe():
            # Missing or unreadable evidence is unknown consumption, never zero.
            record.update(events_sha256=checksum(raw) if raw.is_file() else None,
                          response_sha256=checksum(response) if response.is_file() else None)
            if not raw.is_file():
                record.update(web_actions=None,web_action_observation="missing_events")
                return None
            try:
                observed=evidence(raw)
                record.update(web_actions=len(observed),web_action_observation="observed_original_trace")
                return observed
            except Exception as exc:
                record.update(web_actions=None,web_action_observation="unreadable_events",
                              observation_error=str(exc)[:1000])
                return None
        def record_failure(exc, status):
            kind=classify_failure(exc)
            record.update(status=status,error=str(exc)[:1000],failure_kind=kind,
                          failure_evidence=failure_evidence(kind,raw_error=str(exc),stage=stage,
                                                            input_sha256=task_sha,executor="codex_cli"))
        try:
            code=invoke(cli(),folder,prompt,task_json,timeout=timeout,model=self.model)
        except Exception as exc:
            record_failure(exc,"technical_block")
            try:
                observe()
            finally:
                write_native_ledger(history,ledger)
            raise
        record["rc"]=code
        try:
            trace=observe()
            if code:
                raise RuntimeError(stage+" native Codex execution failed; see local original logs")
            if trace is None:
                raise RuntimeError(stage+" native search provenance unreadable or absent")
            if must_search and not trace:
                raise RuntimeError(stage+" has no native search provenance")
            session=transcript_session(raw)
            packet=heritage.read(response)
        except Exception as exc:
            record_failure(exc,"failed")
            write_native_ledger(history,ledger)
            raise
        record.update(status="completed",thread_id=session)
        write_native_ledger(history,ledger)
        return packet,folder,session,trace,url_event


def relative_path(path, base):
    return Path(path).resolve().relative_to(Path(base).resolve()).as_posix()


def prepare_issue_task(run_id):
    """Freeze original issue-positioning inputs, without dispatch or new search allowance."""
    import task_packet as contract
    heritage.doctor()
    state=heritage.state_of(run_id)
    if state["status"]!="issue_positioning" or not state.get("issue_search"):
        raise ValueError("Original issue positioning is not due")
    work=(heritage.RUNS/run_id).resolve(strict=True)
    manifest=contract.run_mode.verified_run(work)
    if manifest.get("run_id")!=run_id:
        raise ValueError("Original run mismatch")
    names=("run_manifest.json","staged_topic.json","reality.json",
           "event_comparison.json","explanation_exchange.json")
    def ref(root,path):
        resolved=path.resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(root.resolve()):
            raise ValueError("Input outside original namespace")
        return {"path":path.relative_to(root).as_posix(),"sha256":heritage.sha(resolved)}
    refs=[ref(work,work/name) for name in names]
    # Native collect_common.digest uses the same canonical JSON encoding as C04.
    for name,key in (("reality.json","reality_sha256"),("event_comparison.json","event_comparison_sha256"),
                     ("explanation_exchange.json","exchange_sha256")):
        if contract._digest(heritage.read(work/name))!=state.get(key):
            raise ValueError("Original pre-search evidence changed: "+name)
    comparison=heritage.read(work/"event_comparison.json")
    exchange=heritage.read(work/"explanation_exchange.json")
    if (comparison.get("run_id")!=run_id or comparison.get("reality_sha256")!=state["reality_sha256"]
            or comparison.get("event_count",0)<2):
        raise ValueError("Original event comparison is not bound to this run")
    original=json.loads(heritage.original_call(heritage.original_command("prepare",run_id)))
    if (original.get("status")!="issue_positioning" or not original.get("issue_positioning_instruction")
            or original.get("exchange")!=exchange or original.get("reality")!=heritage.read(work/"reality.json")):
        raise ValueError("Original issue task differs from frozen inputs")
    question=exchange.get("candidate_question")
    if not isinstance(question,str) or not question.strip():
        raise ValueError("Missing candidate question in original exchange")
    journals=heritage.read(heritage.V3_POLICY)["journals"]
    instruction=json.dumps({"original_prepare":original,"event_comparison":comparison,
        "original_journals":journals},ensure_ascii=False)+(
        "\nCreate issue, why, object_search, issue_search, theory_search. "
        "Only include specialist_journals with publisher URL, verified standing and topical fit. "
        "Pending sources and uncertain facts are not established evidence. "
        "Plan the three levels; do not collect literature or grant a research gate.")
    packet={"schema_version":1,"research_id":run_id,"stage_id":"issue_positioning",
        "task_id":"original_issue_positioning","purpose":instruction,"research_question":question,
        "search_levels":[],"input_files":refs,
        "source_scope":{"journals":journals,"policy_refs":[ref(heritage.ROOT,heritage.V3_POLICY),
            ref(heritage.ROOT,heritage.V3_SEARCH_PROMPT)]},
        "quantity_budget":{},"time_budget_seconds":0,
        "output_schema":{"kind":"inline","schema":SCHEMAS["issue"]},
        "stop_conditions":["Original input or state changed","No original executor allowance"],
        "notes":["Three-layer planning only; original Executor reserves its own budget before execution."]}
    snapshot=contract.freeze_packet(packet,current_run_id=run_id)
    contract.verify_snapshot(snapshot,current_run_id=run_id)
    return {"task_packet":packet,"task_snapshot":snapshot,"instruction":instruction,
            "dispatch_authorized":False,"formal_eligible":False}


def event_preflight(work,state,*,comparison_required):
    """Use original read-only evidence reconstruction before a new model call."""
    sys.path.insert(0,str(heritage.V32/"tools"))
    from staged_topic import verify_automatic_event_inputs
    verify_automatic_event_inputs(work,state,comparison_required=comparison_required)


def step(run_id, *, executor=None):
    from advance_trace import observe_advance
    return observe_advance(run_id,"autopilot_step",lambda: _step(run_id,executor=executor))


def _step(run_id, *, executor=None):
    heritage.doctor()
    work=heritage.RUNS/heritage.run_id_guard(run_id)
    state=heritage.state_of(run_id)
    phase=state["status"]
    from user_wait import checkpoint
    waiting=checkpoint(run_id,state)
    if waiting is not None:
        return waiting
    engine=executor or Executor()
    if phase=="reality":
        instructions=json.loads(heritage.original_call(heritage.original_command("prepare",run_id)))
        packet,folder,session,trace,url_event=call_once(engine,
            work,"reality",json.dumps(instructions,ensure_ascii=False),must_search=True)
        source_proof(packet,trace,url_event)
        report=folder/"response.json"
        heritage.original_call(heritage.original_command("reality",run_id,report=report))
        return {"next":heritage.state_of(run_id)["status"],
                "actions":"source-verified reality via original v3.2"}
    if phase=="explanation_exchange":
        comparison=work/"event_comparison.json"
        if state.get("issue_search"):
            event_preflight(work,state,comparison_required=comparison.is_file())
        if not comparison.is_file():
            packet,folder,session,trace,url_event=call_once(engine,
                work,"events","Compare at least two distinct independently identified "
                "real events from the frozen reality.json at "+str(work)+
                ". Sources is an ID-to-HTTPS-URL map; open each cited source page "
                "with the native open_page/find_in_page action before using it. Search snippets "
                "alone are not sufficient. Each event has identity and facts with source_id, "
                "statement, use, key and credibility status. One report describing two places "
                "is not two independent reports.",
                must_search=True)
            # Let the original event_protocol preserve unresolved sources as pending.
            path=folder/"response.json"
            events_path=folder/"events.jsonl"
            cmd=[sys.executable,"-B",str(heritage.V3_EVENTS),
                 "--dev-run",str(work),"--input",str(path),
                 "--events-jsonl",str(events_path)]
            heritage.original_call(cmd)
            if state.get("issue_search"):
                event_preflight(work,state,comparison_required=True)
        task=json.loads(heritage.original_call(heritage.original_command("prepare",run_id)))
        research_task=json.dumps(task,ensure_ascii=False)+(
            "\nRecord original explanation and what evidence would distinguish it. "
            "Only event_comparison retained_facts with source_verification_status=verified "
            "may be treated as verified empirical support. Treat uncertain_facts, pending_sources, "
            "and pending source_verification_status as unresolved gaps; do not cite or promote them "
            "as established facts.")
        researcher,ra,rs,rt,ref=call_once(engine,work,"research_exchange",research_task)

        saved_input,input_path=saved_critical_input(work)
        researcher_json=json.dumps(researcher,ensure_ascii=False)
        if saved_input is not None:
            critic_task=(saved_input+
                "\n\nCurrent researcher's evidence-bound response (JSON):\n"+
                researcher_json+
                "\nIndependently challenge this response. Do not reuse a failed prior session "
                "or treat same-session roleplay as independent evidence.")
        else:
            critic_task=("You are a FRESH independent critic session. "
                "Read only the frozen reality and event_comparison at "+str(work)+
                " and the researcher's evidence-bound explanation at "+str(ra/"response.json")+
                ". Critique the strongest assumption, counterexample and competing explanation. "
                "Do not assert an independent academic gate pass.\nResearcher response:\n"+
                researcher_json)
        critic,ca,cs,ct,ref=call_once(engine,work,"critical_exchange",critic_task,
                                         exclude_thread_id=rs)
        if rs==cs:
            raise RuntimeError("Independent critical receipt must be a separate actual session")
        if not isinstance(critic.get("challenge"),str) or not critic["challenge"].strip():
            raise ValueError("Independent critical session returned no substantive challenge")

        research_events=ra/"events.jsonl"
        research_response=ra/"response.json"
        critical_events=ca/"events.jsonl"
        critical_response=ca/"response.json"
        receipt_path=ca/"critical_receipt.json"
        input_path_value=(relative_path(input_path,heritage.ROOT)
                          if input_path is not None else None)
        receipt={
            "schema_version":1,
            "run_id":run_id,
            "stage":"explanation_exchange",
            "research_thread_id":rs,
            "research_events_path":relative_path(research_events,work),
            "research_events_sha256":checksum(research_events),
            "research_response_path":relative_path(research_response,work),
            "research_response_sha256":checksum(research_response),
            "critical_thread_id":cs,
            "critical_attempt":ca.name,
            "critical_task_sha256":text_checksum(critic_task),
            "critical_input_path":input_path_value,
            "critical_input_sha256":text_checksum(saved_input) if saved_input is not None else None,
            "critical_events_path":relative_path(critical_events,work),
            "critical_events_sha256":checksum(critical_events),
            "critical_response_path":relative_path(critical_response,work),
            "critical_response_sha256":checksum(critical_response),
            "thread_separation":"verified_by_distinct_thread_ids",
            "status":"separate_session_receipt_recorded",
        }
        if receipt_path.exists():
            if heritage.read(receipt_path)!=receipt:
                raise FileExistsError("Preserve the existing critical receipt; it does not match this attempt")
        else:
            heritage.write(receipt_path,receipt)
        combined={**researcher,"challenge":critic["challenge"],
                  "research_actor":"codex_research_session_"+rs,
                  "critical_actor":"codex_critical_session_"+cs,
                  "critical_receipt":cs,
                  "critical_receipt_path":relative_path(receipt_path,work),
                  "research_events_sha256":receipt["research_events_sha256"],
                  "research_response_sha256":receipt["research_response_sha256"],
                  "critical_task_sha256":receipt["critical_task_sha256"],
                  "critical_input_path":input_path_value,
                  "critical_input_sha256":receipt["critical_input_sha256"],
                  "critical_events_sha256":receipt["critical_events_sha256"],
                  "critical_response_sha256":receipt["critical_response_sha256"]}
        result=ca/"exchange_payload.json"
        if result.exists():
            if heritage.read(result)!=combined:
                raise FileExistsError("Preserve the existing exchange payload; it does not match this attempt")
        else:
            heritage.write(result,combined)
        heritage.original_call(heritage.original_command("exchange",run_id,report=result))
        return {"next":heritage.state_of(run_id)["status"],
                "actions":"original event and independent-session exchange with raw receipts"}
    if phase=="issue_positioning":
        from task_packet import verify_snapshot
        task=prepare_issue_task(run_id)
        if state.get("issue_search"):
            event_preflight(work,state,comparison_required=True)
        packet,folder,session,trace,url_event=call_once(engine,work,"issue",task["instruction"])
        verify_snapshot(task["task_snapshot"],current_run_id=run_id)
        heritage.original_call(heritage.original_command("issue",run_id,
                                                        report=folder/"response.json"))
        return {"next":heritage.state_of(run_id)["status"],
                "actions":"original v3.2 three-layer issue positioning"}
    from review_task import STAGES
    if phase in STAGES or phase=="frozen":
        return heritage.status(run_id,progress=True)
    if phase in heritage.PHASES or phase=="s08_ready":
        result=heritage.status(run_id,progress=True)
        if result.get("after") in STAGES:
            wait=heritage.status(run_id,progress=True)
            return {**wait,"original_transition":result}
        return result
    return {"next":phase,"status":"blocked_by_original_v3_gate",
            "reason":"Use authentic independent academic review / 06 material adequacy "
                     "and 07 writing receipts; no internal same-model promotion.",
            "originals":heritage.status(run_id)}


def run_autopilot(run_id, *, theme="社会生活", model=None, timeout=900, max_steps=8):
    """Shared implementation; original gates and bounded step loop are unchanged."""
    heritage.doctor()
    path=heritage.RUNS/heritage.run_id_guard(run_id)
    if not path.exists():
        saved_checkpoint=heritage.ROOT/"handoff_runs"/run_id/"staged_topic.json"
        if saved_checkpoint.is_file():
            raise RuntimeError(
                "Saved handoff checkpoint exists but the original v3 run directory is missing; "
                "restore the exact original run before resuming. Refusing to initialize a fresh run.")
        heritage.original_call(heritage.original_command("init",run_id,theme=theme))
    engine=Executor(timeout=timeout,model=model)
    result=None
    for _ in range(max(1,min(max_steps,20))):
        result=step(run_id,executor=engine)
        if result.get("status")=="blocked_by_original_v3_gate" or result.get("actions") is None and result.get("action")!="original_s08_freeze":
            break
    from run_observation import command_observation
    checkpoint={"status":"checkpoint","result":result,"v3_stage":heritage.state_of(run_id)["status"],"formal_eligible":False}
    from runtime_waiting import attach_wait
    runtime=attach_wait(command_observation("autopilot",checkpoint),checkpoint,run_id=run_id)
    return {**checkpoint,"runtime":runtime}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id",required=True)
    p.add_argument("--theme",default="社会生活")
    p.add_argument("--model")
    p.add_argument("--timeout",type=int,default=900)
    p.add_argument("--max-steps",type=int,default=8)
    args=p.parse_args(argv)
    try:
        print(json.dumps(run_autopilot(args.run_id,theme=args.theme,model=args.model,
            timeout=args.timeout,max_steps=args.max_steps),ensure_ascii=False,indent=2))
        return 0
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,TimeoutError) as exc:
        print(json.dumps({"status":"blocked","reason":str(exc)},ensure_ascii=False))
        return 2


if __name__=="__main__":
    sys.exit(main())
