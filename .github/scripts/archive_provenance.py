"""I22: validate archive identity, inventory and byte binding, not execution."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath

RUN_ID=re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
SHA256=re.compile(r"[0-9a-f]{64}")
LEGACY_TYPES={"historical","chat_native_v5_experiment"}
ARCHIVE_TYPE="archived_run_snapshot"


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _relative(value):
    _require(isinstance(value,str) and value and "\\" not in value and "\x00" not in value,
             "Invalid archive relative path")
    path=PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and path.as_posix()==value
             and not any(":" in part for part in path.parts),
             "Invalid archive relative path")
    return path


def _unique_object(pairs):
    obj={}
    for key,value in pairs:
        _require(key not in obj,"Duplicate manifest key")
        obj[key]=value
    return obj


def load_manifest(path):
    return json.loads(Path(path).read_bytes(),object_pairs_hook=_unique_object)


def verify_archive(root, manifest):
    root=Path(root).resolve(strict=True)
    _require(manifest.get("archive_scope")=="existing_records_only"
             and manifest.get("new_execution_proven") is False,
             "Archive scope must not claim a new execution")
    runs={}
    for row in manifest["runs"]:
        rid=row.get("run_id")
        _require(isinstance(rid,str) and RUN_ID.fullmatch(rid) and rid not in runs,
                 "Invalid or duplicate archived run identity")
        _require(type(row.get("files")) is int and row["files"]>=0,
                 "Invalid archived file count")
        original=_relative(row["root"])
        _require(rid in original.parts,"Archive source root does not bind run identity")
        _require(row.get("type") in LEGACY_TYPES|{ARCHIVE_TYPE},
                 "Unknown archive nature")
        _require(row.get("formal_eligible") is not True and
                 row.get("new_execution_proven") is not True,
                 "Archive cannot assert new execution or formal authorization")
        runs[rid]=row
    counts=Counter()
    indexed=set()
    for name,digest in manifest["files"].items():
        relative=_relative(name)
        _require(len(relative.parts)>=2 and relative.parts[0] in runs,
                 "File has no registered archive run")
        _require(isinstance(digest,str) and SHA256.fullmatch(digest),
                 "Invalid archived SHA-256")
        path=root.joinpath(*relative.parts)
        _require(not path.is_symlink() and path.resolve().is_relative_to(root)
                 and path.is_file(),"Missing or escaped archived file")
        raw=path.read_bytes()
        _require(hashlib.sha256(raw).hexdigest()==digest,"Archived bytes do not match manifest")
        if path.suffix==".json":
            payload=json.loads(raw)
            if path.name in {"run_manifest.json","staged_topic.json"} and isinstance(payload,dict):
                if "run_id" in payload:
                    _require(payload["run_id"]==relative.parts[0],
                             "Original run record identity mismatch")
        counts[relative.parts[0]]+=1
        indexed.add(name)
    omitted=set()
    for row in manifest.get("omitted",[]):
        _require(isinstance(row,list) and len(row)==4,"Invalid omission entry")
        rid,name,digest,reason=row
        _require(rid in runs and isinstance(digest,str) and SHA256.fullmatch(digest)
                 and isinstance(reason,str) and bool(reason),"Invalid omission binding")
        key=rid+"/"+_relative(name).as_posix()
        _require(key not in indexed and key not in omitted,"Omitted path also indexed or duplicated")
        omitted.add(key)
    actual=set()
    for path in root.rglob("*"):
        _require(not path.is_symlink(),"Archive contains a symlink")
        if path.is_file() and path!=root/"manifest.json":
            actual.add(path.relative_to(root).as_posix())
    _require(actual==indexed,"Archive inventory differs from indexed files")
    for rid,row in runs.items():
        _require(row["files"]==counts[rid],"Archive file count differs from index")
        if row["type"]==ARCHIVE_TYPE:
            source=row.get("source_manifest")
            _require(row.get("source_run_id")==rid and isinstance(source,dict),
                     "New archive snapshot lacks source run binding")
            path=_relative(source.get("path"))
            _require(path.parts[0]==rid and manifest["files"].get(path.as_posix())==source.get("sha256")
                     and isinstance(source.get("sha256"),str) and SHA256.fullmatch(source["sha256"]),
                     "New archive snapshot lacks indexed original manifest")
            _require(path.name in {"run_manifest.json","manifest.json"},
                     "Source must be a run manifest")
            payload=json.loads(root.joinpath(*path.parts).read_bytes())
            _require(isinstance(payload,dict) and
                     payload.get("research_id",payload.get("run_id"))==rid,
                     "Snapshot source manifest belongs to another run")
    return {"archived_runs":len(runs),"archived_files":len(indexed),"omitted_files":len(omitted),
            "new_execution_proven":False,"formal_eligible":False,
            "run_types":{rid:row["type"] for rid,row in runs.items()}}
