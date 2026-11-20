"""Replaceable estimation engines. Explicit design matrices; no eval/formula execution."""
from __future__ import annotations

import warnings
from typing import Protocol

from common06 import clean, environment

SUPPORTED = {"OLS", "BINARY_LOGIT", "POISSON", "NEGATIVE_BINOMIAL", "ZIP", "ZINB", "ORDERED_LOGIT", "MULTINOMIAL_LOGIT"}


class EstimationEngine(Protocol):
    engine_id: str
    def capabilities(self): ...
    def fit(self, frame, spec): ...


def matrix(frame, spec):
    import numpy as np
    import pandas as pd
    x = pd.DataFrame(index=frame.index)
    if spec.get("intercept", True):
        x["const"] = 1.0
    for name in spec["predictors"]:
        if name in spec.get("categorical", {}):
            levels = spec["categorical"][name]
            if len(levels) < 2 or not frame[name].isin(levels).all():
                raise ValueError(f"{name}: 类别/参照组须预先冻结且覆盖实际值")
            for level in levels[1:]:
                x[f"{name}[{level}]"] = (frame[name] == level).astype(float)
        else:
            x[name] = pd.to_numeric(frame[name], errors="raise").astype(float)
    for pair in spec.get("interactions", []):
        if len(pair) != 2 or not all(v in x for v in pair):
            raise ValueError("交互项须引用已存在的两个数值列/虚拟列")
        x[":".join(pair)] = x[pair[0]] * x[pair[1]]
    if x.empty or not np.isfinite(x.to_numpy()).all():
        raise ValueError("设计矩阵为空或包含非有限值")
    if np.linalg.matrix_rank(x.to_numpy()) != len(x.columns):
        raise ValueError("设计矩阵秩亏；不自动删变量")
    if len(frame) <= len(x.columns) + 1:
        raise ValueError("样本量不足以估计和推断")
    return x


class StatsmodelsEngine:
    engine_id = "statsmodels"

    def capabilities(self):
        return {"methods": sorted(SUPPORTED), "covariance": ["nonrobust", "HC1", "HC3", "cluster"],
                "complex_survey": False, "missing_policy": ["complete_case"],
                "notice": "不把freq_weights/var_weights冒充调查pweight；复杂抽样使用专用提供方"}

    def fit(self, frame, spec):
        import numpy as np
        import pandas as pd
        import statsmodels.api as sm
        from statsmodels.miscmodels.ordinal_model import OrderedModel
        from statsmodels.discrete.count_model import ZeroInflatedPoisson, ZeroInflatedNegativeBinomialP
        method = spec["method_id"]
        if method not in SUPPORTED:
            raise ValueError(f"内置引擎不支持{method}；须注册并核验专用提供方")
        survey = spec.get("survey_design", {})
        if any(survey.get(k, {}).get("status") == "specified" for k in ("weights", "strata", "psu")):
            raise ValueError("内置引擎不支持复杂抽样；不能用普通稳健误差代替设计型推断")
        x = matrix(frame, spec)
        y = pd.to_numeric(frame[spec["outcome"]], errors="raise").astype(float)
        if not np.isfinite(y).all():
            raise ValueError("结局存在非有限值")
        if method == "BINARY_LOGIT" and (not set(y.unique()).issubset({0.0, 1.0}) or y.nunique() != 2):
            raise ValueError("二元结局须同时存在0和1；预先明确事件编码")
        if method in ("POISSON", "NEGATIVE_BINOMIAL", "ZIP", "ZINB") and (y.lt(0).any() or not np.equal(y, np.floor(y)).all()):
            raise ValueError("计数结局须非负整数")
        covariance = spec.get("covariance", "HC1")
        if covariance not in self.capabilities()["covariance"]:
            raise ValueError("未知标准误方案")
        kwargs = {"cov_type": covariance}
        if covariance == "cluster":
            group = frame[spec["cluster"]]
            if group.isna().any() or group.nunique() < 2:
                raise ValueError("聚类变量缺失或少于2组")
            kwargs["cov_kwds"] = {"groups": group, "use_correction": True}
        offset = None
        if spec.get("exposure"):
            exposure = pd.to_numeric(frame[spec["exposure"]], errors="raise")
            if not np.isfinite(exposure).all() or exposure.le(0).any():
                raise ValueError("暴露量须为正且有限")
            offset = np.log(exposure)
            if method not in ("POISSON", "NEGATIVE_BINOMIAL", "ZIP", "ZINB"):
                raise ValueError("仅计数模型接受暴露量")
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter("always")
            if method == "OLS":
                model = sm.OLS(y, x)
            elif method == "BINARY_LOGIT":
                model = sm.Logit(y, x)
            elif method == "POISSON":
                model = sm.GLM(y, x, family=sm.families.Poisson(), offset=offset)
            elif method == "NEGATIVE_BINOMIAL":
                model = sm.NegativeBinomial(y, x, offset=offset)
            elif method in ("ZIP", "ZINB"):
                if not spec.get("zero_process_rationale") or not spec.get("inflation_predictors"):
                    raise ValueError("零膨胀须冻结结构零解释和零过程变量")
                inflation = matrix(frame, {"predictors": spec["inflation_predictors"], "intercept": True})
                klass = ZeroInflatedPoisson if method == "ZIP" else ZeroInflatedNegativeBinomialP
                model = klass(y, x, exog_infl=inflation, offset=offset)
            elif method == "ORDERED_LOGIT":
                order = spec.get("outcome_levels", [])
                if len(order) < 3 or not y.isin(order).all() or y.nunique() != len(order) or spec.get("intercept", True):
                    raise ValueError("有序logit须冻结至少3个有序编码、均有观测、intercept=false")
                yy = pd.Series(pd.Categorical(y, categories=order, ordered=True).codes, index=y.index)
                model = OrderedModel(yy, x, distr="logit")
            else:
                order = spec.get("outcome_levels", [])
                if len(order) < 3 or not y.isin(order).all() or y.nunique() != len(order):
                    raise ValueError("多项logit须冻结类别顺序和首位参照组，且均有观测")
                model = sm.MNLogit(pd.Series(pd.Categorical(y, categories=order).codes, index=y.index), x)
            if method in ("OLS", "POISSON"):
                fit = model.fit(**kwargs)
            else:
                fit = model.fit(disp=False, maxiter=spec.get("maxiter", 200), **kwargs)
        converged = bool(getattr(fit, "converged", getattr(fit, "mle_retvals", {}).get("converged", True)))
        notices = [{"category": w.category.__name__, "message": str(w.message)} for w in observed]
        problems = []
        if not converged:
            problems.append("估计未收敛")
        if any(any(t in n["category"] for t in ("Separation", "Convergence", "Hessian", "Runtime")) for n in notices):
            problems.append("估计警告要求处理；不静默接受分离/奇异Hessian/数值失败")
        params = fit.params
        rows = []
        alpha = 1 - spec.get("ci_level", 0.95)
        ci = np.asarray(fit.conf_int(alpha=alpha))
        if params.ndim == 1:
            for i, term in enumerate(params.index):
                if method == "OLS":
                    scale = "coefficient"
                elif str(term) == "alpha":
                    scale = "dispersion"
                elif str(term).startswith("inflate_"):
                    scale = "log_odds_structural_zero"
                elif method == "BINARY_LOGIT":
                    scale = "log_odds"
                elif method == "ORDERED_LOGIT":
                    thresholds = [str(t) for t in params.index if "/" in str(t)]
                    scale = ("threshold" if str(term) == thresholds[0] else "log_threshold_increment") if "/" in str(term) else "log_odds"
                else:
                    scale = "log_mean"
                rows.append({"term": str(term), "estimate": float(params.iloc[i]), "std_error": float(fit.bse.iloc[i]),
                             "p_value": float(fit.pvalues.iloc[i]), "ci_low": float(ci[i, 0]), "ci_high": float(ci[i, 1]),
                             "scale": scale})
        else:
            for j in range(params.shape[1]):
                for i, term in enumerate(params.index):
                    lo, hi = ci[j, i] if ci.ndim == 3 else ci[j * len(params) + i]
                    rows.append({"term": f"{term}|outcome={spec['outcome_levels'][j+1]}", "estimate": float(params.iloc[i, j]),
                                 "std_error": float(fit.bse.iloc[i, j]), "p_value": float(fit.pvalues.iloc[i, j]),
                                 "ci_low": float(lo), "ci_high": float(hi), "scale": "log_relative_risk"})
        if not all(np.isfinite(r[k]) for r in rows for k in ("estimate", "std_error", "p_value", "ci_low", "ci_high")):
            problems.append("参数/标准误/区间含非有限值")
        diagnostics = {"converged": converged, "rank": int(np.linalg.matrix_rank(x)), "n_parameters": len(rows),
                       "condition_number": float(np.linalg.cond(x)), "warnings": notices, "errors": problems,
                       "n_clusters": int(frame[spec['cluster']].nunique()) if covariance == "cluster" else None,
                       "llf": float(fit.llf), "aic": float(fit.aic), "bic": None,
                       "r_squared": float(fit.rsquared) if method == "OLS" else None}
        if method == "POISSON":
            diagnostics["pearson_dispersion"] = float(fit.pearson_chi2 / fit.df_resid)
        if method == "OLS":
            from statsmodels.stats.diagnostic import het_breuschpagan
            if "const" in x and len(x.columns) > 1:
                diagnostics["breusch_pagan_p"] = float(het_breuschpagan(fit.resid, x)[1])
        return clean({"engine": self.engine_id, "environment": environment(), "parameters": rows,
                      "diagnostics": diagnostics, "n_obs": len(frame), "covariance": covariance,
                      "ci_level": 1 - alpha, "prediction_exported": False})
