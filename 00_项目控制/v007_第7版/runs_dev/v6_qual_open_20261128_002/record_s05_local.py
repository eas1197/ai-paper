import hashlib,json,sys
from pathlib import Path
from staged_topic import evidence_hash,load,write
r=Path(sys.argv[1]); d=r/sys.argv[2]; state=load(r/'staged_topic.json')
events=[json.loads(x) for x in (d/'review_events.jsonl').read_text(encoding='utf-8-sig').splitlines() if x]
assert state['status']=='S05' and any(x['type']=='turn.completed' for x in events)
p=load(d/'review_response.json')
p.update(model='gpt-6.2-sol',invocation_id=next(x['thread_id'] for x in events if x['type']=='thread.started'),evidence_sha256=evidence_hash(r,state,r/'initial/literature_matrix.json',r/'initial/theories.json'),supplement_sha256={str(f.relative_to(r)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in d.iterdir() if f.suffix in ('.json','.jsonl','.txt') and f.name!='review_report.json'})
write(d/'review_report.json',p)
