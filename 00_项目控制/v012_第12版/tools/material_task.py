"""F06: prepare a frozen material-acquisition task without native execution."""
import json
import sys
from pathlib import Path
import task_packet as c

FIELDS=("target_objects","events","time_range","material_types","exclusions")

def prepare_material_task(run_id):
    h=c.heritage
    h.doctor()
    work=(h.RUNS/h.run_id_guard(run_id)).resolve(strict=True)
    manifest=c.run_mode.verified_run(work)
    state=h.state_of(run_id)
    if state["status"]!="frozen":
        raise ValueError("Original S08 must be frozen")
    route=h.frozen_route(run_id)
    if route["method"] not in {"secondary_interviews","online_qualitative"}:
        raise ValueError("Original qualitative method required")
    reviewed=state["history"][-1]
    decision=reviewed["method_assessment"]["paths"][route["method"]]
    attempt=decision.get("search_attempt","")
    import re
    if not re.fullmatch(r"attempt_[0-9]{3}",attempt):
        raise ValueError("Original reviewed material attempt required")
    folder=work/"qualitative"/attempt
    conversion=h.read(folder/"conversion.json")
    script=("import sys,json; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
            "from qual_materials import verify_frozen_conversion,schema,validate_conversion; "
            "from collect_common import load; work=Path(sys.argv[2]); "
            "packet=load(Path(sys.argv[3])); validate_conversion(packet); "
            "verify_frozen_conversion(work,packet); print(json.dumps(schema()))")
    spec=json.loads(h.original_call([sys.executable,"-B","-c",script,str(h.MATERIAL.parent),
        str(work),str(folder/"conversion.json")],timeout=60))
    def ref(root,path):
        actual=path.resolve(strict=True)
        if not actual.is_file() or not actual.is_relative_to(root.resolve()):
            raise ValueError("Input outside original namespace")
        return {"path":path.relative_to(root).as_posix(),"sha256":h.sha(actual)}
    inputs=[ref(work,work/name) for name in ("run_manifest.json","staged_topic.json","s08_topic.json")]
    inputs += [ref(work,folder/name) for name in ("conversion.json","material_receipt.json","events.jsonl","response.json")]
    # No inference of an empirical scope from a free-text design. Only an explicit
    # scope carried by the frozen review may fill these fields.
    supplied=reviewed.get("material_scope",{})
    if not isinstance(supplied,dict): raise ValueError("Invalid reviewed material scope")
    scope={}
    for key in FIELDS:
        value=supplied.get(key)
        if key=="time_range":
            scope[key]=value.strip() if isinstance(value,str) and value.strip() else None
        else:
            scope[key]=value if isinstance(value,list) and value and all(isinstance(x,str) and x.strip() for x in value) else None
    missing=[key for key in FIELDS if scope[key] is None]
    budget=manifest["workload"]["11"]
    instruction={"frozen_design":reviewed["design"],"conversion":conversion,
        "method":route["method"],"reviewed_scope":scope,"unresolved_scope":missing,
        "original_limits":{"max_batches":budget["max_batches"],"native_search_actions":budget["native_search_actions"],
            "timeout_seconds":budget["timeout_seconds"]},
        "rules":"Use original 06 source/access/locator/boundary rules; distinguish actor claims, reporting, rules and observed actions. No private identifiers, inference as evidence, reprints as independent events, or scope expansion. Missing scope requires original review, not invented dates or events."}
    packet={"schema_version":1,"research_id":run_id,"stage_id":"qualitative_materials",
        "task_id":"frozen_material_acquisition","purpose":json.dumps(instruction,ensure_ascii=False,sort_keys=True),
        "research_question":conversion["new_question"],"search_levels":[],
        "input_files":inputs,"source_scope":{"policy_refs":[ref(h.ROOT,h.MATERIAL),ref(h.ROOT,h.V3_POLICY)]},
        "quantity_budget":{},"time_budget_seconds":0,"output_schema":{"kind":"inline","schema":spec},
        "stop_conditions":["Missing reviewed scope","Changed frozen input","Original budget or independent authorization unavailable"],
        "notes":["Candidate only; native 06 reserves original budget separately."]}
    snapshot=c.freeze_packet(packet,current_run_id=run_id)
    c.verify_snapshot(snapshot,current_run_id=run_id)
    return {"task_packet":packet,"task_snapshot":snapshot,"scope":scope,"unresolved_scope":missing,
        "status":"waiting_for_user" if missing else "candidate_ready","dispatch_authorized":False,"formal_eligible":False}
