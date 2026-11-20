"""按用户的议题—文献—现实—问题逻辑建立新版规范与契约，保留旧版。"""
from pathlib import Path
import csv, hashlib, importlib.util, json, re, shutil
from datetime import datetime, timezone, timedelta

ROOT=Path(__file__).resolve().parents[3]
M02=ROOT/'02_文章结构学习/v004_第4版'
M07=ROOT/'07_三稿独立写作/v004_第4版'
M04=ROOT/'04_议题文献与现实/v002_第2版'
M05=ROOT/'05_研究问题与假设/v002_第2版'
CONTROL=ROOT/'00_项目控制/v002_第2版'
OLD02=ROOT/'02_文章结构学习/v003_第3版'
OLD07=ROOT/'07_三稿独立写作/v003_第3版'
CORPUS=ROOT/'02_文章结构学习/v002_第2版/outputs/资源建设_20261114_attempt002'
NOW=datetime.now(timezone(timedelta(hours=8))).isoformat()
def rd(p):return p.read_text(encoding='utf8')
def jrd(p):return json.loads(rd(p))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()
def wr(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf8')
def jw(p,o):wr(p,json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def table(p,fields):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:csv.writer(f).writerow(fields)

versions=[(M02,OLD02,'02',4),(M07,OLD07,'07',4),
          (M04,ROOT/'04_议题文献与现实/v001_第1版','04',2),
          (M05,ROOT/'05_研究问题与假设/v001_第1版','05',2)]
for new,old,mid,ver in versions:
    for folder in ('templates','outputs'):(new/folder).mkdir(parents=True,exist_ok=True)
    for p in (old/'templates').iterdir():
        if p.is_file() and not (new/'templates'/p.name).exists():shutil.copy2(p,new/'templates'/p.name)

guide=M02/'assets/写作架构/定量社会学论文写作架构.md'
oldguide=OLD02/'assets/写作架构/定量社会学论文写作架构.md'
s=rd(oldguide)
s=s.replace('架构版本：1.0；','架构版本：2.0；')
s=s.replace('保留热点切入、理论切入和测量切入三种入口。','以现实与理论张力、同层级理论待解释处为两个问题触发起点，连接四种理论推进方式。')
s=s.replace('本文件是根据用户本次要求制定的**项目写作规范**。','本文件是根据用户最新修订要求制定的**项目写作规范**。2—4条解释路径、关系类型和研究流程是本项目规范，不是对两刊总体的频率判断。')
start=s.index('## 1.');s=s[:start]+rd(M02/'assets/写作架构/章节规范/00_研究怎样产生.md')+'\n\n'+s[start:]
for n,name in [(4,'04_摘要.md'),(5,'05_引言.md'),(6,'06_文献回顾.md'),(7,'07_理论与假设.md')]:
    a=s.index(f'## {n}.');b=s.index(f'## {n+1}.',a)
    s=s[:a]+rd(M02/'assets/写作架构/章节规范'/name)+'\n\n'+s[b:]
s=s.replace('梳理已有答案；推导自己的解释；','梳理2—4条主要解释路径及其联系；定位理论待推进处并推导自己的解释；')
s=s.replace('每个重要假设在理论节有推导，','问题在完成议题文献与现实材料对照后形成。每个重要假设在理论节有推导，')
s=s.replace('## 9. 第五部分：实证结果，4000字','## 9. 第五部分：实证结果，4000字\n\n结果组织与主推进一致：G1检验对现实张力的解释；G2检验新增因素或过程；G3检验条件和适用范围；G4比较原关系与修正关系。由问题决定主要估计与必要延伸，不按路径数量机械生成同样数量的模型。')
s=s.replace('说明是支持、修正、区分还是限定，给出修改后的命题','说明补充了哪一空白、整合了哪段关系，或怎样修正/限定命题')
s=s.replace('指明支持哪一解释、哪一部分仍不确定','指明新增环节或原命题得到什么证据，哪一部分仍不确定')
s=s.replace('热点稿解释现实困境；理论稿说明制度边界','按实际主推进回扣现实问题与制度意义，必要时说明边界')
a=s.index('### 10.3');b=s.index('### 10.4',a)
s=s[:a]+'''### 10.3 按实际触发起点和推进方式回收研究

现实张力起点的开头：“围绕【情境】中【旧解释不能充分覆盖的问题】，本文利用【资料与设计】考察了【具体关系】。结果显示【主要回答】，为理解【现实张力】补充了【解释环节】。”

理论待解释处起点的开头：“既有研究已从【主要路径】解释【议题】，本文进一步考察其中【尚待核实的关系或环节】。基于【资料与设计】，研究发现【主要回答】，从而补充了【具体命题】。”

第四段讨论按主推进选择：G1说明现实张力如何被重新解释；G2说明哪个未覆盖环节获得证据；G3说明原条件如何扩缩；G4说明原关系的方向、形式或过程如何被修正。若数据未能支持预期，明确报告未得到支持及其不确定性，不能宣称已经填补空白。

分类或测量贡献回到它怎样改变对实质关系的认识。上述均为原创占位句式，不是已完成研究的结论。

'''+s[b:]
s=s.replace('讨论理论贡献时，使用“原有命题—本文证据—需要怎样修改—修改的范围”四步。','讨论理论贡献时，使用“原有认识—本文证据—新增/整合/调整/修正的具体内容—适用范围”四步。')
s=s.replace('例：“既有解释将【条件】视为常量；本文发现【有证据的条件差别】。因此，对【关系】的理解需要加入【具体边界】，而非只主张【笼统理论失效】。”',
            '例如，补充空白时说明“既有研究已揭示【原关系】，本文进一步提供了【新增环节】的证据”；调整条件时再说明“原命题在【条件】下需要重新界定”。')
s=s.replace('| 理论引言开头 | 提出命题 | “关于【关系】，既有解释主要存在【明确分歧】。” | 确有分歧，正文能准确重构 |',
'''| 理论待解释处开头 | 定位已有认识与未覆盖环节 | “既有研究已从【主要路径】解释【关系】，但对【具体环节】仍缺少充分说明。” | 核心全文核查后使用，不预认存在理论分歧 |
| 政策依据处 | 说明国家性意义 | “【国家政策】提出【直接相关目标】，理解其实现条件需要认识【具体关系】。” | 原文、日期、范围和相关性均核实 |
| 路径联系处 | 说明解释怎样连接 | “在解释【前一环节】的基础上，相关研究进一步关注【后一环节】。” | 确为递进关系时使用；其他联系据实改写 |''')
s=s.replace('| 文献分类段首 | 建立解释线索 | “一种解释强调【机制A】；另一种解释则关注【机制B】。” | 以解释分类，不能只按国家或年代罗列 |',
             '| 文献路径段首 | 建立解释线索 | “围绕【关系】，这一路径强调【因素/机制/条件】。” | 默认2—4条，联系按证据组织，不能只按国家或年代罗列 |')
s=s.replace('| 文献节末 | 引入本文 | “要回答这一问题，需要进一步区分【关键差别】。” | 关键差别应在理论与设计中兑现 |',
             '| 文献节末 | 定位本文推进 | “在已有认识基础上，仍需解释【具体关系或环节】。” | 可为补充空白、条件扩缩或关系修正，后文须兑现 |')
s=s.replace('| 理论竞争切入 | A/B前提、可区分预期、证据支持与未区分部分 | 无关新闻与政策开场 | 可从引言减200、文献减200，理论加400 |',
             '| 理论待解释处切入 | 同层级缺口、与2—4条路径的联系、补充或修正的理由 | 重复背景和并不存在的理论竞争 | 可从引言减200、文献减200，理论加400；相关国家政策依据保留 |')
s=s.replace('至少填写：中心问题一句话；热点/理论/测量入口；对象与制度范围；主要结果变量；核心解释；竞争解释；',
             '先填写主题、议题、约100摘要图谱、25核心全文状态、2—4条解释路径与相互关系、国家政策与现实情境。再填写：中心问题一句话；R/T触发起点与G1—G4主推进；对象与制度范围；主要结果变量；核心解释；必要时的替代解释；')
s=s.replace('- 文献是否按照解释组织，缺口是否有限且同层级？',
             '- 文献是否归纳2—4条主要路径并说明联系，实际空白是否由全文核查、是否同层级或有明确桥接？')
s=s.replace('支持测量切入分支，不证明换指标必然构成贡献','支持分类与测量手段，不另立第三种问题触发起点，也不证明换指标必然构成贡献')
wr(guide,s)

# 更新02/07模块说明，保留原有全文、冻结证据和模式门槛。
d=rd(OLD02/'模块说明.md').replace('第3版','第4版').replace('架构1.0','架构2.0').replace('候选资源第2版','候选资源第3版')
d=d.replace('引言提供热点、理论和分类测量分支；','引言采用R现实张力/T理论待解释处两个起点，连接G1—G4推进；文献回顾默认2—4条非固定并列路径；')
d+='\n## 第4版研究逻辑衔接\n\n新增第0节，明确主题→议题→100摘要图谱→25核心全文→政策现实→问题假设。第四、第五步契约同步升级，文献不再默认A/B竞争，空白、条件和关系修正分别定位。国家政策优先进入引言开头；分类与测量作为解题手段。具体采集与研究尚未执行。\n'
wr(M02/'模块说明.md',d)
d=rd(OLD07/'模块说明.md').replace('第3版','第4版').replace('架构1.0','架构2.0')
d=d.replace('引言在热点、理论、分类测量入口中选择；到研究问题处汇合。',
            '先接收04的议题图谱、25核心全文对话及政策现实材料，再接收05的问题假设卡。引言按R现实张力/T理论待解释处起点选择，连接G1—G4推进；文献回顾归纳2—4条路径，明确并列、互补、递进、嵌套或竞争等实际联系。')
d+='\n## 研究逻辑的写作兑现\n\n写作计划先登记主题、议题、具体问题，100摘要/25核心状态，主要路径关系和全文对话。理论段不机械设置竞争解释；结论按实际补充、整合、条件调整或关系修正回扣。政策依据优先在开头交代，新闻必须与学术证据分工。未形成合格上游证据时只能交模板。\n'
wr(M07/'模块说明.md',d)

# 机器配置与清单：不降低旧数量和科研门槛。
profile=jrd(OLD02/'templates/writing_profile.json')
profile.update(profile_version='2.0',module_version=4,created_at=NOW,guide_path=rel(guide),guide_sha256=sha(guide))
profile['introduction_routes']=['reality_theory_tension','theory_unexplained_gap']
profile['theoretical_advances']=['G1_reality_explanation','G2_same_level_gap','G3_scope_adjustment','G4_relation_revision']
profile['literature_review']=dict(preferred_path_count=[2,4],path_count_is_flexible_with_reason=True,
    default_competition=False,relations=['parallel','complementary','sequential','nested','shared_condition','competitive','revision'],
    budgets=dict(concepts=240,paths_total=1440,path_connections=240,theory_opportunity=300,paper_position=180))
profile['theory_budgets']=[300,500,650,500,250]
profile['introduction_paragraph_budgets']=[200,240,260,300,200,340,260]
profile['research_inputs']=dict(theme_issue_question_distinct=True,abstract_target=100,core_fulltext_target=25,
    abstract_and_fulltext_reading_separate=True,policy_basis='prefer_directly_relevant_national_primary_source_at_opening',news_lookback_years=3,
    same_level_dimensions=['abstraction','unit','relation_role','explanatory_dimension','timing'],core_fulltext_dialogue_required=True)
for row in profile['sections']:
    if row['id'] in ('L','T'):row['default_paragraph_slots']=None
jw(M02/'templates/writing_profile.json',profile)
binding=dict(profile_id=profile['profile_id'],profile_version='2.0',profile_path=rel(M02/'templates/writing_profile.json'),profile_sha256=sha(M02/'templates/writing_profile.json'),guide_path=rel(guide),guide_sha256=sha(guide))
shutil.copy2(M02/'templates/写作计划.md',M07/'templates/写作计划.md')
jw(M07/'templates/writing_architecture_binding.json',binding)
for name in ('draft_manifest.json','frozen_manifest.json'):
    data=jrd(M07/'templates'/name);data['writing_architecture']=binding
    data['research_logic_inputs']=['theme_issue_question','abstract_relation_scope_map','core25_fulltext_dialogue','path_synthesis','policy_reality_context','gap_same_level_review']
    if name=='frozen_manifest.json':data['required_contents']=list(dict.fromkeys(data['required_contents']+data['research_logic_inputs']))
    jw(M07/'templates'/name,data)

ms=rd(OLD07/'templates/manuscript.md').replace('架构1.0','架构2.0')
ms=ms.replace('【I1—I4按热点/理论/测量入口展开；I5中心问题；I6资料设计及主要回答预告；I7具体贡献。】',
              '【I1国家政策/制度意义200字；I2现实情境240；I3主要路径260；I4实际理论待推进处300；I5中心问题200；I6设计及主要回答340；I7具体贡献260。R/T两个起点的重点按架构选择。】')
a=ms.index('## 二、');b=ms.index('## 四、',a)
ms=ms[:a]+'''## 二、文献回顾（目标2400字）

### （一）概念与关系范围（240字）

【界定核心关系、单位与角色。】

### （二）主要解释路径及证据（合计1440字，默认2—4条）

【每条：命题→逻辑链→代表全文证据→适用范围→与下一条连接。标题按实际内容命名，篇幅按重要性分配。】

### （三）路径联系、理论待推进处与本文位置（240＋300＋180字）

【关系按并列/互补/递进/嵌套/共同条件/竞争/修正等实际材料写。定位空白、解释不足、条件扩缩或关系修正，给出全文证据与同层级检查。】

## 三、理论分析与研究假设（目标2200字）

【T0理论起点与概念对齐300；T1推进理由500；T2核心关系推导650；T3必要进一步预期500；T4汇总与检验接口250。】

【原命题→本文保留/推进→机制理由→预期与反证。假设数量由问题决定，不机械安排竞争、中介或调节。】

'''+ms[b:]
ms=ms.replace('【C4约400字，对话具体理论命题，说明如何支持/修正/限定。】',
              '【C4约400字，对话具体原命题，说明如何补充空白、整合关系、调整条件或修正方向/形式；未支持的预期如实说明。】')
wr(M07/'templates/manuscript.md',ms)

# 第四/第五步的新契约均为待填模板，不伪装完成文献与假设。
table(M04/'templates/views.csv',['view_id','name','central_proposition','logical_chain','concept_roles','relation_ids','core_paper_ids','scope','unexplained_part','fulltext_review_status','evidence_ids'])
table(M04/'templates/view_links.csv',['link_id','from_view','to_view','relation_type','relationship_explanation','evidence_ids','review_status'])
jw(M04/'templates/topic_scope.json',dict(template=True,theme=None,issue=None,question_candidates=[],search_scope=None,journal_aliases_review_status='pending',status='not_selected'))
jw(M04/'templates/acquisition_request.json',dict(template=True,status='planned',theme=None,issue=None,abstract_target=100,core_fulltext_target=25,
    source_labels=['社会','社会学研究','中国社会科学','管理世界','经济学研究','探索与证明'],
    proposed_aliases={'经济学研究':'经济研究','探索与证明':'探索与争鸣'},alias_confirmation='required_before_formal_search',
    reading_phases=['archive_available_sources','read_abstracts','select_and_read_core25'],
    legacy_reference_root='E:/文章/cnki爬虫',legacy_access='read_only',destination='current_run/literature',
    adapter_implementation='not_implemented_in_this_revision'))
table(M05/'templates/same_level_review.csv',['candidate_id','baseline_concept','proposed_concept','abstraction','analysis_unit','relation_role','explanatory_dimension','timing','bridge_if_needed','overlap_search_evidence','decision','reason'])
table(M05/'templates/literature_dialogue.csv',['candidate_id','hypothesis_id','baseline_paper_id','original_proposition','original_scope','fulltext_locator','retained_part','proposed_change','advance_type','mechanism_reason','expected_pattern','falsification','evidence_ids','status'])

with (OLD07/'templates/architecture_self_check.csv').open(encoding='utf-8-sig',newline='') as f:checks=list(csv.DictReader(f))
for check in checks:
    if check['check_id']=='A03':check['criterion']='R/T两个触发起点与G1—G4实际推进匹配，分类测量按解题作用安排'
extra=[('A13','路径图谱','2—4条主要路径及其联系由图谱/全文核实，不默认并列竞争'),
       ('A14','问题来源','R/T起点与G1—G4推进分别登记'),('A15','同层级','缺口检查抽象层、单位、角色、维度和时间，必要时说明桥接'),
       ('A16','核心对话','25篇核心全文各有对话和拟引用位置，100摘要与全文状态分开'),
       ('A17','现实政策','开头优先有相关国家政策，现实情境和证据时间匹配')]
checks.extend(dict(check_id=i,category=c,criterion=k,status='pending',evidence_or_note='') for i,c,k in extra)
with (M07/'templates/architecture_self_check.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(checks[0]));w.writeheader();w.writerows(checks)

for new,old,mid,ver in versions:
    mf=jrd(old/'manifest.json');mf.update(version=ver,version_label=f'第{ver}版')
    if mid in ('02','07'):mf['writing_architecture']=binding
    if mid=='02':mf['folders']=['assets/corpus','assets/写作架构','templates','outputs','tools']
    if mid=='04':mf['expected_artifacts']+=['views.csv','view_links.csv','topic_scope.json','acquisition_request.json']
    if mid=='05':mf['expected_artifacts']+=['研究问题卡.md','same_level_review.csv','literature_dialogue.csv']
    for folder in mf['folders']:(new/folder).mkdir(parents=True,exist_ok=True)
    jw(new/'manifest.json',mf)
    for folder in ('templates','outputs'):
        wr(new/folder/'README.md',f'# 第{ver}版{folder}\n\n本轮更新研究逻辑与写作规范，模板未填不等于已完成100摘要、25全文、假设或论文。具体规则见本版模块说明。旧版与旧运行保留，当前版本以控制注册表为准。\n')
    wr(new/'CHANGELOG.md',f'''# 第{ver}版变更记录

日期：2026-11-14；依据：用户修正解释路径数量、联系类型、理论空白与研究流程。

- 新增：主题—议题—问题区分；约100摘要关系图谱、25核心全文对话、政策与近年情境衔接；两个触发起点、四种推进；同层级检查。
- 修改：文献回顾按2—4条实际路径组织，不固定A/B竞争；引言、理论、结论与写作计划同步调整。
- 兼容：保留既有标准字段和数量/证据门槛，新增契约与清单字段；旧版本不覆盖、旧运行不迁移；single默认，09关闭。
- 验收：见outputs/revision_validation.json；属于规范、配置和框架核对，不是科研业务验收。原爬虫未改，实际检索与研究未执行。
''')
    history=[p for p in new.parent.iterdir() if p.is_dir() and re.fullmatch(r'v\d{3}_第\d+版',p.name)]
    lines=['# 版本索引',f'\n当前版本：`{new.name}`。','']
    for p in sorted(history,reverse=True):lines.append(f'- [{p.name}]({p.name}/模块说明.md)：'+('研究逻辑与架构2.0衔接。' if p==new else '历史保留。'))
    wr(new.parent/'版本索引.md','\n'.join(lines)+'\n')

wr(M02/'assets/corpus/README.md','# 语料引用\n\n20篇章节/摘要编码仍在第2版attempt002；逐段精校未完成，本版不重跑或重新认证。\n')
for label in ('A稿','B稿','C稿'):wr(M07/label/'README.md',f'# {label}\n\n模块占位；single仅A，B/C仅three_plus_review。\n')
jw(M02/'outputs/resource_snapshot.json',dict(schema_version=1,module_id='02',module_version=4,resource_version=3,
    resource_snapshot_id='structure_candidate_r3_architecture_2_0',lifecycle='build_once_reuse_many',status='needs_review',
    files=[dict(path=rel(p),sha256=sha(p)) for p in [guide,M02/'templates/writing_profile.json',M02/'templates/写作计划.md',*sorted((M02/'assets/写作架构/章节规范').glob('*.md')),CORPUS/'corpus20.csv',CORPUS/'structure_moves.csv',CORPUS/'abstract_sentences.csv',CORPUS/'structure_handbook.md']],
    business_gate_report=rel(CORPUS/'gate_report.json'),writing_norm_available=True,
    note='架构2.0规范可用；20篇逐段精校与G2仍待验收，不将其改为passed。'))

hist=M02/'outputs/activation_history';hist.mkdir(exist_ok=True)
for name in ('module_registry.json','project_config.json'):
    if not (hist/('before_'+name)).exists():shutil.copy2(CONTROL/name,hist/('before_'+name))
reg=jrd(CONTROL/'module_registry.json')
for new,old,mid,ver in versions:
    row=next(r for r in reg['modules'] if r['module_id']==mid);row.update(path=rel(new),version=ver)
jw(CONTROL/'module_registry.json',reg)
conf=jrd(CONTROL/'project_config.json');conf['writing']['architecture']=binding
conf['shared_resources']['resource_manifests']['02']=rel(M02/'outputs/resource_snapshot.json')
conf['research']['literature_workflow']=dict(abstract_target=100,core_fulltext_target=25,preferred_view_count=[2,4],view_relations=profile['literature_review']['relations'],
    triggers=profile['introduction_routes'],advances=profile['theoretical_advances'],policy_preference='national_primary_source_direct_relevance',
    inputs_before_final_question=['abstract_relation_scope_map','core25_fulltext_dialogue','policy_reality_context'],actual_topic_selected=False)
jw(CONTROL/'project_config.json',conf)

spec=importlib.util.spec_from_file_location('project_control',CONTROL/'tools/project.py');pc=importlib.util.module_from_spec(spec);spec.loader.exec_module(pc)
framework=pc.validate();problems=list(framework['problems'])
for value,target in [(sum(profile['literature_review']['budgets'].values()),2400),(sum(profile['theory_budgets']),2200),(sum(profile['introduction_paragraph_budgets']),1800),(sum(x['target_characters'] for x in profile['sections']),15000)]:
    if value!=target:problems.append('budget mismatch')
if len({r['check_id'] for r in checks})!=len(checks):problems.append('duplicate architecture check IDs')
for key,hashkey in [('profile_path','profile_sha256'),('guide_path','guide_sha256')]:
    if sha(ROOT/binding[key])!=binding[hashkey]:problems.append('binding hash mismatch')
for dest in re.findall(r'\]\(<([^>]+)>\)',rd(guide)):
    if not Path(dest).exists():problems.append('broken guide link '+dest)
states={r['module_id']:r['status'] for r in pc.resource_bindings()}
if states['02']!='needs_review':problems.append('G2 incorrectly upgraded or stale')
for mode,review in [('single',False),('three_plus_review',True)]:
    if next(r['enabled'] for r in pc.plan(writing_mode=mode) if r['module_id']=='08')!=review:problems.append('mode routing changed')
if '解释A的前提→核心链条' in rd(guide) or '## 6. 第二部分：文献回顾，2400字，默认八段' in rd(guide):problems.append('old fixed binary review remains')
audit=dict(checked_at=NOW,passed=not problems,problems=problems,framework=framework,
    profile_version='2.0',preferred_views=[2,4],view_relation_count=len(profile['literature_review']['relations']),
    budget_sums_checked=[1800,2400,2200,15000],resource_G2_status=states['02'],research_gates_evaluated=False,
    empirical_work_executed=False,crawler_modified=False)
for new,old,mid,ver in versions:jw(new/'outputs/revision_validation.json',audit)
jw(M02/'outputs/revision_manifest.json',dict(created_at=NOW,request='用户最新修正：2—4条非固定并列解释路径；同层级空白与议题研究流程衔接',
    modules={mid:dict(path=rel(new),version=ver) for new,old,mid,ver in versions},architecture=binding,status='norm_revision_complete',
    source_inputs=[dict(path=rel(p),sha256=sha(p)) for p in [ROOT/'AGENTS.md',ROOT/'基础要求.md',ROOT/'项目架构.md',oldguide,OLD02/'templates/writing_profile.json',ROOT/'04_议题文献与现实/v001_第1版/模块说明.md',ROOT/'05_研究问题与假设/v001_第1版/模块说明.md',ROOT/'11_文献采集适配/v001_第1版/模块说明.md']],
    control_files=[dict(path=rel(CONTROL/n),sha256=sha(CONTROL/n)) for n in ['module_registry.json','project_config.json']],
    seed=None,model='current Codex conversation; exact model identifier not exposed',validation=audit,
    outputs=[dict(path=rel(p),sha256=sha(p)) for new,old,mid,ver in versions for p in sorted(new.rglob('*')) if p.is_file() and p.name!='revision_manifest.json' and '__pycache__' not in p.parts]))
print(json.dumps(dict(passed=not problems,problems=problems,guide=rel(guide),guide_characters=len(''.join(rd(guide).split())),architecture='2.0'),ensure_ascii=False))
if problems:raise SystemExit(1)
