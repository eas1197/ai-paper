"""Package the agent's source-based style observations; no automatic learning claim."""
import csv
import hashlib
import json
import platform
import sys
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
OUT = BASE / 'outputs'
OLD = ROOT / '03_学术语言学习/v003_第3版/outputs/资源建设_attempt001'
UP = ROOT / '02_文章结构学习/v002_第2版/outputs/资源建设_20261114_attempt002'
CONTROL = ROOT / '00_项目控制/v003_第3版'
STAMP = datetime.now(timezone(timedelta(hours=8))).isoformat()

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def lock(p):
    return {'path': Path(p).relative_to(ROOT).as_posix(), 'sha256': sha(p)}

def dump(p, value):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def norm(t):
    return ''.join(c for c in unicodedata.normalize('NFKC',t)
                   if not c.isspace() and unicodedata.category(c) not in ('Co','Cc','Cf'))

def csvout(p, rows, fields=None):
    with Path(p).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def main():
    if (OUT / 'run_manifest.json').exists():
        raise SystemExit('Version already built. Use a new version or attempt.')
    OUT.mkdir(exist_ok=True)
    study = read(BASE / 'assets/style_study.json')
    styles = read(BASE / 'assets/style_patterns.json')
    exercises = read(BASE / 'assets/paragraph_exercises.json')
    corpus = {p['paper_id']:p for p in read(OLD/'corpus_input_lock.json')}
    candidates = {c['candidate_id']:c for c in read(OLD/'passage_candidates.json')}
    evidence = []
    for cid, anchor, sids, observation, kind in study['passages']:
        c = candidates[cid]
        p = corpus[c['paper_id']]
        pages = read(ROOT/c['pages_path'])
        page = pages[c['pdf_page']-1]['text']
        start, end = max(0,c['char_start']-120), min(len(page),c['char_end']+130)
        assert norm(anchor) in norm(page[start:end]), (cid,anchor)
        assert len(anchor)<=12
        assert sha(p['pdf_path']) == p['pdf_sha256']
        evidence.append({
            'evidence_id':'E_STYLE_'+cid, 'paper_id':p['paper_id'],
            'display_id':p['display_id'], 'title':p['title'], 'journal':p['journal'],
            'source_id':'S_ZOTERO_'+p['paper_id'].removeprefix('zotero_'),
            'pdf_path':p['pdf_path'], 'pdf_sha256':p['pdf_sha256'],
            'pages_file':lock(ROOT/c['pages_path']),
            'pdf_page':c['pdf_page'], 'char_start':start,'char_end':end,
            'page_text_sha256':hashlib.sha256(page.encode()).hexdigest(),
            'passage_sha256':hashlib.sha256(page[start:end].encode()).hexdigest(),
            'short_anchor':anchor, 'section_navigation':c['section_candidates'],
            'natural_paragraph_number':None, 'paragraph_number_note':'02段界未精校，保留未知，以页内字符定位',
            'passage_kind':kind, 'style_ids':sids.split(';'),
            'observation_paraphrase':observation, 'evidence_type':'direct',
            'review_status':'agent_targeted_style_reread',
            'reviewed_at':STAMP, 'client_review_date':'2026-11-15',
            'fulltext_read_complete_certified':False})
    assert len(evidence)==40 and len({e['paper_id'] for e in evidence})==20
    with (OUT/'style_evidence.jsonl').open('w',encoding='utf-8') as f:
        for e in evidence:
            f.write(json.dumps(e,ensure_ascii=False)+'\n')

    source_for = lambda rid: [e for e in evidence if rid in e['style_ids']]
    guide = ['# 学到的语言风格：怎样把意思写成论文的表达', '',
             '本版回应“学习他们的语言风格”：重点放在实际文字怎样表达，以及我在后续起草中怎样运用。', '',
             '这次重新阅读了原20篇论文的40个片段及邻接语境。下面的观察以这些片段为依据，不代表所有作者、更不代表两刊只有一种文风。', '',
             '## 总体把握', '',
             '这些片段给我的主要启发，是把学术表达落实为清楚的关系：句子有明确对象，概念之间用准确的动词连接，前一句留下的问题在后一句得到展开。术语可以有密度，但抽象判断后往往接一句说明，让读者知道它在当前问题上意味着什么。', '',
             '行文可以长，也可以短。长句主要容纳条件、比较和解释；需要集中注意时，用一句较短的判断或问句收束。段落围绕一项认识持续推进，转折和过渡交代为什么要换一个角度。', '',
             '作者的声音有差别。P01、P08、P16的所读片段更适合学习概念辨析与关系展开；P04、P05、P18、P19中可学设问转折；P09的所读片段和P06、P14的方法说明片段可学解释和带读者进入分析的口吻。这是对片段的用途区分，不是对整篇文章或期刊的风格分类。', '',
             '我会把这些表达习惯用于起草：先说清本段的意思，再整理主语、动词、限定和衔接。风格调整要保留原来的对象、关系与判断强度，不能靠补造研究内容让文字显得完整。', '',
             '## 词语怎样选择', '',
             '- 指出对象：本文关注、就…而言、围绕…展开。',
             '- 写出关系：形成、构成、转化、强化、削弱、受制于。按具体含义选用，不是替换词清单。',
             '- 展开说明：具体而言、换言之、前者/后者、例如。',
             '- 承接推进：然而、不过、与此不同、进一步、基于此、为此。每个词都要有实际逻辑关系。',
             '- 控制评价：较少、尚待、未必、相对、提示。明确判断照常直说，不把所有句子写得含糊。', '',
             '以上是表达资源的归纳，不是这些词在语料中的频率排行榜。原作者特定理论概念（如P01的“引塑效应”）只作为来源概念理解，不当作到处套用的学术修饰词。', '',
             '## 十五项风格与原创改写', '',
             '下列普通表达和改写均由本项目新写。它们用于显示表达效果；不是原论文原句，也不是已经完成研究的正文。', '']
    exampledoc = ['# 原创句子与段落练习', '',
                  '以下全部为新写的风格练习。普通表达和学术改写围绕同一表达意图；没有加入经验数据、文献发现或虚构来源。凡〔〕内的信息须以后用真实材料填写。', '',
                  '## 句子练习', '']
    rule_rows = []
    audit_rows = []
    for s in styles:
        ev = source_for(s['id'])
        assert ev, s['id']
        locators = '；'.join(f"{e['display_id']} PDF第{e['pdf_page']}页" for e in ev)
        guide += [f"### {s['id']} {s['name']}", '', f"**原文观察：** {s['observation']}", '',
                  f"**写法：** {s['how_to_write']}", '',
                  f"普通表达：{s['before']}", '', f"风格改写：{s['after']}", '',
                  f"**表达效果：** {s['effect']}", '',
                  f"**适用与分寸：** {s['condition']}", '',
                  f"**反例倾向：** {s['anti_pattern']}", '', f"依据：{locators}。", '']
        exampledoc += [f"### {s['id']} {s['name']}", '', '普通表达：'+s['before'], '',
                       '风格改写：'+s['after'], '', '变化：'+s['effect'], '', '使用条件：'+s['condition'], '']
        rule_rows.append({'rule_id':s['id'],'rhetorical_move':s['dimension'],
                          'rule_text':s['how_to_write'],'syntax_pattern':s['name'],
                          'hedging':s['strength'],'evidence_ids':';'.join(e['evidence_id'] for e in ev),
                          'paper_ids':';'.join(sorted({e['paper_id'] for e in ev})),
                          'frequency':len({e['paper_id'] for e in ev}),
                          'scope':'style_selected_passages_not_journal_wide_prevalence',
                          'original_example':s['after'],'counterexample':s['anti_pattern'],
                          'preconditions':s['condition'],'causal_strength':'style_exercise_only',
                          'review_status':'style_reviewed_formal_G3_pending',
                          'plain_expression':s['before'],'expression_effect':s['effect'],
                          'evidence_type':'synthesis','checked_at':STAMP})
        audit_rows.append({'draft_id':'STYLE_EXERCISE_NOT_MANUSCRIPT','sentence_id':s['id'],
                           'rule_id':s['id'],'claim_strength':'hypothetical_style_practice',
                           'evidence_strength':'original_synthetic_example',
                           'problem':s['anti_pattern'],'revision':s['after'],
                           'status':'expression_reviewed','semantic_scope':'保持对象、关系及强度；不新增研究事实',
                           'plain_text':s['before']})
    guide += ['## 连成段落以后是什么样', '',
              '完整的五组普通段落、风格改写及逐项说明见`original_examples.md`。这里只展示一段原创理论解释练笔：', '',
              '> '+exercises[2]['styled'], '',
              '这一段学的是：对象先出现、关系逐步展开、抽象句后接解释、末句把语气收住。它不构成本项目的机制发现。', '',
              '## 后续起草怎样使用', '',
              '起草先确定本段要推进的认识，再选合适的表达动作。写完检查：主语是否清楚？动词有没有说出关系？限定放得是否自然？后一句比前一句增加了什么？长句是否需要拆开？有没有为了像论文而新增事实或堆砌术语？', '',
              '这些写法只影响表达层。每篇研究仍使用自己的问题、文献、设计和结果，例句不能直接冒充正文。旧版的事实、数字审查记录保留，按相应环节执行。', '',
              '## 学习记录范围', '',
              '证据详见`style_evidence.jsonl`和`逐篇风格观察.md`。P03第17页的一项为脚注；抽取噪声已标明，不据此统计句长或标点。原PDF只读，原文仅保存极短定位锚点。', '',
              '本次是有来源的风格定向学习和原创练习。02的连续全文精读与逐段精校未认证，本版正式资源快照仍为needs_review；这项状态不改变上述已经记录的风格观察。', '']
    exampledoc += ['## 五组段落练习', '']
    for x in exercises:
        exampledoc += [f"### {x['exercise_id']} {x['section']}", '', '表达意图：'+x['meaning_to_preserve'], '',
                       '**普通表达**', '', x['plain'], '', '**风格改写**', '', x['styled'], '',
                       '**改变了哪里：** '+x['what_changed'], '', '**使用条件：** '+x['do_not_copy'], '',
                       '对应风格：'+ '、'.join(x['style_ids'])+'。','']
        audit_rows.append({'draft_id':'STYLE_EXERCISE_NOT_MANUSCRIPT','sentence_id':x['exercise_id'],
                           'rule_id':';'.join(x['style_ids']),'claim_strength':'hypothetical_style_practice',
                           'evidence_strength':'original_synthetic_example','problem':x['do_not_copy'],
                           'revision':x['styled'],'status':'expression_reviewed',
                           'semantic_scope':x['meaning_to_preserve'],'plain_text':x['plain']})
    (OUT/'语言风格学习.md').write_text('\n'.join(guide),encoding='utf-8')
    (OUT/'original_examples.md').write_text('\n'.join(exampledoc),encoding='utf-8')
    csvout(OUT/'language_rules.csv',rule_rows)
    csvout(OUT/'language_audit.csv',audit_rows)
    csvout(BASE/'templates/language_rules.csv',[],list(rule_rows[0]))
    csvout(BASE/'templates/language_audit.csv',[],list(audit_rows[0]))
    notes = ['# 逐篇风格观察', '', '仅记录本轮40个片段的表达方式，不扩写成整篇作者风格结论。', '']
    for pid,p in corpus.items():
        notes += [f"## {p['display_id']} {p['title']}", '', f"{p['journal']}，{p['year']}。paper_id：{pid}。", '']
        for e in evidence:
            if e['paper_id']==pid:
                notes += [f"- PDF第{e['pdf_page']}页（{e['passage_kind']}），原文短锚点“{e['short_anchor']}”：{e['observation_paraphrase']} 定位：{e['evidence_id']}，页内字符[{e['char_start']},{e['char_end']})。",'']
    (OUT/'逐篇风格观察.md').write_text('\n'.join(notes),encoding='utf-8')
    profile = {'profile_id':'corpus20_language_style','profile_version':'2.0',
               'created_on':'2026-11-15','resource_version':2,
               'scope':'expression_style_from_targeted_passages',
               'focus':['用词','主语与谓语','修饰位置','长短句节奏','指代','段落衔接','作者语气'],
               'style_ids':[s['id'] for s in styles],
               'guide':lock(OUT/'语言风格学习.md'),'examples':lock(OUT/'original_examples.md'),
               'application':lock(BASE/'templates/后续写作风格约定.md'),
               'author_variation_preserved':True,'fixed_sentence_length':None,
               'require_semantic_preservation':True,'copy_source_paragraphs':False,
               'allow_inventing_facts_for_style':False,
               'formal_resource_gate_status':'needs_review'}
    dump(OUT/'style_profile.json',profile)

    # Activate only after substantive style artifacts exist. Archive the exact
    # previous control entries, without mutating prior module versions/runs.
    regpath,confpath = CONTROL/'module_registry.json',CONTROL/'project_config.json'
    reg, conf = read(regpath),read(confpath)
    m = next(m for m in reg['modules'] if m['module_id']=='03')
    assert m['version']==3
    archive=OUT/'activation_before'
    archive.mkdir()
    (archive/'module_registry.json').write_bytes(regpath.read_bytes())
    (archive/'project_config.json').write_bytes(confpath.read_bytes())
    index=BASE.parent/'版本索引.md'
    (archive/'版本索引.md').write_bytes(index.read_bytes())
    m.update(version=4,path=BASE.relative_to(ROOT).as_posix())
    conf['shared_resources']['resource_manifests']['03']=(OUT/'resource_snapshot.json').relative_to(ROOT).as_posix()
    conf['writing']['language_style']={'profile_path':(OUT/'style_profile.json').relative_to(ROOT).as_posix(),
                                       'profile_sha256':sha(OUT/'style_profile.json'),
                                       'purpose':'学习并运用原语料的表达风格；保留意思与证据强度',
                                       'formal_resource_status':'needs_review'}
    dump(regpath,reg)
    dump(confpath,conf)
    index.write_text('''# 版本索引

当前版本：`v004_第4版`，由00第3版注册表启用。

- [第4版](v004_第4版/模块说明.md)：按用户澄清聚焦语言风格，15项写法、15组句子改写与5组段落练习；正式资源状态needs_review。
- [第3版](v003_第3版/模块说明.md)：语言与统计措辞审查候选，历史保留。
- [第2版](v002_第2版/模块说明.md)：一次性资源生命周期框架，历史保留。
- [第1版](v001_第1版/模块说明.md)：初始框架，历史保留。
''',encoding='utf-8')
    with (CONTROL/'CHANGELOG.md').open('a',encoding='utf-8') as f:
        f.write('\n## 2026-11-15 第三步语言风格修正\n\n根据用户澄清启用03第4版：重新聚焦用词、句法、节奏、衔接及作者语气，新增15项写法和20组原创练习。配置绑定style_profile哈希；旧研究不迁移，旧模块保留。技术检查见03第4版outputs/technical_validation.json；正式G3状态保持needs_review。\n')
    with (ROOT/'README.md').open('a',encoding='utf-8') as f:
        f.write('\n## 第三步当前入口：语言风格\n\n按2026-11-15澄清，03当前为第4版。主交付为[学到的语言风格](03_学术语言学习/v004_第4版/outputs/语言风格学习.md)及[原创句段练习](03_学术语言学习/v004_第4版/outputs/original_examples.md)。前面第3版入口为历史交付；当前版本和资源以注册表为准。\n')
    dump(OUT/'activation_record.json',{'date':'2026-11-15','from_module_version':3,'to_module_version':4,
                                      'previous_control_files':[lock(p) for p in archive.iterdir()],
                                      'active_registry':lock(regpath),'active_config':lock(confpath),
                                      'old_runs_migrated':False})
    gate={'gate':'G3','status':'needs_review','passed':False,'checked_at':STAMP,
          'style_study_status':'source_based_style_observations_and_original_practice_built',
          'counts':{'corpus_papers':20,'reviewed_passages':40,'style_patterns':15,
                    'sentence_exercises':15,'paragraph_exercises':5},
          'upstream_gate':lock(UP/'gate_report.json'),
          'note':'用户澄清已落实为表达风格学习；不将定向复读计为20篇连续全文精读认证。'}
    dump(OUT/'gate_report.json',gate)
    releasefiles=[p for p in OUT.glob('*') if p.is_file()]
    snapshot={'schema_version':1,'module_id':'03','module_version':4,'resource_version':2,
              'resource_snapshot_id':'language_style_r2_corpus20_v004','lifecycle':'build_once_reuse_many',
              'status':'needs_review','style_study_deliverable_available':True,
              'resource_available_for_formal_writing':False,
              'files':[lock(p) for p in sorted(releasefiles)],
              'business_gate_report':(OUT/'gate_report.json').relative_to(ROOT).as_posix(),
              'counts':gate['counts'],'created_at':STAMP}
    dump(OUT/'resource_snapshot.json',snapshot)
    inputs=[ROOT/n for n in ('AGENTS.md','基础要求.md','项目架构.md')]
    inputs += [OLD/'corpus_input_lock.json',OLD/'passage_candidates.json',UP/'gate_report.json',
               ROOT/'02_文章结构学习/v005_第5版/manifest.json',
               ROOT/'02_文章结构学习/v005_第5版/outputs/resource_snapshot.json',
               ROOT/'10_共享证据与契约/v002_第2版/manifest.json']
    inputs += sorted((BASE/'assets').glob('*.json'))
    dump(OUT/'run_manifest.json',{'run_id':'language_style_resource_r2','stage_id':'03','attempt':'attempt001',
                                'module_version':4,'schema_version':1,'status':'needs_review',
                                'input_files':[lock(p) for p in inputs],
                                'root_requirements_sha256':sha(ROOT/'基础要求.md'),
                                'config_sha256':sha(confpath),
                                'upstream_manifest_sha256':sha(ROOT/'02_文章结构学习/v005_第5版/manifest.json'),
                                'script_files':[lock(p) for p in sorted((BASE/'tools').glob('*.py'))],
                                'seed':20261115,'random_sampling':False,
                                'model':'Codex_session_agent_exact_backend_not_exposed',
                                'prompt_version':'style_learning_v2_user_clarification',
                                'environment':{'python':sys.version,'platform':platform.platform()},
                                'output_files':[lock(p) for p in sorted(OUT.glob('*')) if p.is_file()],
                                'gate_report':(OUT/'gate_report.json').relative_to(ROOT).as_posix(),
                                'exceptions':['G2 continuous reading and paragraph review not certified'],
                                'created_at':STAMP,'client_date':'2026-11-15','timezone':'Asia/Shanghai'})
    print(json.dumps(gate['counts'],ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
