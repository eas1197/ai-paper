"""Independent provenance/content checks. A technical pass NEVER passes G3."""
import csv
import hashlib
import json
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
OUT = BASE / 'outputs/资源建设_attempt001'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text)
                   if not c.isspace() and unicodedata.category(c) not in ('Co','Cc','Cf'))

def rows(path):
    return list(csv.DictReader(Path(path).open(encoding='utf-8-sig', newline='')))

def validate():
    errors = []
    def check(value, label):
        if not value:
            errors.append(label)
    corpus = read(OUT / 'corpus_input_lock.json')
    evidence = [json.loads(line) for line in (OUT / 'language_evidence.jsonl').read_text(encoding='utf-8').splitlines()]
    rules = rows(OUT / 'language_rules.csv')
    rule_ids = {r['rule_id'] for r in rules}
    evidence_ids = {e['evidence_id'] for e in evidence}
    pids = {p['paper_id'] for p in corpus}
    check(len(corpus) == len(pids) == 20, 'same20_unique')
    check({p['journal'] for p in corpus} == {'中国社会科学','社会学研究'}, 'both_journals')
    check(len(evidence_ids) == len(evidence), 'unique_evidence_ids')
    check({e['paper_id'] for e in evidence} == pids, 'all20_have_reviewed_evidence')
    check(len(rule_ids) == len(rules) == 27, '27_unique_rules')
    pagecache = {}
    for p in corpus:
        check(sha(p['pdf_path']) == p['pdf_sha256'], f"original_pdf_changed:{p['paper_id']}")
        check(sha(ROOT / p['pages_path']) == p['pages_sha256'], f"page_file_changed:{p['paper_id']}")
        pagecache[p['paper_id']] = read(ROOT / p['pages_path'])
    for e in evidence:
        loc = e['locator']
        text = pagecache[e['paper_id']][loc['pdf_page']-1]['text']
        start, end = loc['page_text_char_start'], loc['page_text_char_end']
        check(0 <= start < end <= len(text), 'bounds:' + e['evidence_id'])
        passage = text[start:end]
        check(norm(e['short_quote']) in norm(passage), 'anchor:' + e['evidence_id'])
        check(sha(ROOT / e['source_files']['pages_path']) == e['source_files']['pages_sha256'], 'evidence_source_hash:' + e['evidence_id'])
        check(hashlib.sha256(text.encode()).hexdigest() == loc['page_text_sha256'], 'page_hash:' + e['evidence_id'])
        check(hashlib.sha256(passage.encode()).hexdigest() == loc['passage_sha256'], 'passage_hash:' + e['evidence_id'])
        check(set(e['rule_ids']) <= rule_ids, 'unknown_rule:' + e['evidence_id'])
        check(len(e['short_quote']) <= 12 and e['evidence_type'] == 'direct', 'quote_or_type:' + e['evidence_id'])
        check(e['fulltext_read_certification'] == 'not_certified_complete', 'false_fulltext_certification')
    # A short quote cap per source additionally prevents an accumulation of
    # long verbatim snippets across multiple selected language actions.
    for pid in pids:
        check(sum(len(e['short_quote']) for e in evidence if e['paper_id'] == pid) <= 100,
              'aggregate_quote_cap:' + pid)
    for r in rules:
        ids = set(r['evidence_ids'].split(';'))
        check(bool(ids) and ids <= evidence_ids, 'broken_rule_evidence:' + r['rule_id'])
        ev = [e for e in evidence if r['rule_id'] in e['rule_ids'] and e['relationship'] != 'caution']
        check(ids == {e['evidence_id'] for e in ev}, 'support_relation:' + r['rule_id'])
        check(int(r['frequency']) == len({e['paper_id'] for e in ev}), 'frequency:' + r['rule_id'])
        for field in ('original_example','counterexample','revision','preconditions','syntax_analysis','project_guardrail'):
            check(bool(r[field]), f"missing_{field}:{r['rule_id']}")
        # Source phrase overlap is only a copying warning check, never proof of
        # originality. All examples were separately authored and read by agent.
        ex = norm(r['original_example'])
        for p in corpus:
            source = ''.join(norm(pg['text']) for pg in pagecache[p['paper_id']])
            check(not any(ex[i:i+24] in source for i in range(max(0, len(ex)-23))),
                  f"long_source_overlap:{r['rule_id']}:{p['paper_id']}")
    audit = rows(OUT / 'language_audit.csv')
    check(len(audit) == 54, '54_synthetic_audit_rows')
    check(all(a['draft_id'] == 'LANGUAGE_DEMO_NOT_RESEARCH_DRAFT' and
              a['evidence_strength'] == 'synthetic_example_not_empirical' for a in audit), 'demo_not_real_draft')
    gate = read(OUT / 'gate_report.json')
    snapshot = read(BASE / 'outputs/resource_snapshot.json')
    check(gate['status'] == snapshot['status'] == 'needs_review', 'false_business_pass')
    check(gate['passed'] is False and snapshot['resource_available_for_formal_writing'] is False, 'release_guard')
    check(read(ROOT / gate['upstream']['path'])['status'] != 'passed', 'upstream_changed_re_review_required')
    for name, expected in [('selected_evidence',len(evidence)), ('rules',len(rules)), ('corpus_pdfs',len(corpus))]:
        check(gate['counts'][name] == expected == snapshot['counts'][name], 'count_mismatch:' + name)
    for group in (snapshot['files'], read(OUT / 'run_manifest.json')['input_files'],
                  read(OUT / 'run_manifest.json')['output_files'],
                  read(OUT / 'run_manifest.json')['code_files'],
                  read(OUT / 'run_manifest.json')['semantic_input_files']):
        for f in group:
            check((ROOT / f['path']).is_file() and sha(ROOT / f['path']) == f['sha256'], 'locked_file_changed:' + f['path'])
    manifest = read(OUT / 'run_manifest.json')
    check(sha(BASE / 'config.json') == manifest['config_sha256'], 'config_changed')
    active = read(ROOT / '00_项目控制/v003_第3版/module_registry.json')
    active03 = next(m for m in active['modules'] if m['module_id'] == '03')
    check(active03['version'] == 3 and active03['path'] == BASE.relative_to(ROOT).as_posix(), 'registry_not_active')
    conf = read(ROOT / '00_项目控制/v003_第3版/project_config.json')
    check(conf['shared_resources']['resource_manifests']['03'] == (BASE / 'outputs/resource_snapshot.json').relative_to(ROOT).as_posix(), 'config_not_active')
    report = {'technical_status': 'passed' if not errors else 'failed',
              'business_gate_status': gate['status'], 'G3_passed': False,
              'errors': errors, 'counts': gate['counts'],
              'checked_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
              'note': 'Anchor/hash/schema/count validation is not research-quality acceptance.'}
    (OUT / 'technical_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    report = validate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report['technical_status'] == 'passed' else 1)
