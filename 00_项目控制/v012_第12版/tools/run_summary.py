"""I20: export observed run-local records, never reconstruct an execution."""
import hashlib
import json
import re
from pathlib import Path

from advance_trace import TRIGGERS
from runtime_log import CONTEXT_FILES, _ref
from run_observation import STATES, OUTCOME_KINDS

HEX64 = re.compile(r"[0-9a-f]{64}")
HEX32 = re.compile(r"[0-9a-f]{32}")
TAG = re.compile(r"[a-zA-Z0-9_-]{1,100}")


def _tag(value):
    return value if isinstance(value, str) and TAG.fullmatch(value) else None


def _read_record(work, path):
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(work):
        raise ValueError("Invalid run record path")
    raw = path.read_bytes()
    ref = {"path":path.relative_to(work).as_posix(),
           "sha256":hashlib.sha256(raw).hexdigest()}
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Invalid run record")
    return ref, data


def _directory(work, name):
    path = work / name
    if path.is_symlink() or (path.exists() and (not path.is_dir() or path.resolve()!=path)):
        raise ValueError("Invalid run record directory")
    return path


def _unresolved(path, reason):
    return {"record":path, "reason":reason}


def build_manifest(run_id):
    import task_packet
    h=task_packet.heritage
    h.run_id_guard(run_id)
    root=h.RUNS.resolve(strict=True)
    candidate=root/run_id
    work=candidate.resolve(strict=True)
    if candidate.is_symlink() or work.parent!=root or work.name!=run_id:
        raise ValueError("Invalid original run")
    # Read the actual original bytes, require the original manifest verifier.
    identity_ref,identity=_read_record(work,work/"run_manifest.json")
    state_ref,state=_read_record(work,work/"staged_topic.json")
    if (task_packet.run_mode.verified_run(work).get("run_id")!=run_id
            or identity.get("run_id")!=run_id or state.get("run_id")!=run_id
            or state.get("mode")!="dev"):
        raise ValueError("Original run identity mismatch")
    commands=[]; traces=[]; unresolved=[]
    for path in sorted(_directory(work,"runtime_log").glob("*.json")):
        label=path.relative_to(work).as_posix()
        try:
            ref,row=_read_record(work,path)
            if (not HEX64.fullmatch(path.stem) or ref["sha256"]!=path.stem
                    or row.get("research_id")!=run_id or row.get("schema_version")!=1
                    or row.get("record_kind")!="command_observation"):
                raise ValueError("Invalid command record")
            exc=row.get("exception")
            kind=exc.get("outcome_kind") if isinstance(exc,dict) else None
            commands.append({"record_ref":ref,"command":_tag(row.get("command")),
                "stage":_tag(row.get("stage_id")),
                "runtime_status":row.get("runtime_status") if row.get("runtime_status") in STATES else None,
                "exception_kind":kind if kind in OUTCOME_KINDS else None,
                "command_success":row.get("command_success") if type(row.get("command_success")) is bool else None})
        except (OSError,ValueError,TypeError,KeyError):
            unresolved.append(_unresolved(label,"invalid_command_record"))
    for path in sorted(_directory(work,"advance_trace").iterdir()) if (work/"advance_trace").exists() else []:
        label=path.relative_to(work).as_posix()
        try:
            if not HEX32.fullmatch(path.name) or path.is_symlink() or not path.is_dir():
                raise ValueError("Invalid trace path")
            ref,start=_read_record(work,path/"start.json")
            if (start.get("trace_id")!=path.name or start.get("research_id")!=run_id
                    or start.get("schema_version")!=1 or start.get("trigger") not in TRIGGERS):
                raise ValueError("Invalid trace identity")
            before=start.get("before")
            if not isinstance(before,dict) or not HEX64.fullmatch(str(before.get("state_sha256",""))):
                raise ValueError("Invalid trace before state")
            item={"trace_id":path.name,"start_ref":ref,"finish_ref":None,
                "trigger":start["trigger"],"before_stage":_tag(before.get("stage")),
                "after_stage":None,"stage_changed":None,"exception_kind":None,
                "status":"incomplete_or_interrupted"}
            finish_path=path/"finish.json"
            if finish_path.exists() or finish_path.is_symlink():
                try:
                    fref,end=_read_record(work,finish_path)
                    if (end.get("start_ref")!=ref or end.get("trace_id")!=path.name
                            or end.get("research_id")!=run_id or end.get("schema_version")!=1):
                        raise ValueError("Trace finish binding mismatch")
                    after=end.get("after")
                    kind=end.get("exception_kind")
                    item.update(finish_ref=fref, after_stage=_tag(after.get("stage")) if isinstance(after,dict) else None,
                                stage_changed=(before.get("stage")!=after.get("stage")) if isinstance(after,dict) else None,
                                exception_kind=kind if kind in OUTCOME_KINDS else None,
                                status="returned" if end.get("command_returned") is True else "failed_or_unknown")
                except (OSError,ValueError,TypeError,KeyError):
                    item["status"]="invalid_finish"
                    unresolved.append(_unresolved(label+"/finish.json","invalid_finish_binding"))
            traces.append(item)
        except (OSError,ValueError,TypeError,KeyError):
            unresolved.append(_unresolved(label,"invalid_trace_start"))
    evidence={key:[ref for name in names if (ref:=_ref(work,name)) is not None]
              for key,names in CONTEXT_FILES.items() if key!="identity"}
    # No replay; record the selected run snapshot only. Never infer the current conversation's execution.
    if _ref(work,"run_manifest.json")!=identity_ref or _ref(work,"staged_topic.json")!=state_ref:
        raise ValueError("Original run changed during summary")
    return work, {"schema_version":1,"research_id":run_id,"original_stage":_tag(state.get("status")),
        "original_identity_refs":[identity_ref,state_ref],"evidence_refs":evidence,
        "command_observations":commands,"advance_observations":traces,"unresolved_records":unresolved,
        "observation_scope":"existing_records_of_selected_original_run",
        "new_execution_performed":False,"complete_history_guaranteed":False,
        "academic_approval_granted":False,"formal_eligible":False,
        "counts":{"command_records":len(commands),"scheduler_iterations":sum(t["trigger"]=="autopilot_step" for t in traces),
                  "original_progress_dispatches":sum(t["trigger"]=="strict_progress" for t in traces),
                  "incomplete_or_invalid_traces":sum(t["status"] in {"incomplete_or_interrupted","invalid_finish"} for t in traces),
                  "unresolved_records":len(unresolved)}}


def render_summary(manifest):
    counts=manifest["counts"]
    lines=["# 研究运行观察摘要","",f"研究 ID：{manifest['research_id']}",
           f"原状态：{manifest['original_stage'] or 'unknown'}",
           "", "本摘要仅汇总选定原研究目录已有记录；本次未运行研究，不证明独立审查、完整历史或正式授权。",
           "", "## 记录数量", ""]
    for key,label in (("command_records","命令观察记录"),("scheduler_iterations","调度迭代"),
                      ("original_progress_dispatches","原推进派发"),("incomplete_or_invalid_traces","未完成或无效推进记录"),
                      ("unresolved_records","无法核验的记录")):
        lines.append(f"- {label}：{counts[key]}")
    lines += ["", "调度迭代和原推进派发可能嵌套，不能相加为阶段转换次数。",
              "", "## 证据索引", ""]
    for ref in manifest["original_identity_refs"]:
        lines.append(f"- {ref['path']} / SHA-256 {ref['sha256']}")
    lines += ["", "详见同目录 manifest.json；原始账本及门禁仍为唯一权威。",""]
    return "\n".join(lines)


def _write_once(path, raw):
    if path.is_symlink():
        raise ValueError("Summary path is symlinked")
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        if not path.is_file() or path.read_bytes()!=raw:
            raise ValueError("Existing summary changed")


def export_summary(run_id):
    work,manifest=build_manifest(run_id)
    raw=(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
    folder=_directory(work,"run_summaries")
    folder.mkdir(exist_ok=True)
    output=folder/hashlib.sha256(raw).hexdigest()
    if output.is_symlink():
        raise ValueError("Invalid summary output")
    output.mkdir(exist_ok=True)
    _write_once(output/"manifest.json",raw)
    _write_once(output/"summary.md",render_summary(manifest).encode())
    return {"status":"summary_exported","research_id":run_id,
            "manifest":_ref(work,output/"manifest.json"),"summary":_ref(work,output/"summary.md"),
            "counts":manifest["counts"],"new_execution_performed":False,"formal_eligible":False}
