"""Read-only metadata-first dataset adapters; case frames never enter manifests."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol

from common06 import clean, load, now, sha


def normalized_labels(mapping):
    """JSON and ReadStat may represent the same label code as 1 or 1.0."""
    result = {}
    for key, value in mapping.items():
        label = str(key)
        try:
            numeric = float(label)
            if numeric.is_integer():
                label = str(int(numeric))
        except ValueError:
            pass
        result[label] = value
    return result


class DatasetAdapter(Protocol):
    def discover(self, root): ...
    def read_metadata(self, path): ...
    def read_subset(self, path, columns): ...
    def harmonize(self, frame, specification): ...


class LocalDatasetAdapter:
    def discover(self, root):
        """Names alone never prove original identity; no case values returned."""
        result = []
        for file in sorted(Path(root).resolve().rglob("*")):
            if file.is_file() and file.suffix.lower() in (".dta", ".sav", ".zsav", ".csv"):
                name = file.name.lower()
                kind = "historical_derived" if any(x in name for x in ("reps", "regress", "clean", "merged", "result")) else "unknown"
                result.append({"path": str(file), "format": file.suffix.lower()[1:],
                               "size_bytes": file.stat().st_size, "identity_status": kind})
        return {"scanned_at": now(), "read_only": True, "files": result}

    def read_metadata(self, path):
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix == ".dta":
            # Prefer ReadStat's explicit missing/value-label metadata when installed.
            try:
                import pyreadstat
            except ImportError:
                import pandas as pd
                with pd.read_stata(path, iterator=True, convert_categoricals=False) as reader:
                    labels = reader.variable_labels()
                    sets = reader.value_labels()
                    # pandas exposes label dictionaries publicly, but not their variable mapping.
                    # This guarded fallback is covered by the DTA round-trip test.
                    names = getattr(reader, "_varlist", None)
                    label_sets = getattr(reader, "_lbllist", None)
                    if names is None or label_sets is None:
                        raise ValueError("此pandas版本无法保留标签映射，请使用pyreadstat")
                    label_names = dict(zip(names, label_sets))
                    columns = {v: {"label": labels.get(v, ""),
                                   "value_labels": sets.get(label_names.get(v), {}),
                                   "special_missing": {"system_and_tagged": "Stata . and .a-.z; masked at read"}}
                               for v in labels}
                    count = int(reader._nobs)
                return clean({"format": "dta", "n_rows": count, "columns": columns,
                              "reader": "pandas", "question_text_available": False})
            _, meta = pyreadstat.read_dta(str(path), metadataonly=True, user_missing=True)
        elif suffix in (".sav", ".zsav"):
            try:
                import pyreadstat
            except ImportError as exc:
                raise ValueError("读取SAV元数据需要可选依赖pyreadstat；未安装时不能冒充已读取") from exc
            _, meta = pyreadstat.read_sav(str(path), metadataonly=True, user_missing=True)
        elif suffix == ".csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                header = next(reader, [])
                if not header or len(header) != len(set(header)):
                    raise ValueError("CSV字段为空或重复")
            return {"format": "csv", "n_rows": None, "columns": {v: {"label": "", "value_labels": {},
                    "special_missing": {}} for v in header}, "reader": "csv_header_only",
                    "question_text_available": False, "notice": "CSV无原生标签，正式分析须提供代码本sidecar"}
        else:
            raise ValueError("仅支持DTA/SAV/ZSAV/CSV；不能将历史回归结果作为原始输入")
        return clean({"format": suffix[1:], "n_rows": meta.number_rows, "reader": "pyreadstat",
                      "question_text_available": False,
                      "columns": {v: {"label": meta.column_names_to_labels.get(v, ""),
                                       "value_labels": normalized_labels(meta.variable_value_labels.get(v, {})),
                                       "special_missing": {"ranges": meta.missing_ranges.get(v, []),
                                                           "user_values": meta.missing_user_values.get(v, [])}}
                                  for v in meta.column_names}})

    def read_subset(self, path, columns):
        import pandas as pd
        path = Path(path)
        columns = list(dict.fromkeys(columns))
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path, usecols=columns)
        if path.suffix.lower() == ".dta":
            # Stata special missing objects remain distinct until explicitly masked.
            from pandas.io.stata import StataMissingValue
            frame = pd.read_stata(path, columns=columns, convert_categoricals=False, convert_missing=True)
            for column in frame:
                frame[column] = frame[column].map(lambda x: float("nan") if isinstance(x, StataMissingValue) else x)
            return frame
        if path.suffix.lower() in (".sav", ".zsav"):
            try:
                import pyreadstat
            except ImportError as exc:
                raise ValueError("SAV需要pyreadstat") from exc
            frame, _ = pyreadstat.read_sav(str(path), usecols=columns, apply_value_formats=False, user_missing=False)
            return frame
        raise ValueError("不支持的数据格式")

    def harmonize(self, frame, specification):
        """Explicit mappings only. No guessed wave/coding equivalence."""
        if specification.get("review_status") != "verified":
            raise ValueError("跨波次映射尚未核验")
        for item in specification.get("recode", []):
            name = item["column"]
            mapping = {str(k): v for k, v in item["mapping"].items()}
            original = frame[name]
            frame[name] = original.map(lambda x: mapping.get(str(x), x) if not pd_isna(x) else x)
        return frame


def pd_isna(value):
    import pandas as pd
    return pd.isna(value)


def merge_frames(left, right, spec):
    """Fail on null/duplicate keys; retain matching counts, never return IDs in logs."""
    keys = spec["on"]
    if not keys or spec.get("validate") not in ("one_to_one", "many_to_one", "one_to_many"):
        raise ValueError("合并须指定主键和1:1/m:1/1:m关系；不允许多对多")
    if spec.get("how") not in ("left", "inner"):
        raise ValueError("仅允许显式left/inner合并")
    if left[keys].isna().any().any() or right[keys].isna().any().any():
        raise ValueError("合并键含缺失；禁止NaN相互匹配")
    overlap = (set(left.columns) & set(right.columns)) - set(keys)
    if overlap:
        raise ValueError(f"合并非键列冲突，须显式重命名: {sorted(overlap)}")
    probe = left.merge(right, on=keys, how="outer", validate=spec["validate"], indicator=True)
    counts = probe["_merge"].value_counts().to_dict()
    left_matches = left[keys].merge(right[keys].drop_duplicates(), on=keys, how="left", indicator=True)["_merge"].eq("both")
    right_matches = right[keys].merge(left[keys].drop_duplicates(), on=keys, how="left", indicator=True)["_merge"].eq("both")
    out = left.merge(right, on=keys, how=spec["how"], validate=spec["validate"])
    return out, {"left_n": len(left), "right_n": len(right), "output_n": len(out),
                 "match_rows": int(counts.get("both", 0)), "left_only_rows": int(counts.get("left_only", 0)),
                 "right_only_rows": int(counts.get("right_only", 0)), "on": keys, "how": spec["how"],
                 "validate": spec["validate"], "left_match_rate": float(left_matches.mean()) if len(left) else None,
                 "right_match_rate": float(right_matches.mean()) if len(right) else None}
