import sys,json,hashlib
from pathlib import Path
import staged_topic as s
r=Path(sys.argv[1]); d=r/sys.argv[2]; state=s.load(r/'staged_topic.json')
events=[json.loads(x) for x in (d/'events.jsonl').read_text(encoding='utf-8-sig').splitlines() if x]
assert any(x['type']=='turn.completed' for x in events)
p=s.load(d/'response.json')
p.update(model='gpt-6.2-sol',invocation_id=next(x['thread_id'] for x in events if x['type']=='thread.started'),evidence_sha256=s.evidence_hash(r,state,r/'initial/literature_matrix.json',r/'initial/theories.json'),receipts={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (d/'prompt.txt',d/'events.jsonl',d/'response.json')})
s.write(d/'report.json',p)
