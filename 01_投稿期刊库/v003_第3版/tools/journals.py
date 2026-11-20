"""01: evidence-backed survey, validation and immutable resource publication."""
from __future__ import annotations
import argparse
import shutil
import sqlite3
import sys
from pathlib import Path
from journal_common import (MODULE, ROOT, CONTROL, csv_write, date_ok, hash_value, inside,
                            load, lock, locks_ok, norm_name, now, output, sha, valid_id, write)

# Every field is either an evidence-backed value or an explicit unknown.
FIELDS = ('issn', 'cn', 'directions', 'columns', 'quantitative_fit', 'official_url',
          'submission_channel', 'submission_url', 'submission_email', 'registration_required',
          'undergraduate_policy', 'acceptance_rate', 'accessibility', 'review_duration',
          'ai_policy', 'exclusive_review_policy', 'metrics', 'fees')
REQUIREMENTS = ('length', 'title_abstract_keywords', 'structure', 'reference_style',
                'tables_figures', 'anonymization', 'author_funding', 'attachments',
                'ethics', 'ai_disclosure', 'copyright', 'exclusive_review')
REQUIRED_EDITIONS = {'CSSCI': '2025-2026', 'PKU': '2023'}

def unknown(reason='官方未公开或本轮尚未取得可复核直接证据'):
    return {'value': None, 'evidence_ids': [], 'unknown_reason': reason}

def plan(inputs, config=None):
    conf = dict(config or {})
    if any(conf.get(k, minimum) < minimum for k, minimum in [('cssci_target', 50), ('pku_target', 50), ('distinct_target', 100)]):
        raise ValueError('不能降低50+50、100家不同期刊要求')
    return {'stage_id': '01', 'module_version': 3, 'inputs': inputs, 'config': conf,
            'operations': ['archive_sources', 'field_evidence_check', 'deduplicate', 'quota_check', 'publish_if_passed'],
            'required_editions': REQUIRED_EDITIONS, 'as_of': inputs['as_of']}

def evidence_index(bundle, base):
    index, errors = {}, []
    for e in bundle.get('evidence', []):
        eid = e.get('evidence_id')
        if not eid or eid in index:
            errors.append('证据ID为空或重复: ' + str(eid))
            continue
        index[eid] = e
        for field in ('source_url', 'retrieved_at', 'locator', 'snapshot_path', 'sha256', 'authority', 'kind'):
            if not e.get(field):
                errors.append(f'{eid}: 缺{field}')
        try:
            p = inside(base, e['snapshot_path'])
            if not p.is_file() or sha(p) != e['sha256']:
                errors.append(eid + ': 快照缺失/哈希变化')
            if not date_ok(e['retrieved_at'], bundle['as_of']):
                errors.append(eid + ': 核验时间晚于as_of或无效')
        except (KeyError, OSError, ValueError) as exc:
            errors.append(f'{eid}: {exc}')
    return index, errors

def refs_ok(ids, index, official=False):
    return bool(ids) and all(eid in index and (not official or index[eid].get('authority') in ('publisher', 'index_owner')) for eid in ids)

def validate_bundle(bundle, base):
    base = Path(base).resolve()
    index, errors = evidence_index(bundle, base)
    names, ids, issns, cns = set(), set(), set(), set()
    counts = {'CSSCI': 0, 'PKU': 0}
    rows, eligible = [], []
    for j in bundle.get('journals', []):
        jid, name = j.get('journal_id'), norm_name(j.get('journal_name', ''))
        gaps = []
        if not jid or jid in ids or not name or name in names:
            errors.append('刊名/ID为空或重复: ' + str(jid))
        ids.add(jid); names.add(name)
        if j.get('quota_group') not in counts:
            errors.append(str(jid) + ': quota_group必须是CSSCI或PKU')
        for field in FIELDS:
            value = j.get(field)
            if not isinstance(value, dict) or not {'value', 'evidence_ids', 'unknown_reason'} <= value.keys():
                gaps.append(field + ': 缺字段或未知原因契约')
                continue
            if value['value'] is None:
                if not value['unknown_reason']:
                    gaps.append(field + ': 未知但无原因')
            elif not refs_ok(value['evidence_ids'], index):
                gaps.append(field + ': 缺证据')
        for field, seen in [('issn', issns), ('cn', cns)]:
            value = j.get(field, {}).get('value')
            if value:
                key = str(value).replace(' ', '').upper()
                if key in seen:
                    errors.append(f'{jid}: {field}重复，需合并同刊')
                seen.add(key)
        group = j.get('quota_group')
        current = []
        for category, edition in REQUIRED_EDITIONS.items():
            item = j.get('indexing', {}).get(category, {})
            ok = (item.get('edition') == edition and item.get('status') == 'verified'
                  and (category != 'CSSCI' or item.get('category') == 'source')
                  and refs_ok(item.get('evidence_ids'), index, official=True)
                  and date_ok(item.get('verified_at'), bundle['as_of']))
            if ok:
                current.append(category)
        if group not in current:
            gaps.append(f'{group}: 缺最新已出版目录{REQUIRED_EDITIONS.get(group)}的官方逐刊收录证据')
        else:
            counts[group] += 1
        guideline = j.get('guideline', {})
        if not refs_ok(guideline.get('evidence_ids'), index, official=True) or not guideline.get('full_snapshot'):
            gaps.append('稿约: 缺官方全文快照')
        for eid in guideline.get('evidence_ids', []):
            if eid in index and index[eid].get('kind') != 'full_guideline':
                gaps.append('稿约: 检索摘录/部分页面不能冒充全文')
        for field in REQUIREMENTS:
            cell = j.get('requirements', {}).get(field)
            if not isinstance(cell, dict) or 'value' not in cell or (cell['value'] is None and not cell.get('unknown_reason')):
                gaps.append('稿约清单缺: ' + field)
            elif cell['value'] is not None and not refs_ok(cell.get('evidence_ids'), index, official=True):
                gaps.append('稿约清单缺官方证据: ' + field)
        for field in ('official_url', 'submission_channel', 'submission_url', 'quantitative_fit'):
            cell = j.get(field, {})
            if cell.get('value') is None or not refs_ok(cell.get('evidence_ids'), index, official=field != 'quantitative_fit'):
                gaps.append(field + ': 未核验，不能进入可投池')
        # Identity must be resolved before the library is certified.
        if not j.get('issn', {}).get('value') or not j.get('cn', {}).get('value'):
            gaps.append('身份: 缺ISSN/CN')
        if j.get('submission_channel', {}).get('value') == 'email' and (
            not j.get('submission_email', {}).get('value') or
            not refs_ok(j.get('submission_email', {}).get('evidence_ids'), index, official=True)):
            gaps.append('邮件渠道缺官方收稿邮箱证据')
        rows.append({'journal_id': jid, 'journal_name': j.get('journal_name'), 'quota_group': group,
                     'eligible': not gaps, 'gaps': gaps, 'verified_index_categories': current})
        if not gaps:
            eligible.append(jid)
    target = {'CSSCI': 50, 'PKU': 50}
    for group, n in target.items():
        if counts[group] < n:
            errors.append(f'{group}当前资质核验数量{counts[group]}，目标{n}')
    if len(ids) < 100:
        errors.append(f'不同期刊数量{len(ids)}，目标100')
    if any(r['gaps'] for r in rows):
        errors.append('逐刊仍有未满足的硬门槛，详见journal_checks')
    return {'stage_id': '01', 'status': 'passed' if not errors else 'needs_review',
            'as_of': bundle['as_of'], 'required_editions': REQUIRED_EDITIONS,
            'surveyed_count': len(bundle.get('journals', [])), 'distinct_count': len(names),
            'verified_quota_counts': counts, 'eligible_ids': eligible, 'errors': errors, 'journal_checks': rows,
            'business_gate': 'G1', 'unknown_values_are_not_verified': True}

def execute(planned, context=None):
    source = Path(planned['inputs']['bundle']).resolve()
    base = source.parent
    bundle = load(source)
    if bundle['as_of'] != planned['as_of']:
        raise ValueError('计划与输入核验日期不同')
    target = output(planned['inputs']['output'])
    report = validate_bundle(bundle, base)
    target.mkdir(parents=True)
    # Rebase and copy evidence so snapshots remain reusable without original folders.
    for e in bundle.get('evidence', []):
        p = inside(base, e['snapshot_path'])
        new = Path('sources') / (e['evidence_id'] + p.suffix)
        if p.is_file():
            (target / new).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target / new)
        e['snapshot_path'] = new.as_posix()
    write(target / 'journal_profiles.json', bundle)
    write(target / 'gate_report.json', report)
    write(target / 'plan.json', planned)
    rows = []
    checklists = []
    for j, check in zip(bundle['journals'], report['journal_checks']):
        rows.append({**{k: j.get(k) for k in ('journal_id', 'journal_name', 'quota_group')},
                     **{k: j.get(k, {}).get('value') for k in FIELDS},
                     'indexing': j.get('indexing'), 'eligible': check['eligible'], 'gaps': check['gaps'], 'as_of': bundle['as_of']})
        checklists += [{'journal_id': j['journal_id'], 'requirement': k, **v} for k, v in j.get('requirements', {}).items()]
    csv_write(target / 'journals.csv', rows, ['journal_id', 'journal_name', 'quota_group', *FIELDS, 'indexing', 'eligible', 'gaps', 'as_of'])
    csv_write(target / 'guidelines_checklist.csv', checklists, ['journal_id', 'requirement', 'value', 'evidence_ids', 'unknown_reason'])
    with sqlite3.connect(target / 'journals.sqlite') as db:
        db.executescript('CREATE TABLE journals(journal_id TEXT PRIMARY KEY,name TEXT UNIQUE,quota_group TEXT,profile_json TEXT); CREATE TABLE evidence(evidence_id TEXT PRIMARY KEY,snapshot_path TEXT,sha256 TEXT);')
        import json
        db.executemany('INSERT INTO journals VALUES(?,?,?,?)', [(j['journal_id'], j['journal_name'], j['quota_group'], json.dumps(j, ensure_ascii=False)) for j in bundle['journals']])
        db.executemany('INSERT INTO evidence VALUES(?,?,?)', [(e['evidence_id'], e['snapshot_path'], e['sha256']) for e in bundle['evidence']])
    files = [lock(p) for p in sorted(target.rglob('*')) if p.is_file()]
    code = [lock(p) for p in sorted((MODULE / 'tools').glob('*.py'))]
    write(target / 'resource_snapshot.json', {'schema_version': 2, 'module_id': '01', 'module_version': 3,
          'resource_snapshot_id': target.name, 'created_at': now(), 'status': report['status'], 'as_of': bundle['as_of'],
          'business_gate_report': str((target / 'gate_report.json').relative_to(ROOT)).replace('\\', '/'),
          'input_files': [lock(source)] + [lock(ROOT / n) for n in ('AGENTS.md', '基础要求.md', '项目架构.md')],
          'code_files': code, 'config_sha256': hash_value(planned['config']), 'seed': None,
          'environment': {'python': sys.version}, 'files': files})
    return {'path': str(target), 'status': report['status'], 'surveyed_count': report['surveyed_count'], 'errors': report['errors']}

def validate(artifacts, evidence=None):
    work = Path(artifacts).resolve()
    snapshot = load(work / 'resource_snapshot.json')
    report = validate_bundle(load(work / 'journal_profiles.json'), work)
    problems = locks_ok(snapshot['files'] + snapshot.get('input_files', []) + snapshot.get('code_files', []))
    report['integrity_errors'] = problems
    if problems:
        report['status'] = 'stale'
    return report

def export(artifacts, target_profile=None):
    work = Path(artifacts).resolve()
    report = validate(work)
    if report['status'] != 'passed':
        raise ValueError('G1未通过；禁止发布可投资源')
    return {'snapshot': str(work / 'resource_snapshot.json'), 'sha256': sha(work / 'resource_snapshot.json')}

def main():
    sys.stdout.reconfigure(encoding='utf-8'); sys.stderr.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser(description=__doc__)
    s = p.add_subparsers(dest='command', required=True)
    b = s.add_parser('build'); b.add_argument('--input', required=True); b.add_argument('--output', required=True)
    for name in ('validate', 'export'):
        v = s.add_parser(name); v.add_argument('--resource', required=True)
    a = p.parse_args()
    try:
        if a.command == 'build':
            data = execute(plan({'bundle': a.input, 'output': a.output, 'as_of': load(a.input)['as_of']}))
        else:
            data = (validate if a.command == 'validate' else export)(a.resource)
        import json
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data.get('status', 'passed') == 'passed' else 1
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr); return 2

if __name__ == '__main__':
    raise SystemExit(main())
