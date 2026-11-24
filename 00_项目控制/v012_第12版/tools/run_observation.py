"""E17/I12: runtime observations and typed failure taxonomy; never academic approval."""
import math
import re
import socket
import subprocess
from urllib.error import URLError

from jsonschema import ValidationError

STATES = frozenset({"queued","running","waiting_for_chat","waiting_for_codex",
    "waiting_for_review","waiting_for_user","blocked","failed","completed"})

class OriginalBudgetExhausted(RuntimeError):
    """A known original budget has no remaining allowance, not a launch failure."""


OUTCOME_KINDS = frozenset({
    "network_failure", "executor_unavailable", "model_timeout", "schema_error",
    "evidence_missing", "academic_failure", "budget_exhausted", "user_cancelled",
    # Backward-compatible labels for older receipts.
    "technical_failure", "research_failure", "review_failure",
})


def classify_failure_message(message):
    """Classify explicit failure evidence; never infer budget exhaustion from vague quota wording."""
    value = str(message or "").casefold()
    if not value:
        return "technical_failure"
    if "original 3.x global model-call allowance exhausted" in value or "budget_exhausted" in value or "original budget exhausted" in value:
        return "budget_exhausted"
    if any(token in value for token in ("timed out", "timeout", "deadline exceeded")):
        return "model_timeout"
    if any(token in value for token in ("codex cli not found", "codex subscription login unavailable",
                                        "needs the existing chatgpt login", "not logged in",
                                        "executable not found", "permission denied")):
        return "executor_unavailable"
    if any(token in value for token in ("network", "connection refused", "connection reset",
                                        "dns", "name resolution", "proxy error", "tls handshake")):
        return "network_failure"
    if any(token in value for token in ("json schema", "schema validation", "invalid schema",
                                        "schema_error", "validationerror")):
        return "schema_error"
    if any(token in value for token in ("missing original", "missing source", "missing evidence",
                                        "missing receipt", "no such file", "file not found",
                                        "out-of-namespace", "evidence missing")):
        return "evidence_missing"
    if any(token in value for token in ("academic_stop", "academic failure", "research eliminated",
                                        "topic eliminated", "academic rejection")):
        return "academic_failure"
    return "technical_failure"


def classify_failure(error):
    """Map typed host failures first, then narrowly recognized original diagnostics."""
    if isinstance(error, OriginalBudgetExhausted):
        return "budget_exhausted"
    if isinstance(error, (subprocess.TimeoutExpired, TimeoutError)):
        return "model_timeout"
    if isinstance(error, ValidationError):
        return "schema_error"
    if isinstance(error, (ConnectionError, URLError, socket.gaierror)):
        return "network_failure"
    if isinstance(error, PermissionError):
        return "executor_unavailable"
    if isinstance(error, FileNotFoundError):
        filename = str(getattr(error, "filename", "") or "").casefold()
        return "executor_unavailable" if "codex" in filename else "evidence_missing"
    return classify_failure_message(error)


RECOVERY_POLICIES = {
    "network_failure": {
        "disposition": "retryable",
        "next_action": "Check the transient network fault, then request an explicitly authorized new attempt.",
        "preconditions": ["same current task snapshot", "original remaining call/time budget is positive",
                         "previous attempt and receipts are preserved", "new attempt identity",
                         "explicit retry authorization"],
    },
    "model_timeout": {
        "disposition": "retryable",
        "next_action": "Inspect timeout and partial receipts, then request an explicitly authorized new attempt.",
        "preconditions": ["same current task snapshot", "original remaining call/time budget is positive",
                         "previous attempt and partial receipts are preserved", "new attempt identity",
                         "explicit retry authorization"],
    },
    "executor_unavailable": {
        "disposition": "manual",
        "next_action": "Restore and verify the selected executor or login before resuming.",
        "preconditions": ["executor availability independently verified", "same active task snapshot"],
    },
    "schema_error": {
        "disposition": "manual",
        "next_action": "Inspect the schema/contract mismatch; correct and freeze a new task version before resubmission.",
        "preconditions": ["schema error understood", "new or revalidated task snapshot", "old result preserved"],
    },
    "evidence_missing": {
        "disposition": "manual",
        "next_action": "Obtain the missing original source, file or receipt; do not rerun the model to fabricate it.",
        "preconditions": ["missing evidence supplied and hash-checked", "dependent snapshot revalidated"],
    },
    "academic_failure": {
        "disposition": "terminate",
        "next_action": "Stop this topic path; only an explicit new research decision may start another path.",
        "preconditions": ["no automatic retry or same-topic promotion"],
    },
    "budget_exhausted": {
        "disposition": "terminate",
        "next_action": "Stop until the user explicitly authorizes a new original budget and a new verified manifest.",
        "preconditions": ["no automatic retry", "no implicit budget increase"],
    },
    "user_cancelled": {
        "disposition": "terminate",
        "next_action": "Remain stopped until the user explicitly starts a new run or authorizes resumption.",
        "preconditions": ["no automatic restart"],
    },
    "technical_failure": {
        "disposition": "manual",
        "next_action": "Inspect and refine the unclassified technical failure before any retry.",
        "preconditions": ["failure reason classified", "original budget checked", "previous attempt preserved"],
    },
    "research_failure": {
        "disposition": "terminate",
        "next_action": "Stop the current research path; do not promote or retry automatically.",
        "preconditions": ["new research path requires explicit authorization"],
    },
    "review_failure": {
        "disposition": "manual",
        "next_action": "Restore the missing independent reviewer/session/receipt and revalidate the same task.",
        "preconditions": ["reviewer independence and original execution records checked"],
    },
}


def recovery_policy(outcome_kind):
    if outcome_kind is None:
        return None
    if outcome_kind not in RECOVERY_POLICIES:
        raise ValueError("Unknown recovery outcome")
    return {"outcome_kind": outcome_kind, **RECOVERY_POLICIES[outcome_kind],
            "automatic_retry": False, "formal_eligible": False}


def retry_decision(outcome_kind, *, remaining_budget=None, task_snapshot_current=False,
                   previous_attempt_preserved=False, new_attempt_identity=False,
                   explicit_retry_authorized=False):
    """Only transient network/timeout failures can be retried, and never automatically."""
    policy = recovery_policy(outcome_kind)
    if policy is None or policy["disposition"] != "retryable":
        return {"allowed": False, "disposition": policy["disposition"] if policy else "manual",
                "reason": "Outcome is not eligible for retry", "automatic_retry": False}
    if task_snapshot_current is not True:
        reason = "Current task snapshot is not verified"
    elif type(remaining_budget) not in (int, float) or not math.isfinite(float(remaining_budget)):
        reason = "Original remaining budget is unknown or non-finite"
    elif remaining_budget <= 0:
        return {"allowed": False, "disposition": "terminate",
                "reason": "Original remaining budget is exhausted; no retry without a newly authorized budget.",
                "automatic_retry": False}
    elif previous_attempt_preserved is not True:
        reason = "Previous attempt and receipts are not preserved"
    elif new_attempt_identity is not True:
        reason = "A new attempt identity is required"
    elif explicit_retry_authorized is not True:
        reason = "Explicit retry authorization is required"
    else:
        return {"allowed": True, "disposition": "retryable",
                "reason": "All original-budget and preservation guards passed",
                "automatic_retry": False}
    return {"allowed": False, "disposition": "manual", "reason": reason,
            "automatic_retry": False}


def failure_evidence(outcome_kind, *, raw_error=None, stage=None, input_sha256=None, executor=None):
    """Record only supplied evidence; missing context stays null, never guessed."""
    policy = recovery_policy(outcome_kind)
    if policy is None:
        return None
    valid_hash = (input_sha256 if isinstance(input_sha256, str)
                  and re.fullmatch(r"[0-9a-f]{64}", input_sha256) else None)
    return {"raw_error": raw_error, "stage": stage, "input_sha256": valid_hash,
            "executor": executor, "recovery_suggestion": policy["next_action"],
            "outcome_kind": outcome_kind, "formal_eligible": False}


def observation(status, *, original_stage=None, scope="command", reason=None, outcome_kind=None,
                error_text=None, input_sha256=None, executor=None):
    if status not in STATES:
        raise ValueError("Unknown runtime observation")
    if outcome_kind not in {None, *OUTCOME_KINDS}:
        raise ValueError("Unknown runtime outcome")
    return {"runtime_status":status,"outcome_kind":outcome_kind,"scope":scope,"original_stage":original_stage,
        "reason":reason,"recovery_policy":recovery_policy(outcome_kind),
        "failure_evidence":failure_evidence(outcome_kind,raw_error=error_text,stage=original_stage,
                                            input_sha256=input_sha256,executor=executor),
        "academic_approval_granted":False,"formal_eligible":False}


def attempt_observation(record):
    """Observe an actual native call ledger entry; don't infer a launch from a task packet."""
    if record is None:
        return observation("queued",scope="native_attempt")
    status={"started":"running","completed":"completed","failed":"failed",
            "technical_block":"failed"}.get(record.get("status"),"blocked")
    failure = record.get("failure_kind")
    if failure not in OUTCOME_KINDS:
        failure = classify_failure_message(record.get("failure") or record.get("error") or record.get("reason"))
    original = record.get("failure_evidence")
    original = original if isinstance(original, dict) else {}
    raw_error = original.get("raw_error", record.get("failure") or record.get("error") or record.get("reason"))
    return observation(status,scope="native_attempt",reason=record.get("status"),
                       original_stage=record.get("stage"),
                       outcome_kind=failure if status=="failed" else None,
                       error_text=raw_error,input_sha256=record.get("task_sha256"),
                       executor=record.get("executor"))


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
    outcome=None
    wait=view.get("wait") if isinstance(view.get("wait"),dict) else {}
    explicit=view.get("failure_kind") or view.get("outcome_kind")
    def failure_kind(fallback="technical_failure"):
        if explicit in OUTCOME_KINDS:
            return explicit
        detail=view.get("failure") or view.get("reason") or view.get("error")
        if isinstance(detail,list):
            detail=" ".join(str(item) for item in detail)
        return classify_failure_message(detail) if detail else fallback
    if status=="cancelled_by_user":
        state="blocked";outcome="user_cancelled"
    elif stage=="literature_budget_exhausted" or view.get("original_gate_status")=="blocked_original_budget":
        state="waiting_for_user" if status=="waiting_for_user" else "blocked";outcome="budget_exhausted"
    elif stage in {"archived","eliminated","academic_stop"} or status=="academic_stop":
        state="failed";outcome="academic_failure"
    elif wait.get("reason_code")=="invalid_or_incomplete_records":
        state="waiting_for_review";outcome="evidence_missing"
    elif wait.get("reason_code") in {"review_execution_incomplete","independent_session_unavailable"}:
        state="waiting_for_review";outcome="review_failure"
    elif status in {"awaiting_original_independent_material_and_writing_receipts","awaiting_material_adequacy","needs_supplement"}:
        state="waiting_for_review";outcome="evidence_missing"
    elif status in {"network_failure","executor_unavailable","model_timeout","schema_error","evidence_missing"} or view.get("execution_status")=="failed" or status=="execution_failed":
        outcome=failure_kind()
        state="blocked" if outcome=="evidence_missing" else "failed"
    elif command=="chat-task":
        state="waiting_for_chat"
    elif command=="codex-task":
        state="waiting_for_codex"
    elif command=="review-task" or action=="await_independent_review" or status=="unable_to_review":
        state="waiting_for_review"
    elif status in {"waiting_for_user","awaiting_original_quantitative_inputs"}:
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
        if status=="queued" and action=="user_hold_acknowledged":
            state="queued"
        elif action in {"original_native_literature_search","original_s08_freeze"} and "after" not in view:
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
    return observation(state,original_stage=stage,scope="command",reason=reason,outcome_kind=outcome,
                       error_text=view.get("error") or view.get("failure") or view.get("reason"),
                       input_sha256=view.get("input_sha256") or view.get("task_sha256"),
                       executor=view.get("executor"))
