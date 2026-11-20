from pathlib import Path
import json, re, hashlib
from datetime import datetime, timezone, timedelta

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(r'C:\Users\hou\Zotero\storage')
now=datetime.now(timezone(timedelta(hours=8))).isoformat()
records=[]
for p in sorted(SOURCE.rglob('*.pdf')):
    cache=p.parent/'.zotero-ft-cache'
    t=cache.read_text(encoding='utf-8',errors='replace') if cache.exists() else ''
    head=t[:4500]
    compact=re.sub(r'\s+','',head)
    journals=[j for j in ['社会学研究','中国社会科学'] if j in compact]
    record=dict(attachment_key=p.parent.name,pdf_path=str(p),filename=p.name,cache_available=bool(t),candidate_journals=journals,screen_status='candidate_needs_pdf_identity' if journals else 'no_target_journal_in_cache_head',checked_at=now)
    records.append(record)
    if journals:
        dest=ROOT/'screening'/f'{p.parent.name}_cache.txt'
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(t,encoding='utf-8')
(ROOT/'screening'/'inventory.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
for r in records:
    if r['candidate_journals']:
        print(r['attachment_key'],'/'.join(r['candidate_journals']),r['filename'])
print('TOTAL',len(records),'CANDIDATE',sum(bool(r['candidate_journals']) for r in records),'NO_CACHE',sum(not r['cache_available'] for r in records))
