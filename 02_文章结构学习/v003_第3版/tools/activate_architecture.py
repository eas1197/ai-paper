"""发布用户要求的默认写作规范；保留既有语料验收状态。"""
from pathlib import Path
import csv, hashlib, importlib.util, json, shutil
from datetime import datetime, timezone, timedelta

ROOT=Path(__file__).resolve().parents[3]
M02=ROOT/'02_文章结构学习/v003_第3版'
M07=ROOT/'07_三稿独立写作/v003_第3版'
CONTROL=ROOT/'00_项目控制/v002_第2版'
OLD=ROOT/'02_文章结构学习/v002_第2版/outputs/资源建设_20261114_attempt002'
NOW=datetime.now(timezone(timedelta(hours=8))).isoformat()

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rel(path):return path.relative_to(ROOT).as_posix()
def js(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def txt(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value,encoding='utf8')
def read(path):return json.loads(path.read_text(encoding='utf8'))

for module in (M02,M07):
    for folder in ('templates','outputs'):
        (module/folder).mkdir(parents=True,exist_ok=True)
    old=module.parent/'v002_第2版'
    for p in (old/'templates').iterdir():
        if p.is_file() and not (module/'templates'/p.name).exists():
            shutil.copy2(p,module/'templates'/p.name)

txt(M02/'templates/README.md','# 模板与默认规范\n\nwriting_profile.json与写作计划.md是本次新增的默认写作规范入口；详细解释见assets/写作架构。其余CSV与structure_handbook.md保留语料建设模板性质，不冒充已完成成果；实际20篇编码仍引用第2版attempt002。\n')
txt(M07/'templates/README.md','# 第3版写作模板\n\n先读取writing_architecture_binding.json指向的详细架构，填写写作计划.md，再按manuscript.md起草。architecture_self_check.csv补充原有自检。所有占位模板不等于真实论文，正式稿件必须读取合格的冻结证据包。single只写一稿；其余业务门槛保持。\n')

(M02/'assets/corpus').mkdir(parents=True,exist_ok=True)
txt(M02/'assets/corpus/README.md',
    '# 原始语料引用\n\n20篇章节与摘要编码保留在第2版attempt002；不复制、覆盖或重新认证。原始Zotero只读。当前逐段精校仍待完成。\n')
for label in ('A稿','B稿','C稿'):
    (M07/label).mkdir(exist_ok=True)
    txt(M07/label/'README.md',f'# {label}\n\n仅为模块占位；single运行只创建A，B/C仅three_plus_review使用。这里不保存正式运行稿件。\n')

guide=M02/'assets/写作架构/定量社会学论文写作架构.md'
profile=M02/'templates/writing_profile.json'
section_data=[('I','问题的提出',1800,7),('L','文献回顾',2400,8),
              ('T','理论分析与研究假设',2200,9),('D','研究设计',2400,10),
              ('R','实证结果',4000,13),('C','结论与讨论',2200,8)]
profile_data=dict(schema_version=1,profile_id='quant_sociology_cn_architecture',profile_version='1.0',
    module_version=3,created_at=NOW,status='available_as_user_requested_writing_norm',
    authority='user_request_20261114',basis='prior section/abstract coding plus explicitly identified project design',
    empirical_G2_status='needs_review',journal_requirement=False,
    guide_path=rel(guide),guide_sha256=sha(guide),default_body_characters=15000,
    count_rule='visible body characters including punctuation, excluding whitespace; title, abstract, headings, table contents, notes, references and appendices excluded',
    sections=[dict(id=i,title=t,target_characters=n,default_paragraph_slots=k) for i,t,n,k in section_data],
    length_profiles=dict(short=[1400,1800,1800,2000,3300,1700],standard=[1800,2400,2200,2400,4000,2200],long=[2100,2800,2700,3000,4800,2600]),
    introduction_routes=['hotspot','theory','measurement'],
    abstract=dict(target_characters=400,default_sentence_slots=6,
        sentence_budgets=[50,50,60,100,80,60],functions=['scope_or_tension','unresolved_question','data_design','main_answer','additional_answer_or_boundary','specific_contribution'],sentence_count_is_flexible=True),
    conditional_result_branches=['pathway','heterogeneity','theory_competition','measurement','time_comparison','exploratory','none'],
    required_conclusion_opening=['return_to_question','briefly_identify_evidence','state_concentrated_answer'],
    fixed_phrases_required=False,causal_language_must_match_design=True,
    writing_modes=['single','three_plus_review'],default_writing_mode='single',
    format=dict(page='A4',margin_cm=2.5,body_font='宋体',body_pt=12,line_spacing=1.5,first_line_indent_chinese_chars=2,
        heading_levels=['一、','（一）','1.'],reference_style='author_year_internal_default; target_journal_overrides'))
js(profile,profile_data)

plan=M02/'templates/写作计划.md'
shutil.copy2(plan,M07/'templates/写作计划.md')
binding=dict(profile_id=profile_data['profile_id'],profile_version='1.0',profile_path=rel(profile),profile_sha256=sha(profile),guide_path=rel(guide),guide_sha256=sha(guide))
js(M07/'templates/writing_architecture_binding.json',binding)

txt(M07/'templates/manuscript.md','''# 【论文标题：明确对象与核心关系】

> 模板状态：未填写真实证据，不能作为已完成论文。使用前读取架构1.0并完成写作计划。正文默认15000字；全部占位符必须由冻结证据替换。

## 摘要

【S1范围/现象或命题；S2具体解释问题；S3数据与关键设计；S4主要发现；S5有证据的条件或限定；S6具体贡献。默认约400字，六句可调整。】

关键词：【4—6个】

## 一、问题的提出（目标1800字）

【I1—I4按热点/理论/测量入口展开；I5中心问题；I6资料设计及主要回答预告；I7具体贡献。】

## 二、文献回顾（目标2400字）

### （一）概念与解释视角

【L1界定；L2—L3解释A及证据；L4—L5解释B及证据。没有竞争理论时按机制或条件组织。】

### （二）证据冲突、适用边界与本文问题

【L6共识和真正冲突；L7有限缺口；L8进入本文解释。】

## 三、理论分析与研究假设（目标2200字）

【T1对象边界；T2机制；T3竞争解释；T4主要预期。】

【T5—T6按真实问题展开第二层解释与边界；不是强制中介/异质性。】

【T7汇总关系并衔接测量。冻结状态和探索状态在工作台账区分。】

## 四、研究设计（目标2400字）

### （一）数据与样本

【D1数据；D2范围和代表性；D3样本流及缺失处理。】

### （二）变量与测量

【D4结果；D5主要解释；D6必要机制/条件测量；D7控制集理由。】

### （三）分析策略与推断边界

【D8估计对象和模型；D9权重/聚类/区间；D10能与不能支持的结论。】

## 五、实证结果（目标4000字）

### （一）描述性结果（600字）

【R1样本和分布；R2关键差别及描述边界。表1。】

### （二）主要结果（1200字）

【R3主要比较；R4效应量/区间和含义；R5关键模型比较；R6竞争和不确定证据。表2。】

### （三）进一步的理论检验（900字；仅保留适用分支）

【R7—R9：理由→比较证据→理论连接与边界。没有必要分支时重新分配预算。】

### （四）可信度与稳健性（800字）

【R10最重要威胁与针对性检查；R11哪些结论改变/稳定、剩余不确定性。】

### （五）结果小结（500字）

【R12—R13按研究问题作答，不新增模型，不隐去重要反证。】

## 六、结论与讨论（目标2200字）

【C1约240字，必须回到问题、概述资料设计、给出集中回答。】

【C2约360字，主要发现及意义。】

【C3约300字，第二层发现或关键限定。】

【C4约400字，对话具体理论命题，说明如何支持/修正/限定。】

【C5约250字，热点稿回到现实困境，理论稿说明制度适用边界。】

【C6约250字，证据支持的实践或研究含义。】

【C7约280字，具体限制及其对结论的影响。】

【C8约120字，有边界地收束，不新增发现或口号。】

## 参考文献

【与正文逐条对应，所有题录字段核验。】

## 附录（必要时）

【附表A1等；保留核心设计、主要估计和必要诊断在正文。】
''')

checks=[('A01','论证对应','研究问题、理论预期、测量、表图、结果与结论逐项对应'),
('A02','字数','六节预算合计匹配总长；偏离记录原因'),('A03','入口','热点/理论/测量路线与实际研究匹配'),
('A04','摘要','问题、数据设计、主要回答和贡献完整；句数不机械'),
('A05','结论开头','回收问题、概述研究、给出集中答案'),
('A06','可选分支','机制、异质性、政策建议有问题和证据依据'),
('A07','证据','摘要、正文、表图、结论方向、量级、尺度和范围一致'),
('A08','边界','关联/路径/差异检验和因果措辞符合设计'),
('A09','反证','重要反向、不显著和不稳健结果如实保留'),
('A10','格式','标题层级、表图说明、引用及参考文献一致'),
('A11','版本','profile与架构文件哈希锁定'),
('A12','资源门槛','未把模板可用等同02/03或研究业务关卡通过')]
with (M07/'templates/architecture_self_check.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow(['check_id','category','criterion','status','evidence_or_note'])
    w.writerows([(*r,'pending','') for r in checks])
for name in ('draft_manifest.json','frozen_manifest.json'):
    data=read(M07/'templates'/name)
    data['writing_architecture']=binding
    data['architecture_deviations']=[]
    js(M07/'templates'/name,data)

for module,mid,title in ((M02,'02','文章结构学习'),(M07,'07','论文写作（单稿或三稿）')):
    mf=read(module.parent/'v002_第2版/manifest.json')
    mf.update(version=3,version_label='第3版',business_status='needs_review' if mid=='02' else 'planned')
    mf['writing_architecture']=binding
    mf['folders']= ['assets/corpus','assets/写作架构','templates','outputs','tools'] if mid=='02' else ['templates','A稿','B稿','C稿','outputs']
    if mid=='02':mf['expected_artifacts']+=['writing_profile.json','定量社会学论文写作架构.md','写作计划.md']
    else:mf['expected_artifacts']+=['写作计划.md','architecture_self_check.csv']
    js(module/'manifest.json',mf)
    txt(module/'CHANGELOG.md',f'''# {title} · 第3版变更记录

日期：2026-11-14；来源：用户要求详细统一架构，后续论文依此写作。

- 新增：六项论证任务、15000字预算、段落/句子顺序、主题入口分支、格式、原创句式功能和写作自检。
- 修改：本模块默认绑定架构1.0；以profile及正文哈希登记，保持研究证据门槛。
- 兼容：第1/2版及旧运行保留，旧语料不复制、不重跑；标准字段保留，清单新增架构字段。single仍默认，09仍关闭。
- 验收：详见outputs/activation_validation.json；只核对规范、配置与框架，不宣称G2/G7科研验收。
''')
    txt(module.parent/'版本索引.md',f'''# 版本索引

当前版本：`v003_第3版`。

- [第3版](v003_第3版/模块说明.md)：详细写作架构1.0、主题分支与默认写作绑定。
- [第2版](v002_第2版/模块说明.md)：一次性资源与可选三稿流程；历史保留。
- [第1版](v001_第1版/模块说明.md)：初始框架；历史保留。
''')

js(M02/'outputs/resource_snapshot.json',dict(schema_version=1,module_id='02',module_version=3,resource_version=2,
    resource_snapshot_id='structure_candidate_r2_with_architecture_1_0',lifecycle='build_once_reuse_many',
    status='needs_review',files=[dict(path=rel(p),sha256=sha(p)) for p in [guide,profile,plan,OLD/'corpus20.csv',OLD/'structure_moves.csv',OLD/'abstract_sentences.csv',OLD/'structure_handbook.md']],
    business_gate_report=rel(OLD/'gate_report.json'),writing_norm_available=True,
    note='用户要求的架构规范已交付；20篇逐段复核仍未完成，不发布passed，不等同语言资源或研究关卡完成。'))

# 控制注册表是当前版本路由；更新前保留完整配置快照，旧运行不迁移。
history=M02/'outputs/activation_history';history.mkdir(exist_ok=True)
for name in ('module_registry.json','project_config.json'):
    target=history/('before_'+name)
    if not target.exists():shutil.copy2(CONTROL/name,target)
reg=read(CONTROL/'module_registry.json')
for m in reg['modules']:
    if m['module_id'] in ('02','07'):
        m['version']=3
        m['path']=rel(M02 if m['module_id']=='02' else M07)
js(CONTROL/'module_registry.json',reg)
conf=read(CONTROL/'project_config.json')
conf['writing']['architecture']=binding
conf['shared_resources']['resource_manifests']['02']=rel(M02/'outputs/resource_snapshot.json')
js(CONTROL/'project_config.json',conf)

spec=importlib.util.spec_from_file_location('project_control',CONTROL/'tools/project.py')
pc=importlib.util.module_from_spec(spec);spec.loader.exec_module(pc)
validation=pc.validate()
problems=list(validation['problems'])
for name,total in [('short',12000),('standard',15000),('long',18000)]:
    if sum(profile_data['length_profiles'][name])!=total:problems.append(name+' budget mismatch')
if sum(profile_data['abstract']['sentence_budgets'])!=400:problems.append('abstract budget mismatch')
if sum(r['target_characters'] for r in profile_data['sections'])!=15000:problems.append('section budget mismatch')
for key in ('profile_path','guide_path'):
    hp='profile_sha256' if key=='profile_path' else 'guide_sha256'
    if sha(ROOT/binding[key])!=binding[hp]:problems.append('architecture binding hash mismatch')
states={r['module_id']:r['status'] for r in pc.resource_bindings()}
if states['02']!='needs_review':problems.append('G2 status incorrectly changed')
for mode,expected in [('single',False),('three_plus_review',True)]:
    rows=pc.plan(writing_mode=mode)
    if next(r['enabled'] for r in rows if r['module_id']=='08')!=expected:
        problems.append(mode+' review routing changed')

audit=dict(checked_at=NOW,passed=not problems,problems=problems,framework_validation=validation,
    budgets_checked=[12000,15000,18000,400],binding_hashes_checked=True,
    empirical_resource_status=states['02'],research_gates_passed=False,
    scope='writing norm completeness, budget arithmetic, configuration paths/hashes, existing framework and routing')
for module in (M02,M07):js(module/'outputs/activation_validation.json',audit)
record=dict(activated_at=NOW,request='后续论文按详细架构写作；需部分顺序、字数、格式、特殊句式及热点/理论分支',
    module_versions={'02':3,'07':3},writing_architecture=binding,
    control_registry=dict(path=rel(CONTROL/'module_registry.json'),sha256=sha(CONTROL/'module_registry.json')),
    config=dict(path=rel(CONTROL/'project_config.json'),sha256=sha(CONTROL/'project_config.json')),
    source_files=[dict(path=rel(p),sha256=sha(p)) for p in [ROOT/'AGENTS.md',ROOT/'基础要求.md',ROOT/'项目架构.md',OLD/'run_manifest.json',OLD/'structure_moves.csv',OLD/'abstract_sentences.csv',OLD/'gate_report.json']],
    seed=None,model='current Codex conversation; exact model identifier not exposed',
    normative_design=True,empirical_G2='needs_review',validation=audit,
    files=[dict(path=rel(p),sha256=sha(p)) for module in (M02,M07) for p in sorted(module.rglob('*')) if p.is_file() and p.name!='activation_manifest.json' and '__pycache__' not in p.parts])
js(M02/'outputs/activation_manifest.json',record)
print(json.dumps(dict(passed=not problems,problems=problems,guide_characters=len(''.join(guide.read_text(encoding='utf8').split())),guide=rel(guide),profile_version='1.0',resource_status=states['02']),ensure_ascii=False))
if problems:raise SystemExit(1)
