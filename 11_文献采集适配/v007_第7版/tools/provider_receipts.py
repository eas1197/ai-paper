"""Verify artifacts exported by a separate provider invocation."""
from pathlib import Path

from collect_common import load, sha


def contained(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if path == root or not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Receipt file is missing or escapes its directory")
    return path


def external_receipt(folder, role):
    path = contained(folder, "provider_receipt.json")
    record = load(path)
    if (record["type"] != "external_agent" or record["status"] != "completed"
            or record["role"] != role or any(not isinstance(record[k], str) or not record[k].strip()
            for k in ("provider", "invocation_id", "model"))):
        raise ValueError("Invalid external agent receipt")
    request = contained(folder, record["request_file"])
    response = contained(folder, "response.json")
    if (request.name not in {"request.json", "prompt.txt"} or request.parent != path.parent
            or response.parent != path.parent or sha(request) != record["request_sha256"]
            or sha(response) != record["response_sha256"]):
        raise ValueError("External invocation artifacts changed")
    return record, request, response
