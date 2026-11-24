"""D21c: prepare candidate reviews from selected original pending artifacts.

File/hash binding only. Does not authenticate prior reviews, dispatch, or advance.
"""
import json
import re
import sys
from pathlib import Path


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


class Inputs:
    def __init__(self, root, heritage):
        self.root, self.h = root.resolve(), heritage
        self.artifacts = {}

    def path(self, raw):
        _require(isinstance(raw, str) and raw and "\\" not in raw and ":" not in raw, "Use a run-relative artifact path")
        rel = Path(raw)
        _require(not rel.is_absolute() and ".." not in rel.parts and rel.as_posix() == raw, "Invalid run-relative artifact")
        path = (self.root / rel).resolve(strict=True)
        _require(path.is_file() and path.is_relative_to(self.root), "Artifact outside selected run")
        return path

    def add(self, raw):
        path = self.path(raw)
        ref = {"path": raw, "sha256": self.h.sha(path)}
        if raw in self.artifacts:
            _require(self.artifacts[raw]["sha256"] == ref["sha256"], "Artifact changed during preparation")
        self.artifacts[raw] = {"artifact_id": raw, "role": raw, **ref}
        return ref

    def read(self, raw):
        ref = self.add(raw)
        data = self.h.read(self.path(raw))
        _require(self.h.sha(self.path(raw)) == ref["sha256"], "Artifact changed while reading")
        return data

    def optional(self, raw):
        if (self.root / raw).exists():
            return self.add(raw)
        return None


def _original_binding(h, work, folder):
    # Invoke the original question-binding function in a separate import context.
    script = "import sys,json; from pathlib import Path; sys.path.insert(0,sys.argv[1]); import staged_topic; from question_binding import binding; print(json.dumps(binding(Path(sys.argv[2]),Path(sys.argv[3]))))"
    return json.loads(h.original_call([sys.executable, "-B", "-c", script,
        str(h.V32 / "tools"), str(work), str(folder)], timeout=30))


def _language_refs(h):
    # Original V16 checks resource locks and G3 status; do not duplicate its rules.
    script = "import sys,json; sys.path.insert(0,sys.argv[1]); from ai_writer4 import language_resources; p,s,r,b,u,l,a,w,v=language_resources(); print(json.dumps({'locks':l,'g3_status':s['status']}))"
    return json.loads(h.original_call([sys.executable, "-B", "-c", script,
        str(h.V16.parent)], timeout=30))


def _base_inputs(run_id, h, contract, work, state, inputs):
    inputs.add("run_manifest.json")
    inputs.add("staged_topic.json")
    original = json.loads(h.original_call(h.original_command("prepare", run_id)))
    _require(original.get("status") == state["status"] and original.get("question") == state.get("question")
             and original.get("evidence_sha256"), "Original review preparation is stale or incomplete")
    papers = "merged_literature.json" if state["status"] == "final_review" or state.get("review_phase") == "final" else "initial/literature_matrix.json"
    _require(Path(original["papers"]).resolve() == inputs.path(papers)
             and Path(original["theories"]).resolve() == inputs.path("initial/theories.json"),
             "Original evidence paths differ from selected run")
    inputs.add(papers)
    inputs.add("initial/theories.json")
    for flag, paths in (("reality_first", ["reality.json"]), ("explanation_first", ["explanation_exchange.json"]),
                        ("issue_search", ["issue_plan.json", "event_comparison.json"])):
        if state.get(flag):
            for path in paths:
                inputs.add(path)
    return original


def _receipt(contract, inputs, folder, framework=False):
    conversion = inputs.read(folder + "/conversion.json")
    receipt = inputs.read(folder + "/material_receipt.json")
    _require(receipt.get("run_id") == inputs.root.name and receipt.get("status") == "pending_independent_review"
             and receipt.get("conversion_sha256") == contract._digest(conversion)
             and receipt.get("events_sha256") == inputs.add(folder + "/events.jsonl")["sha256"]
             and receipt.get("response_sha256") == inputs.add(folder + "/response.json")["sha256"]
             and type(receipt.get("tool_events")) is int and receipt["tool_events"] > 0,
             "Material receipt or original bytes differ")
    _require((receipt.get("phase") == "framework_collection") == framework, "Wrong original material collection phase")
    rows = receipt.get("materials")
    _require(isinstance(rows, list), "Missing material candidates")
    ids = [row.get("material_id") for row in rows]
    _require(all(isinstance(i, str) and i for i in ids) and len(set(ids)) == len(ids), "Invalid material IDs")
    return conversion, receipt, set(ids)


def _matrix_claims(matrix, ids):
    rows = matrix.get("rows")
    _require(isinstance(rows, list) and rows, "Missing empirical matrix dimensions")
    claims, dimensions, seen = [], [], set()
    for row in rows:
        key = row["dimension_id"]
        _require(isinstance(key, str) and key and key not in seen and row.get("status") in {"tentative", "unresolved"},
                 "Invalid matrix dimension")
        seen.add(key)
        refs = [item["material_id"] for item in row["evidence"]]
        _require(set(refs) <= ids, "Matrix refers to unavailable material ID")
        claims.append({"claim_id": "matrix:" + key, "statement": row["conclusion"], "type": row["status"],
                       "evidence_ids": refs, "scope": row["boundary"]})
        dimensions.append("matrix:" + key)
    return claims, dimensions


def _matrix(contract, h, inputs, path):
    _require(re.fullmatch(r"qualitative_framework/attempt_[0-9]{3}/analysis_matrix(?:_reviewed)?\.json", path) is not None,
             "Select an original matrix in its run-owned framework attempt")
    folder = path.rsplit("/", 1)[0]
    conversion, receipt, ids = _receipt(contract, inputs, folder, framework=True)
    framework = inputs.read(folder + "/framework.json")
    matrix = inputs.read(path)
    # Check parent paths and cycles before calling the original recursive binding.
    seen = {folder}
    parent = receipt.get("parent_attempt")
    while parent:
        _require(re.fullmatch(r"attempt_[0-9]{3}", parent) is not None, "Invalid parent attempt")
        prior = "qualitative_framework/" + parent
        _require(prior not in seen, "Cyclic parent attempt")
        seen.add(prior)
        _, old, _ = _receipt(contract, inputs, prior, framework=True)
        inputs.add(prior + "/framework.json")
        parent = old.get("parent_attempt")
    binding = _original_binding(h, inputs.root, inputs.root / folder)
    _require(matrix.get("framework_sha256") == contract._digest(framework)
             and matrix.get("collection_sha256") == contract._digest(receipt)
             and (matrix.get("question_binding") is None or matrix["question_binding"] == binding),
             "Matrix differs from original framework, collection or question binding")
    claims, dimensions = _matrix_claims(matrix, ids)
    return matrix, binding, ids, claims, dimensions


def _plan(contract, h, inputs, request_path, *, require_pending):
    _require(re.fullmatch(r"(?:autonomous_writing/draft_[0-9]+|writing)/writing_plan_review_request\.json", request_path) is not None,
             "Select an original V15 review request")
    folder = request_path.rsplit("/", 1)[0]
    request = inputs.read(request_path)
    packet_path = folder + "/plan_input.json"
    packet = inputs.read(packet_path)
    plan = inputs.add(folder + "/论文写作方案.md")
    _require(request.get("run_id") == inputs.root.name and request.get("status") == "plan_prepared"
             and request.get("review_status") in ({"pending"} if require_pending else {"pending", "pass", "conditional_pass"})
             and request.get("formal_eligible") is False
             and request.get("input_sha256") == contract._digest(packet)
             and request.get("plan_sha256") == plan["sha256"]
             and request.get("topic_sha256") == inputs.add("s08_topic.json")["sha256"],
             "V15 request, plan, packet or frozen topic differs")
    matrix_path = packet.get("analysis_matrix")
    _require(isinstance(matrix_path, str) and matrix_path.endswith("/analysis_matrix_reviewed.json"),
             "V15 needs the original reviewed-matrix artifact; no adequacy is inferred")
    matrix, binding, ids, claims, dims = _matrix(contract, h, inputs, matrix_path)
    _require(request.get("analysis_matrix_sha256") == inputs.add(matrix_path)["sha256"]
             and request.get("question_binding") == packet.get("question_binding") == binding
             and packet.get("specific_question") == binding["specific_question"]
             and packet.get("method") == binding["method"],
             "V15 packet differs from original question or matrix")
    inputs.optional("matrix_independent_review.json")
    inputs.optional("autonomous_writing/revision_checkpoint.json")
    sources = packet.get("sources")
    _require(isinstance(sources, dict) and sources, "V15 sources are missing")
    pending = set(sources) - ids
    for chapter in packet["chapters"]:
        for index, section in enumerate(chapter["sections"], 1):
            refs = section["source_ids"]
            _require(set(refs) <= sources.keys(), "V15 section refers to unknown source")
            claims.append({"claim_id": "plan:" + chapter["id"] + ":" + str(index), "statement": section["argument"],
                           "type": "proposed_argument", "evidence_ids": refs,
                           "scope": "Planned argument; not an established empirical result."})
    return packet, binding, ids, claims, dims, pending


def prepare_artifact_review_task(run_id, review_object, *, packet_path=None, manuscript_path=None, claims_path=None,
                                 prior_report=None, revision_record=None):
    import task_packet as contract
    h = contract.heritage
    h.doctor()
    h.run_id_guard(run_id)
    work = (h.RUNS / run_id).resolve(strict=True)
    manifest = contract.run_mode.verified_run(work)
    state = h.state_of(run_id)
    _require(manifest.get("run_id") == run_id and state.get("run_id") == run_id, "Original research identity mismatch")
    from review_revision_task import select_lineage, attach_lineage, revision_task_id
    lineage = select_lineage(contract, work, prior_report, revision_record)
    inputs = Inputs(work, h)
    original = _base_inputs(run_id, h, contract, work, state, inputs)
    question = state.get("question")
    _require(isinstance(question, str) and question.strip(), "Missing original reviewed question")
    frozen = state["status"] == "frozen"
    design = {"status": "not_frozen", "freeze_ref": None, "proposal_refs": []}
    policy = [{"path": path.relative_to(h.ROOT).as_posix(), "sha256": h.sha(path)}
              for path in (h.V3_POLICY, h.V3_SEARCH_PROMPT)]
    if frozen:
        topic = inputs.read("s08_topic.json")
        history = state.get("history", [])
        _require(history and topic.get("stage") == "S08" and topic.get("question") == question
                 and topic.get("evidence_sha256") == original["evidence_sha256"]
                 and topic.get("review_sha256") == contract._digest(history[-1])
                 and history[-1].get("outcome") == "pass" and history[-1].get("question") == question,
                 "Frozen topic differs from original state or evidence")
        design = {"status": "frozen", "freeze_ref": inputs.add("s08_topic.json"), "proposal_refs": []}
    ids, pending, claims = set(), set(), []
    selected = inputs.path(review_object)
    _require(not any((packet_path, manuscript_path, claims_path)) or selected.name == "writing_review_request.json",
             "Draft paths apply only to an original V16 request")
    if re.fullmatch(r"qualitative/attempt_[0-9]{3}/material_receipt\.json", review_object):
        _require(state["status"] in {"design_review", "materials_pending", "final_review"}, "Qualitative design review is not due")
        folder = review_object.rsplit("/", 1)[0]
        _require(not (work / folder / "review.json").exists(), "Original qualitative review already recorded")
        conversion, receipt, ids = _receipt(contract, inputs, folder)
        _require(question in {conversion.get("prior_question"), conversion.get("new_question")}, "Conversion differs from original question")
        design["proposal_refs"] = [inputs.add(folder + "/conversion.json")]
        kind, gate, dims = "qualitative_design", "06/v005 qual_materials.record_review", ["question_continuity", "three_method_paths", "material_access"]
    elif selected.name == "analysis_matrix.json":
        _require(frozen, "Empirical matrix review requires original S08 freeze")
        _require(lineage is not None or not (work / "matrix_independent_review.json").exists(), "Existing matrix review requires explicit re-review lineage")
        inputs.optional("matrix_independent_review.json")
        matrix, binding, ids, claims, dims = _matrix(contract, h, inputs, review_object)
        _require(matrix.get("status") == "pending_independent_review", "Matrix is not pending review")
        kind, gate, dims = "empirical_matrix", "00/v009 resume_writing.resume", dims + ["material_adequacy", "theoretical_increment"]
    elif selected.name == "writing_plan_review_request.json":
        _require(frozen, "V15 academic review requires original S08 freeze")
        _, _, ids, claims, dims, pending = _plan(contract, h, inputs, review_object, require_pending=True)
        kind, gate, dims = "writing_plan", "00/v009 resume_writing.resume + V15", dims + ["paragraph_progression", "theory_evidence_scope", "material_adequacy"]
    elif selected.name == "writing_review_request.json":
        _require(frozen and all((packet_path, manuscript_path, claims_path)), "V16 requires original freeze and explicit packet/draft/ledger paths")
        _require(packet_path.endswith("/plan_input.json"), "Select original V15 plan_input.json")
        request = inputs.read(review_object)
        folder = review_object.rsplit("/", 1)[0]
        _require("/" in review_object, "V16 request must be in its own workspace")
        writer = inputs.read(folder + "/writer_manifest.json")
        inputs.add(folder + "/style_review.json")
        _require(request.get("status") == "exploratory_draft_awaiting_review"
                 and request.get("independent_review") == "pending" and request.get("formal_pass") is False
                 and request.get("gate") == "G7" and request.get("structural_errors") == []
                 and writer.get("run_id") in {None, run_id} and writer.get("mode") == "exploratory"
                 and request.get("packet_sha256") == writer.get("packet_sha256") == inputs.add(packet_path)["sha256"]
                 and request.get("manuscript_sha256") == inputs.add(manuscript_path)["sha256"]
                 and request.get("claim_ledger_sha256") == inputs.add(claims_path)["sha256"],
                 "V16 request is not pending or selected draft inputs changed")
        packet, _, ids, _, _, pending = _plan(contract, h, inputs,
            packet_path.rsplit("/", 1)[0] + "/writing_plan_review_request.json", require_pending=False)
        locks = _language_refs(h)
        _require(writer.get("resource_sha256") == locks["locks"], "Original V16 language resources changed")
        policy.extend({"path": Path(ref["path"]).as_posix(), "sha256": ref["sha256"]} for ref in locks["locks"].values())
        ledger = inputs.read(claims_path)["claims"]
        manuscript = inputs.path(manuscript_path).read_text(encoding="utf-8-sig")
        seen = set()
        for row in ledger:
            key = row["claim_id"]
            literal = row.get("exact_text") or row.get("claim_text")
            refs = row["source_ids"]
            _require(isinstance(key, str) and key and key not in seen and isinstance(literal, str)
                     and literal and literal in manuscript and isinstance(refs, list) and refs
                     and set(refs) <= packet["sources"].keys(), "V16 claim not located or source unknown")
            seen.add(key)
            claims.append({"claim_id": key, "statement": literal, "type": "draft_claim",
                           "evidence_ids": refs, "scope": "Candidate claim, semantic support requires independent review."})
        _require(claims, "V16 claim ledger is empty")
        kind, gate, dims = "qualitative_g7", "V16 writing_review_request", ["claim_support", "counterevidence", "argument_progression", "language_and_scope"]
    else:
        raise ValueError("Unrecognized original pending review object")
    artifacts = list(inputs.artifacts.values())
    allowed = sorted({a["artifact_id"] for a in artifacts} | ids)
    pending = sorted(pending - set(allowed))
    _require(len({c["claim_id"] for c in claims}) == len(claims), "Duplicate review claim")
    purpose = "Candidate review of " + kind + "; original gate retains authority."
    context = {"context_version": 1, "review_kind": kind, "review_type": "academic_review",
        "gate_ref": gate, "research_question": question, "design": design, "input_materials": artifacts,
        "key_claims": claims, "claims_scope": "Only the selected original artifacts; no established mechanism or formal pass is implied.",
        "evidence_scope": {"allowed_ids": allowed, "excluded_or_pending_ids": pending,
            "limitations": ["Candidate material IDs are not authenticated semantic support.",
                            "Prior review/adequacy and G3 flags are not independent authorization."], "policy_refs": policy},
        "review_dimensions": [{"dimension_id": d, "question": d, "evidence_ids": allowed,
            "failure_condition": "Insufficient traceable evidence or unresolved scope."} for d in dict.fromkeys(dims)],
        "prohibitions": ["No additional search", "No source invention", "No original state mutation", "No formal approval"],
        "prior_review": None, "input_binding": {"original_evidence_sha256": original["evidence_sha256"],
            "selected_object": inputs.add(review_object)}}
    refs = attach_lineage(contract, work, context, [{"path": a["path"], "sha256": a["sha256"]} for a in artifacts], lineage, stage_id=kind)
    context_path = work / "review_tasks" / (contract._digest(context) + ".json")
    _require(context_path.resolve().is_relative_to(work), "Review context outside run")
    if context_path.exists():
        _require(h.read(context_path) == context, "Existing review context changed")
    else:
        contract._atomic_json(context_path, context)
    refs.append(inputs.add(context_path.relative_to(work).as_posix()))
    schema = Path(__file__).resolve().parents[1] / "schemas/review_result.schema.json"
    packet = {"schema_version": 1, "research_id": run_id, "stage_id": kind,
        "task_id": revision_task_id(contract, "original_artifact_review_" + contract._digest(review_object)[:24], lineage),
        "purpose": purpose, "research_question": question, "search_levels": [], "input_files": refs,
        "source_scope": {"policy_refs": policy}, "quantity_budget": {}, "time_budget_seconds": 0,
        "output_schema": {"kind": "file", "file": {"path": schema.relative_to(h.ROOT).as_posix(), "sha256": h.sha(schema)}},
        "stop_conditions": ["Original artifacts or state changed", "No independent execution authorization", "Missing required evidence"]}
    _require(h.state_of(run_id) == state and json.loads(h.original_call(h.original_command("prepare", run_id))) == original,
             "Original state or evidence changed during review preparation")
    snapshot = contract.freeze_packet(packet, current_run_id=run_id,
        **({"supersedes": [lineage["old"]]} if lineage is not None else {}))
    contract.verify_snapshot(snapshot, current_run_id=run_id)
    return {"task_packet": packet, "task_snapshot": snapshot, "context_path": context_path.relative_to(work).as_posix(),
            "dispatch_authorized": False, "formal_eligible": False}
