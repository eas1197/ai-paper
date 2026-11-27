"""V14 qualitative manuscript contracts; no promotion to a formal research run."""
import json
from pathlib import Path

from manuscript07 import parse_structure, review
from language07 import style_findings
from runtime import file_lock, load, now, value_hash, verify_locks, write


def catalog(task):
    sources = {r['material_id']: r for r in task['materials']}
    sources.update({r['article_id']: r for r in task['literature']['rows'] if r.get('article_id')})
    theories = task['theories']
    if isinstance(theories, dict):
        theories = theories.get('rows', theories.get('theories', []))
    for row in theories:
        if isinstance(row, dict):
            key = row.get('theory_id') or row.get('id')
            if key:
                sources[key] = row
    return sources


def receive(task, draft):
    """Machine check a single manuscript, never deem it academically accepted."""
    errors = []
    if verify_locks(task['input_files']):
        raise ValueError('冻结研究输入已变化')
    if draft.get('pack_id') != value_hash(task) or not draft.get('authorship'):
        errors.append('稿件必须绑定当前证据包及起草者')
    text = draft['manuscript']
    profile = {'sections': [{'id': str(i), 'title': row['section']}
                            for i, row in enumerate(task['sections'], 1)]}
    sections, structure, counts, abstract_count = parse_structure(text, None, profile, errors)
    sources = catalog(task)
    refs = draft.get('references', [])
    refmap = {r['source_id']: r for r in refs}
    if len(refmap) != len(refs) or any(r['source_id'] not in sources or not r.get('entry')
                                     or not r.get('marker') for r in refs):
        errors.append('参考文献未唯一绑定已冻结的材料或文献')
    entries = {r.get('entry') for r in refs}
    if {line.strip() for line in sections.get('参考文献', '').splitlines() if line.strip()} != entries:
        errors.append('参考文献台账与正文不一致')
    dimensions = {r['dimension_id']: r for r in task['matrix']['rows']}
    claims = draft.get('claims', [])
    used, ids, covered, empirical_sections = set(), set(), set(), set()
    for claim in claims:
        ident, heading, anchor = claim['claim_id'], claim['section'], claim['text']
        source_ids = claim.get('source_ids', [])
        if not ident or ident in ids or not anchor.strip() or anchor not in sections.get(heading, '') or heading == '参考文献':
            errors.append(f'{ident} 主张无唯一正文定位')
        ids.add(ident)
        if claim.get('claim_type') not in {'direct', 'synthesis', 'inference', 'result'} or not claim.get('scope_limit'):
            errors.append(f'{ident} 缺主张类别或适用边界')
        if not source_ids or any(s not in sources for s in source_ids):
            errors.append(f'{ident} 缺冻结来源')
        for sid in source_ids:
            ref = refmap.get(sid)
            if not ref or ref['marker'] not in anchor:
                errors.append(f'{ident} 引文标记与来源不对应: {sid}')
            used.add(sid)
        if claim['claim_type'] == 'result':
            dim = claim.get('dimension_id')
            row = dimensions.get(dim, {})
            evid = {r['material_id'] for r in row.get('evidence', []) if r['relation'] != 'context'}
            if row.get('status') != 'tentative' or not source_ids or not set(source_ids) <= evid:
                errors.append(f'{ident} 实证结果未绑定有证据的矩阵维度')
            else:
                covered.add(dim)
                empirical_sections.add(heading)
    if not refs or used != set(refmap):
        errors.append('正文引文与参考文献须逐条对应')
    empirical = {'摘要', '五、经验发现', '六、讨论与结论'}
    if not empirical <= empirical_sections:
        errors.append('摘要、经验发现和结论必须绑定实证矩阵')
    if not {r['dimension_id'] for r in task['findings']} <= covered:
        errors.append('未覆盖冻结的主要发现')
    errors.extend(f"第{hit['line']}行 {hit['rule_id']}：{hit['match']}" for hit in style_findings(text))
    subject = {'pack_id': value_hash(task), 'draft': draft}
    return {'status': 'needs_revision' if errors else 'needs_review', 'errors': errors,
            'subject': subject, 'content_sha256': value_hash(subject),
            'section_characters': counts, 'abstract_characters': abstract_count}


REVIEW_CHECKS = ('research_question', 'literature', 'framework', 'method', 'evidence',
                 'counterexamples', 'claims_and_citations', 'language', 'conclusion')


def native_receipt(folder):
    """Read real CLI artifacts rather than trusting an asserted invocation ID."""
    folder = Path(folder)
    events = [json.loads(line) for line in (folder / 'events.jsonl').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    threads = [r['thread_id'] for r in events if r.get('type') == 'thread.started' and r.get('thread_id')]
    if len(threads) != 1 or not any(r.get('type') == 'turn.completed' for r in events):
        raise ValueError('未见完整独立 Codex 调用')
    if any(r.get('type') in {'turn.failed', 'error'} for r in events):
        raise ValueError('Codex 调用失败')
    return {'invocation_id': threads[0], 'files': [file_lock(folder / n) for n in
            ('events.jsonl', 'response.json', 'prompt.txt')]}


def independent_review(intake, response, receipt, prior_invocations):
    """Reuse V14 signoff; an independent verdict must bind the current draft."""
    if intake['status'] != 'needs_review':
        raise ValueError('技术门禁未通过，不可登记实质审查通过')
    ident = receipt['invocation_id']
    if not ident or ident in prior_invocations or verify_locks(receipt['files']):
        raise ValueError('审查调用重复或原始记录已变化')
    paths = {Path(r['path']).name: Path(r['path']) for r in receipt['files']}
    if set(paths) != {'events.jsonl', 'response.json', 'prompt.txt'} or native_receipt(paths['events.jsonl'].parent) != receipt:
        raise ValueError('审查缺完整原生凭证')
    if load(paths['response.json']) != response or intake['content_sha256'] not in paths['prompt.txt'].read_text(encoding='utf-8-sig'):
        raise ValueError('审查响应或提示与当前稿件不一致')
    if response.get('content_sha256') != intake['content_sha256']:
        raise ValueError('审查未绑定当前稿件')
    checks = response.get('checks', {})
    if set(checks) != set(REVIEW_CHECKS) or any(not isinstance(v, dict) or v.get('status') not in {'pass', 'revise'}
            or not str(v.get('reason', '')).strip() for v in checks.values()):
        raise ValueError('缺逐项实质审查依据')
    verdict = response.get('decision')
    if verdict not in {'accepted', 'revise', 'rejected'} or not str(response.get('assessment', '')).strip():
        raise ValueError('缺审查判断')
    issues = response.get('issues', [])
    if verdict == 'accepted' and (issues or any(v['status'] != 'pass' for v in checks.values())):
        raise ValueError('存在未修问题，不得通过')
    if verdict == 'revise' and (not issues or any(not isinstance(v, dict) or not v.get('location')
            or not v.get('reason') or not v.get('action') for v in issues)):
        raise ValueError('返修必须有定位、原因和具体动作')
    signoff = dict(response, reviewer='gpt-6.2-sol', reviewed_at=now()[:10], invocation_id=ident, receipt=receipt)
    if verdict == 'accepted':
        errors = []
        review(intake['subject'], signoff, errors)
        if errors:
            raise ValueError('; '.join(errors))
    return signoff
