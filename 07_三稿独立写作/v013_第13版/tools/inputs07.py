"""第七步只读取同一运行已经验收、仍然有效的输入。"""
from pathlib import Path

from runtime import ROOT, file_lock, inside, integrity, load, sha
from exemplars07 import MOVES, read_index
from paragraph07 import style_resource


def locked_output(work, manifest, name):
    path = inside(work, name)
    if not any(inside(work, row["path"]) == path for row in manifest["output_files"]):
        raise ValueError(f"产物不在阶段哈希锁内: {name}")
    return path


def stage_input(run, row, stage_id):
    if row.get("status") != "passed":
        raise ValueError(f"G{int(stage_id)} 当前状态 {row.get('status', 'not_started')}")
    path = inside(run / f"stage_{stage_id}", row["manifest_path"])
    manifest = load(path)
    if (path.name != "stage_manifest.json" or row.get("manifest_sha256") != sha(path)
            or manifest.get("attempt") != row.get("attempt")
            or manifest.get("run_id") != run.name or manifest.get("stage_id") != stage_id
            or manifest.get("status") != "passed"):
        raise ValueError(f"G{int(stage_id)} 未绑定同一运行的当前通过记录")
    errors = integrity(path.parent)
    gate = load(locked_output(path.parent, manifest, manifest["gate_report"]))
    if errors or gate.get("gate") != f"G{int(stage_id)}" or gate.get("status") != "passed":
        raise ValueError(f"G{int(stage_id)} 验收或完整性检查失败: {errors}")
    return path, manifest


def resource_input(bindings, mid):
    binding = bindings.get(mid, {})
    if binding.get("status") != "passed":
        raise ValueError(f"G{int(mid)} 运行锁定资源状态 {binding.get('status', 'not_built')}")
    path = inside(ROOT, binding["snapshot_manifest_path"])
    snapshot = load(path)
    if (sha(path) != binding["manifest_sha256"] or snapshot.get("module_id") != mid
            or snapshot.get("status") != "passed" or not snapshot.get("files")):
        raise ValueError(f"G{int(mid)} 资源版本变化或未验收")
    files = {inside(ROOT, row["path"]): row["sha256"] for row in snapshot["files"]}
    gate = inside(ROOT, snapshot["business_gate_report"])
    if (gate not in files or any(sha(p) != digest for p, digest in files.items())
            or load(gate).get("status") != "passed"):
        raise ValueError(f"G{int(mid)} 资源文件或业务报告未通过哈希复验")
    return file_lock(path), {str(p): digest for p, digest in files.items()}


def collect(run, data, module, version):
    errors, resources, stages, locks = [], {}, {}, {}
    exemplar_indexes = []
    rows = {row["stage_id"]: row for row in data["stages"]}
    bound_to_version = rows.get("07", {}).get("module_version") == version
    if not bound_to_version:
        errors.append(f"本运行锁定第7步旧版本，未迁移；第{version}版用于新初始化运行")
    bindings = {row["module_id"]: row for row in data.get("shared_resource_bindings", [])}
    for mid in ("02", "03"):
        try:
            snapshot, files = resource_input(bindings, mid)
            resources[mid] = snapshot
            locks.update(files)
            if mid == "03":
                exemplar_indexes = [Path(path) for path in files if Path(path).name == "writing_exemplars.json"]
            locks[snapshot["path"]] = snapshot["sha256"]
        except (OSError, ValueError, KeyError) as exc:
            errors.append(str(exc))
    documents, bundles, gates = {}, {}, {}
    for mid in ("04", "05", "06"):
        try:
            path, manifest = stage_input(run, rows.get(mid, {}), mid)
            gates[mid] = load(locked_output(path.parent, manifest, manifest["gate_report"]))
            bundle = load(locked_output(path.parent, manifest, "bundle.json"))
            if bundle.get("run_id") != run.name:
                raise ValueError(f"G{int(mid)} bundle 的 run_id 不一致")
            bundles[mid] = bundle
            stages[mid] = file_lock(path)
            for row in manifest["output_files"]:
                locks[str(inside(path.parent, row["path"]))] = row["sha256"]
            locks[str(path)] = stages[mid]["sha256"]
            if mid == "05":
                documents["design"] = load(locked_output(path.parent, manifest, "analysis_design.json"))
        except (OSError, ValueError, KeyError) as exc:
            errors.append(str(exc))
    config = data.get("config_snapshot", {})
    writing = config.get("writing", {})
    architecture = writing.get("architecture", {})
    style = writing.get("language_style", {})
    materials, style_ids = {}, []
    try:
        if architecture != load(module / "manifest.json")["writing_architecture"]:
            raise ValueError("运行锁定的写作架构与第7步版本不同")
        for spec, key in ((architecture, "profile"), (architecture, "guide"), (style, "profile")):
            path = inside(ROOT, spec[key + "_path"])
            digest = sha(path)
            if digest != spec[key + "_sha256"]:
                raise ValueError(f"写作架构或语言规范已变化: {path.name}")
            if not errors and locks.get(str(path)) != digest:
                raise ValueError(f"写作规范没有纳入已验收资源: {path.name}")
            locks[str(path)] = digest
        profile = load(inside(ROOT, style["profile_path"]))
        style_ids = profile["style_ids"]
        if not style_ids:
            raise ValueError("03语言风格条目为空")
        paragraph_style = profile.get("paragraph_style")
        if bound_to_version:
            if not paragraph_style:
                raise ValueError("当前03资源缺少逐段写法映射")
            style_resource(paragraph_style, architecture, style_ids)
            for source in paragraph_style.values():
                path = inside(ROOT, source["path"])
                if not errors and locks.get(str(path)) != source["sha256"]:
                    raise ValueError("03逐段写法及规则须列入已验收的G3快照")
                locks[str(path)] = source["sha256"]
        for key in ("guide", "examples", "application"):
            material = profile[key]
            path = inside(ROOT, material["path"])
            if sha(path) != material["sha256"]:
                raise ValueError(f"03语言材料已变化: {path.name}")
            materials[key] = material
            locks[str(path)] = material["sha256"]
    except (OSError, ValueError, KeyError) as exc:
        errors.append(str(exc))
    if errors:
        return errors, None, {}

    literature, theory, analysis = (bundles[mid] for mid in ("04", "05", "06"))
    core = {row["paper_id"] for row in literature["core"]}
    dialogue = {row["paper_id"] for row in literature["dialogue"]}
    if len(core) < 25 or not core <= dialogue:
        errors.append("G4 缺少至少25篇核心全文及逐篇对话")
    gate04 = gates["04"]
    if (not core <= set(gate04.get("source_eligible_paper_ids", []))
            or gate04.get("counts", {}).get("abstracts_read", 0) < 100):
        errors.append("G4 缺少指定文献库准入及摘要核验")
    design = documents["design"]
    if (theory["upstream"]["manifest_sha256"] != stages["04"]["sha256"]
            or design.get("frozen") is not True or design.get("pre_analysis") is not True):
        errors.append("G5 未锁定当前 G4 或设计未事前冻结")
    if (Path(analysis["upstream"]["path"]).resolve() != Path(stages["05"]["path"])
            or analysis["upstream"]["design_sha256"] != design.get("design_sha256")
            or not all(analysis.get(key) for key in ("actual_run_at", "sample_flow", "models",
                                                     "method_references", "reproduction", "results"))):
        errors.append("G6 没有与当前冻结设计对应的真实模型、样本流、方法范例和复现结果")
    binding = config.get("analysis", {}).get("method_library_resource")
    if not binding or analysis.get("method_library_binding") != binding or gates["06"].get("phase") != "approve":
        errors.append("G6 未通过登记方法库和正式分析复核")
    mode = data.get("writing_mode")
    expected = {"single": ["A"], "three_plus_review": ["A", "B", "C"]}
    if mode not in expected or data.get("draft_labels") != expected[mode]:
        errors.append("运行的写作模式与稿件标签不一致")
    if errors:
        return errors, None, {}
    exemplar_binding = None
    try:
        if len(exemplar_indexes) > 1:
            raise ValueError("G3 快照存在多个同名范例索引")
        if exemplar_indexes:
            exemplar_index = exemplar_indexes[0]
            read_index(exemplar_index)
            presets = writing.get("exemplar_queries", {})
            default_topic = " ".join(str(data[key]) for key in ("theme", "issue", "question") if data.get(key))
            queries = {}
            for move in MOVES:
                query = presets.get(move, {})
                topic = query.get("topic", default_topic)
                queries[move] = {**query, "move": move, "topic": topic}
            exemplar_binding = {"path": str(exemplar_index), "sha256": locks[str(exemplar_index)],
                                "queries": queries}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return [f"G3 范例读取失败：{exc}"], None, {}
    requirements = file_lock(module / "templates/文字要求.md")
    locks[requirements["path"]] = requirements["sha256"]
    for p in sorted((module / "tools").glob("*.py")) + [
            module / "manifest.json", module / "templates/architecture_self_check.csv",
            ROOT / "基础要求.md", ROOT / "项目架构.md",
            ROOT / "AGENTS.md"]:
        locks[str(p)] = sha(p)
    pack = {
        "schema_version": 1, "run_id": run.name, "module_version": version,
        "writing_mode": mode, "draft_labels": expected[mode], "writing_architecture": architecture,
        "language_style": style, "style_ids": style_ids, "style_materials": materials,
        "writing_requirements": requirements, "writing_exemplars": exemplar_binding,
        "paragraph_style": paragraph_style,
        "eligible_literature_ids": gate04["source_eligible_paper_ids"],
        "method_library_binding": binding, "seed": analysis["protocol"]["seed"],
        "resources": resources, "upstream_manifests": stages,
        "input_files": [{"path": path, "sha256": digest} for path, digest in sorted(locks.items())],
    }
    return [], pack, bundles
