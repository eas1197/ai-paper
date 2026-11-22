"""Resume a frozen qualitative experiment through independent writing-plan review."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from staged_topic import ROOT, run_mode, job_lock
from codex_literature import cli_environment, cli_executable, login_probe
from question_binding import binding, evidence_digest, file_hash

sys.path.insert(0, str(ROOT / "06_数据方法与分析/v005_第5版/tools"))
from framework import analysis_matrix
sys.path.insert(0, str(ROOT / "07_三稿独立写作/v015_第15版/tools"))
from writing_plan import produce

REVIEWER = "gpt-6.2-sol"
load, write = run_mode.load, run_mode.write


def dispatch(area, label, instruction, inputs, *, reviewer=False):
    request = {"instruction": instruction, "inputs": inputs,
               "model": REVIEWER if reviewer else "subscription_default"}
    root = area / label
    root.mkdir(exist_ok=True)
    for attempt in sorted(root.glob("attempt_*")):
        if (attempt / "validated.json").exists() and load(attempt / "request.json") == request:
            return load(attempt / "validated.json")
    attempt = root / f"attempt_{len(list(root.glob('attempt_*'))) + 1:03}"
    attempt.mkdir()
    write(attempt / "request.json", request)
    executable, env = cli_executable(), cli_environment()
    login = login_probe(executable, env)
    write(attempt / "login.json", login)
    if not login["chatgpt"]:
        raise RuntimeError("Codex subscription login unavailable")
    output = attempt / "response.json"
    command = [executable, "-a", "never", "exec", "--ignore-user-config", "--ephemeral",
               "--skip-git-repo-check", "-s", "read-only", "--json", "-o", str(output)]
    if reviewer:
        command += ["-m", REVIEWER]
    with (attempt / "events.jsonl").open("wb") as events, (attempt / "stderr.log").open("wb") as errors:
        result = subprocess.run(command + ["-"], env=env, cwd=attempt,
                                input=json.dumps(request, ensure_ascii=False).encode(),
                                stdout=events, stderr=errors, timeout=480)
    if result.returncode:
        raise RuntimeError(f"{label} exited {result.returncode}; see {attempt}")
    calls = [json.loads(line) for line in (attempt / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    thread = next(row["thread_id"] for row in calls if row["type"] == "thread.started")
    usage = next(row.get("usage") for row in reversed(calls) if row["type"] == "turn.completed")
    answer = load(output)
    if reviewer and (not isinstance(answer, dict) or answer.get("decision") not in {"pass", "revise", "stop"}
                     or not str(answer.get("reason", "")).strip()):
        raise ValueError("Independent decision requires decision and reason")
    record = {"answer": answer, "thread_id": thread, "usage": usage,
              "response_sha256": file_hash(output), "model": request["model"]}
    write(attempt / "validated.json", record)
    return record


def resume(work, folder, prior_review):
    manifest = run_mode.verified_run(work)
    if run_mode.writing_policy(manifest)["deliverable"] != "plan":
        raise ValueError("This resume entry produces experimental plans only")
    area = work / "autonomous_writing"
    area.mkdir(exist_ok=True)
    contract = binding(work, folder)
    framework, receipt = (load(folder / name) for name in ("framework.json", "material_receipt.json"))
    current = load(folder / "analysis_matrix.json")
    if (current["framework_sha256"] != receipt["framework_sha256"]
            or current["collection_sha256"] != evidence_digest(receipt)):
        raise ValueError("Starting matrix evidence differs from the verified receipt")
    context = {"question_binding": contract, "framework": framework, "receipt": receipt,
               "freeze": load(work / "s08_topic.json")}
    review = load(prior_review)
    if (review["matrix_sha256"] != file_hash(folder / "analysis_matrix.json")
            or review.get("reviewer") != REVIEWER or not review.get("invocation_id")
            or review.get("decision") not in {"revise", "pass", "stop"}):
        raise ValueError("Prior review does not bind this matrix")
    spent = 0
    while review["decision"] == "revise" and spent < 2:
        updated = dispatch(area, f"matrix_revision_{spent + 1}",
                           "Apply the independent review using ONLY the supplied evidence. JSON array only, no fences. "
                           "Each dimension: dimension_id, evidence [{material_id,relation,reason}], conclusion, "
                           "alternatives, unresolved, boundary, status. All scalar fields are strings; preserve unresolved claims.",
                           {**context, "matrix": current, "review": review, "remaining_revisions": 2 - spent})
        findings = updated["answer"]
        for finding in findings:
            for key in ("conclusion", "boundary", "unresolved", "alternatives"):
                if isinstance(finding.get(key), list) and all(isinstance(x, str) for x in finding[key]):
                    finding[key] = "；".join(finding[key])
        current = analysis_matrix(framework, receipt, findings)
        spent += 1
        write(folder / f"analysis_matrix_autonomous_revision_{spent}.json",
              {**current, "question_binding": contract})
        review = dispatch(area, f"matrix_review_{spent}",
                          "Independently review the revised matrix against the sources, freeze and unresolved findings. "
                          "Return JSON only: decision (pass/revise/stop), reason and concrete changes if needed.",
                          {**context, "matrix": current, "previous_review": review}, reviewer=True)["answer"]
    if review["decision"] != "pass":
        return {"status": "academic_stop", "stage": "matrix", "review": review, "revisions": spent}
    current["question_binding"] = contract
    matrix_path = folder / "analysis_matrix_reviewed.json"
    write(matrix_path, current)
    context.update(matrix=current, literature=load(work / "merged_literature.json"),
                   theories=load(work / "initial/theories.json"))
    packet, review = None, None
    for revision in range(3):
        if revision and spent == 2:
            break
        answer = dispatch(area, f"plan_{revision}",
                          "Create or revise a detailed paragraph-level writing PLAN, not a full paper. Output JSON only. "
                          "Include answer_strategy; sources mapping evidence IDs to kind (theory/literature/empirical), "
                          "label and locator; framework fields prior_explanation,gap,theory_choice,deduction,increment,integration; "
                          "case fields background,selection,materials,method; chapters in order problem,framework,case, "
                          "each framework dimension ID,conclusion. Each chapter has id,task,bridge,sections. Each section has "
                          "title,task,argument,evidence_use,source_ids and paragraphs (nonempty array of distinct paragraph tasks). "
                          "Each analytic chapter uses theory and empirical sources. Preserve uncertain findings and evidence limits.",
                          {**context, "previous_plan": packet, "review": review, "remaining_revisions": 2 - spent})
        packet = answer["answer"]
        packet.update(question_binding=contract, core_question=contract["core_question"],
                      specific_question=contract["specific_question"], method=contract["method"],
                      analysis_matrix=str(matrix_path.relative_to(work)))
        packet["framework"].update(core_concept=framework["core_concept"],
                                   dimensions=[{"id": row["id"], "title": row["name"], "deduction": row["deduction"]}
                                               for row in framework["dimensions"]])
        if any(not section.get("paragraphs") for chapter in packet["chapters"] for section in chapter["sections"]):
            raise ValueError("Every section requires paragraph-level tasks")
        output = area / f"draft_{revision}"
        if (output / "plan_input.json").is_file() and load(output / "plan_input.json") == packet:
            plan = output / "论文写作方案.md"
            request = load(output / "writing_plan_review_request.json")
            if file_hash(plan) != request["plan_sha256"] or request["analysis_matrix_sha256"] != file_hash(matrix_path):
                raise ValueError("Previously rendered plan or matrix changed")
        else:
            plan = produce(work, packet, manifest, output=output)
            write(output / "plan_input.json", packet)
        if revision:
            spent += 1
        record = dispatch(area, f"plan_review_{revision}",
                          "Independently review this paragraph-level plan against the actual design and evidence. "
                          "Check logical progression, source traceability and inference limits. Return JSON only: "
                          "decision (pass/revise/stop), reason and concrete changes if needed.",
                          {**context, "plan": plan.read_text(encoding="utf-8"), "plan_sha256": file_hash(plan)}, reviewer=True)
        review = record["answer"]
        if review["decision"] in {"pass", "stop"}:
            request_path = output / "writing_plan_review_request.json"
            request = load(request_path)
            request.update(review_status=review["decision"], independent_review=record)
            write(request_path, request)
            return {"status": "reviewed_plan" if review["decision"] == "pass" else "academic_stop",
                    "plan": str(plan.relative_to(work)), "plan_sha256": file_hash(plan),
                    "review": record, "revisions": spent}
    return {"status": "academic_stop", "stage": "plan", "review": review, "revisions": spent}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--attempt", default="attempt_001")
    args = parser.parse_args()
    work = (run_mode.RUNS / args.run_id).resolve()
    run_mode.verified_run(work)
    with job_lock(work):
        status = work / "autonomous_writing_status.json"
        try:
            result = resume(work, work / "qualitative_framework" / args.attempt,
                            work / "matrix_independent_review.json")
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as error:
            write(status, {"status": "technical_block", "reason": str(error)})
            raise
        write(status, result)
        print(result["status"])


if __name__ == "__main__":
    main()
