"""Check only CFPS2022 item validity and eligible group sizes for the topic trial."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.io.stata import StataReader

from topic_cards import WORK
from runtime import file_lock, now, write

COLS = ("age", "employ", "jobclass", "qg1", "qg101", "qg5", "qg501", "qg502", "qg9_a_4")


def check(source):
    lock = file_lock(source)
    with StataReader(source) as reader:
        labels = reader.variable_labels()
        values = reader.value_labels()
    data = pd.read_stata(source, columns=list(COLS), convert_categoricals=False)
    eligible = data.loc[(data["age"] >= 18) & (data["employ"] == 1) & (data["jobclass"] == 4)
                        & (data["qg1"] == 5) & (data["qg101"] == 5) & (data["qg5"] == 1)
                        & (data["qg501"] == 1) & data["qg502"].isin([0, 1])]
    count = {str(k): int((eligible["qg502"] == k).sum()) for k in (0, 1)}
    valid = eligible.loc[eligible["qg9_a_4"].isin([0, 1])]
    measurable = {str(k): int((valid["qg502"] == k).sum()) for k in (0, 1)}
    if file_lock(source) != lock:
        raise ValueError("检查期间CFPS源文件发生变化")
    return {"checked_at": now(), "source": lock, "script": file_lock(__file__),
            "source_obs": len(data), "variable_labels": {k: labels[k] for k in COLS},
            "value_labels": {k: {str(code): label for code, label in values[k].items()}
                             for k in COLS if k in values},
            "sample": "18岁及以上、在业、当前非农受雇、有合同并约定期限、有有效签约对象答案",
            "contrast": {"0": "未报告与派遣/中介单位签合同", "1": "报告与派遣/中介单位签合同"},
            "eligible": count, "valid_work_injury_item": measurable, "wrote_respondents": False,
            "estimated_outcome_differences": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", type=Path)
    args = p.parse_args()
    target = WORK / "选题试跑_CFPS测量可行性.json"
    write(target, check(args.source.resolve()))
