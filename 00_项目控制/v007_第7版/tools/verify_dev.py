"""Exercise the experiment contract with verified articles and local real survey data."""

import argparse
import hashlib
from pathlib import Path
import sys

from run_mode import ROOT, PRODUCTION, enforce, load, verified_run, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("pilot", type=Path)
    parser.add_argument("data", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    contract = verified_run(run)
    citations = load(args.pilot / "literature_matrix.json")
    review = load(args.pilot / "pilot_review.json")
    if review["decision"] != "accepted_20" or review["collection_sha256"] != citations["collection_sha256"]:
        raise ValueError("Literature review does not match the source collection")
    target = contract["workload"]["04"]["abstract_target"]
    eligible = set(review["article_ids"])
    reviewed = [row for row in citations["rows"] if row["article_id"] in eligible][:target]
    if len(reviewed) < target:
        raise ValueError("Insufficient verified source abstracts")
    enforce(run, "04", {"abstract_target": len(reviewed)})
    registry = {item["module_id"]: item["path"] for item in load(PRODUCTION / "module_registry.json")["modules"]}
    sys.path.insert(0, str(ROOT / registry["06"] / "tools"))
    from engines import StatsmodelsEngine
    import pandas as pd

    limits = enforce(run, "06", {"primary_models": 1, "robustness_models": 1, "repetitions": 1})
    frame = pd.read_stata(args.data, columns=["a2", "a7a"], convert_categoricals=False)
    complete = frame[frame["a2"].isin([1, 2]) & frame["a7a"].between(1, 14)]
    sample = complete.sample(n=min(limits["sample_max"], len(complete)), random_state=20261121)
    # Numeric codes exercise the engine only, with no substantive interpretation.
    spec = {"method_id": "OLS", "outcome": "a7a", "predictors": ["a2"]}
    engine = StatsmodelsEngine()
    fits = [engine.fit(sample, dict(spec, covariance=cov)) for cov in ("HC1", "HC3")]
    if any(fit["diagnostics"]["errors"] for fit in fits):
        raise ValueError("Estimation diagnostics blocked experiment")
    try:
        enforce(run, "06", {"robustness_models": 2})
    except ValueError:
        excessive_work_rejected = True
    else:
        raise AssertionError("Experimental budget was not enforced")
    hasher = hashlib.sha256()
    with args.data.open("rb") as data:
        for block in iter(lambda: data.read(1024 * 1024), b""):
            hasher.update(block)
    write(run / "engine_smoke.json", {
        "run_mode": "dev", "formal_eligible": False,
        "workload_sha256": contract["workload_sha256"],
        "reviewed_articles_reused": [row["article_id"] for row in reviewed],
        "source_review_collection_sha256": review["collection_sha256"],
        "data_sha256": hasher.hexdigest(), "n_obs": len(sample), "fits": fits,
        "excessive_work_rejected": excessive_work_rejected,
        "scope": "题录来源凭证和真实数据估计联调，未通过正式研究关卡",
    })


if __name__ == "__main__":
    main()
