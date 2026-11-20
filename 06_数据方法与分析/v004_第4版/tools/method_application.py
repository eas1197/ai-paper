"""将每个模型的设定、诊断和报告规则绑定到登记的方法库。"""
from pathlib import Path

from common06 import ROOT, sha


def registered_snapshot(path, binding):
    if not binding or binding.get("status") != "passed":
        raise ValueError("运行未绑定已验收的登记方法库")
    expected = (ROOT / binding["snapshot_directory"]).resolve()
    if Path(path).resolve() != expected:
        raise ValueError("执行协议必须使用运行登记的方法库快照")
    manifest = expected / "resource_snapshot.json"
    if sha(manifest) != binding["snapshot_manifest_sha256"]:
        raise ValueError("登记的方法库快照哈希不一致")
    return {"resource_id": binding["resource_id"], "manifest_sha256": sha(manifest)}


def application_errors(models, references):
    errors = []
    roles = {(r["method_id"], r["paper_id"]): r["reference_role"] for r in references}
    for model in models:
        mid = model["model_id"]
        required = set(model.get("method_tags", [])) | {model.get("method_id")}
        applications = model.get("method_applications", [])
        if not isinstance(applications, list) or any(not isinstance(a, dict) for a in applications):
            errors.append(f"{mid}: method_applications须为逐方法记录")
            continue
        by_method = {a.get("method_id"): a for a in applications}
        if set(by_method) != required or len(by_method) != len(applications):
            errors.append(f"{mid}: 估计器及所有方法标签均须逐项提交方法库应用记录")
            continue
        for method, use in by_method.items():
            if (roles.get((method, use.get("foundation_paper_id"))) != "method_foundation"
                    or roles.get((method, use.get("empirical_paper_id"))) != "empirical_example"):
                errors.append(f"{mid}/{method}: 未绑定该方法的原理及实证范例")
            for field in ("specification_basis", "diagnostics_basis", "reporting_basis"):
                if not isinstance(use.get(field), str) or not use[field].strip():
                    errors.append(f"{mid}/{method}: 缺少{field}，须交代范例对本模型的具体安排")
    return errors
