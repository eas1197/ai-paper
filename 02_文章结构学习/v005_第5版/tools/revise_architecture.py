"""架构2.1修订；只写本次新模块版本和当前入口，不重建旧语料。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import csv, hashlib, json, re

ROOT=Path(__file__).resolve().parents[3]
M02=ROOT/'02_文章结构学习/v005_第5版'
M04=ROOT/'04_议题文献与现实/v003_第3版'
M07=ROOT/'07_三稿独立写作/v005_第5版'
M10=ROOT/'10_共享证据与契约/v002_第2版'
CONTROL=ROOT/'00_项目控制/v003_第3版'
CORPUS=ROOT/'02_文章结构学习/v002_第2版/outputs/资源建设_20261114_attempt002'
NOW=datetime.now(timezone(timedelta(hours=8))).isoformat()
def rd(p):return p.read_text(encoding='utf-8-sig')
def jr(p):return json.loads(rd(p))
def wr(p,t):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t,encoding='utf8')
def jw(p,d):wr(p,json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.relative_to(ROOT).as_posix()

# 每次均从保留的旧版本生成，避免累加替换。
old02=ROOT/'02_文章结构学习/v004_第4版'
old07=ROOT/'07_三稿独立写作/v004_第4版'
old04=ROOT/'04_议题文献与现实/v002_第2版'
zero=rd(old02/'assets/写作架构/章节规范/00_研究怎样产生.md')
zero=re.sub(r'^## 0\..*$', '## 0. 怎样产生议题与问题：从第四步的现实和理论线索逐渐聚焦', zero, flags=re.M)
zero=re.sub(r'^\| 议题 \|.*$', '| 议题 | 主题中持续被讨论的一类关系 | 教育与阶层 | 第四步及以后，结合现实或理论线索生成、筛选并修订 |', zero, flags=re.M)
zero=zero.replace('先固定主题和议题，保留具体问题候选；不能先认定一个“新颖”假设，再只找支持它的文献。','启动时可以只有宽泛主题或现实线索，议题允许为空。第1—3步不替具体论文预选议题。第4步结合现实变化、政策与理论线索提出候选议题，初步检索后聚焦，再开展摘要图谱与核心全文阅读；第4—5步可往返修订。不能先认定假设，再只找支持它的文献。')
zero=re.sub(r'^\*\*学术线：.*$', '**学术线：宽泛主题与理论线索 → 初步检索 → 候选议题及价值判断 → 聚焦检索、权威筛选与去重 → 约100篇摘要 → 关系与适用范围图谱 → 主要解释路径 → 25篇核心全文 → 修订议题、校准问题。**',zero,flags=re.M)
zero=re.sub(r'^\*\*现实线：.*$', '**现实线：宽泛主题或现实线索 → 国家政策原文及制度目标 → 近年新闻及其原始材料 → 可核实的变化和解释需要 → 产生、筛选候选议题。**',zero,flags=re.M)
zero=zero.replace('实际检索启动前确定主题、议题、范围与检索策略。','初步扫描可只有宽泛主题与现实/理论关键词；第4步形成候选议题后，为聚焦检索登记暂定议题、范围与策略，并保留后续修订依据。')
zero=zero.replace('两条线在第五步汇合。','两条线从第4步开始相互参照，并在第5步形成具体问题与假设；议题可以随阅读核查继续修订。')
zero=zero.replace('## 0. 怎样产生问题：先建立议题认识，再确定具体问题','## 0. 怎样产生议题与问题：从第四步的现实和理论线索逐渐聚焦')
zero=zero.replace('| 议题 | 主题中持续被讨论的一类关系 | 教育与阶层 | 第四步检索前 |','| 议题 | 主题中持续被讨论的一类关系 | 教育与阶层 | 第四步及以后，结合现实或理论线索生成、筛选并修订 |')
zero=zero.replace('先固定主题和议题，不能先凭直觉选一个看似新颖的假设，再只找支持它的文献。','启动时可以只有宽泛主题或现实线索，议题允许为空。第1—3步不替具体论文预选议题。第4步先看现实变化、国家政策和主题内理论线索，形成若干候选议题，经初步检索判断价值与范围，再开展聚焦检索、摘要图谱与核心全文阅读；第4—5步可往返收窄议题和问题。不能先凭直觉固定假设，再只找支持它的文献。')
zero=zero.replace('**学术线：检索 → 权威筛选与去重 → 约100篇摘要 → 关系与适用范围图谱 → 2—4条主要解释路径 → 25篇核心全文 → 校准候选问题。**','**学术线：宽泛主题与理论线索 → 初步检索 → 候选议题及其价值判断 → 聚焦检索、权威筛选与去重 → 约100篇摘要 → 关系与适用范围图谱 → 主要解释路径 → 25篇核心全文 → 修订议题、校准候选问题。**')
zero=zero.replace('**现实线：主题 → 国家政策原文及制度目标 → 近年热点新闻及其原始材料 → 可核实的情境变化 → 现实中需要解释的问题。**','**现实线：宽泛主题或现实线索 → 国家政策原文及制度目标 → 近年热点新闻及其原始材料 → 可核实的变化与解释需要 → 产生、筛选候选议题。**')
zero=zero.replace('两线在第五步会合。','两线从第四步就相互参照，在第五步形成有文献对话的具体问题与假设。议题不是第4步开始前必须交齐的输入。候选议题至少写明现实/理论依据、学术价值、已有认识、尚待解释的关系及数据可行性；热点热度本身不证明学术价值。')
zero=zero.replace('实际检索任务前确定主题、议题、范围、检索式。','初步扫描可只有宽泛主题与情境/理论关键词；形成候选议题后，为聚焦检索记录暂定议题、范围与检索式。新增线索允许调整议题，但保留检索版本和纳入理由，避免事后迎合结果。')
wr(M02/'assets/写作架构/章节规范/00_研究怎样产生.md',zero)

intro=rd(old02/'assets/写作架构/章节规范/05_引言.md')
intro=intro.replace('1800字，默认七段','1800字，七个功能单元（段数可变）').replace('已有解释概貌','对象、过程或关系聚焦').replace('### 5.1 两条路线的七段安排','### 5.1 两条路线的功能与预算安排')
intro=intro.replace('### 5.1 两个起点的七段安排','### 5.1 两个起点的功能与预算安排')
intro=intro.replace('既有解释概貌','对象、过程或关系聚焦').replace('| 段落 | 字数 |','| 功能单元 | 字数 |')
intro=intro.replace('| I3 | 260 | 概括已有2—4条主要解释路径及能解释的部分 | 概括已有2—4条路径的覆盖及相互联系 |','| I3 | 260 | 聚焦要解释的对象、过程或关系；按需简述直接相关的已有认识 | 界定理论问题所在的具体关系或阶段；按需引入相关研究 |')
a=intro.index('### 5.4');b=intro.index('### 5.5',a)
intro=intro[:a]+'''### 5.4 从研究聚焦进入待推进处，不固定第三段综述路径

I3的任务是使读者明确本文究竟研究哪个对象、过程、阶段或关系。可以先界定对象、从宏观现象转到具体过程、说明为什么选择某个结果变量，也可以按需概括与问题直接相关的研究。I4随后说明这一聚焦位置上仍有哪一点需要解释。两项可以合段，也可依论证需要分开；功能编号不是对实际第三、第四自然段的强制排序。

本次专项回查8篇引言，发现制度条款设问、研究对象界定、从最终结果转向过程、理论与经验张力等多种推进方式，不能据此规定所有文章在引言第三段概括2—4条解释路径。完整路径及相互关系主要在文献回顾中组织。若问题本身需要较长理论铺垫，引言也可以展开相关研究，如《文化再生产还是文化流动》的引言；不因此禁止引言中的实质综述。详见本版outputs/引言专项对比.md。该回查是定向功能比较，不是两刊总体频率调查。

缺口要明确原有研究已经解释什么、具体还缺哪一环、为何重要、本文准备推进什么。不要把补充空白写成否定全部既有理论。有关未覆盖环节的判断仍须检索与核心全文核查，不能只凭摘要中没有出现某个词。

'''+intro[b:]
intro=intro.replace('第五段将缺口','I5将缺口').replace('第六段说明','I6说明').replace('第七段按','I7按')
intro+='\n预算是起草用的功能预算，可以合并、拆分或调配；政策、情境、聚焦、缺口、问题、回应和贡献不等于七个固定自然段。\n'
wr(M02/'assets/写作架构/章节规范/05_引言.md',intro)

guide=M02/'assets/写作架构/定量社会学论文写作架构.md'
s=rd(old02/'assets/写作架构/定量社会学论文写作架构.md').replace('架构版本：2.0','架构版本：2.1')
for n,fragment in [(0,zero),(5,intro),(8,rd(M02/'assets/写作架构/章节规范/08_研究设计.md'))]:
 a=s.index(f'## {n}.');b=s.index(f'## {n+1}.',a);s=s[:a]+fragment+'\n\n'+s[b:]
s=s.replace('先填写主题、议题、约100摘要图谱','先登记宽泛主题与第4步议题生成依据，再填写暂定议题、约100摘要图谱')
s=s.replace('02_文章结构学习/v004_第4版','02_文章结构学习/v005_第5版')
s=s.replace('数据、样本、测量、模型、推断边界','数据、实际样本处理、测量、模型与估计设置')
wr(guide,s)

profile=jr(old02/'templates/writing_profile.json')
profile.update(profile_version='2.1',module_version=5,created_at=NOW,guide_path=rel(guide),guide_sha256=sha(guide))
profile['research_inputs'].update(issue_generation_stage='04',issue_required_before_stage_04=False,issue_refinement_stages=['04','05'],early_issue_is_only_candidate=True)
profile['introduction']={'units_are_not_fixed_paragraphs':True,'I3_function':'focus_object_process_or_relation_with_relevant_prior_knowledge_if_needed','path_count_required_in_I3':False,'literature_in_introduction_allowed_when_needed':True}
profile['design']={'unit_budgets':[400,350,250,350,200,250,350,250],'mandatory_sampling_skepticism_paragraph':False,'mandatory_inference_boundary_closing':False,'last_unit':'estimation_implementation'}
for row in profile['sections']:
 if row['id']=='D':row['default_paragraph_slots']=8
 if row['id']=='I':row['default_paragraph_slots']=None;row['default_function_units']=7
jw(M02/'templates/writing_profile.json',profile)
binding={'profile_id':profile['profile_id'],'profile_version':'2.1','profile_path':rel(M02/'templates/writing_profile.json'),'profile_sha256':sha(M02/'templates/writing_profile.json'),'guide_path':rel(guide),'guide_sha256':sha(guide)}

plan=rd(old02/'templates/写作计划.md').replace('架构2.0','架构2.1')
plan=plan.replace('议题：【例如教育与阶层；正式检索前确定】','议题：【第4步结合现实/理论线索生成；初始可空；例如教育与阶层仅作层级说明】\n- 候选议题、现实/理论依据、筛选理由与修改记录：【】')
plan=plan.replace('情境→已有路径→待推进处','情境→研究聚焦→待推进处').replace('数据、样本、测量、估计对象、推断边界','D1数据400＋D2实际样本处理350＋D3结果250＋D4解释变量350＋D5必要延伸变量200＋D6控制250＋D7模型350＋D8实施250')
plan=plan.replace('引言七段与摘要六句','引言七个功能单元与摘要六句').replace('I3主要路径260','I3对象/过程/关系聚焦260').replace('R/T起点改变I2/I4的重点','各功能可合并、拆分或按论证调整；I3不强制概括2—4条路径。R/T起点改变I2/I4的重点')
plan=plan.replace('主题、议题、问题不混淆；','议题在第4步及以后生成并可修订；主题、议题、问题不混淆；')
for m in (M02,M07):wr(m/'templates/写作计划.md',plan)
for name in ('writing_architecture_binding.json','draft_manifest.json','frozen_manifest.json'):
 d=jr(old07/'templates'/name) if name!='writing_architecture_binding.json' else binding
 if name!='writing_architecture_binding.json':d['writing_architecture']=binding
 jw(M07/'templates'/name,d)
ms=rd(old07/'templates/manuscript.md').replace('架构2.0','架构2.1').replace('I3主要路径260','I3对象/过程/关系聚焦260')
ms=ms.replace('【D1数据；D2范围和代表性；D3样本筛选与缺失处理。】','【D1数据来源、版本、结构和适用性400字；D2实际样本筛选、匹配、缺失处理及最终N350字。成熟公开数据库的规范抽样通常简述并引正式说明；不强制写代表性质疑段。】')
ms=ms.replace('【D4结果；D5主要解释；D6必要机制/条件变量；D7控制及理由。】','【D3结果变量250；D4主要解释变量350；D5必要机制/条件变量200；D6控制及理由250。】')
ms=ms.replace('（三）分析策略与推断边界','（三）分析策略').replace('【D8估计对象与模型；D9权重/标准误/区间；D10能与不能支持的结论。】','【D7估计对象、模型与参数解释350；D8实际使用的权重、相关性处理、标准误与区间250。完成分析策略后进入结果。】')
ms=ms.replace('R/T两个起点的重点按架构选择。','上述是功能单元，可合段或拆段，I3不要求路径综述。R/T两个起点的重点按架构选择。')
a=ms.index('## 四、');b=ms.index('## 五、',a)
ms=ms[:a]+'''## 四、研究设计（目标2400字）

### （一）数据与样本

【D1数据来源、版本、结构和适用性400字；D2实际样本筛选、匹配、缺失处理及最终N350字。成熟公开数据库的规范抽样通常简述并引用正式说明，不强制写代表性质疑段。】

### （二）变量与测量

【D3结果变量250；D4核心解释变量350；D5必要机制/条件变量200；D6控制及理由250。】

### （三）分析策略

【D7估计对象、模型与参数解释350；D8实际使用的权重、相关性处理、标准误与区间250。完成分析策略后进入结果。】

'''+ms[b:]
wr(M07/'templates/manuscript.md',ms)

d=jr(old04/'templates/topic_scope.json');d.update(issue=None,issue_candidates=[],issue_generation_stage='04',issue_status='to_be_generated',issue_is_frozen=False,selection_bases=['reality_context','theoretical_opportunity','policy_relevance','researchability'],revision_log=[]);jw(M04/'templates/topic_scope.json',d)
d=jr(old04/'templates/acquisition_request.json');d.update(issue_required_at_initial_scan=False,search_phases=['broad_theme_context_theory_scan','candidate_issue_generation','focused_issue_search','abstract_map_and_core25'],issue_generation_stage='04');jw(M04/'templates/acquisition_request.json',d)
d=rd(old04/'模块说明.md').replace('第2版','第3版').replace('先确定主题与议题，再形成具体问题。','启动时允许只有宽泛主题或现实/理论线索，议题在第4步及以后生成。先扫描现实与理论、提出并比较候选议题，再聚焦检索与形成具体问题；第4—5步允许往返修订。')
d+='\n## 第3版：议题生成属于本模块\n\n输入议题可以为空；已有议题只是候选。先以现实变化、国家政策和主题内理论线索生成候选，比较现实/理论价值、已有解释、可研究性与数据条件，再锁定一版暂定议题开展聚焦检索。约100摘要与25核心全文进一步验证议题是否值得研究，并与05往返形成具体问题。第1—3步不预选论文议题。topic_scope.json保存候选、依据与变更；不将热点热度自动等同于理论价值。\n'
d=d.replace('先确定主题和议题，不提前锁死问题。','启动时只有宽泛主题或现实/理论线索也可，第4步生成候选议题并逐渐聚焦，不提前锁死议题和具体问题。')
d=d.replace('学术线：议题检索→','学术线：主题内理论线索与初步检索→候选议题及价值筛选→聚焦议题检索→')
wr(M04/'模块说明.md',d)
d=rd(old04/'采集与归档规格.md').replace('第2版','第3版').replace('1. 输入主题、议题、同义词、年份、已核对期刊名、授权来源和目标数量。具体研究问题可以为空。','1. 初步扫描输入宽泛主题或现实/理论线索，议题和具体问题均可为空；第4步生成候选议题后，聚焦检索再输入暂定议题、同义词、年份、已核对期刊名、授权来源和目标数量。保留各版检索及议题修改依据。')
wr(M04/'采集与归档规格.md',d)

d=rd(ROOT/'00_项目控制/v002_第2版/模块说明.md').replace('第2版','第3版').replace('研究主题与议题、可选研究问题','宽泛研究主题、可选候选议题与问题').replace('保存主题/议题/问题。','保存主题和候选议题/问题；议题可空，记录在第4步生成且尚未冻结。')
d+='\n## 第3版兼容\n\ninit不再要求--issue；传入时记为用户候选，不视为已完成议题选择。运行目录仍由runtime.run_store_root指向原v002/runs，保持既有运行位置；配置、注册表与工具入口改为本版。旧运行和旧配置不自动迁移。本工具只建立计划，不会执行议题生成或科研。\n';wr(CONTROL/'模块说明.md',d)
sql=rd(ROOT/'10_共享证据与契约/v001_第1版/knowledge.sql').replace('theme TEXT NOT NULL, issue TEXT NOT NULL','theme TEXT NOT NULL, issue TEXT')
wr(M10/'knowledge.sql',sql)
for name in ('模块说明.md','数据契约.md'):
 d=rd(ROOT/'10_共享证据与契约/v001_第1版'/name).replace('第1版','第2版')
 d+='\n## 第2版议题可空契约\n\nresearch_runs.issue允许NULL，表示议题尚待第4步结合现实或理论线索生成；不以空字符串伪造已选议题。theme仍为宽泛主题输入。运行JSON以topic_state记录候选、生成阶段及未冻结状态。已有非空议题兼容保留，但不能仅凭非空认定已经核验或冻结。SQL列序及其他表不变。新库使用本版knowledge.sql；旧库先备份，再在独立连接执行migrations/v1_to_v2.sql并检查foreign_key_check；本轮只测试迁移，不操作正式数据库。\n'
 wr(M10/name,d)

versions=[(CONTROL,'00',3),(M02,'02',5),(M04,'04',3),(M07,'07',5),(M10,'10',2)]
for m,mid,v in versions:
 d=jr(m/'manifest.json');d.update(version=v,version_label=f'第{v}版')
 if mid in ('02','07'):d['writing_architecture']=binding
 if mid=='10':d['storage_schema_version']=2;d['expected_artifacts']+=['migrations/v1_to_v2.sql'];d['folders']+=['migrations','outputs']
 if 'outputs' not in d['folders']:d['folders'].append('outputs')
 d['folders']=list(dict.fromkeys(d['folders']))
 d['expected_artifacts']=list(dict.fromkeys(d['expected_artifacts']))
 for f in d['folders']:(m/f).mkdir(parents=True,exist_ok=True)
 jw(m/'manifest.json',d)
 for folder in ('templates','outputs'):
  wr(m/folder/'README.md',f'# 第{v}版{folder}\n\n本版对应本轮修订。模板、专项回查及技术验证分别记账；空表不等于已完成研究，框架有效不等于科研业务验收通过。\n')
 wr(m/'CHANGELOG.md',f'''# 第{v}版变更记录

日期：2026-11-14；依据：用户本轮对议题产生阶段、I3、公开数据库抽样说明及D10的修正。

- 新增：第4步候选议题生成/修订状态；8篇引言专项对比与证据定位；兼容议题可空的入口和SQL迁移。
- 修改：架构2.1的I3为研究聚焦，可按需引入已有认识；方法不强制抽样质疑段，删除D10，以8个功能单元重配2400字。
- 兼容：旧版、原语料及旧运行保留；新配置继续使用原run存储路径。现有非空候选议题可继续传入；SQL列序和其他表不变。
- 验收：见outputs/revision_validation.json。只核验本次规范、代码与契约；专项回查不替代20篇逐段精校，不改变G2 needs_review。100摘要/25核心研究仍未执行。
''')
 lines=['# 版本索引',f'\n当前版本：`{m.name}`；由00第3版注册表启用。','']
 for p in sorted(m.parent.glob('v*_第*版'),reverse=True):lines.append(f'- [{p.name}]({p.name}/模块说明.md)：'+('本轮修订。' if p==m else '历史保留。'))
 wr(m.parent/'版本索引.md','\n'.join(lines)+'\n')

for m,old in [(M02,old02),(M07,old07)]:
 d=rd(old/'模块说明.md').replace('第4版','第5版').replace('架构2.0','架构2.1')
 d=d.replace('主题→议题→100摘要图谱','第4步现实/理论线索→候选议题→100摘要图谱')
 d+='\n## 本轮修订\n\n议题在第4步及以后生成并可修订；I3不再固定概括2—4条路径，改为对象/过程/关系聚焦；七项是功能单元而非固定自然段。公开数据库通常简述规范来源及实际样本处理，不强制代表性质疑段；D10删除，研究设计重排为8个单元、合计2400字。8篇引言定向回查见02本版outputs/引言专项对比.md，不代表20篇逐段精校完成。\n'
 wr(m/'模块说明.md',d)

reg=jr(ROOT/'00_项目控制/v002_第2版/module_registry.json')
for m,mid,v in versions:
 row=next(x for x in reg['modules'] if x['module_id']==mid);row.update(path=rel(m),version=v)
jw(CONTROL/'module_registry.json',reg)
conf=jr(ROOT/'00_项目控制/v002_第2版/project_config.json');conf['writing']['architecture']=binding
conf['research']['literature_workflow'].update(issue_generation_stage='04',issue_required_before_stage_04=False,issue_refinement_stages=['04','05'])
conf['runtime']['run_store_root']='00_项目控制/v002_第2版/runs'
conf['shared_resources']['resource_manifests']['02']=rel(M02/'outputs/resource_snapshot.json');jw(CONTROL/'project_config.json',conf)

# 定向比较记录；页码指PDF页序，不臆造自然段序号。
cases=[
 ('P02','SCCKUUS9','当代中国的代际流动模式及其变迁','中国社会科学，2015(5)',[1,2],'40—41','社会变化与不平等→代际流动与机会结构→研究的公共及学术意义；两种逻辑在下一节展开。','研究意义与对象聚焦先行，不要求I3列出解释路径。'),
 ('P05','MY99VSIF','资源、激励与部门利益：中国社会保险征缴体制的纵贯研究(1999—2008)','中国社会科学，2011(3)',[1,2],'139—140','未决征缴条款→制度选择疑问及规模意义→部门利益→资料与两个问题；文献综述随后开始。','制度条款可以直接组织设问，不需先形成2—4条路径清单。'),
 ('P08','89UP6KH7','文化再生产还是文化流动——中国大学生的教育成就获得不平等研究','社会学研究，2018(1)',[1,2,3,4],'142—144（引言）','现代化与教育不平等的经验疑问→升学阶段→学业成就环节→文化理论及问题；下一节从PDF第4页开始。','引言确可展开较长理论铺垫，不能反向规定引言一律不综述。'),
 ('P10','FQ7RQ5NC','低生育率社会中的家庭结构与育儿功能——基于资源供需视角的实证分析','社会学研究，2025(2)',[1,2,3],'19—21','低生育情境、政策与资源→育儿功能研究需要→家庭对象界定→供需视角→贡献。','理论引入服务对象与功能界定，顺序取决于问题。'),
 ('P12','CJB64WZK','从自动化技术到生成式人工智能——技术对劳动者影响的技能异质性研究','社会学研究，2024(4)',[1,2],'69—70','国家目标→技术演变与中国情境→生成式技术的新变化→劳动问题；替代与控制的系统综述在下一节。','引言可优先搭建情境，解释路径放入后续文献节。'),
 ('P15','ZLZANUD2','技术变革中的福利态度转变——自动化替代对个体养老责任偏好的影响','社会学研究，2021(1)',[1,2,3],'160—162','自动化情境与风险→福利联系→养老责任→相关因素及技术风险待解释处→数据与贡献。','从现实风险收窄到具体态度关系，不必按路径数量组织I3。'),
 ('P16','V3CA3AZW','家庭背景如何影响儿童学业成就——义务教育阶段家庭社会经济地位影响差异分析','社会学研究，2016(4)',[1,2,3],'121—122（引言）','教育公平意义→已有家庭背景关系→最终获得研究与过程问题→义务教育成就→研究问题；三类资本综述在下一节。','从最终结果转向过程是研究聚焦动作，不等于解释路径概括。'),
 ('P19','GTUTSZDI','外出还是留守——农村夫妻外出安排的经验研究','社会学研究，2016(5)',[1,2],'139—140','家庭迁移变化→社会后果→外出安排的基础分布问题→既有资料与家庭单位→CFPS问题；随后进入文献节。','对象与分析单位可以成为引言推进的核心。')]
records=[];lines=['# I3是否应固定概括解释路径：8篇引言专项对比',f'\n核查时间：{NOW}。核查对象为既有20篇语料中定向选取的8篇；读取页级全文及相邻章节起点，未完成全部20篇逐段精校。PDF页序从1开始。下述推进链均为本次综合概括，不是原文逐字引述。','\n| 文章 | 核查位置 | 实际推进及对I3的启示 |','|---|---|---|']
for pid,key,title,journal,pages,printed,chain,implication in cases:
 folder=CORPUS/'fulltext'/key;source=jr(folder/'source.json');page_data=jr(folder/'pages.json')
 # 复用抽取文本且重新核对来源文件哈希，来源PDF保持只读。
 pdf=Path(source['pdf_path']);actual_sha=sha(pdf)
 if actual_sha!=source['pdf_sha256']:raise ValueError('source changed '+key)
 row={'paper_id':pid,'attachment_key':key,'title':title,'journal_issue':journal,'checked_at':NOW,'pdf_path':source['pdf_path'],'pdf_sha256':actual_sha,'pages_json_path':rel(folder/'pages.json'),'pages_json_sha256':sha(folder/'pages.json'),'checked_pdf_pages':pages,'printed_intro_pages':printed,'progression_summary':chain,'I3_implication':implication,'evidence_type':'direct_page_text_plus_cross_paper_synthesis','paragraph_numbers_verified':False}
 row['page_locators']=[{'pdf_page':p,'text_sha256':hashlib.sha256(page_data[p-1]['text'].encode('utf8')).hexdigest(),'text_length':len(page_data[p-1]['text'])} for p in pages]
 records.append(row)
 lines.append(f'| {pid}《{title}》；{journal} | [原PDF](<{source["pdf_path"].replace(chr(92),"/")}>)；PDF {"、".join(map(str,pages))}页；引言印刷页{printed} | {chain}<br>{implication} |')
lines+=['\n本次比较支持的修订：I3改为“对象、过程或关系聚焦，按需引入直接相关认识”；允许与情境或缺口合段。完整路径联系仍主要在文献回顾呈现，默认2—4条是本项目组织建议，不是由本次回查证明的期刊通则。引言也可以有必要的实质综述。','\n证据区分：论文页级文本是直接证据；上表推进概括及跨文比较是本次综合；“I3功能、260字预算和章节分工”是项目写作规范。不能由8篇定向样本推算两刊比例，也不把印刷页或章节边界当成已校准的自然段编号。','\n逐篇路径、源PDF/抽取文件哈希、核查页码和时间见同目录intro_comparison_evidence.json。']
wr(M02/'outputs/引言专项对比.md','\n'.join(lines)+'\n');jw(M02/'outputs/intro_comparison_evidence.json',{'checked_at':NOW,'scope':'targeted_8_introductions','records':records,'G2_status':'needs_review'})

files=[guide,M02/'templates/writing_profile.json',M02/'templates/写作计划.md',*sorted((M02/'assets/写作架构/章节规范').glob('*.md')),M02/'outputs/引言专项对比.md',M02/'outputs/intro_comparison_evidence.json',*[CORPUS/n for n in ('corpus20.csv','structure_moves.csv','abstract_sentences.csv','structure_handbook.md')]]
jw(M02/'outputs/resource_snapshot.json',{'schema_version':1,'module_id':'02','module_version':5,'resource_version':4,'resource_snapshot_id':'structure_candidate_r4_architecture_2_1','lifecycle':'build_once_reuse_many','status':'needs_review','files':[{'path':rel(p),'sha256':sha(p)} for p in files],'business_gate_report':rel(CORPUS/'gate_report.json'),'writing_norm_available':True,'note':'架构2.1规范可用；8篇引言专项回查不替代20篇逐段精校与G2验收。'})

readme=rd(ROOT/'README.md').replace('当前框架：第2版（2026-11-14）；02与07为第4版，04与05为第2版，启用详细写作架构2.0。','当前框架：根规范第2版；控制模块第3版，02与07第5版、04第3版、05第2版、10第2版，启用写作架构2.1（2026-11-14）。')
readme=readme.replace('00_项目控制/v002_第2版','00_项目控制/v003_第3版').replace('00_项目控制\\v002_第2版','00_项目控制\\v003_第3版').replace('02_文章结构学习/v004_第4版','02_文章结构学习/v005_第5版').replace('07_三稿独立写作/v004_第4版','07_三稿独立写作/v005_第5版').replace('04_议题文献与现实/v002_第2版','04_议题文献与现实/v003_第3版').replace('写作架构2.0','写作架构2.1').replace(' --issue "教育与阶层"','')
readme=readme.replace('初始化只建计划工作区；','启动可只给宽泛主题，议题在第4步及以后依据现实/理论线索生成；--issue仅用于传入可修改的候选。初始化只建计划工作区；')
readme+='\n本轮专项修订：[8篇引言对比](02_文章结构学习/v005_第5版/outputs/引言专项对比.md)。I3不固定综述2—4条路径；公开数据库不强制抽样质疑段；D10已删除，研究设计重排8个功能单元。旧运行仍保存在00第2版runs，本版不迁移旧运行或正式数据库。\n'
wr(ROOT/'README.md',readme)
print(json.dumps({'architecture':'2.1','guide':rel(guide),'comparison_count':len(records),'source_pdf_hashes_verified':True},ensure_ascii=False))
