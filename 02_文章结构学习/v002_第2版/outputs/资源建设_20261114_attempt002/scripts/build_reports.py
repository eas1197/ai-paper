from pathlib import Path
import csv, json, re, hashlib, statistics, unicodedata
from collections import Counter
from datetime import datetime, timezone, timedelta
from annotations import PAPERS, ABSTRACT_NOTES

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parents[3]
NOW=datetime.now(timezone(timedelta(hours=8))).isoformat()
OUT=ROOT/'reports';OUT.mkdir(exist_ok=True)
def write(path,text):path.write_text(text,encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(t):return re.sub(r'\s+','',unicodedata.normalize('NFKC',re.sub(r'[\ue000-\uf8ff]','',t))).replace('\x82','，')
def canon(t):return re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]','',clean(t))
def csvout(name,rows):
    if not rows:return
    with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def link(path,label):return f'[{label}](<{path.resolve().as_posix()}>)'
def printed(p,n):return str(p['print_start']+n-1-(1 if p['key']=='DD4I5QA4' and n>=20 else 0)) if not (p['key']=='DD4I5QA4' and n==19) else '插页表4（无连续正文页码）'
def locator(p,a,b=None):
    b=a if b is None else b
    return f'PDF第{a}页/刊内第{printed(p,a)}页' if a==b else f'PDF第{a}—{b}页/刊内第{printed(p,a)}—{printed(p,b)}页'
def sentences(text):return [x for x in re.findall(r'.+?[。！？?](?:[”’」』])?|.+$',text) if x.strip()]

raw=json.loads((ROOT/'abstract_raw.json').read_text(encoding='utf8'))
raw={r['attachment_key']:r for r in raw}
corpus=[];moves=[];abstract_rows=[];evidences=[];paragraph_rows=[];section_rows=[];audit=[]
for p in PAPERS:
    key=p['key'];label=p['label'];pid='zotero_'+key
    folder=ROOT/'fulltext'/key
    src=json.loads((folder/'source.json').read_text(encoding='utf8'))
    pages=json.loads((folder/'pages.json').read_text(encoding='utf8'))
    cache=(ROOT/'screening'/f'{key}_cache.txt').read_text(encoding='utf8')
    cache_pages=cache.split('\f')
    title=src['filename'].split(' - ',2)[-1].removesuffix('.pdf')
    authors=src['filename'].split(' - ',1)[0]
    year=int(re.search(r' - (\d{4}) - ',src['filename']).group(1))
    abs_text=raw[key]['abstract']
    if label=='P07':
        t=clean(cache);abs_text=t[t.index('本文运用推拉理论模型'):t.index('关键词')]
    if label=='P02':abs_text=abs_text.replace('"市场排斥”','“市场排斥”')
    if label=='P04':
        abs_text='户籍制度是中国社会一项基本的制度安排，它把户口作为资源配置和利益分配的重要凭据，对社会分层和流动产生了较大的影响。在改革开放近三十年后，中国的户口还起不起作用，以及起着怎样的作用？通过对综合社会调查数据的分析，发现中国社会分层具有城乡户口差别和城市户口等级差别并存的特点，户口转变和迁移的开放性程度与个人社会流动机会获得有正相关关系。市场转型虽带来了较多流动机会，但户口等级差别以及户口对体制内流动所起的结构性影响依然存在。鉴于户籍制度的强粘附性生成了社会差别，改革这一制度的基本方向是推行户口一元化和迁移自主化。'
    if label=='P05':
        abs_text='筹资是社会保险制度运行的基础，而筹资机构的选择是社会保险制度设计的关键环节。在中国社会保险费征缴体制中，地方税务机构和社会保险经办机构并存，形成二元征缴局面。新通过的《社会保险法》也未能终结征缴主体之争。为什么这一权力分散的格局得以延续十余年？由谁征收社会保险费更有利于社会保险事业的发展？事实上，两种征缴方式各具优势，与征缴相对应的权力以及征缴所带来的资金流和人事编制才是双方相持不下的动因。本研究追踪了1999至2008年各省级单位征缴主体的变迁，并构建了一个历时10年的面板数据库。统计分析发现，地方税务机构征收社会保险费更有利于扩大社会保险覆盖面，有利于促进社会保险基金收入增长。作为独立的经验研究，分析结果有助于终结长达十余年的征缴主体之争；同时，部门利益的分析框架也可应用于对其他政府机构的分析。'
    ss=sentences(abs_text)
    notes=ABSTRACT_NOTES[label]
    assert len(ss)==len(notes),(label,len(ss),len(notes))
    fn=f'{label}_{title[:24]}_结构拆解.md'
    p['report_file']=fn;p['abstract_n']=len(ss)
    numbered=sum(bool(re.match(r'^[一二三四五六七八九十]+、',s[0])) for s in p['sections'])
    corpus.append(dict(paper_id=pid,display_id=label,title=title,authors=authors,journal=p['journal'],year=year,issue=p['issue'],method=p['method'],pdf_path=src['pdf_path'],pdf_sha256=src['pdf_sha256'],page_count=src['page_count'],target_article_chinese_pages=f'1-{p["reference_end"]}',body_pdf_last_page=p['body_end'],fulltext_complete=True,quantitative_confirmed=True,inclusion_reason='目标刊正文页眉和题录相符；有实质调查数据及定量分析；两刊分层目的选样',exclusion_reason='',read_status='sections_and_abstract_coded;paragraph_precision_review_pending',fulltext_read='not_certified_complete',reader='Codex，当前会话单代理编码',read_at=NOW,abstract_sentence_count=len(ss),numbered_main_sections=numbered,analysis_units=len(p['sections']),report_path=str(OUT/fn)))
    text=[f'# {label}｜{title}',f'{authors}｜《{p["journal"]}》{p["issue"]}',
          f'\n原文：{link(Path(src["pdf_path"]),"打开Zotero原始PDF（只读）")}。核验时间：{NOW}。',
          f'\n稳定ID：`{pid}`；文件SHA-256：`{src["pdf_sha256"]}`。',
          f'\nPDF共{src["page_count"]}页；中文目标文章（含参考文献）为PDF第1—{p["reference_end"]}页。后附英文摘要页不计正文。',
          '\n## 先看整篇的推进关系',f'\n{p["logic"]}',f'\n定量依据：{p["method"]}。',
          f'\n本报告分成{len(p["sections"])}个论证单元，其中原文有{numbered}个带汉字序号的大节；未编号引言和收束单列，不冒充原文编号。',
          '\n'+' → '.join(s[0] for s in p['sections']),
          '\n## 逐部分：先说什么，再说什么，怎样连接']
    for n,(heading,a,b,seq,relation) in enumerate(p['sections'],1):
        sid=f'{pid}_SEC{n:02}';eid=f'{sid}_E'
        steps=seq.split('→')
        excerpt='';candidates=json.loads((folder/'paragraph_candidates.json').read_text(encoding='utf8'))
        acceptable=[x for x in candidates if a<=x['pdf_page']<=b and x['kind']=='paragraph_candidate' and len(x['text'])>70 and len(re.findall(r'[\u4e00-\u9fff]',x['text']))/len(x['text'])>.6]
        if acceptable:excerpt=acceptable[0]['text'][:28]
        evidences.append(dict(evidence_id=eid,paper_id=pid,source_type='local_pdf',pdf_path=src['pdf_path'],sha256=src['pdf_sha256'],locator=locator(p,a,b)+'；'+heading,short_excerpt=excerpt,assertion_type='direct_text_locator_plus_analyst_interpretation',extraction='PDF文字、Zotero缓存交叉定位；章节推进为本会话逐项语义释义',verified_at=NOW,review_status='section_level_coded;paragraph_boundaries_unverified'))
        row=dict(paper_id=pid,section_id=sid,section_title=heading,section_order=n,page_start=a,page_end=b,paragraph_id='',paragraph_order='',move_code='SECTION_SEQUENCE',first_says=steps[0],next_says='→'.join(steps[1:-1]),ends_with=steps[-1],word_count='',body_word_share='',evidence_id=eid,verified='section_semantic_coding',level='section',relationship=relation)
        moves.append(row);section_rows.append(row)
        text += [f'\n### {n}. {heading}',f'\n位置：{locator(p,a,b)}；证据ID：`{eid}`。']
        text += ['\n'+'\n'.join(f'{j}. {step}。' for j,step in enumerate(steps,1))]
        text += [f'\n**这一部分内部与前后的关系：**{relation}']
        # Exact subordinate headings are a source navigation aid, not a semantic claim.
        subs=[]
        for pi in range(a,min(b,len(cache_pages))+1):
            for line in cache_pages[pi-1].splitlines():
                q=clean(line)
                if re.match(r'^[(（][一二三四五六七八九十]+[)）]',q) and 5<len(q)<55:
                    item=(pi,q)
                    if item not in subs:subs.append(item)
        if subs:
            text += ['\n原文小节导航（边界页可能同时出现相邻大节的小节，以PDF为准）：', '\n'+'；'.join(f'{q}〔PDF {pi}〕' for pi,q in subs)+'。']
    text+=['\n## 摘要逐句：内容、功能及承接',f'\n共{len(ss)}句。按句号、问号、叹号断句；分号和编号结果属于句内层次，不另外增加句数。S序号对应原文顺序。归一化处理换行、全半角和明显编码异常；P04、P05的标点已对照首页图像恢复。',
           '\n| 句号 | 这句具体说什么 | 论证功能 | 与前句怎样连接 |','|---|---|---|---|']
    for i,(sentence,(function,summary,rel)) in enumerate(zip(ss,notes),1):
        eid=f'{pid}_ABS_S{i:02}'
        text.append(f'| S{i} | {summary} | {function} | {rel} |')
        abstract_rows.append(dict(paper_id=pid,display_id=label,sentence_no=i,sentence_text=sentence,primary_function=function.split('/')[0],secondary_functions='/'.join(function.split('/')[1:]),content_paraphrase=summary,logical_predecessor='开篇' if i==1 else f'S{i-1}',relationship=rel,evidence_id=eid,verified='sentence_function_coded',pdf_page=1,print_page=p['print_start'],checked_at=NOW))
        evidences.append(dict(evidence_id=eid,paper_id=pid,source_type='local_pdf',pdf_path=src['pdf_path'],sha256=src['pdf_sha256'],locator=locator(p,1)+f'；摘要S{i}',short_excerpt=sentence[:32],assertion_type='direct_sentence_plus_analyst_function_coding',extraction='Zotero全文缓存与PDF首页对照；异常标点归一化',verified_at=NOW,review_status='coded'))
    text+=['\n### 句内怎样推进', '\n'+'\n'.join(f'- S{i}：'+(' → '.join(re.split(r'[;；]',s)) if re.search(r'[;；]',s) else notes[i-1][1]) for i,s in enumerate(ss,1)),
           '\n### 对照用摘要文本（仅保存在本地）','\n'+'\n\n'.join(f'**S{i}** {s}' for i,s in enumerate(ss,1)),
           '\n## 可学习的组织方式及边界',f'\n{p["logic"]}',f'\n**需要保留的限制：**{p["caution"]}',
           '\n## 段落与证据的使用状态',
           '\n以上章节推进和摘要功能为本次分析者编码，属于对原文组织的解释；不是作者自己标注的写作意图。节范围包含的连续正文均可回到原PDF核对。',
           '\n另附几何分段得到的段落候选索引，列首句、下一句与末句短锚点。跨页续段、表格、脚注和标题碎片可能需要合并或剔除；这些候选行尚未逐段精校，**不将其计作已完成的逐段人工编码，也不认证20篇全文精读或G2已通过**。',
           f'\n{link(ROOT/"paragraph_index.csv","打开段落候选索引")}；{link(ROOT/"evidence.jsonl","打开证据台账")}。']
    if key=='DD4I5QA4':text+=['\n特别页码说明：PDF第19页是横向表4“个人月收入多元线性回归模型”，文字提取为空，已渲染核对；它是额外表页，后续PDF页码较刊内页码多偏移1页，不是空白页或缺页。']
    write(OUT/fn,'\n'.join(text)+'\n')
    # Preserve provenance and limitations for every machine-generated paragraph candidate.
    for j,block in enumerate(candidates,1):
        if block['pdf_page']>p['body_end']:continue
        if block['kind'] not in ('paragraph_candidate','note_or_table'):continue
        tx=block['text']; sents=sentences(tx)
        sec=next((s for s in reversed(p['sections']) if s[1]<=block['pdf_page']),p['sections'][0])
        rel='未知；需逐段判断'
        if re.match(r'^(然而|但是|但|相反|不过|尽管)',tx):rel='转折或限定（依段首连接语自动建议）'
        elif re.match(r'^(因此|由此|据此|所以|综上|总之|总体而言)',tx):rel='推论或收束（依段首连接语自动建议）'
        elif re.match(r'^(此外|另外|同时|进一步|其次|再次)',tx):rel='补充或递进（依段首连接语自动建议）'
        peid=block['block_id']+'_E'
        paragraph_rows.append(dict(paper_id=pid,display_id=label,paragraph_candidate_id=block['block_id'],pdf_page=block['pdf_page'],print_page=printed(p,block['pdf_page']),section_suggested=sec[0],block_kind=block['kind'],first_says=(sents[0][:140] if sents else tx[:140]),next_says=(sents[1][:140] if len(sents)>1 else '本候选块没有第二个完整句；可能是短段或跨页续段'),ends_with=(sents[-1][-140:] if sents else tx[-140:]),relationship_suggested=rel,evidence_id=peid,verified=False,review_status='automatic_candidate_not_manually_validated',source_text_path=str(folder/'paragraph_candidates.json'),checked_at=NOW))
        evidences.append(dict(evidence_id=peid,paper_id=pid,source_type='local_pdf',pdf_path=src['pdf_path'],sha256=src['pdf_sha256'],locator=locator(p,block['pdf_page'])+f'；几何候选块{block["block_id"]}；top={block["top"]}',short_excerpt=tx[:28],assertion_type='automatic_text_anchor_only',extraction='pdfminer几何分段；不等于真实段界',verified_at=NOW,review_status='needs_paragraph_review'))
    audit.append(dict(paper_id=pid,display_id=label,pdf_pages=src['page_count'],chinese_article_last_pdf_page=p['reference_end'],chinese_body_last_pdf_page=p['body_end'],printed_body_pages=f'{p["print_start"]}-{printed(p,p["body_end"])}',abstract_sentences=len(ss),sections=len(p['sections']),numbered_main_sections=numbered,pdf_hash_unique=src['pdf_sha256'],paragraph_review_complete=False))

csvout('corpus20.csv',corpus);csvout('structure_moves.csv',moves);csvout('abstract_sentences.csv',abstract_rows);csvout('paragraph_index.csv',paragraph_rows);csvout('coverage_audit.csv',audit)
write(ROOT/'evidence.jsonl','\n'.join(json.dumps(x,ensure_ascii=False) for x in evidences)+'\n')
write(ROOT/'annotations.json',json.dumps(PAPERS,ensure_ascii=False,indent=2)+'\n')

counts=Counter(p['journal'] for p in PAPERS)
intro_groups={'背景或经验反常':['P01','P04','P05','P11','P19','P20'],'数据和研究任务/发现':['P02','P03','P06','P08','P14'],'问题、研究对象或解释缺口':['P07','P09','P10','P12','P15','P16'],'理论争议或理论命题':['P13','P17','P18']}
hand=['# 20篇文章结构手册｜本次章节与摘要编码','\n核验日期：2026-11-14（Asia/Shanghai）；语料：本地Zotero；目的选样，不代表两刊总体。',
      f'\n本次选取20篇完整PDF：《中国社会科学》{counts["中国社会科学"]}篇、《社会学研究》{counts["社会学研究"]}篇。逐篇报告覆盖{len(section_rows)}个论证单元、96个摘要句。章节与摘要已有本次编码；逐段候选尚未精校，资源未通过G2，不能称作20篇全文精读验收完成。',
      '\n## 先读哪几篇',
      '\n- 想学理论竞争：P06、P08、P18。它们把不同理论预期真正写成可以比较的答案。',
      '- 想学“先定义对象，再分析”：P02、P10、P19。分类、矩阵或测量本身承担主要论证。',
      '- 想学路径安排：P09、P15、P16。区分主关系、传导路径和情境差别。',
      '- 想学平均结果与异质性分开：P03、P11、P12。先给总体图景，再解释不同人群或时期。',
      '- 想学制度解释：P01、P04、P05、P14。制度背景需要进入变量、样本或对照，不只写在开头。',
      '\n## 可复用的是论证动作的连接，而不是一套固定目录',
      '\n| 实际观察 | 支持/分母 | 如何使用 | 反例或限制 |','|---|---|---|---|',
      '| 单列“研究问题与假设/研究假设”为一个大节 | 2/20：P06、P08 | 理论命题多、竞争关系强时，单列有利于看清对应 | 其余文章多放在理论、综述或分析框架内部；P12还在分析部分呈现待检验预期，发表时的排列不能证明研究决策的先后 |',
      '| 数据、变量或方法有专门大节 | 19/20；例外P07 | 复杂测量和模型通常需要独立交代 | P07主要把调查说明放在引言及脚注，不能据此认定没有实证数据 |',
      '| 独立的大节或未编号收束承担结论/总结/讨论 | 19/20；例外P13 | 回答问题，再回理论和边界 | P13将结果与讨论合为第四节，不应硬拆成原文没有的第5节 |',
      '| 多个独立的结果大节 | 5/20：P03、P04、P11、P12、P16 | 分析任务确实不同，才分为不同大节 | 其余文章也可能在一个结果大节内有多个小节，不能据大节数推断分析复杂度 |',
      '| 先修正对象或测量，再估计关系 | 可清晰对照的例子P02、P10、P19（3/20为本文列举口径） | 概念混淆会使后续模型失去意义时，应把分类论证写足 | 不是说其他17篇没有定义概念；此处只统计列举的突出案例 |',
      '\n这些是分析者对本样本的综合归纳，依据为逐篇章节页码和语义编码。不是全期刊频率推断。',
      '\n## 摘要实际有几句',f'\n20篇共{len(abstract_rows)}句；中位数{statistics.median([p["abstract_n"] for p in PAPERS]):g}句，范围{min(p["abstract_n"] for p in PAPERS)}—{max(p["abstract_n"] for p in PAPERS)}句。句内分号、编号结果不另算句。',
      '\n| 句数 | 篇数 | 文章 |','|---|---|---|']
for n in sorted(set(p['abstract_n'] for p in PAPERS)):
    group=[p['label'] for p in PAPERS if p['abstract_n']==n];hand.append(f'| {n} | {len(group)} | {"、".join(group)} |')
hand+=['\n### 第一句承担什么功能','\n下面四类是本次为了比较所作的归并；原句允许多功能，详细次功能见逐句CSV。','\n| 起句类型 | 篇数/20 | 文章 |','|---|---|---|']
for name,ids in intro_groups.items():hand.append(f'| {name} | {len(ids)}/20 | {"、".join(ids)} |')
hand+=['\n### 两篇都只有2句，组织却完全不同',
       '\n| 文章 | S1 | S2 | 不能怎样套用 |','|---|---|---|---|',
       '| P06 收入不平等与公平分配 | 数据开场，分号内已经给出三组发现 | 把共识与差异概括成贡献 | 不能把S1简单标成“介绍数据”，漏掉其中结果 |',
       '| P19 外出还是留守 | 趋势加既有家庭边界和数据缺陷 | CFPS、类型描述和三情境分析任务 | 本摘要没有独立实质结果句，不能补造一句“研究发现” |',
       '\n### 三种可以对照学习的摘要顺序',
       '\n- P05：制度重要性→二元安排→新法未解决→两个问题→组织机制答案→十年面板→绩效结果→两类贡献。适合双问题、混合证据的研究。',
       '- P08：数据任务→方向相反的结果→评价制度的解释→资源协同与理论对话。适合“某关系为何在不同结果上相反”的研究。',
       '- P16：解释缺口→数据→两条过程路径→城乡差别→公平意义。适合路径研究，但横截面路径不能自动变为因果过程。',
       '\n## 两刊比较：只描述这20篇',
       '\n| 项目 | 中国社会科学（n=7） | 社会学研究（n=13） |','|---|---|---|']
for label,field in [('摘要句数中位数','abstract_n'),('论证单元数中位数（含未编号引入/收束）',None)]:
    vals=[]
    for journal in ['中国社会科学','社会学研究']:
        xs=[p[field] if field else len(p['sections']) for p in PAPERS if p['journal']==journal];vals.append(f'{statistics.median(xs):g}〔范围{min(xs)}—{max(xs)}〕')
    hand.append(f'| {label} | {vals[0]} | {vals[1]} |')
hand += ['\n样本不是按年份、议题与设计随机配对，7/13的比例是本次目的选样，不是两刊资源不足的证明。不能把这组中位数差别解释为期刊固定风格或审稿偏好。',
         '\n## 发现的原文不一致与提取异常',
         '\n1. P15摘要末句写有代际陪伴的家庭、公共服务较好的地区强化效应更明显，正文PDF第17页却分别写没有代际陪伴的家庭、公共服务履职较差的地区更加明显。两页已渲染核对；两项差异保留并列，待回表和作者原义进一步核对，本次不改写原文消除冲突。',
         '2. P13的PDF第19页为横向表4，文字提取为空；已渲染确认不是空白，也不是正文缺页。刊内页码映射在该页后另减1。',
         '3. 若干PDF附整期英文摘要或其他文章的摘要，均不计入目标文章正文。中文参考文献仍作为完整性核查范围。',
         '4. P04、P05的嵌入字体标点异常，摘要句界已用首页图像复核；其余原始文本保留在本地，未静默补造未知数值。',
         '\n## 尚不能宣称完成的项目',
         '\n- 段落候选已提取，但跨页合段、脚注排除、横表及同页章节交界尚未逐段人工复核。因此不标记fulltext_read=complete，不发布passed资源。',
         '- 字数和正文占比未提供伪精确值。现有分段若未精校，不能据其字符数计算可靠节/段占比；对应CSV字段留空。',
         '- 本报告研究文章怎样组织证据，不代表重算原论文数据、核验全部统计数字或完成第三步语言学习。']
write(ROOT/'structure_handbook.md','\n'.join(hand)+'\n')

index=['# 第二步｜20篇定量文章结构拆解','\n日期：2026-11-14。已扩展至整个 `C:\\Users\\hou\\Zotero\\storage`，原始目录只读。',
       f'\n本次交付：20篇文章的{len(section_rows)}个论证单元和{len(abstract_rows)}个摘要句的内容、功能及前后关系；另附段落候选索引。**段落级精校未完成，G2仍为needs_review，不能把这一版算作20篇全文精读验收通过。**',
       '\n'+link(ROOT/'structure_handbook.md','先读：跨篇结构手册与实际分布'),
       '\n## 逐篇阅读入口','\n| 编号 | 文章 | 期刊/年份 | 摘要句数 | 拆解 |','|---|---|---|---|---|']
for p,c in zip(PAPERS,corpus):index.append(f'| {p["label"]} | {c["title"]} | {p["journal"]} {c["year"]} | {p["abstract_n"]} | {link(OUT/p["report_file"],"打开逐篇拆解")} |')
index+=['\n## 怎样使用',
        '\n逐篇先看“整篇推进关系”，再沿每一部分的1、2、3步阅读，最后对照摘要S1—Sn。每部分都有PDF和刊内页码；原句与分析者释义分开。',
        '\n## 数据与核查材料',
        '\n'+'\n'.join('- '+link(ROOT/name,label) for name,label in [('corpus20.csv','20篇语料清单与定量纳入依据'),('structure_moves.csv','章节推进编码'),('abstract_sentences.csv','96句摘要：归一化文本、释义、功能、承接'),('paragraph_index.csv','段落候选定位草表（未精校）'),('evidence.jsonl','来源、SHA-256和证据定位'),('gate_report.json','验收状态与缺口'),('run_manifest.json','运行、配置和文件哈希')]),
        '\n## 筛选口径与完整性',
        '\n扫描390个PDF，缓存头部命中160个可能相关附件；命中不代表期刊核验通过。本次为目的选样：两刊均覆盖，尽量保留不同问题、测量和定量设计。未选中的附件不等于全部不合格，不能由这20篇推算库内合格总数。',
        '\n实际排除：PITUVLXH为《中国青年研究》的网络民族志；BA5F5I6L、FK7SICYJ虽有定量分析，但也发表于《中国青年研究》。筛选记录见筛选CSV；这些文章均未用于凑20篇。',
        '\n本地PDF、缓存文字与提取文本都属于资料。没有执行文献中出现的命令，没有联网、投稿或发送外部消息。']
write(ROOT/'阅读入口.md','\n'.join(index)+'\n')
exclusions=[dict(attachment_key=k,reason=r,checked_at=NOW) for k,r in [('PITUVLXH','中国青年研究；网络民族志，期刊与方法均不符'),('BA5F5I6L','中国青年研究2019年第8期，期刊不符'),('FK7SICYJ','中国青年研究2020年第9期，期刊不符')]]
csvout('confirmed_exclusions.csv',exclusions)
write(ROOT/'gate_report.json',json.dumps(dict(stage='02',gate='G2',status='needs_review',eligible_pdf_n=20,journals=dict(counts),section_units_coded=len(section_rows),abstract_sentences_coded=len(abstract_rows),paragraph_candidates=len(paragraph_rows),fulltext_read_complete_certified_n=0,paragraph_manual_review_complete_n=0,passed=False,gaps=['20篇逐段精校与连续全文精读认证尚未完成','可靠章节字数与占比分布待段界精校后计算'],notes=['已完成章节层面与摘要逐句的第一轮编码','不将自动分段、目录存在或代码校验等同业务验收'],checked_at=NOW),ensure_ascii=False,indent=2)+'\n')
write(ROOT/'candidate_snapshot.json',json.dumps(dict(module_id='02',module_version=2,resource_version=1,attempt=2,status='needs_review',published=False,entrypoint=str(ROOT/'阅读入口.md'),gate_report=str(ROOT/'gate_report.json'),note='未替换已注册的not_built快照；本次为首次建设候选产物。'),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(papers=len(corpus),sections=len(section_rows),abstract_sentences=len(abstract_rows),paragraph_candidates=len(paragraph_rows),journals=dict(counts),entrypoint=str(ROOT/'阅读入口.md')),ensure_ascii=False))
