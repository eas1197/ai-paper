"""Stage 06 utilities. No network, credentials, or model calls."""
from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parents[1]
CONTROL = ROOT / "00_项目控制/v003_第3版"
# Reuse the existing evidence/run contracts, without changing historical modules.
sys.path.insert(0, str(ROOT / "04_议题文献与现实/v004_第4版/tools"))
from runtime import (canonical, csv_write, file_lock, indexed, inside, integrity, load,
                     now, present, require_fields, run_directory, sha, valid_date,
                     value_hash, verify_locks, write)


def environment():
    versions = {"python": sys.version}
    for name in ("pandas", "numpy", "scipy", "statsmodels", "pyreadstat"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not_installed"
    return versions


def clean(value):
    """Only JSON primitives, finite numbers, no per-case arrays."""
    import math
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if hasattr(value, "item"):
        return clean(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def project_output(path):
    target = Path(path).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError("输出必须位于本项目内")
    if target.exists():
        raise FileExistsError("拒绝覆盖已有产物；请使用新路径/attempt")
    return target


def review_ok(review, digest):
    return (isinstance(review, dict) and review.get("decision") == "accepted"
            and review.get("content_sha256") == digest
            and present(review.get("reviewer")) and valid_date(review.get("reviewed_at"))
            and present(review.get("assessment")))
