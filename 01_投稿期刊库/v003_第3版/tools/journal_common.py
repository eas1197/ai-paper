"""Local evidence and immutable resource helpers (Python 3.10+)."""
from __future__ import annotations
import csv
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
ROOT = MODULE.parents[1]
CONTROL = ROOT / '00_项目控制/v003_第3版'

def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def hash_value(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(temp, path)
    finally:
        if Path(temp).exists():
            Path(temp).unlink()

def inside(root, path):
    root = Path(root).resolve()
    result = (root / path).resolve()
    if not result.is_relative_to(root):
        raise ValueError('路径越界: ' + str(path))
    return result

def output(path):
    result = inside(ROOT, path)
    if result.exists():
        raise FileExistsError('拒绝覆盖已有产物，请新建attempt: ' + str(result))
    return result

def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', value):
        raise ValueError('ID须为英文数字、下划线、连字符，长度1—80')
    return value

def csv_write(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})

def norm_name(name):
    return re.sub(r'[\s.·、（）()：:，,]', '', str(name))

def lock(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT)).replace('\\', '/'), 'sha256': sha(path)}

def locks_ok(files):
    errors = []
    for item in files:
        try:
            p = inside(ROOT, item['path'])
            if not p.is_file() or sha(p) != item['sha256']:
                errors.append('输入/产物哈希变化: ' + item['path'])
        except (OSError, KeyError, ValueError) as exc:
            errors.append(str(exc))
    return errors

def date_ok(value, as_of):
    try:
        return datetime.fromisoformat(value).date() <= datetime.fromisoformat(as_of).date()
    except (TypeError, ValueError):
        return False
