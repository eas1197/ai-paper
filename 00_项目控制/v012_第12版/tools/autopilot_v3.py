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


def source_proof(packet, trace, url_event):
    for index,source in enumerate(packet["sources"],1):
        url=source.get("url")
        if not heritage.valid_https(url) or not url_event(url,trace):
            raise ValueError("Reality source %d not bound to an actual original native web event"%index)


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
                ". Sources is an ID-to-HTTPS-URL map; each event has identity and facts "
                "with source_id, statement, use, key and credibility status. "
                "One report describing two places is not two independent reports.")
            path=folder/"response.json"
            cmd=[sys.executable,"-B",str(heritage.V3_EVENTS),
                 "--dev-run",str(work),"--input",str(path)]
            heritage.original_call(cmd)
        task=json.loads(heritage.original_call(heritage.original_command("prepare",run_id)))
        researcher,ra,rs,rt,ref=engine.call(
            work,"research_exchange",json.dumps(task,ensure_ascii=False)+
            "\nRecord original explanation and what evidence would distinguish it.")
        critic,ca,cs,ct,ref=engine.call(
            work,"critical_exchange","You are a FRESH independent critic session. "
            "Read only the frozen reality and event_comparison at "+str(work)+
            " and the researcher's evidence-bound explanation at "+str(ra/"response.json")+
            ". Critique strongest assumption, counterexample and competing explanation. "
            "Do not assert an independent academic gate pass.")
        if rs==cs:
            raise RuntimeError("Independent critical receipt must be a separate actual session")
        combined={**researcher,"challenge":critic["challenge"],
                  "research_actor":"codex_research_session_"+rs,
                  "critical_actor":"codex_critical_session_"+cs,
                  "critical_receipt":cs,
                  "critical_response_sha256":checksum(ca/"response.json")}
        result=work/"v5_native"/"exchange_payload.json"
        if result.exists():
            raise FileExistsError("Do not rewrite a critical exchange")
        heritage.write(result,combined)
        heritage.original_call(heritage.original_command("exchange",run_id,report=result))
        return {"next":heritage.state_of(run_id)["status"],
                "actions":"original event and independent-session exchange"}
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


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id",required=True)
    p.add_argument("--theme",default="社会生活")
    p.add_argument("--model")
    p.add_argument("--timeout",type=int,default=900)
    p.add_argument("--max-steps",type=int,default=8)
    args=p.parse_args(argv)
    try:
        heritage.doctor()
        path=heritage.RUNS/heritage.run_id_guard(args.run_id)
        if not path.exists():
            heritage.original_call(heritage.original_command("init",args.run_id,theme=args.theme))
        engine=Executor(timeout=args.timeout,model=args.model)
        result=None
        for _ in range(max(1,min(args.max_steps,20))):
            result=step(args.run_id,executor=engine)
            if result.get("status")=="blocked_by_original_v3_gate" or result.get("actions") is None and result.get("action")!="original_s08_freeze":
                break
        print(json.dumps({"status":"checkpoint","result":result,
                          "v3_stage":heritage.state_of(args.run_id)["status"],
                          "formal_eligible":False},ensure_ascii=False,indent=2))
        return 0
    except (OSError,RuntimeError,ValueError,KeyError,TypeError,TimeoutError) as exc:
        print(json.dumps({"status":"blocked","reason":str(exc)},ensure_ascii=False))
        return 2


if __name__=="__main__":
    sys.exit(main())
