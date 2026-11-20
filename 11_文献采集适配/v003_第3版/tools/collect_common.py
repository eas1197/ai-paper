"""Small shared utilities for authorized acquisition; no credentials are serialized."""
from __future__ import annotations
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)

def contained(root, relative):
    root = Path(root).resolve(); target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("输出路径越界")
    return target

def output_path(raw):
    return contained(ROOT, raw)

def normalize(value):
    import unicodedata
    return re.sub(r"[^\w]", "", unicodedata.normalize("NFKC", str(value or "")).casefold())

def article_id(record):
    strong = record.get("doi") or record.get("source_record_id") or record.get("url")
    if not strong:
        strong = [normalize(record.get("title")), record.get("authors"), record.get("year")]
    return "P_" + digest(["cnki", strong])[:20]

class AccessStop(RuntimeError):
    def __init__(self, status, message):
        super().__init__(message); self.status = status
