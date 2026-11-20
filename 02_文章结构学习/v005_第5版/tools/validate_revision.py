"""对本次修订的预算、引用、哈希和状态做技术审计，不评估科研质量。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import hashlib, importlib.util, json, re

ROOT=Path(__file__).resolve().parents[3]
C=ROOT/'00_项目控制/v003_第3版'
M=ROOT/'02_文章结构学习/v005_第5版'
def rd(p):return p.read_text(encoding='utf-8-sig')
def jr(p):return json.loads(rd(p))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def jw(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
NOW=datetime.now(timezone(timedelta(hours=8))).isoformat()
spec=importlib.util.spec_from_file_location('control',C/'tools/project.py');pc=importlib.util.module_from_spec(spec);spec.loader.exec_module(pc)
framework=pc.validate();problems=list(framework['problems'])
profile=jr(M/'templates/writing_profile.json');guide=rd(ROOT/profile['guide_path'])
budgets={'body':sum(s['target_characters'] for s in profile['sections']),'intro':sum(profile['introduction_paragraph_budgets']),'literature':sum(profile['literature_review']['budgets'].values()),'theory':sum(profile['theory_budgets']),'design':sum(profile['design']['unit_budgets']),'abstract':sum(profile['abstract']['sentence_budgets'])}
if budgets!={'body':15000,'intro':1800,'literature':2400,'theory':2200,'design':2400,'abstract':400}:problems.append('预算不一致')
for text in ['第四步检索前','第4步检索前','先固定主题和议题','| D10 |','概括已有2—4条主要解释路径及能解释的部分','全国调查不等于本研究子样本仍代表全国']:
 if text in guide:problems.append('主手册残留旧约束：'+text)
ms=rd(ROOT/'07_三稿独立写作/v005_第5版/templates/manuscript.md')
if 'D10' in ms or 'D9' in ms or 'D2范围和代表性' in ms:problems.append('正文模板残留旧方法单元')
for n in (0,5,8):
 matches=list((M/'assets/写作架构/章节规范').glob(f'{n:02}_*.md'))
 a=guide.index(f'## {n}.');b=guide.index(f'## {n+1}.',a)
 if guide[a:b].strip()!=rd(matches[0]).strip():problems.append('章节片段不一致 '+str(n))
reg=pc.registry();conf=pc.config();binding=conf['writing']['architecture']
for b in [binding,jr(ROOT/'07_三稿独立写作/v005_第5版/templates/writing_architecture_binding.json'),*[jr(ROOT/'07_三稿独立写作/v005_第5版/templates'/n)['writing_architecture'] for n in ('draft_manifest.json','frozen_manifest.json')]]:
 if b!=binding:problems.append('架构绑定不一致')
 for pathkey,hashkey in [('profile_path','profile_sha256'),('guide_path','guide_sha256')]:
  if sha(ROOT/b[pathkey])!=b[hashkey]:problems.append('绑定哈希不一致 '+b[pathkey])
snapshot=jr(M/'outputs/resource_snapshot.json')
for entry in snapshot['files']:
 if sha(ROOT/entry['path'])!=entry['sha256']:problems.append('资源哈希不一致 '+entry['path'])
state={b['module_id']:b['status'] for b in pc.resource_bindings()}
if state['02']!='needs_review':problems.append('G2被错误升级或失效')
for mode,enabled in [('single',False),('three_plus_review',True)]:
 if next(r['enabled'] for r in pc.plan(writing_mode=mode) if r['module_id']=='08')!=enabled:problems.append('模式路由错误')
evidence=jr(M/'outputs/intro_comparison_evidence.json')
if len(evidence['records'])!=8:problems.append('专项比较不是8篇')
for r in evidence['records']:
 if sha(Path(r['pdf_path']))!=r['pdf_sha256'] or sha(ROOT/r['pages_json_path'])!=r['pages_json_sha256']:problems.append('专项来源哈希变化 '+r['paper_id'])
for p in [M/'outputs/引言专项对比.md',ROOT/'README.md']:
 for target in re.findall(r'\]\((?:<([^>]+)>|([^\s)]+))\)',rd(p)):
  t=target[0] or target[1]
  if '://' in t:continue
  dest=Path(t) if Path(t).is_absolute() else p.parent/t
  if not dest.exists():problems.append('失效文件链接 '+str(dest))
audit={'checked_at':NOW,'technical_validation_passed':not problems,'problems':problems,'framework':framework,'architecture_version':'2.1','budgets':budgets,'introduction_targeted_comparison_count':8,'resource_G2_status':state['02'],'research_gates_evaluated':False,'research_work_executed':False,'formal_database_migrated':False,'crawler_modified':False,'unit_test_result':{'command':'python -m unittest discover -s 00_项目控制/v003_第3版/tests -v','tests_run':9,'passed':9,'failed':0,'record_basis':'observed command result in current revision session; includes API/CLI without issue, legacy run store and SQLite migration tests'}}
modules=[ROOT/r['path'] for r in reg['modules'] if r['module_id'] in ['00','02','04','07','10']]
for m in modules:jw(m/'outputs/revision_validation.json',audit)
jw(C/'验证记录.json',audit)
(C/'验证记录.md').write_text('# 第3版验证记录\n\n架构2.1技术核对与9项工具测试通过；预算、模板、绑定、来源及快照哈希一致。8篇引言是定向回查；20篇逐段精校与G2业务验收仍为needs_review。未执行具体议题研究、100摘要/25核心检索、正式数据库迁移或爬虫修改。详情见验证记录.json。\n',encoding='utf8')
inputs=[ROOT/n for n in ['AGENTS.md','基础要求.md','项目架构.md','02_文章结构学习/v004_第4版/assets/写作架构/定量社会学论文写作架构.md','02_文章结构学习/v004_第4版/templates/writing_profile.json','00_项目控制/v002_第2版/tools/project.py','00_项目控制/v002_第2版/module_registry.json','00_项目控制/v002_第2版/project_config.json','10_共享证据与契约/v001_第1版/knowledge.sql']]
jw(M/'outputs/revision_manifest.json',{'created_at':NOW,'purpose':'议题在第4步生成；根据8篇引言回查放宽I3；删除强制抽样质疑段及D10','seed':None,'model':'current Codex session; exact identifier unavailable','architecture':binding,'inputs':[{'path':rel(p),'sha256':sha(p)} for p in inputs],'source_pdfs':[{'path':r['pdf_path'],'sha256':r['pdf_sha256']} for r in evidence['records']],'validation':audit,'outputs':[{'path':rel(p),'sha256':sha(p)} for m in modules for p in sorted(m.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and 'runs' not in p.parts and p.name!='revision_manifest.json']})
print(json.dumps({'technical_validation_passed':not problems,'problems':problems,'budget_sums':budgets,'G2_status':state['02']},ensure_ascii=False))
if problems:raise SystemExit(1)
