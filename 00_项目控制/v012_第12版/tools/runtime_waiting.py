"""E18: immutable recovery contracts for actual waiting observations."""
import hashlib
import json
from pathlib import Path

WAITING = {
    "waiting_for_chat": ("Chat native tool executor", ["result bundle JSON","actual Chat source/open-page records","independently selected execution binding and observed actions"],
        ["literature-receive","--run-id","<run_id>","--task","<task JSON>","--result","<run-relative bundle>","--execution-binding","<actual binding JSON>","--observed-actions","<observed actions JSON>","--output","<new audit JSON>"]),
    "waiting_for_codex": ("authorized Codex executor", ["result bundle JSON","original login/events/response receipts","independently selected execution binding"],
        ["literature-receive","--run-id","<run_id>","--task","<task JSON>","--result","<run-relative bundle>","--execution-binding","<actual binding JSON>","--output","<new audit JSON>"]),
    "waiting_for_review": ("independent review executor and receiver", ["frozen review task/context","actual independent report","original launch/execution/identity/isolation receipts","trusted host authorization"],
        ["advance","--run-id","<run_id>"]),
    "waiting_for_user": ("user or original data owner", ["explicit user decision or required original input files","original reviewed data/design/analysis receipts where applicable"],
        ["status","--run-id","<run_id>"]),
}
ENTRY="00_项目控制/v012_第12版/tools/ai_paper5_strict.py"


def wait_contract(runtime,run_id=None):
    status=runtime.get("runtime_status")
    if status not in WAITING:
        return None
    owner,files,args=WAITING[status]
    return {"runtime_status":status,"research_id":run_id,"waiting_on":owner,
        "expected_deliverables":files,
        "resume_argv_template":["python",ENTRY,*[run_id if arg=="<run_id>" and run_id is not None else arg for arg in args]],
        "resume_precondition":"Revalidate original run and current snapshot; select actual original records independently.",
        "resume_is_authorization":False,"automatic_retry":False,
        "timeout_policy":{"deadline":None,"on_timeout":"Preserve receipts and wait; report timeout, no automatic retry or budget increase.",
                          "note":"No new execution deadline until an original authorized call starts."},
        "formal_eligible":False}


def attach_wait(runtime,result,*,run_id=None,task_file=None,persist=True):
    """Bind a wait to an explicit original run/active task; query-only calls never write."""
    contract=wait_contract(runtime,run_id)
    if contract is None:
        return runtime
    view=result.get("result",result) if isinstance(result,dict) else {}
    if not isinstance(view,dict):
        view={}
    candidate=view.get("candidate",view)
    if not isinstance(candidate,dict):
        candidate={}
    reference=candidate.get("task_snapshot")
    freeze=view.get("freeze_sha256")
    result_view={**runtime,"waiting":contract}
    if run_id is None or (reference is None and freeze is None):
        return {**result_view,"wait_record_status":"unbound_observation_only"}
    import task_packet
    h=task_packet.heritage
    h.run_id_guard(run_id)
    work=(h.RUNS/run_id).resolve(strict=True)
    manifest=task_packet.run_mode.verified_run(work)
    state=h.state_of(run_id)
    if manifest.get("run_id")!=run_id or state.get("run_id")!=run_id:
        raise ValueError("Wait belongs to another original run")
    state_hash=h.sha(work/"staged_topic.json")
    if reference is not None:
        snap=task_packet.verify_snapshot(reference,current_run_id=run_id)
        timeout=snap["packet"]["time_budget_seconds"]
    else:
        if state["status"]!="frozen" or h.sha(work/"s08_topic.json")!=freeze:
            raise ValueError("Wait frozen input changed")
        timeout=0
    contract={**contract,"original_stage":state["status"],"state_sha256":state_hash,
        "task_snapshot":reference,"freeze_sha256":freeze,
        "timeout_policy":{**contract["timeout_policy"],"frozen_task_time_budget_seconds":timeout}}
    if task_file is not None:
        path=Path(task_file).resolve(strict=True)
        if h.read(path).get("task_snapshot")!=reference:
            raise ValueError("Wait task file differs from selected snapshot")
        contract["task_file"]={"path":str(path),"sha256":h.sha(path)}
        contract["resume_argv_template"]=[str(path) if arg=="<task JSON>" else arg
                                        for arg in contract["resume_argv_template"]]
    wait=view.get("wait")
    if isinstance(wait,dict) and wait.get("wait_ref") is not None:
        from review_execution import load_ref
        raw=json.loads(load_ref(work,wait["wait_ref"]))
        if raw.get("task_snapshot")!=reference:
            raise ValueError("D18 wait record differs from selected task")
        contract["original_review_wait"]=wait["wait_ref"]
    if h.sha(work/"staged_topic.json")!=state_hash:
        raise ValueError("Original state changed during wait recording")
    result_view={**runtime,"waiting":contract}
    if not persist:
        return {**result_view,"wait_record_status":"read_only"}
    folder=work/"runtime_waiting"
    folder.mkdir(exist_ok=True)
    if folder.resolve()!=folder:
        raise ValueError("Wait directory outside original run")
    raw=(json.dumps(contract,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode()
    target=folder/(hashlib.sha256(raw).hexdigest()+".json")
    try:
        with target.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if target.is_symlink() or target.read_bytes()!=raw:
            raise ValueError("Existing wait record changed")
    return {**result_view,"wait_record_status":"recorded",
        "wait_record":{"path":target.relative_to(work).as_posix(),"sha256":h.sha(target)}}
