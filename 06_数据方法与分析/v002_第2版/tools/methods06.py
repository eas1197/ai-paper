"""Immutable long-term method-library snapshots, with page/quote verification."""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

from common06 import (MODULE, csv_write, indexed, inside, load, now, present, project_output,
                      require_fields, review_ok, sha, valid_date, value_hash, write)


def catalog():
    with (MODULE / "方法库/method_catalog.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def norm(value):
    return "".join(str(value).split())


def coverage_ok(matches):
    identities = {norm(str(r.get("doi") or r["title"]).lower()) for r in matches}
    return (len({r["paper_id"] for r in matches}) >= 2 and len(identities) >= 2
            and len({r["pdf_sha256"] for r in matches}) >= 2
            and {"method_foundation", "empirical_example"}.issubset({r["reference_role"] for r in matches}))


def verify_references(records, base, required=None, pdf_reader=None):
    from providers import PdfReader
    pdf_reader = pdf_reader or PdfReader()
    errors, checked, files, seen, cache = [], [], [], set(), {}
    methods = {r["method_id"] for r in catalog()}
    required = set(required or methods)
    for row in records:
        e = []
        label = f"{row.get('method_id')}:{row.get('paper_id')}"
        require_fields(row, ("method_id", "paper_id", "title", "authors", "year", "source_url", "retrieved_at",
                            "access_basis", "pdf_path", "pdf_sha256", "identity_basis", "reader", "read_at",
                            "selection_reason", "model_specification", "assumptions", "diagnostics",
                            "reporting_rules", "applicability", "verified_at"), label, e)
        if row.get("method_id") not in methods:
            e.append(label + ": 未知方法")
        if type(row.get("year")) is not int or not 1 <= row["year"] <= int(now()[:4]):
            e.append(label + ": 文献年份无效")
        if not isinstance(row.get("authors"), list) or not row["authors"] or not all(isinstance(a, str) and a.strip() for a in row["authors"]):
            e.append(label + ": authors须为真实作者列表")
        pair = (row.get("method_id"), row.get("paper_id"))
        if pair in seen:
            e.append(label + ": 同一方法内文献重复")
        seen.add(pair)
        if row.get("reference_role") not in ("method_foundation", "empirical_example"):
            e.append(label + ": 须区分原理文献/实证范例")
        if row.get("retain_allowed") is not True or row.get("review_status") != "verified" or row.get("read_status") != "fulltext_read":
            e.append(label + ": 全文阅读/复核/合法本地保留尚未确认")
        if not all(valid_date(row.get(k)) for k in ("read_at", "retrieved_at", "verified_at")):
            e.append(label + ": 阅读/核验时间无效")
        path = (Path(base) / row.get("pdf_path", "MISSING")).resolve()
        try:
            if sha(path) != row.get("pdf_sha256"):
                raise ValueError("PDF哈希不符")
            if path not in cache:
                cache[path] = pdf_reader.inspect(path)
            pages = cache[path]
            files.append(path)
            locators = row.get("method_evidence", [])
            if not locators:
                e.append(label + ": 缺少方法页码/原文短摘")
            if row.get("reference_role") == "empirical_example":
                if not row.get("table_evidence") or not row.get("table_structure"):
                    e.append(label + ": 实证范例须抽取表格页码、短摘、行列与注释规则")
            for item in locators + row.get("table_evidence", []):
                page = item.get("pdf_page")
                quote = item.get("short_excerpt")
                if type(page) is not int or not 1 <= page <= len(pages) or not quote or norm(quote) not in norm(pages[page - 1]):
                    e.append(label + ": 页码或短摘不能在原文定位")
        except (OSError, ValueError) as exc:
            e.append(label + ": " + str(exc))
        if not e:
            checked.append(row)
        errors.extend(e)
    for mid in sorted(required):
        matches = [r for r in checked if r["method_id"] == mid]
        # Duplicated titles/DOIs/files cannot count as two different papers.
        if not coverage_ok(matches):
            errors.append(f"{mid}: 未满足两篇不同已读全文（原理文献+实证表格范例）")
    return {"errors": errors, "verified_records": checked, "required_methods": sorted(required),
            "verified_count": len(checked), "files": list(dict.fromkeys(files))}


def build_library(input_file, output, review_file=None):
    source = Path(input_file).resolve()
    data = load(source)
    target = project_output(output)
    # Complete all checks before creating immutable snapshot.
    before = sha(source)
    report = verify_references(data.get("references", []), source.parent)
    records = []
    target.mkdir(parents=True)
    for row in report["verified_records"]:
        copied = dict(row)
        path = (source.parent / row["pdf_path"]).resolve()
        filename = "literature/" + row["pdf_sha256"] + ".pdf"
        destination = inside(target, filename)
        destination.parent.mkdir(exist_ok=True)
        if not destination.exists():
            shutil.copyfile(path, destination)
        copied["pdf_path"] = filename
        if sha(destination) != row["pdf_sha256"]:
            raise ValueError("全文在归档期间改变；该快照不可使用")
        records.append(copied)
    digest = value_hash(records)
    review = load(review_file) if review_file else None
    errors = list(report["errors"])
    if not review_ok(review, digest):
        errors.append("长期方法库尚需绑定内容哈希的实质复核")
    if sha(source) != before:
        errors.append("输入在建设期间变化")
    write(target / "references.json", records)
    rows = []
    for item in catalog():
        matches = [r for r in records if r["method_id"] == item["method_id"]]
        rows.append(dict(item, reference_1_paper_id=matches[0]["paper_id"] if matches else "",
                         reference_2_paper_id=matches[1]["paper_id"] if len(matches) > 1 else "",
                         reference_status="verified_coverage" if coverage_ok(matches) else "pending"))
    csv_write(target / "method_catalog.csv", rows, list(rows[0]))
    write(target / "gate_report.json", {"status": "needs_review" if errors else "passed", "errors": errors,
          "verified_references": len(records), "required_methods": report["required_methods"]})
    write(target / "quality_review_request.json", {"content_sha256": digest, "decision": "pending",
          "reviewer": None, "reviewed_at": None, "assessment": None})
    if review:
        write(target / "quality_review.json", review)
    write(target / "resource_snapshot.json", {"schema_version": 1, "module_id": "06", "module_version": 2,
          "built_at": now(), "status": "needs_review" if errors else "passed", "content_sha256": digest,
          "input_sha256": before, "output_files": [{"path": str(p.relative_to(target)).replace("\\", "/"), "sha256": sha(p)}
                    for p in sorted(target.rglob("*")) if p.is_file()], "share_scope": "local_only"})
    return {"status": "needs_review" if errors else "passed", "path": str(target), "errors": errors}


def load_library(snapshot, used_methods):
    target = Path(snapshot)
    mf = load(target / "resource_snapshot.json")
    errors = []
    for item in mf["output_files"]:
        path = inside(target, item["path"])
        if not path.is_file() or sha(path) != item["sha256"]:
            errors.append("方法库产物已改变: " + item["path"])
    records = load(target / "references.json")
    used_records = [r for r in records if r["method_id"] in used_methods]
    result = verify_references(used_records, target, used_methods)
    errors.extend(result["errors"])
    # A partial library can support verified covered methods, but cannot claim the full 22-method library passed.
    if not review_ok(load(target / "quality_review.json") if (target / "quality_review.json").exists() else None, value_hash(records)):
        errors.append("方法库未绑定实质复核")
    return used_records, errors
