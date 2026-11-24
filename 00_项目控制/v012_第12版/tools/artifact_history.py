"""Content-addressed history for mutable JSON working artifacts.

The current path remains the active view; every distinct prior byte sequence is
archived before replacement. Original inputs are never passed to this writer.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def write_json_preserving_history(path, value):
    path = Path(path)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Refusing to replace a symlinked artifact")
    if path.exists():
        if not path.is_file():
            raise ValueError("Artifact path is not a regular file")
        previous = path.read_bytes()
        if previous == raw:
            return path
        archive_dir = path.parent / "history" / path.name
        if archive_dir.is_symlink():
            raise ValueError("Artifact history directory is symlinked")
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive = archive_dir / (hashlib.sha256(previous).hexdigest() + ".bin")
        if archive.is_symlink():
            raise ValueError("Artifact history entry is symlinked")
        try:
            with archive.open("xb") as stream:
                stream.write(previous)
        except FileExistsError:
            if not archive.is_file() or archive.read_bytes() != previous:
                raise ValueError("Content-addressed artifact history collision")
    fd, temporary = tempfile.mkstemp(prefix="." + path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
