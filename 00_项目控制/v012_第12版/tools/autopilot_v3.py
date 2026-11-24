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
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_paper5_strict as heritage


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
            if saved_task.get("instruction") != task:
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


class Executor:
    def __init__(self, *, timeout=900, model=None):
        self.timeout,self.model=timeout,model

    def call(self, work, stage, task, *, must_search=False):
        cli,invoke,evidence,url_event=native_modules()
        history=work/"v5_native_calls.json"
        ledger=heritage.read(history) if history.is_file() else {"records":[],"budget":6}
        profile=heritage.read(heritage.CONTROL/"v007_第7版/dev_profile.json")
        ledger["budget"]=profile["00"]["model_calls"]
        if len(ledger["records"])>=ledger["budget"]:
            raise RuntimeError("Original 3.x global model-call allowance exhausted")
        attempt=sum(1 for row in ledger["records"] if row["stage"]==stage)+1
        folder=work/"v5_native"/stage/("attempt_%03d"%attempt)
        folder.mkdir(parents=True,exist_ok=False)
        task_json=folder/"schema.json"
        heritage.write(task_json,SCHEMAS[stage])
        heritage.write(folder/"task.json",{"stage":stage,"instruction":task})
        # Keep a durable call reservation before trying Codex. Never erase failed calls.
        record={"stage":stage,"attempt":attempt,"status":"started"}
        ledger["records"].append(record);heritage.write(history,ledger)
        prompt=(task+"\nRead 3.x project rules; use native live web ONLY for needed "
                "observations. Avoid shell/MCP/browser/plugins and never invent a source, "
                "actor action, DOI, review identity or evidence. "
                "Return JSON according to output schema; distinguish reported claims "
                "from empirical outcomes and preserve uncertainty.")
        try:
            code=invoke(cli(),folder,prompt,task_json,timeout=self.timeout,model=self.model)
        except Exception as exc:
            record.update(status="technical_block",error=str(exc)[:1000])
            heritage.write(history,ledger)
            raise
        raw=folder/"events.jsonl"
        record.update(rc=code,events_sha256=checksum(raw),
                      response_sha256=checksum(folder/"response.json")
                      if (folder/"response.json").is_file() else None)
        heritage.write(history,ledger)
        if code:
            record["status"]="failed";heritage.write(history,ledger)
            raise RuntimeError(stage+" native Codex execution failed; see local original logs")
        trace=evidence(raw)
        if must_search and not trace:
            record["status"]="failed";heritage.write(history,ledger)
            raise RuntimeError(stage+" has no native search provenance")
        session=transcript_session(raw)
        packet=heritage.read(folder/"response.json")
        record.update(status="completed",thread_id=session,web_actions=len(trace))
        heritage.write(history,ledger)
        return packet,folder,session,trace,url_event


def relative_path(path, base):
    return Path(path).resolve().relative_to(Path(base).resolve()).as_posix()


def step(run_id, *, executor=None):
    heritage.doctor()
    work=heritage.RUNS/heritage.run_id_guard(run_id)
    state=heritage.state_of(run_id)
    phase=state["status"]
    engine=executor or Executor()
    if phase=="reality":
        instructions=json.loads(heritage.original_call(heritage.original_command("prepare",run_id)))
        packet,folder,session,trace,url_event=engine.call(
            work,"reality",json.dumps(instructions,ensure_ascii=False),must_search=True)
        source_proof(packet,trace,url_event)
        report=folder/"response.json"
        heritage.original_call(heritage.original_command("reality",run_id,report=report))
        return {"next":heritage.state_of(run_id)["status"],
                "actions":"source-verified reality via original v3.2"}
    if phase=="explanation_exchange":
        comparison=work/"event_comparison.json"
        if not comparison.is_file():
            packet,folder,session,trace,url_event=engine.call(
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
        task=json.loads(heritage.original_call(heritage.original_command("prepare",run_id)))
        research_task=json.dumps(task,ensure_ascii=False)+(
            "\nRecord original explanation and what evidence would distinguish it. "
            "Only event_comparison retained_facts with source_verification_status=verified "
            "may be treated as verified empirical support. Treat uncertain_facts, pending_sources, "
            "and pending source_verification_status as unresolved gaps; do not cite or promote them "
            "as established facts.")
        research_call=completed_call(work,"research_exchange",research_task)
        if research_call is None:
            researcher,ra,rs,rt,ref=engine.call(
                work,"research_exchange",research_task)
        else:
            researcher,ra,rs,rt,ref=research_call

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
        critic_call=completed_call(work,"critical_exchange",critic_task,
                                   exclude_thread_id=rs)
        if critic_call is None:
            critic,ca,cs,ct,ref=engine.call(
                work,"critical_exchange",critic_task)
        else:
            critic,ca,cs,ct,ref=critic_call
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
        instructions=json.loads(heritage.original_call(heritage.original_command("prepare",run_id)))
        packet,folder,session,trace,url_event=engine.call(
            work,"issue",json.dumps(instructions,ensure_ascii=False)+
            "\nCreate issue, why, object_search, issue_search, theory_search. "
            "Only include specialist_journals with publisher URL and verified standing.")
        heritage.original_call(heritage.original_command("issue",run_id,
                                                        report=folder/"response.json"))
        return {"next":heritage.state_of(run_id)["status"],
                "actions":"original v3.2 three-layer issue positioning"}
    if phase in heritage.PHASES or phase=="s08_ready":
        return heritage.status(run_id,progress=True)
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
    return {"status":"checkpoint","result":result,"v3_stage":heritage.state_of(run_id)["status"],"formal_eligible":False}


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
