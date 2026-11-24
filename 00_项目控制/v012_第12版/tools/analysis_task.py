"""F12: frozen original framework and matrix preparation, never model execution."""
import json
import re
import sys
import task_packet as c
from review_artifact_task import Inputs, _receipt, _original_binding

def prepare_analysis_task(run_id, kind, attempt="attempt_001"):
    h=c.heritage
    if kind not in {"framework","matrix"} or not re.fullmatch(r"attempt_[0-9]{3}",attempt):
        raise ValueError("Select an original framework or matrix attempt")
    h.doctor()
    work=(h.RUNS/h.run_id_guard(run_id)).resolve(strict=True)
    state=h.state_of(run_id)
    if state["status"]!="frozen":
        raise ValueError("Original S08 must be frozen")
    route=h.frozen_route(run_id)
    method=route["method"]
    if method not in {"secondary_interviews","online_qualitative"}:
        raise ValueError("Original qualitative method required")
    reviewed=state["history"][-1]["method_assessment"]["paths"][method]
    preliminary=reviewed.get("search_attempt")
    if not isinstance(preliminary,str) or not re.fullmatch(r"attempt_[0-9]{3}",preliminary):
        raise ValueError("Original preliminary material attempt required")
    if kind=="framework" and attempt!=preliminary:
        raise ValueError("Select the reviewed preliminary attempt")
    inputs=Inputs(work,h)
    for name in ("run_manifest.json","staged_topic.json","s08_topic.json","merged_literature.json","initial/theories.json"):
        inputs.add(name)
    for flag,names in (("reality_first",["reality.json"]),("explanation_first",["explanation_exchange.json"]),
                       ("issue_search",["issue_plan.json","event_comparison.json"])):
        if state.get(flag):
            for name in names: inputs.add(name)
    prior,_,_= _receipt(c,inputs,"qualitative/"+preliminary)
    folder=("qualitative/" if kind=="framework" else "qualitative_framework/")+attempt
    conversion,receipt,ids=_receipt(c,inputs,folder,framework=kind=="matrix")
    if prior!=conversion or conversion["new_question"]!=state["question"]:
        raise ValueError("Original reviewed conversion differs")
    framework=inputs.read(folder+"/framework.json") if kind=="matrix" else None
    script=("import sys,json; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
        "from qual_materials import verify_frozen_conversion; from collect_common import load; "
        "from framework import FRAMEWORK_CONTEXT,DIMENSION_FIELDS,CLAIM_FIELDS,RELATIONS,validate_framework; "
        "work=Path(sys.argv[2]); folder=Path(sys.argv[3]); "
        "f=load(folder/'framework.json') if sys.argv[4]=='matrix' else None; "
        "verify_frozen_conversion(work,load(folder/'conversion.json'),framework=f); "
        "validate_framework(f) if f is not None else None; "
        "print(json.dumps([FRAMEWORK_CONTEXT,DIMENSION_FIELDS,CLAIM_FIELDS,sorted(RELATIONS)]))")
    fields,dims,claims,relations=json.loads(h.original_call([sys.executable,"-B","-c",script,
        str(h.MATERIAL.parent),str(work),str(work/folder),kind],timeout=60))
    if kind=="matrix":
        binding=_original_binding(h,work,work/folder)
        if receipt["framework_sha256"]!=c._digest(framework):
            raise ValueError("Original framework receipt changed")
        out={"type":"array","items":{"type":"object","required":["dimension_id","status","evidence",*claims],
            "properties":{**{key:{"type":"string"} for key in claims},
                "dimension_id":{"enum":[row["id"] for row in framework["dimensions"]]},
                "status":{"enum":["tentative","unresolved"]},
                "evidence":{"type":"array","items":{"type":"object","required":["material_id","relation","reason"],
                    "properties":{"material_id":{"enum":sorted(ids)},"relation":{"enum":relations},"reason":{"type":"string"}}}}}}}
    else:
        binding=None
        out={"type":"object","required":[*fields,"dimensions"],"properties":{
            **{key:{"type":"string"} for key in fields},
            "dimensions":{"type":"array","minItems":1,"items":{"type":"object","required":dims,
                "properties":{key:{"type":"string"} for key in dims}}}}}
    purpose={"kind":kind,"original_design":state["history"][-1]["design"],
        "core_question":conversion["core_question"],"material_ids":sorted(ids),
        "instructions":"Use original framework/analysis_matrix validators. All dimensions required, keep counterexamples, competing explanations, unknowns and boundaries. Do not invent evidence or infer an independent pass."}
    packet={"schema_version":1,"research_id":run_id,"stage_id":"qualitative_"+kind,"task_id":kind+"_"+attempt,
        "purpose":json.dumps(purpose,ensure_ascii=False,sort_keys=True),"research_question":state["question"],
        "search_levels":[],"input_files":[{"path":x["path"],"sha256":x["sha256"]} for x in inputs.artifacts.values()],
        "source_scope":{"policy_refs":[{"path":(h.MATERIAL.parent/"framework.py").relative_to(h.ROOT).as_posix(),
                                        "sha256":h.sha(h.MATERIAL.parent/"framework.py")}]},
        "quantity_budget":{},"time_budget_seconds":0,"output_schema":{"kind":"inline","schema":out},
        "stop_conditions":["Original input changed","Unresolved evidence cannot be promoted","No independent approval"]}
    snapshot=c.freeze_packet(packet,current_run_id=run_id)
    c.verify_snapshot(snapshot,current_run_id=run_id)
    return {"task_packet":packet,"task_snapshot":snapshot,"question_binding":binding,
            "dispatch_authorized":False,"formal_eligible":False,"status":"candidate_ready"}
