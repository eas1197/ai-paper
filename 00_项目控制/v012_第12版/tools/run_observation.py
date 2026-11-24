"""E17: runtime observations, never a parallel academic state machine."""

STATES = frozenset({"queued","running","waiting_for_chat","waiting_for_codex",
    "waiting_for_review","waiting_for_user","blocked","failed","completed"})

def observation(status, *, original_stage=None, scope="command", reason=None):
    if status not in STATES:
        raise ValueError("Unknown runtime observation")
    return {"runtime_status":status,"scope":scope,"original_stage":original_stage,
        "reason":reason,"academic_approval_granted":False,"formal_eligible":False}


def attempt_observation(record):
    """Observe an actual native call ledger entry; don't infer a launch from a task packet."""
    if record is None:
        return observation("queued",scope="native_attempt")
    status={"started":"running","completed":"completed","failed":"failed",
            "technical_block":"failed"}.get(record.get("status"),"blocked")
    return observation(status,scope="native_attempt",reason=record.get("status"))


def command_observation(command,result):
    """Interpret known command contracts, not result-declared academic passes."""
    result=result if isinstance(result,dict) else {}
    if command=="autopilot" and isinstance(result.get("result"),dict):
        stage=result.get("v3_stage")
        view=result["result"]
    else:
        view=result
        stage=view.get("after") or view.get("stage") or view.get("next")
    action=view.get("action")
    status=view.get("status")
    reason=status or action
    if command=="chat-task":
        state="waiting_for_chat"
    elif command=="codex-task":
        state="waiting_for_codex"
    elif command=="review-task" or action=="await_independent_review" or status=="unable_to_review":
        state="waiting_for_review"
    elif status=="awaiting_original_independent_material_and_writing_receipts":
        state="waiting_for_review"
    elif status=="awaiting_original_quantitative_inputs":
        state="waiting_for_user"
    elif view.get("execution_status")=="failed" or status=="execution_failed":
        state="failed"
    elif view.get("original_gate_status")=="blocked_original_budget":
        state="blocked"
    elif command in {"chat-receive","codex-receive","literature-receive","chat-audit","merge-results"}:
        # Technical receipt handling is not a completed academic task.
        state="blocked" if (view.get("acceptance_status")=="rejected" or str(status).startswith("pending")) else "waiting_for_review"
    elif status=="blocked_by_original_v3_gate" or stage in {"archived","eliminated","literature_budget_exhausted"}:
        state="blocked"
    elif command in {"status","advance","autopilot"}:
        if action in {"original_native_literature_search","original_s08_freeze"} and "after" not in view:
            state="queued"
        elif action=="original_v3_requires_staged_evidence_or_independent_review":
            state="blocked"
        elif view.get("after") or view.get("next") and view.get("actions"):
            state="completed"  # step only, never whole research
        else:
            state="blocked"
    elif command=="prepare":
        state="queued"
    elif command in {"commands","doctor","init","event-compare","materials","resume-writing",
                    "writer4","review-counts","reality","exchange","issue","review"}:
        state="completed"
    else:
        state="blocked"
    return observation(state,original_stage=stage,scope="command",reason=reason)
