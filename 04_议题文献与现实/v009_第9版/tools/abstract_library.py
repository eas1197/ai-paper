"""04 receiving contract. Intentionally does not call the existing formal G4."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "00_项目控制/v006_第6版/v3.1_摘要候选注册表.json"


def load_candidate():
    def read(path):
        return json.loads(path.read_text(encoding="utf-8-sig"))
    profile = read(PROFILE)
    if (profile["profile"], profile["acquisition_mode"], profile["scope"],
        profile["enabled_by_default"]) != ("paper_autonomous_v31", "abstract_only", "acquisition_only", False):
        raise ValueError("候选注册表不符合摘要模式")
    if (ROOT / profile["modules"]["04"]).resolve() != HERE:
        raise ValueError("当前04版本未注册在摘要候选")
    old = {m["module_id"]: m for m in read(ROOT / profile["production_registry"])["modules"]}
    other = (ROOT / profile["modules"]["11"]).resolve()
    expected = (ROOT / old["11"]["path"] / "tools").resolve()
    if not other.is_relative_to(ROOT) or not expected.is_relative_to(ROOT) or other == expected.parent:
        raise ValueError("候选和生产11必须独立")
    for path in (expected, other / "tools"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from abstract_acquisition import collect
    return collect


def receive(work):
    from abstract_acquisition import MODE, TARGET, SEEDS, abstract_text, relevance, safe_url, text_hash
    from collect_common import digest, load, write
    bundle = load(work / "abstract_collection.json")
    if (bundle.get("schema_version"), bundle.get("acquisition_mode"), bundle.get("target")) != (1, MODE, TARGET):
        raise ValueError("04摘要接收只接受已登记摘要合同")
    searches = {s["search_id"]: s for s in bundle["searches"]}
    ids, rows = set(), []
    for paper in bundle["articles"]:
        ident = paper["article_id"]
        if ident in ids or paper["journal"] not in SEEDS or not safe_url(paper["source_url"]):
            raise ValueError("摘要身份重复、期刊或来源无效")
        ids.add(ident)
        for item in paper["provenance"]:
            search = searches.get(item["search_id"], {})
            origin = any(record["url"] == item["url"] or item.get("status") == "valid_abstract"
                         and record.get("source_record_id") and
                         record["source_record_id"] == item.get("source_record_id")
                         for record in search.get("records", []))
            if (search.get("provider") != item["provider"] or search.get("journal") != paper["journal"]
                    or search.get("status") != "accessible" or not origin):
                raise ValueError("摘要来历与检索记录不符")
            if item["status"] == "valid_abstract" and (not item.get("raw_abstract")
                    or text_hash(item["raw_abstract"]) != item["raw_hash"]
                    or not item.get("locator") or not item.get("retrieved_at")):
                raise ValueError("原始摘要不一致或缺定位")
        if not any(item["status"] == "valid_abstract" and item["provider"] == paper["source"]
                   and item["search_id"] == paper["search_id"] and item["url"] == paper["source_url"]
                   and item["raw_abstract"] == paper["raw_abstract"] and item["raw_hash"] == paper["raw_hash"]
                   and item["locator"] == paper["locator"] and item["retrieved_at"] == paper["retrieved_at"]
                   for item in paper["provenance"]):
            raise ValueError("选用摘要缺少匹配的原始来源")
        clean = abstract_text(paper["raw_abstract"], paper["title"])
        if (not clean or clean != paper["abstract_text"] or text_hash(clean) != paper["abstract_hash"]
                or text_hash(paper["raw_abstract"]) != paper["raw_hash"]):
            raise ValueError("摘要正文或哈希不一致")
        matched, signals = relevance(paper, bundle["relevance_groups"])
        if matched != paper["relevance_status"] or signals != paper["relevance_matches"]:
            raise ValueError("相关性状态不一致")
        rows.append(dict(paper, evidence_id="E_" + digest([ident, paper["raw_hash"]])[:24],
                         analysis_status="not_analyzed"))
    relevant = sum(row["relevance_status"] == "relevant" for row in rows)
    if bundle["counts"]["unique_valid_abstracts"] != len(rows) or bundle["counts"]["unique_relevant_abstracts"] != relevant:
        raise ValueError("摘要统计与明细不符")
    result = {"schema_version": 1, "acquisition_mode": MODE,
              "collection_id": bundle["collection_id"], "theme": bundle["theme"],
              "acquisition_status": bundle["status"], "source_collection_hash": digest(bundle),
              "counts": bundle["counts"], "target": TARGET, "target_met": relevant >= TARGET,
              "gap": max(0, TARGET - relevant),
              "source_failures": bundle["source_failures"], "conflicts": bundle["conflicts"],
              "analysis_fields": ["research_question", "theories", "concepts", "mechanism",
                                  "population", "methods", "findings", "conclusions", "topic_relation"],
              "rows": rows}
    write(work / "literature_matrix.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, choices=("paper_autonomous_v31",))
    parser.add_argument("--work", required=True, help="项目内新的采集目录")
    actions = parser.add_subparsers(dest="action", required=True)
    run = actions.add_parser("collect")
    run.add_argument("--config", type=Path, default=HERE / "templates/abstract_request.json")
    run.add_argument("--theme")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--session-requests", type=int, help="此轮至多发出多少次请求后保存暂停")
    actions.add_parser("receive")
    args = parser.parse_args(argv)
    collect = load_candidate()
    from collect_common import contained, load
    work = contained(ROOT, args.work)
    if work == ROOT:
        raise ValueError("需要单独工作目录")
    if args.action == "collect":
        spec = load(args.config)
        if args.theme:
            spec["theme"] = args.theme
        status = collect(spec, work, resume=args.resume, session_requests=args.session_requests)
        receive(work)
        summary = {k: status[k] for k in ("status", "counts", "target", "target_met", "attempted_journals", "unattempted_journals", "source_failures", "usage")}
    else:
        matrix = receive(work)
        summary = {k: matrix[k] for k in ("acquisition_status", "counts", "target", "target_met")}
    print(json.dumps(dict(summary, work=str(work)), ensure_ascii=False, indent=2))
    return 0 if summary["target_met"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
