"""Deterministic transformations, sample accounting, fitting, and replay comparison."""
from __future__ import annotations

from common06 import clean, value_hash
from data_adapters import merge_frames


def used_columns(protocol, dataset_id):
    dataset = next(d for d in protocol["datasets"] if d["dataset_id"] == dataset_id)
    return sorted(set(dataset.get("keys", {}).values()) |
                  {v["source_variable"] for v in protocol["variables"] if v["dataset_id"] == dataset_id})


def prepare_frame(protocol, adapter):
    import numpy as np
    import pandas as pd
    frames, flow, merges, missing = {}, [], [], []
    for dataset in protocol["datasets"]:
        did = dataset["dataset_id"]
        raw = adapter.read_subset(dataset["path"], used_columns(protocol, did))
        frame = pd.DataFrame(index=raw.index)
        for alias, original in dataset.get("keys", {}).items():
            frame[alias] = raw[original]
        for variable in [v for v in protocol["variables"] if v["dataset_id"] == did]:
            name = variable["variable_id"]
            x = raw[variable["source_variable"]].copy()
            codes = [float(k) if str(k).replace("-", "", 1).replace(".", "", 1).isdigit() else k
                     for k in variable["special_missing"]]
            x = x.mask(x.isin(codes))
            missing.append({"variable_id": name, "n_source": len(x), "n_missing": int(x.isna().sum()),
                            "special_missing_codes": codes})
            operation = variable.get("transform", {"op": "identity"})
            op = operation["op"]
            if op == "recode":
                mapping = {str(k): v for k, v in operation["mapping"].items()}
                # JSON keys are strings; numeric 1 and 1.0 share an explicit map.
                def key(value):
                    if isinstance(value, (int, float)) and float(value).is_integer():
                        return str(int(value))
                    return str(value)
                known = x.dropna().map(key).isin(mapping).all()
                if not known:
                    raise ValueError(f"{name}: 再编码未覆盖非缺失值；不自动把遗漏编码设缺失")
                x = x.map(lambda v: mapping.get(key(v)) if pd.notna(v) else np.nan)
            elif op in ("log", "log1p", "square"):
                x = pd.to_numeric(x, errors="raise")
                if (op == "log" and x.dropna().le(0).any()) or (op == "log1p" and x.dropna().le(-1).any()):
                    raise ValueError(f"{name}: 对数定义域不满足；须在事前排除规则中处理")
                x = np.log(x) if op == "log" else np.log1p(x) if op == "log1p" else x ** 2
            elif op != "identity":
                raise ValueError("未知变换；不执行输入中的Python/Stata/R代码")
            frame[name] = x
        frames[did] = frame
        flow.append({"step": "read:" + did, "n_before": len(raw), "n_after": len(frame), "n_excluded": 0,
                     "reason": "只读原始数据，按冻结列投影"})
    primary = protocol["primary_dataset"]
    frame = frames[primary]
    loaded = {primary}
    for spec in protocol.get("joins", []):
        right = spec["right_dataset"]
        if right in loaded:
            raise ValueError("同一数据集不能重复合并")
        frame, info = merge_frames(frame, frames[right], spec)
        merges.append(info)
        loaded.add(right)
    if loaded != set(frames):
        raise ValueError("有数据集未参与合并；不隐式拼接")
    if frame.empty:
        raise ValueError("合并后无样本")
    for i, rule in enumerate(protocol.get("sample_filters", [])):
        x = frame[rule["variable"]]
        value = rule["value"]
        op = rule["op"]
        if op == "in":
            mask = x.isin(value)
        elif op == "eq":
            mask = x.eq(value)
        elif op == "ne":
            mask = x.ne(value)
        elif op == "ge":
            mask = x.ge(value)
        elif op == "gt":
            mask = x.gt(value)
        elif op == "le":
            mask = x.le(value)
        elif op == "lt":
            mask = x.lt(value)
        else:
            raise ValueError("未知样本筛选操作")
        mask = mask & x.notna()  # Missing values must not slip through !=.
        before = len(frame)
        frame = frame.loc[mask].copy()
        flow.append({"step": "filter:" + str(i + 1), "n_before": before, "n_after": len(frame),
                     "n_excluded": before - len(frame), "reason": rule["reason"]})
    if frame.empty:
        raise ValueError("事前筛选后无样本")
    return frame.reset_index(drop=True), {"sample_flow": flow, "merges": merges, "missing": missing}


def model_columns(model):
    return list(dict.fromkeys([model["outcome"]] + model["predictors"] + model.get("inflation_predictors", [])
                              + [model[k] for k in ("cluster", "exposure") if model.get(k)]))


def estimate(protocol, adapter, engine, run_id):
    import numpy as np
    import pandas as pd
    frame, audit = prepare_frame(protocol, adapter)
    model_specs = protocol["models"]
    required = list(dict.fromkeys(c for m in model_specs for c in model_columns(m)))
    if protocol["common_sample"]:
        before = len(frame)
        frame = frame.dropna(subset=required).copy()
        audit["sample_flow"].append({"step": "complete_case:common", "n_before": before, "n_after": len(frame),
                                     "n_excluded": before - len(frame), "reason": "冻结的共同完整案例样本"})
    if frame.empty:
        raise ValueError("缺失处理后无样本")
    np.random.seed(protocol["seed"])
    outputs, results, descriptions, failures = [], [], [], []
    for spec in model_specs:
        mid = spec["model_id"]
        sample = frame.dropna(subset=model_columns(spec)).copy()
        audit["sample_flow"].append({"step": "model:" + mid, "n_before": len(frame), "n_after": len(sample),
                                     "n_excluded": len(frame) - len(sample), "reason": "预定模型完整案例样本"})
        # Only digests and counts leave the process, never case values or identifiers.
        sample_version = value_hash({"protocol": value_hash(protocol), "model": mid,
                                    "positions": sample.index.tolist()})
        for column in model_columns(spec):
            s = pd.to_numeric(sample[column], errors="coerce")
            descriptions.append(clean({"model_id": mid, "variable_id": column, "n": len(sample),
                                      "mean": s.mean(), "sd": s.std(), "min": s.min(), "max": s.max(),
                                      "n_distinct": int(sample[column].nunique())}))
        try:
            output = engine.fit(sample, dict(spec, survey_design=protocol["survey_design"], seed=protocol["seed"]))
            output.update(model_id=mid, sample_version=sample_version, analysis_role=spec["analysis_role"],
                          hypothesis_id=spec.get("hypothesis_id"), outcome=spec["outcome"])
            if not output.get("parameters") or output.get("n_obs") != len(sample):
                raise ValueError("引擎输出参数为空或样本数不匹配")
            for i, parameter in enumerate(output["parameters"]):
                results.append(dict(parameter, result_id=f"{run_id}:{mid}:R{i+1:03d}", run_id=run_id,
                                    model_id=mid, hypothesis_id=spec.get("hypothesis_id"), sample_version=sample_version,
                                    outcome=spec["outcome"], n_obs=len(sample), engine=output["engine"],
                                    ci_level=output["ci_level"], analysis_role=spec["analysis_role"],
                                    n_clusters=output["diagnostics"].get("n_clusters"),
                                    status="executed"))
            outputs.append(output)
        except Exception as exc:
            # Keep all planned models and failed/inconclusive outputs; never select on p.
            failures.append({"model_id": mid, "error_type": type(exc).__name__, "error": str(exc)})
    return clean({"models": outputs, "results": results, "descriptive": descriptions,
                  "failures": failures, **audit})


def compare(first, second, rtol=1e-8, atol=1e-10):
    import math
    problems = []
    keys = ("model_id", "term", "outcome")
    a = {tuple(r[k] for k in keys): r for r in first["results"]}
    b = {tuple(r[k] for k in keys): r for r in second["results"]}
    if (set(a) != set(b) or first["sample_flow"] != second["sample_flow"] or first["failures"] != second["failures"]
            or first.get("merges") != second.get("merges") or first.get("missing") != second.get("missing")):
        problems.append("重跑的结果集合、样本流或失败模型不一致")
    for key in set(a) & set(b):
        for field in ("estimate", "std_error", "ci_low", "ci_high", "p_value"):
            x, y = a[key].get(field), b[key].get(field)
            if x is None or y is None or not math.isclose(x, y, rel_tol=rtol, abs_tol=atol):
                problems.append(f"复现差异 {key}:{field}")
        if a[key]["n_obs"] != b[key]["n_obs"] or a[key]["sample_version"] != b[key]["sample_version"]:
            problems.append(f"复现样本不一致 {key}")
        if any(a[key].get(field) != b[key].get(field) for field in ("scale", "ci_level", "n_clusters", "engine")):
            problems.append(f"复现尺度/推断设计不一致 {key}")
    return {"passed": not problems, "rtol": rtol, "atol": atol, "errors": problems,
            "comparison": "independent reload and refit; same locked raw inputs/specification"}
