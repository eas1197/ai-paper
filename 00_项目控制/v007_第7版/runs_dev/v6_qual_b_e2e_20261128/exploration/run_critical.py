import json,sys
from pathlib import Path
root=Path.cwd()
sys.path.insert(0,str(root/'00_项目控制/v009_第9版/tools'))
from research_experiment import native_call
base=Path(__file__).resolve().parent
d=base/'critical_01'
d.mkdir()
proposal=json.loads((base/'producer_01/response.json').read_text(encoding='utf-8-sig'))
req={'instruction': '独立反方。逐项核对提案里一手事件资格、独立性、公开可追加性及论证。提出最强近邻和可区分的竞争解释、反例、可证伪条件和候选问题，允许淘汰。需要时打开来源并记录，检索最多12动作。读取 validate_exchange 契约，输出 JSON，research_actor 用给出的真实值，critical_actor 留待运行器以实际thread绑定。记录缺口。不可写盘。', 'root':str(root),'proposal':proposal}
req['research_actor']=next(json.loads(l)['thread_id'] for l in (base/'producer_01/events.jsonl').read_text(encoding='utf-8-sig').splitlines() if json.loads(l)['type']=='thread.started')
(d/'request.json').write_text(json.dumps(req,ensure_ascii=False),encoding='utf-8')
rec=native_call(d,req,allow_search=True,timeout=720)
(d/'invocation.json').write_text(json.dumps(rec),encoding='utf-8')
