"""E19: operator decisions pause orchestration, never modify academic state or budgets."""
from pathlib import Path
import json
import re

REASONS={
    "question": "Select the research question or request original academic revision.",
    "materials": "Provide actual applicable material evidence or decide whether to stop.",
    "budget": "Review the original stop record; only the original approved policy can change the allowance.",
}
NATIVE={"materials_pending":"materials","literature_budget_exhausted":"budget"}


def _work(run_id):
    import task_packet as c
    c.heritage.run_id_guard(run_id)
    work=(c.heritage.RUNS/run_id).resolve(strict=True)
    manifest=c.run_mode.verified_run(work)
    if manifest.get("run_id")!=run_id:
        raise ValueError("User wait belongs to another run")
    return c,work


def _root(work):
    root=work/"runtime_user_holds"
    if root.exists() and root.resolve()!=root:
        raise ValueError("User hold directory escapes run")
    return root


def _read_active(c,work):
    root=_root(work)
    active=root/"active.json"
    if not active.exists():
        return None
    identity=c.heritage.read(active).get("hold_id")
    if not isinstance(identity,str) or not re.fullmatch("[0-9a-f]{64}",identity):
        raise ValueError("Invalid user hold identity")
    path=root/(identity+".json")
    record=c.heritage.read(path)
    if c._digest(record)!=identity or record["research_id"]!=work.name:
        raise ValueError("User hold changed")
    ack=root/(identity+".ack.json")
    if ack.exists():
        decision=c.heritage.read(ack)
        if (decision.get("research_id")!=work.name or decision.get("hold_id")!=identity
                or decision.get("continue_original_task") is not True or not str(decision.get("decision","")).strip()):
            raise ValueError("Invalid recorded user acknowledgement")
        return None
    return identity,record


def checkpoint(run_id,state):
    """Read-only wait projection; never infer an operator decision from model text."""
    import task_packet as c
    work=(c.heritage.RUNS/run_id).resolve()
    root=_root(work)
    active=_read_active(c,work) if (root/"active.json").is_file() else None
    if active is None and state["status"] not in NATIVE:
        return None
    c,work=_work(run_id)
    actual=c.heritage.state_of(run_id)
    if actual!=state:
        raise ValueError("Original state changed during user wait")
    state_sha=c.heritage.sha(work/"staged_topic.json")
    reason=NATIVE.get(state["status"])
    hold_id=None
    if active is not None:
        hold_id,record=active
        if record["state_sha256"]!=state_sha:
            raise ValueError("Unacknowledged user hold has a changed original state; resolve it explicitly")
        reason=record["reason"]
    return {"action":"await_user_decision","status":"waiting_for_user","stage":state["status"],
        "user_wait_reason":reason,"user_action":REASONS[reason],"user_hold_id":hold_id,
        "state_sha256":state_sha,"advance_gate":False,"automatic_retry":False,
        "budget_changed":False,"formal_eligible":False}


def request_hold(run_id,reason):
    if reason not in REASONS:
        raise ValueError("Unknown user decision type")
    c,work=_work(run_id)
    state=c.heritage.state_of(run_id)
    prior=checkpoint(run_id,state)
    if prior and prior.get("user_hold_id"):
        if prior["user_wait_reason"]!=reason:
            raise ValueError("A different explicit user hold is active")
        return prior
    record={"research_id":run_id,"reason":reason,"state_sha256":c.heritage.sha(work/"staged_topic.json")}
    identity=c._digest(record)
    root=_root(work)
    root.mkdir(exist_ok=True)
    if (root/(identity+".ack.json")).exists():
        raise ValueError("This exact hold was already acknowledged; original state must change first")
    path=root/(identity+".json")
    if path.exists():
        if c.heritage.read(path)!=record:
            raise ValueError("Existing user hold changed")
    else:
        with path.open("x",encoding="utf-8") as stream:
            json.dump(record,stream,sort_keys=True,ensure_ascii=False)
    c._atomic_json(root/"active.json",{"hold_id":identity})
    return checkpoint(run_id,state)


def acknowledge_hold(run_id,decision_path):
    """Explicit operator-selected file; not evidence of academic or budget approval."""
    c,work=_work(run_id)
    state=c.heritage.state_of(run_id)
    wait=checkpoint(run_id,state)
    if not wait or not wait.get("user_hold_id"):
        raise ValueError("No active explicit user hold")
    decision=c.heritage.read(Path(decision_path))
    if (not isinstance(decision,dict) or set(decision)!={"research_id","hold_id","continue_original_task","decision"}
            or decision["research_id"]!=run_id or decision["hold_id"]!=wait["user_hold_id"]
            or decision["continue_original_task"] is not True
            or not isinstance(decision["decision"],str) or not decision["decision"].strip()):
        raise ValueError("Select the actual user acknowledgement for this hold; changed question requires original revision")
    target=_root(work)/(wait["user_hold_id"]+".ack.json")
    with target.open("x",encoding="utf-8") as stream:
        json.dump(decision,stream,ensure_ascii=False,sort_keys=True)
    return {"action":"user_hold_acknowledged","status":"queued","stage":state["status"],
        "acknowledgement_sha256":c.heritage.sha(target),"advance_gate":False,
        "budget_changed":False,"formal_eligible":False}
