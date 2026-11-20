"""Stage 06: metadata-first prepare, frozen-protocol analysis, review, local handoff."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

from common06 import (CONTROL, MODULE, ROOT, canonical, clean, csv_write, environment,
                      file_lock, indexed, inside, integrity, load, now, present,
                      project_output, require_fields, review_ok, run_directory,
                      sha, valid_date, value_hash, verify_locks, write)
from data_adapters import LocalDatasetAdapter, normalized_labels
from engines import StatsmodelsEngine
from methods06 import build_library, catalog, coverage_ok, load_library
from pipeline06 import compare, estimate, used_columns
from method_application import application_errors, registered_snapshot

VERSION = 3
PHASES = ("prepare", "analyze", "approve")


def resolve_protocol(raw, base):
    protocol = json.loads(json.dumps(raw))
    for dataset in protocol.get("datasets", []):
        for field in ("path", "metadata_sidecar"):
            if dataset.get(field):
                dataset[field] = str((Path(base) / dataset[field]).resolve())
        proof = dataset.get("identity_evidence", {})
        if proof.get("path"):
            proof["path"] = str((Path(base) / proof["path"]).resolve())
    if protocol.get("method_library"):
        protocol["method_library"] = str((Path(base) / protocol["method_library"]).resolve())
    return protocol


def plan(inputs, config=None):
    from runtime import make_plan
    phase = inputs.get("phase", "prepare")
    if phase not in PHASES:
        raise ValueError("未知phase")
    base = Path(inputs.get("base_dir", ROOT)).resolve()
    result = make_plan("06", inputs, config)
    normalized, locks = result["inputs"], result["input_files"]
    normalized["phase"] = phase
    for path in sorted(MODULE.rglob("*")):
        if path.is_file() and path.suffix in (".py", ".json", ".csv", ".md") and not any(x in path.parts for x in ("outputs", "__pycache__", "tests")):
            locks.append(file_lock(path))
    for key in ("protocol", "protocol_review", "preflight", "source", "quality_review"):
        if inputs.get(key):
            normalized[key] = str((base / inputs[key]).resolve())
            locks.append(file_lock(normalized[key]))
    if inputs.get("protocol"):
        protocol = resolve_protocol(load(normalized["protocol"]), Path(normalized["protocol"]).parent)
        result["protocol_sha256"] = value_hash(protocol)
        for dataset in protocol.get("datasets", []):
            for path in (dataset.get("path"), dataset.get("metadata_sidecar"), dataset.get("identity_evidence", {}).get("path")):
                if path:
                    locks.append(file_lock(path))
        if protocol.get("method_library"):
            locks.extend(file_lock(p) for p in sorted(Path(protocol["method_library"]).rglob("*")) if p.is_file())
    for key in ("upstream", "preflight", "source"):
        if normalized.get(key):
            locks.extend(file_lock(p) for p in sorted(Path(normalized[key]).parent.rglob("*")) if p.is_file())
    for raw_path in (config or {}).get("provider_files", []):
        locks.append(file_lock((base / raw_path).resolve()))
    if phase == "analyze" and not all(inputs.get(k) for k in ("preflight", "protocol", "upstream")):
        raise ValueError("analyze须绑定协议、当前05冻结manifest和06 preflight manifest")
    if phase == "approve" and not all(inputs.get(k) for k in ("source", "quality_review")):
        raise ValueError("approve须绑定实际分析manifest及其内容复核文件")
    result.update(input_files=list({p["path"]: p for p in locks}.values()), environment=environment(),
                  operations=["metadata_first", "frozen_protocol_check", "fit_all_models", "diagnostics", "reload_refit", "review", "local_export"])
    return result


@contextmanager
def new_attempt(planned):
    if verify_locks(planned["input_files"]) or environment() != planned["environment"]:
        raise ValueError("输入、代码或环境已变化，须重新plan")
    run = run_directory(planned["run_id"])
    run.mkdir(parents=True, exist_ok=True)
    lock = run / ".research.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, canonical({"pid": os.getpid(), "created_at": now()}))
    os.close(fd)
    work, mf = None, None
    try:
        stage = run / "stage_06"
        stage.mkdir(exist_ok=True)
        nums = [int(p.name[8:]) for p in stage.glob("attempt_*") if re.fullmatch(r"attempt_\d+", p.name)]
        number = max(nums, default=0) + 1
        work = stage / f"attempt_{number:03d}"
        work.mkdir()
        write(work / "plan.json", planned)
        mf = {"record_type": "stage_manifest", "schema_version": 1, "stage_id": "06", "module_version": VERSION,
              "run_id": planned["run_id"], "attempt": number, "phase": planned["inputs"]["phase"], "status": "running",
              "input_files": planned["input_files"], "upstream_manifests": [], "output_files": [],
              "config_sha256": value_hash(planned["config"]), "root_requirements_sha256": sha(ROOT / "基础要求.md"),
              "environment": planned["environment"], "seed": planned["seed"], "model": None,
              "gate_report": "gate_report.json", "started_at": now(), "deviations": [], "share_scope": "local_only"}
        write(work / "stage_manifest.json", mf)
        yield work, mf
        changed = verify_locks(planned["input_files"])
        if changed:
            mf["status"] = "stale"
            mf["deviations"].append({"input_changed_during_execution": changed})
    except Exception as exc:
        if mf is not None:
            mf["status"] = "failed"
            mf["deviations"].append({"type": type(exc).__name__, "message": str(exc)})
            write(work / "failure.json", {"at": now(), "error_type": type(exc).__name__, "error": str(exc),
                  "recovery": "修正后新建attempt，不覆盖失败记录"})
        raise
    finally:
        try:
            if mf is not None:
                mf["finished_at"] = now()
                mf["output_files"] = [{"path": str(p.relative_to(work)).replace("\\", "/"), "sha256": sha(p)}
                                      for p in sorted(work.rglob("*")) if p.is_file() and p.name != "stage_manifest.json"]
                write(work / "stage_manifest.json", mf)
                update_ledger(run, work, mf)
        finally:
            lock.unlink(missing_ok=True)


def update_ledger(run, work, mf):
    path = run / "run_manifest.json"
    data = load(path) if path.exists() else {"schema_version": 2, "run_id": mf["run_id"], "stages": []}
    rows = data.setdefault("stages", [])
    row = next((r for r in rows if r["stage_id"] == "06"), None)
    if row is None:
        row = {"stage_id": "06"}
        rows.append(row)
    row.update(status=mf["status"], attempt=mf["attempt"], manifest_path=str(work / "stage_manifest.json"),
               manifest_sha256=sha(work / "stage_manifest.json"), gate_report=str(work / "gate_report.json"))
    for downstream in rows:
        if downstream["stage_id"] in ("07", "08", "09") and downstream.get("status") not in ("planned", "skipped", "stale"):
            downstream.update(status="stale", stale_reason="stage_06 attempt changed")
    data["implemented_stage_executors"] = sorted(set(data.get("implemented_stage_executors", [])) | {"04", "05", "06"})
    data["updated_at"] = now()
    write(path, data)
    with (run / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": now(), "stage": "06", "attempt": mf["attempt"], "phase": mf["phase"], "status": mf["status"]}, ensure_ascii=False) + "\n")


def upstream_checks(path, run_id):
    from runtime import load_stage
    if not path:
        return ["缺少同一run的第五步冻结设计"], {}, {}
    path = Path(path)
    mf = load(path)
    if path.name != "stage_manifest.json" or mf.get("stage_id") != "05" or mf.get("run_id") != run_id:
        return ["上游必须为同一run的05 stage_manifest.json"], {}, {}
    errors = integrity(path.parent)
    ledger = load(path.parent.parents[1] / "run_manifest.json")
    row = next((r for r in ledger["stages"] if r["stage_id"] == "05"), {})
    if mf.get("status") != "passed" or row.get("status") != "passed" or row.get("attempt") != mf["attempt"]:
        errors.append("G5未通过或不是当前版本")
    if not errors:
        up_plan = load(path.parent / "plan.json")
        review_file = up_plan["inputs"].get("quality_review")
        report = load_stage("05").validate(path.parent, {"quality_review": load(review_file) if review_file else None})
        errors.extend("G5复核: " + e for e in report["errors"])
    design, bundle = load(path.parent / "analysis_design.json"), load(path.parent / "bundle.json")
    if design.get("frozen") is not True or design.get("pre_analysis") is not True or not valid_date(design.get("frozen_at")):
        errors.append("第五步设计未事前冻结")
    if value_hash(bundle.get("analysis_design", {})) != design.get("design_sha256"):
        errors.append("冻结设计与第五步内容不一致")
    return errors, design, bundle


def check_protocol(protocol, upstream_bundle, design, adapter, engine, library_binding=None):
    errors, metadata = [], {}
    require_fields(protocol, ("datasets", "primary_dataset", "variables", "models", "method_library", "survey_design",
                              "missing_policy", "diagnostics_plan", "robustness_plan", "multiple_testing_policy", "precision_plan"), "执行协议", errors)
    if type(protocol.get("seed")) is not int or type(protocol.get("common_sample")) is not bool:
        errors.append("须显式冻结随机种子和common_sample")
    if protocol.get("missing_policy") != "complete_case":
        errors.append("内置缺失处理仅支持complete_case；插补须提供专用执行器与诊断")
    if protocol.get("template") is True:
        errors.append("模板不能作为已完成分析协议")
    mode = protocol.get("analysis_mode", "confirmatory")
    if mode not in ("confirmatory", "exploratory"):
        errors.append("analysis_mode须confirmatory或exploratory")
    for key in ("weights", "strata", "psu"):
        item = protocol.get("survey_design", {}).get(key, {})
        if item.get("status") not in ("specified", "not_applicable") or not present(item.get("rationale")):
            errors.append("抽样设计未落实: " + key)
    if protocol.get("engine", "statsmodels") != engine.engine_id:
        errors.append("协议与实际引擎不一致")
    if design.get("execution06_sha256") != value_hash(protocol):
        errors.append("第五步未事前冻结本执行协议哈希；须在主分析前补充设计并重新冻结05")
    if protocol.get("seed") != design.get("seed"):
        errors.append("06随机种子与05不同")
    if protocol.get("survey_design") != design.get("survey_design"):
        errors.append("06抽样设计与05不同")
    if any(protocol.get("survey_design", {}).get(k, {}).get("status") == "specified" for k in ("weights", "strata", "psu")) and not engine.capabilities().get("complex_survey"):
        errors.append("引擎未实现所需复杂抽样设计")
    datasets = indexed(protocol.get("datasets", []), "dataset_id", errors)
    variables = indexed(protocol.get("variables", []), "variable_id", errors)
    models = indexed(protocol.get("models", []), "model_id", errors)
    measurements = {v["variable_id"]: v for v in upstream_bundle.get("measurements", [])}
    hypotheses = {h["hypothesis_id"]: h for h in upstream_bundle.get("hypotheses", []) if h.get("review_status") == "accepted"}
    if protocol.get("primary_dataset") not in datasets:
        errors.append("主数据集ID不存在")
    for did, dataset in datasets.items():
        require_fields(dataset, ("name", "wave", "path", "sha256", "access_basis", "identity_basis", "verified_at"), did, errors)
        if dataset.get("identity_status") != "raw_original_verified" or dataset.get("review_status") != "verified":
            errors.append(did + ": 原始身份未核验；不得使用历史衍生/回归输出")
        if not valid_date(dataset.get("verified_at")):
            errors.append(did + ": 身份核验时间无效")
        try:
            path = Path(dataset.get("path", "MISSING"))
            if sha(path) != dataset.get("sha256"):
                errors.append(did + ": 原始数据哈希不符")
            proof = dataset.get("identity_evidence", {})
            if sha(proof.get("path", "MISSING")) != proof.get("sha256") or not proof.get("locator") or not proof.get("short_excerpt"):
                raise ValueError("缺少官方发布/版本证据哈希与定位")
            from providers import PdfReader
            proof_path = Path(proof["path"])
            if proof_path.suffix.lower() == ".pdf":
                pages = PdfReader().inspect(proof_path)
                page = proof.get("pdf_page")
                if type(page) is not int or not 1 <= page <= len(pages):
                    raise ValueError("身份文档页码无效")
                text = pages[page - 1]
            else:
                text = proof_path.read_text(encoding="utf-8-sig")
            if "".join(proof["short_excerpt"].split()) not in "".join(text.split()):
                raise ValueError("身份证据短摘无法定位")
            meta = adapter.read_metadata(path)
            if dataset.get("metadata_sidecar"):
                sidecar = load(dataset["metadata_sidecar"])
                if sidecar.get("data_sha256") != dataset["sha256"]:
                    raise ValueError("代码本sidecar未绑定数据哈希")
                if meta["format"] == "csv":
                    for col, content in sidecar["columns"].items():
                        if col in meta["columns"]:
                            meta["columns"][col] = content
            metadata[did] = meta
            for column in used_columns(protocol, did):
                if column not in meta["columns"]:
                    errors.append(did + ": 数据中无实际列 " + column)
        except (OSError, ValueError, ImportError) as exc:
            errors.append(did + ": " + str(exc))
    for vid, variable in variables.items():
        measurement = measurements.get(vid, {})
        did, original = variable.get("dataset_id"), variable.get("source_variable")
        if not measurement or original != measurement.get("source_variable"):
            errors.append(vid + ": 未匹配05已核验测量")
        if did not in datasets or datasets.get(did, {}).get("name") != measurement.get("dataset") or str(datasets.get(did, {}).get("wave")) != str(measurement.get("wave")):
            errors.append(vid + ": 数据库/波次与05不一致")
        if variable.get("special_missing") != measurement.get("special_missing") or not isinstance(variable.get("special_missing"), dict):
            errors.append(vid + ": 特殊缺失与05不同/未核对")
        actual = metadata.get(did, {}).get("columns", {}).get(original, {})
        if actual.get("label") != variable.get("expected_label"):
            errors.append(vid + ": 变量标签与预定映射不符")
        if normalized_labels(actual.get("value_labels", {})) != normalized_labels(measurement.get("value_labels", {})):
            errors.append(vid + ": 实际取值标签与问卷/05字典不同")
        if variable.get("transform", {"op": "identity"}).get("op") not in ("identity", "recode", "log", "log1p", "square"):
            errors.append(vid + ": 未实现构造，须新增可信提供方")
    for dataset in datasets.values():
        if set(dataset.get("keys", {})) & set(variables):
            errors.append("合并键别名不能覆盖研究变量ID")
    if set(measurements) - set(variables):
        errors.append("06未覆盖05冻结测量集合")
    if len({d.get("name") for d in datasets.values()}) > 1:
        errors.append("不同独立调查不能直接拼接为同一分析样本；须拆为独立研究/复现")
    if len({str(d.get("wave")) for d in datasets.values()}) > 1 and design.get("harmonization", {}).get("review_status") != "verified":
        errors.append("跨波次合并未核验题义、编码、样本与权重")
    allowed, catalog_ids, used = set(engine.capabilities().get("methods", [])), {r["method_id"] for r in catalog()}, set()
    for mid, model in models.items():
        require_fields(model, ("method_id", "outcome", "predictors", "hypothesis_id", "diagnostics_required"), mid, errors)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", str(mid)):
            errors.append("model_id须为安全英文数字ID")
        if model.get("method_id") not in allowed:
            errors.append(mid + ": 引擎未实现该方法")
        if model.get("analysis_role") not in ("primary", "robustness", "exploratory"):
            errors.append(mid + ": 未标记主分析/稳健性/探索")
        if mode == "exploratory" and model.get("analysis_role") != "exploratory":
            errors.append(mid + ": 探索性协议中全部模型须标记exploratory")
        if model.get("outcome") not in variables or any(p not in variables for p in model.get("predictors", [])):
            errors.append(mid + ": 模型变量悬空")
        if model.get("outcome") in model.get("predictors", []):
            errors.append(mid + ": 结局不能同时作为同一模型的自变量")
        if model.get("hypothesis_id") not in hypotheses:
            errors.append(mid + ": 未对应已接受假设/RQ")
        controls = {v["variable_id"] for v in measurements.values() if v.get("role") == "control"}
        if model.get("analysis_role") == "primary" and not controls.issubset(set(model.get("predictors", []))):
            errors.append(mid + ": 主模型遗漏05预定控制量；不能按结果删控制变量")
        for name in model.get("method_tags", []) + [model.get("method_id")]:
            if name not in catalog_ids:
                errors.append(mid + ": 未知方法标签")
            else:
                used.add(name)
        if model.get("interactions") and "MODERATION" not in model.get("method_tags", []):
            errors.append(mid + ": 交互须登记MODERATION并配套范例")
        if not 0 < model.get("ci_level", 0.95) < 1:
            errors.append(mid + ": 区间置信水平无效")
        for field in ("cluster", "exposure"):
            if model.get(field) and model[field] not in variables:
                errors.append(mid + ": " + field + "变量未登记")
    primary = [m for m in models.values() if m.get("analysis_role") == "primary"]
    if mode == "confirmatory" and (not primary or {m.get("outcome") for m in primary} != set(design.get("primary_outcomes", []))):
        errors.append("主模型结局集合与05不同")
    if mode == "confirmatory" and set(hypotheses) - {m.get("hypothesis_id") for m in primary}:
        errors.append("存在未执行主假设/RQ")
    if not models:
        errors.append("没有可执行模型")
    references = []
    if protocol.get("method_library"):
        try:
            registered_snapshot(protocol["method_library"], library_binding)
            references, problems = load_library(protocol["method_library"], used)
            errors.extend(problems)
            errors.extend(application_errors(models.values(), references))
        except (OSError, ValueError, KeyError) as exc:
            errors.append("方法库: " + str(exc))
    else:
        errors.append("缺少长期方法库")
    return errors, metadata, references


def check_source(path, run_id, phase):
    work, mf = Path(path).parent, load(path)
    errors = integrity(work)
    if Path(path).name != "stage_manifest.json" or mf.get("run_id") != run_id or mf.get("stage_id") != "06" or mf.get("phase") != phase:
        errors.append("06来源run/阶段/phase不一致")
    if mf.get("module_version") != VERSION:
        errors.append("06来源没有使用当前方法库执行版本")
    ledger = load(work.parents[1] / "run_manifest.json")
    row = next((r for r in ledger["stages"] if r["stage_id"] == "06"), {})
    retry_review = False
    if phase == "analyze" and row.get("status") in ("needs_review", "failed") and row.get("manifest_path"):
        current_work = Path(row["manifest_path"]).parent
        current_mf = load(row["manifest_path"])
        if current_mf.get("phase") == "approve":
            current_plan = load(current_work / "plan.json")
            prior_source = current_plan["inputs"].get("source")
            retry_review = prior_source and Path(prior_source).resolve() == Path(path).resolve()
    if (row.get("attempt") != mf.get("attempt") and not retry_review) or (row.get("status") in ("stale", "failed") and not retry_review):
        errors.append("06来源不是当前有效attempt")
    return work, mf, errors


def execute(planned, context=None):
    context = context or {}
    if planned.get("stage_id") != "06":
        raise ValueError("不是06计划")
    inputs, adapter, engine = planned["inputs"], context.get("dataset_adapter") or LocalDatasetAdapter(), context.get("engine") or StatsmodelsEngine()
    import inspect
    for provider, default in ((adapter, LocalDatasetAdapter), (engine, StatsmodelsEngine)):
        if type(provider) is not default:
            code = Path(inspect.getfile(type(provider))).resolve()
            if not any(p["path"] == str(code) and p["sha256"] == sha(code) for p in planned["input_files"]):
                raise ValueError("自定义提供方代码未锁定：加入config.provider_files后重新plan")
    phase, source = inputs["phase"], None
    if phase in ("analyze", "approve"):
        key, expected = ("preflight", "prepare") if phase == "analyze" else ("source", "analyze")
        source, source_mf, problems = check_source(inputs[key], planned["run_id"], expected)
        if problems:
            raise ValueError("; ".join(problems))
    with new_attempt(planned) as (work, mf):
        if source is not None:
            problems = check_source(inputs[key], planned["run_id"], expected)[2]
            if problems:
                raise ValueError("; ".join(problems))
        if phase == "approve":
            bundle = load(source / "bundle.json")
            mf["seed"] = bundle["protocol"]["seed"]
            for path in source.iterdir():
                if path.is_file() and path.name not in ("stage_manifest.json", "plan.json", "gate_report.json", "quality_review_request.json", "阅读入口.md", "knowledge.sqlite"):
                    shutil.copyfile(path, work / path.name)
            mf["upstream_manifests"] = [file_lock(source / "stage_manifest.json")]
            review = load(inputs["quality_review"])
            errors = analysis_errors(bundle)
            if not review_ok(review, value_hash(bundle)):
                errors.append("实质复核须绑定实际结果内容哈希、审查人、时间和依据")
            write(work / "quality_review.json", review)
            status = "needs_review" if errors else "passed"
        else:
            protocol = resolve_protocol(load(inputs["protocol"]), Path(inputs["protocol"]).parent) if inputs.get("protocol") else {}
            errors, design, up_bundle = upstream_checks(inputs.get("upstream"), planned["run_id"])
            run_path = run_directory(planned["run_id"]) / "run_manifest.json"
            run_config = load(run_path).get("config_snapshot", {}) if run_path.is_file() else {}
            library_binding = run_config.get("analysis", {}).get("method_library_resource")
            problems, metadata, references = check_protocol(protocol, up_bundle, design, adapter, engine, library_binding)
            errors.extend(problems)
            history = run_directory(planned["run_id"]) / "analysis_history.jsonl"
            prior = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()] if history.exists() else []
            if protocol.get("analysis_mode", "confirmatory") == "confirmatory" and any(
                    event["protocol_sha256"] != value_hash(protocol) or event["design_sha256"] != design.get("design_sha256")
                    for event in prior):
                errors.append("本run主分析已开始；变更设计/假设/样本协议须明确改为探索性，不能倒填事前分析")
            if not review_ok(load(inputs["protocol_review"]) if inputs.get("protocol_review") else None, value_hash(protocol)):
                errors.append("分析前须有绑定协议哈希的研究复核")
            if inputs.get("upstream"):
                mf["upstream_manifests"] = [file_lock(inputs["upstream"])]
            mf["seed"] = protocol.get("seed", planned["seed"])
            bundle = {"schema_version": 2, "run_id": planned["run_id"], "protocol": protocol,
                      "protocol_sha256": value_hash(protocol), "metadata": metadata, "method_references": references,
                      "method_library_binding": library_binding if references else None,
                      "measurements": up_bundle.get("measurements", []), "results": [], "models": [], "failures": [],
                      "sample_flow": [], "missing": [], "merges": [], "descriptive": [], "reproduction": None,
                      "upstream": {"path": inputs.get("upstream"), "design_sha256": design.get("design_sha256")},
                      "environment": environment(), "actual_run_at": None, "preflight_errors": errors}
            if phase == "analyze":
                frozen = load(source / "analysis_plan.json")
                if frozen.get("frozen") is not True or frozen.get("protocol_sha256") != value_hash(protocol):
                    errors.append("preflight未冻结或协议改变")
                if errors:
                    raise ValueError("主分析未启动: " + "; ".join(errors))
                event = {"at": now(), "attempt": mf["attempt"], "protocol_sha256": value_hash(protocol),
                         "design_sha256": design.get("design_sha256"), "analysis_mode": protocol.get("analysis_mode", "confirmatory")}
                with history.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                write(work / "analysis_started.json", event)
                first = estimate(protocol, adapter, engine, planned["run_id"])
                second = estimate(protocol, adapter, engine, planned["run_id"])
                bundle.update(first, reproduction=compare(first, second), actual_run_at=now())
                bundle["preflight_errors"] = []
                for row in bundle["results"]:
                    row.update(actual_run_at=bundle["actual_run_at"], code_sha256=sha(MODULE / "tools/engines.py"),
                               output_path="model_outputs.json", weight_spec=protocol.get("survey_design"),
                               engine_version=bundle["environment"].get("statsmodels"))
                errors = analysis_errors(bundle) + ["实际分析已运行，须审查诊断与结论边界后approve"]
                status = "needs_review"
                shutil.copyfile(source / "analysis_plan.json", work / "analysis_plan.json")
            else:
                status = "needs_review" if errors else "ready"
                write(work / "analysis_plan.json", {"schema_version": 2, "run_id": planned["run_id"],
                      "protocol": protocol, "protocol_sha256": value_hash(protocol), "frozen": not errors,
                      "frozen_at": now() if not errors else None, "source_stage05": inputs.get("upstream"),
                      "notice": "ready仅表示分析前检查通过；G6须实际估计、诊断、复现与研究复核"})
            write(work / "metadata.json", metadata)
        report = {"gate": "G6", "phase": phase, "status": status, "errors": errors,
                  "content_sha256": value_hash(bundle), "counts": {"models": len(bundle["models"]), "results": len(bundle["results"])},
                  "business_quality_automatic": False}
        for name, data in (("bundle.json", bundle), ("gate_report.json", report), ("model_outputs.json", bundle["models"]),
                           ("diagnostics.json", [{"model_id": m["model_id"], **m["diagnostics"]} for m in bundle["models"]]),
                           ("reproduction.json", bundle["reproduction"]),
                           ("cleaning_log.json", {k: bundle[k] for k in ("sample_flow", "missing", "merges", "failures")})):
            write(work / name, data)
        write(work / "quality_review_request.json", {"content_sha256": value_hash(bundle), "decision": "pending",
              "reviewer": None, "reviewed_at": None, "assessment": None,
              "notice": "复核主模型、稳健性、不显著结果、诊断和因果边界；另存后approve"})
        output_tables(work, bundle)
        from knowledge06 import build
        build(work, bundle, status)
        (work / "阅读入口.md").write_text("# 第六步\n\n状态：" + status + "；phase=" + phase + "。\n\n" + "\n".join("- " + e for e in errors)
                                           + "\n\n查看analysis_plan.json、results.csv、diagnostics.json和reproduction.json。无个案数据输出。\n", encoding="utf-8")
        mf["status"] = status
        result = {"attempt_path": str(work), "stage_id": "06", "phase": phase, "status": status}
    result["status"] = load(work / "stage_manifest.json")["status"]
    return result


def analysis_errors(bundle):
    errors = list(bundle.get("preflight_errors", []))
    if not bundle.get("actual_run_at") or not bundle.get("results"):
        errors.append("尚无实际运行结果")
    errors.extend("模型失败: " + f["model_id"] + ": " + f["error"] for f in bundle.get("failures", []))
    if not (bundle.get("reproduction") or {}).get("passed"):
        errors.append("独立重读重估复现未通过")
    expected = {m["model_id"]: m for m in bundle["protocol"].get("models", [])}
    actual = {m["model_id"]: m for m in bundle.get("models", [])}
    if set(expected) != set(actual):
        errors.append("未完整保留全部预定模型")
    for mid, output in actual.items():
        diag = output.get("diagnostics", {})
        errors.extend(mid + ": " + e for e in diag.get("errors", []))
        if not diag.get("converged"):
            errors.append(mid + ": 未收敛")
        for check in expected.get(mid, {}).get("diagnostics_required", []):
            if check not in diag or diag[check] is None:
                errors.append(mid + ": 缺少预定诊断 " + check)
    ids = set()
    for row in bundle.get("results", []):
        if row["result_id"] in ids:
            errors.append("result_id重复")
        ids.add(row["result_id"])
        for name in ("estimate", "std_error", "ci_low", "ci_high", "p_value"):
            val = row.get(name)
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                errors.append("结果含非有限/缺失推断值")
        if row.get("std_error") is not None and row["std_error"] < 0:
            errors.append("标准误负值")
        if row.get("p_value") is not None and not 0 <= row["p_value"] <= 1:
            errors.append("p值超范围")
        if row.get("ci_low") is not None and row.get("ci_high") is not None and row["ci_low"] > row["ci_high"]:
            errors.append("区间上下界颠倒")
        if not 0 < row.get("ci_level", 0) < 1 or row.get("n_obs", 0) <= 0:
            errors.append("置信水平/样本数无效")
    return errors


def output_tables(work, bundle):
    import csv
    tables = {"results.csv": bundle["results"], "sample_flow.csv": bundle["sample_flow"],
              "descriptive.csv": bundle["descriptive"], "method_references.csv": bundle["method_references"]}
    variables = []
    for variable in bundle["protocol"].get("variables", []):
        measurement = next((v for v in bundle["measurements"] if v["variable_id"] == variable["variable_id"]), {})
        dataset = next((d for d in bundle["protocol"].get("datasets", []) if d["dataset_id"] == variable.get("dataset_id")), {})
        variables.append(dict(measurement, run_id=bundle["run_id"], file_path=dataset.get("path"), file_sha256=dataset.get("sha256"),
                              variable_label=variable.get("expected_label"), construction_formula=variable.get("transform", {"op": "identity"})))
    tables["variable_dictionary.csv"] = variables
    for filename, rows in tables.items():
        with (MODULE / "templates" / filename).open(encoding="utf-8-sig", newline="") as stream:
            headers = next(csv.reader(stream))
        csv_write(work / filename, rows, headers)
    methods = []
    for row in catalog():
        matches = [r for r in bundle["method_references"] if r["method_id"] == row["method_id"]]
        methods.append(dict(row, reference_1_paper_id=matches[0]["paper_id"] if matches else "",
                            reference_2_paper_id=matches[1]["paper_id"] if len(matches) > 1 else "",
                            reference_status="verified_coverage" if coverage_ok(matches) else "pending"))
    csv_write(work / "method_catalog.csv", methods, list(methods[0]))
    lines = ["# 实际模型结果", "", "仅从实际引擎输出生成；无星号筛选，完整报告预定模型。", ""]
    if not bundle["results"]:
        lines += ["尚未运行，以下无实证结果。", ""]
    def cell(value):
        return str(value).replace("|", r"\|").replace("\n", " ")
    for model in bundle["protocol"].get("models", []):
        mid = model["model_id"]
        lines += ["## " + mid, "", f"方法：{model['method_id']}；分析角色：{model.get('analysis_role')}。", "",
                  "| result_id | term | scale | estimate | SE | CI low | CI high | p | N |",
                  "|---|---|---|---:|---:|---:|---:|---:|---:|"]
        for row in (r for r in bundle["results"] if r["model_id"] == mid):
            values = [row.get(k) for k in ("result_id", "term", "scale", "estimate", "std_error", "ci_low", "ci_high", "p_value", "n_obs")]
            lines.append("| " + " | ".join(cell(f"{v:.8g}" if isinstance(v, float) else v) for v in values) + " |")
        lines += ["", "误差方案：" + cell(model.get("covariance", "HC1")) + "；置信水平：" + str(model.get("ci_level", .95)) + "。", ""]
        for failure in bundle["failures"]:
            if failure["model_id"] == mid:
                lines += ["模型失败：" + failure["error"], ""]
    (work / "tables.md").write_text("\n".join(lines), encoding="utf-8")


def validate(artifacts, evidence=None):
    work = Path(artifacts).resolve()
    mf, bundle = load(work / "stage_manifest.json"), load(work / "bundle.json")
    changed, errors = integrity(work), analysis_errors(bundle)
    if mf.get("phase") != "approve" or not review_ok(load(work / "quality_review.json") if (work / "quality_review.json").exists() else None, value_hash(bundle)):
        errors.append("尚未完成实际结果复核approve")
    path = bundle.get("upstream", {}).get("path")
    if path:
        errors.extend(upstream_checks(path, mf["run_id"])[0])
    else:
        errors.append("无冻结上游")
    current = next((r for r in load(work.parents[1] / "run_manifest.json")["stages"] if r["stage_id"] == "06"), {})
    if current.get("attempt") != mf["attempt"] or current.get("status") == "stale":
        changed.append("不是当前有效06 attempt")
    return {"gate": "G6", "status": "stale" if changed else "needs_review" if errors else "passed",
            "errors": errors, "integrity_errors": changed, "read_only": True, "business_quality_automatic": False}


def export(artifacts, target_profile=None):
    work = Path(artifacts).resolve()
    report, mf = validate(work), load(work / "stage_manifest.json")
    if report["status"] != "passed" or mf["status"] != "passed":
        raise ValueError("G6未通过，禁止交付07: " + "; ".join(report["errors"] + report["integrity_errors"]))
    target = work.parents[1] / "exports" / f"stage_06_attempt_{mf['attempt']:03d}"
    target.mkdir(parents=True, exist_ok=False)
    names = ("results.csv", "variable_dictionary.csv", "sample_flow.csv", "descriptive.csv", "diagnostics.json",
             "reproduction.json", "model_outputs.json", "cleaning_log.json", "analysis_plan.json", "tables.md")
    for name in names:
        shutil.copyfile(work / name, target / name)
    write(target / "handoff.json", {"schema_version": 2, "run_id": mf["run_id"], "stage_id": "06",
          "manifest_path": str(work / "stage_manifest.json"), "manifest_sha256": sha(work / "stage_manifest.json"),
          "profile": target_profile or "stage07_empirical_results", "share_scope": "local_only",
          "files": [{"path": name, "sha256": sha(target / name)} for name in names],
          "code_files": [file_lock(p) for p in sorted((MODULE / "tools").glob("*.py"))],
          "notice": "无个案数据、受限全文和账号；按原协议本地复现"})
    return {"status": "passed", "path": str(target / "handoff.json")}


def main(argv=None):
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--input", required=True)
        p.add_argument("--run-id", required=True)
        if name == "plan":
            p.add_argument("--output", required=True)
    p = sub.add_parser("execute")
    p.add_argument("--plan", required=True)
    for name in ("validate", "export"):
        p = sub.add_parser(name)
        p.add_argument("--attempt", required=True)
    p = sub.add_parser("discover")
    p.add_argument("--root", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("metadata")
    p.add_argument("--data", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("protocol-hash")
    p.add_argument("--protocol", required=True)
    p = sub.add_parser("library-build")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--review")
    p = sub.add_parser("status")
    p.add_argument("--run-id", required=True)
    sub.add_parser("capabilities")
    args = parser.parse_args(argv)
    try:
        if args.command in ("plan", "run"):
            file = Path(args.input).resolve()
            raw = load(file)
            planned = plan(dict(raw.get("06", raw), run_id=args.run_id, base_dir=str(file.parent)), raw.get("config", {}))
            if args.command == "plan":
                target = project_output(args.output)
                write(target, planned)
                result = {"path": str(target), "status": "planned"}
            else:
                result = execute(planned)
        elif args.command == "execute":
            result = execute(load(args.plan))
        elif args.command in ("validate", "export"):
            result = validate(args.attempt) if args.command == "validate" else export(args.attempt)
        elif args.command in ("discover", "metadata"):
            target = project_output(args.output)
            if args.command == "discover":
                data = LocalDatasetAdapter().discover(args.root)
                result = {"path": str(target), "count": len(data["files"]), "status": "identity_unverified"}
            else:
                data = LocalDatasetAdapter().read_metadata(args.data)
                data.update(data_path=str(Path(args.data).resolve()), data_sha256=sha(args.data), read_at=now())
                result = {"path": str(target), "columns": len(data["columns"]), "case_values_returned": False}
            write(target, data)
        elif args.command == "protocol-hash":
            file = Path(args.protocol).resolve()
            result = {"execution06_sha256": value_hash(resolve_protocol(load(file), file.parent)),
                      "notice": "写入05 analysis_design.execution06_sha256，在主分析前重新复核冻结"}
        elif args.command == "library-build":
            result = build_library(args.input, args.output, args.review)
        elif args.command == "capabilities":
            result = StatsmodelsEngine().capabilities()
        else:
            result = {"run_id": args.run_id, "stages": []}
            for row in load(run_directory(args.run_id) / "run_manifest.json")["stages"]:
                item = dict(row)
                if item.get("manifest_path") and integrity(Path(item["manifest_path"]).parent):
                    item["status"] = "stale"
                result["stages"].append(item)
        print(json.dumps(clean(result), ensure_ascii=False, indent=2))
        return 3 if result.get("status") in ("needs_review", "failed", "stale") else 0
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
