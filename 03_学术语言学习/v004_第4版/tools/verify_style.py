"""Check source anchors and resource bindings, without certifying research gates."""
import csv
import hashlib
import json
import sys
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
ROOT=BASE.parents[1]
OUT=BASE/'outputs'

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def norm(t):
    return ''.join(c for c in unicodedata.normalize('NFKC',t)
                   if not c.isspace() and unicodedata.category(c) not in ('Co','Cc','Cf'))

def main():
    errors=[]
    def check(ok,label):
        if not ok:
            errors.append(label)
    patterns=read(BASE/'assets/style_patterns.json')
    exercises=read(BASE/'assets/paragraph_exercises.json')
    evidence=[json.loads(s) for s in (OUT/'style_evidence.jsonl').read_text(encoding='utf-8').splitlines()]
    ids={s['id'] for s in patterns}
    check(len(patterns)==len(ids)==15,'style_count')
    check(len(evidence)==40 and len({e['paper_id'] for e in evidence})==20,'same20_40passages')
    check({e['journal'] for e in evidence}=={'中国社会科学','社会学研究'},'journal_coverage')
    pages={}
    for e in evidence:
        path=ROOT/e['pages_file']['path']
        check(sha(path)==e['pages_file']['sha256'],'pages_hash:'+e['evidence_id'])
        if str(path) not in pages:
            pages[str(path)]=read(path)
        text=pages[str(path)][e['pdf_page']-1]['text']
        chunk=text[e['char_start']:e['char_end']]
        check(norm(e['short_anchor']) in norm(chunk),'anchor:'+e['evidence_id'])
        check(len(e['short_anchor'])<=12,'quote_length:'+e['evidence_id'])
        check(hashlib.sha256(text.encode()).hexdigest()==e['page_text_sha256'],'page_text_hash:'+e['evidence_id'])
        check(hashlib.sha256(chunk.encode()).hexdigest()==e['passage_sha256'],'passage_hash:'+e['evidence_id'])
        check(sha(e['pdf_path'])==e['pdf_sha256'],'original_pdf_changed:'+e['paper_id'])
        check(set(e['style_ids'])<=ids,'unknown_style_id')
        check(e['fulltext_read_complete_certified'] is False,'false_read_certification')
    with (OUT/'language_rules.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    for s,r in zip(patterns,rows):
        ev=[e for e in evidence if s['id'] in e['style_ids']]
        check(bool(ev),'no_style_evidence:'+s['id'])
        check(set(r['evidence_ids'].split(';'))=={e['evidence_id'] for e in ev},'support_mapping:'+s['id'])
        check(int(r['frequency'])==len({e['paper_id'] for e in ev}),'support_count:'+s['id'])
        check(s['before']!=s['after'] and all(s[k] for k in ('condition','effect','anti_pattern')),'style_fields:'+s['id'])
    check(len(exercises)==5,'paragraph_exercises')
    for x in exercises:
        check(set(x['style_ids'])<=ids and x['plain']!=x['styled'],'exercise_mapping:'+x['exercise_id'])
    # Warn if new examples accidentally include a long verbatim source phrase.
    # This is a copying check, not a claim to measure stylistic similarity.
    sources=[''.join(norm(p['text']) for p in v) for v in pages.values()]
    for eid,text in [(s['id'],s['after']) for s in patterns]+[(x['exercise_id'],x['styled']) for x in exercises]:
        t=norm(text)
        check(not any(t[i:i+30] in source for i in range(max(0,len(t)-29)) for source in sources),'long_verbatim_overlap:'+eid)
    snapshot=read(OUT/'resource_snapshot.json')
    manifest=read(OUT/'run_manifest.json')
    for group in (snapshot['files'],manifest['input_files'],manifest['output_files'],manifest['script_files']):
        for entry in group:
            p=ROOT/entry['path']
            check(p.is_file() and sha(p)==entry['sha256'],'changed_file:'+entry['path'])
    check(snapshot['status']=='needs_review' and not snapshot['resource_available_for_formal_writing'],'gate_state')
    control=ROOT/'00_项目控制/v003_第3版'
    m=next(m for m in read(control/'module_registry.json')['modules'] if m['module_id']=='03')
    check(m['version']==4 and m['path']==BASE.relative_to(ROOT).as_posix(),'active_module')
    conf=read(control/'project_config.json')
    binding=conf['writing']['language_style']
    check(binding['profile_sha256']==sha(ROOT/binding['profile_path']),'style_profile_binding')
    check(conf['shared_resources']['resource_manifests']['03']==(OUT/'resource_snapshot.json').relative_to(ROOT).as_posix(),'snapshot_binding')
    check(sha(control/'project_config.json')==manifest['config_sha256'],'config_lock')
    report={'technical_status':'passed' if not errors else 'failed','errors':errors,
            'style_focus':['词语选择','句法','句子节奏','衔接','作者声音'],
            'counts':snapshot['counts'],'business_gate_status':'needs_review','G3_passed':False,
            'checked_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'note':'技术核验不是对学习效果的独立评分，也不认证全文精读。'}
    (OUT/'technical_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if not errors else 1

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
