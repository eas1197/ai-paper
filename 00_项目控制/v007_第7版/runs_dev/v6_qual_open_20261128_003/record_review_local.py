import hashlib,json,sys
from pathlib import Path
from staged_topic import evidence_hash,load,write
r=Path(sys.argv[1]); d=r/sys.argv[2]; s=load(r/'staged_topic.json')
ev=[json.loads(line) for line in (d/'events.jsonl').read_text(encoding='utf-8-sig').splitlines() if line]
assert any(x['type']=='turn.completed' for x in ev)
p=load(d/'response.json')
p.update(model='gpt-6.2-sol',invocation_id=next(x['thread_id'] for x in ev if x['type']=='thread.started'),
         evidence_sha256=evidence_hash(r,s,r/'initial/literature_matrix.json',r/'initial/theories.json'),
         events_sha256=hashlib.sha256((d/'events.jsonl').read_bytes()).hexdigest())
w=r/'qualitative/attempt_001/material_receipt.json'
for item in p.get('method_assessment',{}).get('paths',{}).values():
    if item.get('search_attempt')=='attempt_001' and item.get('status') in {'ready','missing'}:
        item['receipt_sha256']=hashlib.sha256(w.read_bytes()).hexdigest()
write(d/'report.json',p)
if p['outcome']=='academic_pass':
    write(r/'conversion_input.json',dict(core_question=p['core_question'],prior_question=load(r/'explanation_exchange.json')['candidate_question'],
          new_question=p['question'],theoretical_concern='正式时间安排转化为实际离岗自主性的条件差异',
          reason_for_conversion='公开亲历文本适合追踪协调、评价和实际离岗过程',
          framework='对照正式规则、任务要求、交接和评价预期，区分自愿留岗与约束留岗',
          literature='两条理论与五条原生初查记录，见 academic_initial/report.json 和 initial 目录',
          context='持续到岗员工的午间或下班离岗实践，通勤变化仅作为适用条件或案例线索'))
