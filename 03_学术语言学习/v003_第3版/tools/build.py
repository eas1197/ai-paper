"""Materialize reviewed language resources, preserving upstream G2 status.

No literature search, original-file mutation or empirical analysis is performed.
The semantic decisions in assets are authored after reading the candidates.
"""
import csv
import hashlib
import json
import platform
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
OUT = BASE / 'outputs/资源建设_attempt001'
UP = ROOT / '02_文章结构学习/v002_第2版/outputs/资源建设_20261114_attempt002'
NOW = datetime.now(timezone(timedelta(hours=8))).isoformat()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rel(path):
    return Path(path).relative_to(ROOT).as_posix()

def lock(path):
    return {'path': rel(path), 'sha256': sha(path)}

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text)
                   if not c.isspace() and unicodedata.category(c) not in ('Co', 'Cc', 'Cf'))

def csvout(path, rows, fields=None):
    fields = fields or list(rows[0])
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        w = csv.DictWriter(stream, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def main():
    if (OUT / 'run_manifest.json').exists():
        raise SystemExit('Attempt already materialized; use a new attempt for revision.')
    rules = read(BASE / 'assets/rules.json')
    decisions = read(BASE / 'assets/review_decisions.json')
    candidates = {c['candidate_id']: c for c in read(OUT / 'passage_candidates.json')}
    papers = {p['paper_id']: p for p in read(OUT / 'corpus_input_lock.json')}
    evidence = []
    selected = set()
    for cid, rule_ids, note, quote, role in decisions['selected']:
        assert cid not in selected, f'duplicate decision {cid}'
        selected.add(cid)
        c = candidates[cid]
        paper = papers[c['paper_id']]
        page = read(ROOT / c['pages_path'])[c['pdf_page']-1]
        assert page['pdf_page'] == c['pdf_page']
        start, end = max(0, c['char_start']-65), min(len(page['text']), c['char_end']+90)
        assert normalized(quote) in normalized(page['text'][start:end]), (cid, quote)
        assert len(quote) <= 12, (cid, quote)
        # Candidate paragraph boundaries are never certified as true paragraphs.
        evidence.append({
            'evidence_id': 'E_LANG_' + cid, 'candidate_id': cid,
            'source_id': 'S_ZOTERO_' + c['paper_id'].removeprefix('zotero_'),
            'paper_id': c['paper_id'], 'display_id': c['display_id'],
            'journal': paper['journal'], 'title': paper['title'],
            'rule_ids': rule_ids.split(';'), 'relationship': role,
            'evidence_type': 'direct',
            'direct_observation_paraphrase': note,
            'short_quote': quote,
            'extraction_method': 'upstream_pdf_page_text_then_agent_context_review',
            'review_status': 'agent_targeted_language_reviewed',
            'reviewer': 'Codex_current_session_single_agent',
            'checked_at': NOW,
            'locator': {'pdf_page': c['pdf_page'], 'printed_page': None,
                        'printed_page_unknown_reason': '本轮未统一复核印刷页，PDF页为有效主定位',
                        'section_candidates': c['section_candidates'],
                        'section_status': 'inherited_page_range_may_overlap',
                        'page_text_char_start': start, 'page_text_char_end': end,
                        'sentence_char_start': c['char_start'], 'sentence_char_end': c['char_end'],
                        'paragraph_number': None,
                        'paragraph_unknown_reason': '02几何候选段界未精校；用页内字符及短摘定位，不伪造自然段号',
                        'page_text_sha256': c['page_text_sha256'],
                        'passage_sha256': hashlib.sha256(page['text'][start:end].encode()).hexdigest(),
                        'normalization': 'NFKC; remove whitespace and Unicode Co/Cc/Cf for short-anchor matching only'},
            'source_files': {'pdf_path': paper['pdf_path'], 'pdf_sha256': paper['pdf_sha256'],
                             'pages_path': c['pages_path'], 'pages_sha256': paper['pages_sha256']},
            'fulltext_read_certification': 'not_certified_complete',
            'reuse_boundary': 'language_form_only; source empirical claims not endorsed or imported'
        })
    with (OUT / 'language_evidence.jsonl').open('w', encoding='utf-8') as stream:
        for e in evidence:
            stream.write(json.dumps(e, ensure_ascii=False) + '\n')

    rejectrows = []
    for cid, c in candidates.items():
        if cid in selected:
            continue
        rejectrows.append({'candidate_id': cid, 'paper_id': c['paper_id'],
                           'pdf_page': c['pdf_page'], 'decision': 'not_used_as_rule_evidence',
                           'reason': '本轮审读未选为规则依据：可能偏离动作、重复、句界/抽取不完整或局部语境不足；不计支持数',
                           'checked_at': NOW})
    csvout(OUT / 'unselected_candidates.csv', rejectrows)

    rule_rows = []
    for rule in rules:
        rid = rule['rule_id']
        ev = [e for e in evidence if rid in e['rule_ids']]
        support = [e for e in ev if e['relationship'] != 'caution']
        assert support, f'rule without positive corpus evidence: {rid}'
        ids = sorted({e['paper_id'] for e in support})
        row = {**rule,
               'evidence_ids': ';'.join(e['evidence_id'] for e in support),
               'paper_ids': ';'.join(ids),
               'frequency': len(ids),
               'frequency_definition': '所选、经定向审读的正向支持文献去重数；非全语料发生率或普遍性',
               'caution_evidence_ids': ';'.join(e['evidence_id'] for e in ev if e['relationship'] == 'caution'),
               'evidence_type': 'synthesis',
               'guardrail_evidence_type': 'inference_plus_project_requirements',
               'guardrail_source': 'AGENTS.md:5,8;基础要求.md:四,五,六',
               'review_status': 'agent_reviewed_candidate_pending_G2', 'checked_at': NOW}
        rule_rows.append(row)
    legacy_rule_fields = ['rule_id','rhetorical_move','rule_text','syntax_pattern','hedging',
                          'evidence_ids','paper_ids','frequency','scope','original_example',
                          'counterexample','preconditions','causal_strength','review_status']
    rule_fields = legacy_rule_fields + [k for k in rule_rows[0] if k not in legacy_rule_fields]
    csvout(OUT / 'language_rules.csv', rule_rows, rule_fields)
    csvout(BASE / 'templates/language_rules.csv', [], rule_fields)

    reviewrows = []
    for pid, paper in papers.items():
        ev = [e for e in evidence if e['paper_id'] == pid]
        reviewrows.append({'paper_id': pid, 'display_id': paper['display_id'], 'title': paper['title'],
                          'journal': paper['journal'], 'pdf_sha256': paper['pdf_sha256'],
                          'fulltext_available': True, 'source_pdf_hash_reverified': True,
                          'upstream_fulltext_read': paper['fulltext_read'],
                          'language_reading_scope': 'targeted_body_passages_with_context_not_continuous_fulltext',
                          'reviewed_evidence_n': len(ev),
                          'pdf_pages_reviewed': ';'.join(map(str, sorted({e['locator']['pdf_page'] for e in ev}))),
                          'evidence_ids': ';'.join(e['evidence_id'] for e in ev),
                          'checked_at': NOW})
    csvout(OUT / 'corpus_language_review.csv', reviewrows)

    # This is a demonstration audit of original synthetic examples, not a
    # sentence audit of a research manuscript or an endorsement of source claims.
    audit = []
    for r in rules:
        for kind, text, problem, revision, status in (
            ('original', r['original_example'], '无经验事实；占位信息不得当真实发现', '', 'illustrative_only'),
            ('counterexample', r['counterexample'], r['rule_text'], r['revision'], 'illustrative_revision_required')):
            audit.append({'draft_id': 'LANGUAGE_DEMO_NOT_RESEARCH_DRAFT',
                          'sentence_id': r['rule_id'] + '_' + kind, 'rule_id': r['rule_id'],
                          'claim_strength': r['causal_strength'], 'evidence_strength': 'synthetic_example_not_empirical',
                          'problem': problem, 'revision': revision, 'status': status,
                          'sentence_text': text, 'audit_scope': 'original_synthetic_examples_only',
                          'claim_id': 'not_applicable_synthetic', 'result_id': 'not_applicable_synthetic'})
    csvout(OUT / 'language_audit.csv', audit)
    csvout(BASE / 'templates/language_audit.csv', [], list(audit[0]))
    cautions = [e for e in evidence if e['relationship'] == 'caution']
    csvout(OUT / 'source_wording_cautions.csv', [
        {'evidence_id': e['evidence_id'], 'paper_id': e['paper_id'], 'pdf_page': e['locator']['pdf_page'],
         'rule_ids': ';'.join(e['rule_ids']), 'risk': e['direct_observation_paraphrase'],
         'status': 'local_wording_risk_not_whole_article_quality_judgment', 'checked_at': NOW}
        for e in cautions])

    examples = ['# 原创例句与反例库', '',
                '所有句子由本项目新写；不是原论文原句，不陈述已发生的实证结果。〔〕内为必须用证据填入的占位符。', '',
                '每条规则分别列出适用前提、句法、原创句、反例及改写方向；不能逐句机械套用。', '']
    handbook = ['# 定量社会学学术语言手册 · 候选资源第1版', '',
                f'核验时间：{NOW}。使用第二步同一20篇定量全文：7篇《中国社会科学》、13篇《社会学研究》。', '',
                '**状态：语言定向审读成果已构建；G3正式验收未通过。** 上游G2仍为needs_review，20篇连续精读与逐段精校未认证。', '',
                '本轮阅读的是181个正文候选句及邻接上下文；经语义审查选作规则依据的片段见证据表。完整PDF取得、定向语言审读、连续全文精读是三个不同状态。不得把本轮读片段计为20篇全文精读完成。', '',
                '## 如何使用', '',
                '1. 按正在完成的论证任务选规则，不按固定句序拼贴论文。',
                '2. 先核对事实、变量、结果和识别，再决定动词与限定语。',
                '3. 用原创表达完成论证；原文仅有极短锚点，具体依据沿evidence_id返回本地PDF。',
                '4. 正式写作仍由07冻结包绑定资源哈希；本候选快照不得作为已passed语言资源放行。', '',
                '## 证据如何理解', '',
                '- direct：论文中实际出现的词句组织及本轮释义；不保证源文章的每个实质判断正确。',
                '- synthesis：本项目把所选语料中的动作归纳为语言规则。规则不是原作者直接颁布的写作规范。',
                '- inference_plus_project_requirements：为满足根规范新增的统计、因果与事实约束，单列在每条规则下。',
                '- frequency仅为所选正向支持文献去重数，不是20篇中所有出现次数、两刊频率或普遍性估计。',
                '- PDF页从1开始，页内字符从0开始、右端开区间；印刷页与自然段号未复核时写未知。02的章节范围可能重叠，仅作导航。', '',
                '## 动词与证据强度', '',
                '|用途|可用表达|使用前提|', '|---|---|---|',
                '|定义|指、包括、在本文中限定为|明确出处与本文范围|',
                '|描述|分布、比例、呈现|有分母、时间、权重与实际统计|',
                '|关联|相关、在调整条件下关联|模型与实际结果可追溯|',
                '|理论预期|若、预期、据此提出|理论推导与可反驳条件，先于分析冻结|',
                '|候选机制|与…一致、可能解释|不能写成已识别因果机制|',
                '|因果结论|导致、使、因果效应|06的设计、假定与诊断确实支持|',
                '|证据不足|未获支持、尚不能区分|报告估计和区间，保留竞争结果|', '',
                '这张表是项目新增的使用约束；不把原论文的强措辞当作本项目强措辞的授权。', '',
                '## 论证动作与句法规则', '']
    for r, row in zip(rules, rule_rows):
        heading = f"## {r['rule_id']} {r['title']}"
        locs = []
        for e in evidence:
            if r['rule_id'] in e['rule_ids']:
                locs.append(f"{e['display_id']} PDF第{e['locator']['pdf_page']}页（{e['evidence_id']}；{e['relationship']}）")
        examples += [heading, '', f"论证动作：{r['rhetorical_move']}。", '',
                     f"前提：{r['preconditions']}", '', f"原创句：{r['original_example']}", '',
                     f"反例：{r['counterexample']}", '', f"改写方向：{r['revision']}", '',
                     f"句法：{r['syntax_analysis']}", '', f"语料定位：{'；'.join(locs)}。", '']
        handbook += [heading, '', r['rule_text'], '',
                     f"**句法及信息顺序：** {r['syntax_analysis']}", '',
                     f"**表达骨架：** {r['syntax_pattern']}", '',
                     f"**限定词：** {r['hedging']}", '',
                     f"**使用条件：** {r['preconditions']}", '',
                     f"**原创示例：** {r['original_example']}", '',
                     f"**反例与改写：** {r['counterexample']} → {r['revision']}", '',
                     f"**本项目新增约束：** {r['project_guardrail']}", '',
                     f"**正向支持文献数：** {row['frequency']}（仅限本轮已选片段）。", '',
                     f"**回查：** {'；'.join(locs)}。", '']
    (OUT / 'original_examples.md').write_text('\n'.join(examples), encoding='utf-8')
    (OUT / 'language_handbook.md').write_text('\n'.join(handbook), encoding='utf-8')

    terms = [
        ('理论假设','hypothesis','未冻结探索判断','事先可反驳预期','05冻结后保留版本'),
        ('相关/关联','association','因果效应','按实际设计使用','L08;L19'),
        ('发生比','odds_ratio','概率差或百分点','优势之比，概率差另算','L18'),
        ('百分点','percentage_point','百分比相对变化','概率或比例的绝对差','L18'),
        ('暴露率','exposure','已发生损害或替代','潜在受影响程度','L17'),
        ('生育行为','observed_fertility','生育意愿','由事件或子女数定义','L17'),
        ('家庭','analysis_field_or_unit','与资本维度直接并列','说明是场域或分析单位','L02;L05'),
        ('调节','moderation','一组显著另一组不显著','直接检验组间差异','L16'),
        ('中介','mediation','必然的因果机制','理论路径与识别另审','L08'),
        ('稳健','specified_sensitivity','普遍有效或没有内生性','仅就已实施替代检验而言','L22'),
        ('未获支持','not_supported','证明零效应','保留估计与区间','L14'),
        ('代理变量','proxy','概念被完全测量','写明覆盖与遗漏','L10;L23')
    ]
    csvout(OUT / 'terminology.csv', [dict(zip(['preferred_term','concept_key','avoid_equating_with','usage_boundary','rule_ids'], t)) for t in terms])

    # Each paper gets an actual reading note, not a copied paragraph dump.
    reports = OUT / '逐篇语言笔记'
    reports.mkdir(exist_ok=True)
    for pid, paper in papers.items():
        ev = [e for e in evidence if e['paper_id'] == pid]
        lines = [f"# {paper['display_id']} {paper['title']} · 语言定向审读", '',
                 f"来源：{paper['journal']}，{paper['year']}，{paper['issue']}。paper_id：{pid}。", '',
                 f"PDF SHA-256：{paper['pdf_sha256']}。核验时间：{NOW}。", '',
                 '本笔记仅记录已选正文片段及邻接语境的语言动作；不认证连续全文精读，不重用其经验数字。', '']
        for e in ev:
            lines += [f"## {e['evidence_id']}", '',
                      f"PDF第{e['locator']['pdf_page']}页；页内字符[{e['locator']['page_text_char_start']}, {e['locator']['page_text_char_end']})；自然段号未知。", '',
                      f"原文极短锚点：“{e['short_quote']}”。", '',
                      f"本轮观察释义：{e['direct_observation_paraphrase']}", '',
                      f"关联规则：{';'.join(e['rule_ids'])}；证据作用：{e['relationship']}。", '']
        (reports / f"{paper['display_id']}_语言笔记.md").write_text('\n'.join(lines), encoding='utf-8')

    upstream_gate = read(UP / 'gate_report.json')
    assert upstream_gate['status'] != 'passed', 'If G2 is upgraded, conduct new business review in a fresh attempt.'
    gate = {'gate': 'G3', 'status': 'needs_review', 'passed': False, 'checked_at': NOW,
            'artifact_review_status': 'agent_reviewed_language_candidate_built',
            'counts': {'corpus_pdfs': len(papers), 'journals': dict(Counter(p['journal'] for p in papers.values())),
                       'candidates_read_in_context': len(candidates), 'selected_evidence': len(evidence),
                       'unselected_candidates': len(rejectrows), 'rules': len(rules), 'original_examples': len(rules),
                       'counterexamples': len(rules), 'source_wording_cautions': len(cautions),
                       'fulltext_read_complete_certified_by_this_attempt': 0},
            'checks': {'same_20_paper_input': True, 'both_journals_present': True,
                       'rules_have_located_evidence': True, 'original_and_source_text_separate': True,
                       'all_actions_have_conditions_examples_counterexamples': True,
                       'null_and_causal_wording_rules_present': True,
                       'source_risks_not_promoted_to_templates': True,
                       'G2_passed': False, 'G2_paragraph_precision_certified': False},
            'upstream': {**lock(UP / 'gate_report.json'), 'status': upstream_gate['status']},
            'remaining': ['02的20篇连续全文精读与逐段精校须完成G2验收。',
                          '之后在新attempt中对本语言候选的上下文、段界和适用性作受影响复核，才可发布passed快照。'],
            'not_done': ['未执行04—07实质研究、统计分析或正式稿句子审查', '未发送任何外部消息或投稿'],
            'release_rule': 'Do not allow formal downstream writing on this candidate snapshot.'}
    write(OUT / 'gate_report.json', gate)
    acceptance = f"""# 第三步交付与验收记录

本轮已形成可审查的语言学习成果：20篇相同全文来源、{len(evidence)}条正文语言证据、{len(rules)}条规则、各{len(rules)}条原创例句和反例、20份逐篇笔记、术语表与例句审查表。来源哈希本轮重新核对；极短原句锚点与原创表达分离。

正式业务状态仍为 **needs_review**，G3未通过。上游G2明确记录连续全文精读认证为0篇、逐段精校认证为0篇。本轮定向语境审读不能替换这一要求；没有把20份PDF或181个关键词候选计成20篇全文已读。

## 本轮完成的检查

- 同一语料：7篇《中国社会科学》、13篇《社会学研究》，paper_id与原PDF SHA-256不变。
- 语言任务：定义、张力、综述、缺口、假设、测量、模型结果、机制、竞争解释及边界均有规则和使用条件。
- 句法层面：主谓、关系动词、限定语、转折、指代及旧信息到新信息顺序在规则内逐项说明。
- 原创性：例句为新写占位表达，不输出原论文连续段落，不移植原经验数字。
- 风险处理：发生比/概率、行为/意愿、不显著/政策无效等措辞单列审查，权威来源不免于核对。
- 频数：仅表示本轮已选、已审查片段中去重的正向支持文献数，不是语料整体频率。
- 自动核验：核对ID关联、页内锚点、源文件哈希、输出哈希、注册入口和状态；详见technical_validation.json。这些只证明技术一致性。

## 正式放行仍缺的条件

1. 02补完20篇连续全文精读及逐段精校并发布passed的G2输入。
2. 显式新建03的后续attempt，复核受影响的片段上下文和段落位置，记录新的输入哈希。
3. 通过G3业务复核后发布passed语言资源；不得修改本attempt伪装原输入已验收。

本版候选可供人工查阅与后续复核，不能替代正式冻结包中对已验收语言资源的要求。当前对话未使用外部模型API或个案数据，也未改变Zotero原件。
"""
    (OUT / '验收报告.md').write_text(acceptance, encoding='utf-8')

    inputs = [ROOT / n for n in ('AGENTS.md', '基础要求.md', '项目架构.md')]
    inputs += [ROOT / '02_文章结构学习/v005_第5版/manifest.json',
               ROOT / '02_文章结构学习/v005_第5版/outputs/resource_snapshot.json',
               UP / 'run_manifest.json', UP / 'gate_report.json', UP / 'corpus20.csv', UP / 'structure_moves.csv',
               ROOT / '10_共享证据与契约/v002_第2版/manifest.json',
               ROOT / '00_项目控制/v003_第3版/module_registry.json',
               ROOT / '00_项目控制/v003_第3版/project_config.json',
               BASE / 'manifest.json']
    inputs += [ROOT / p['pages_path'] for p in papers.values()]
    artifact_paths = sorted(p for p in OUT.rglob('*') if p.is_file()
                            and p.name not in ('passage_candidates.json','corpus_input_lock.json'))
    snapshot = {'schema_version': 1, 'module_id': '03', 'module_version': 3, 'resource_version': 1,
                'resource_snapshot_id': 'language_candidate_r1_corpus20_attempt001',
                'lifecycle': 'build_once_reuse_many', 'status': 'needs_review',
                'resource_available_for_formal_writing': False,
                'files': [lock(p) for p in artifact_paths],
                'business_gate_report': rel(OUT / 'gate_report.json'),
                'upstream_snapshot': lock(ROOT / '02_文章结构学习/v005_第5版/outputs/resource_snapshot.json'),
                'counts': gate['counts'], 'created_at': NOW,
                'note': 'Actual reviewed language candidate, not an accepted G3 resource. Original PDFs remain external/read-only.'}
    write(BASE / 'outputs/resource_snapshot.json', snapshot)
    manifest = {'run_id': 'language_resource_r1', 'stage_id': '03', 'attempt': 'attempt001',
                'module_version': 3, 'schema_version': 1, 'status': 'needs_review',
                'input_files': [lock(p) for p in inputs],
                'upstream_manifest_sha256': sha(ROOT / '02_文章结构学习/v005_第5版/manifest.json'),
                'upstream_run_manifest_sha256': sha(UP / 'run_manifest.json'),
                'root_requirements_sha256': sha(ROOT / '基础要求.md'),
                'config_sha256': sha(BASE / 'config.json'),
                'code_files': [lock(p) for p in sorted((BASE / 'tools').glob('*.py'))],
                'semantic_input_files': [lock(BASE / 'assets/rules.json'), lock(BASE / 'assets/review_decisions.json')],
                'environment': {'python': sys.version, 'platform': platform.platform(),
                                'external_model_api': None, 'individual_data_used': False},
                'model': 'Codex_session_agent; exact_backend_model_not_exposed',
                'prompt_version': 'language_review_v1', 'seed': 20261114, 'random_sampling_used': False,
                'output_files': [lock(p) for p in artifact_paths] + [lock(BASE / 'outputs/resource_snapshot.json'), lock(OUT / 'corpus_input_lock.json')],
                'gate_report': rel(OUT / 'gate_report.json'),
                'exceptions': ['G2 not passed; retained needs_review, no fulltext-read certification'],
                'created_at': NOW, 'timezone': 'Asia/Shanghai'}
    write(OUT / 'run_manifest.json', manifest)
    print(json.dumps(gate['counts'], ensure_ascii=False))

if __name__ == '__main__':
    main()
