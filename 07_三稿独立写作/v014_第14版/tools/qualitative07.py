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
            key = row.get('theory_id') or row.get('id') or ('T_' + value_hash(row)[:20])
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
    limit = task.get('writing_budget', {}).get('max_words')
    if limit is not None and sum(counts.values()) > limit:
        errors.append(f'正文超出本实验冻结篇幅上限 {limit}')
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
    if load(folder / 'login_status.json') != {'chatgpt': True}:
        raise ValueError('缺原生 ChatGPT 登录检查记录')
    return {'invocation_id': threads[0], 'files': [file_lock(folder / n) for n in
            ('events.jsonl', 'response.json', 'prompt.txt', 'login_status.json')]}


def independent_review(intake, response, receipt, prior_invocations):
    """Reuse V14 signoff; an independent verdict must bind the current draft."""
    if intake['status'] != 'needs_review':
        raise ValueError('技术门禁未通过，不可登记实质审查通过')
    ident = receipt['invocation_id']
    if not ident or ident in prior_invocations or verify_locks(receipt['files']):
        raise ValueError('审查调用重复或原始记录已变化')
    paths = {Path(r['path']).name: Path(r['path']) for r in receipt['files']}
    if set(paths) != {'events.jsonl', 'response.json', 'prompt.txt', 'login_status.json'} or native_receipt(paths['events.jsonl'].parent) != receipt:
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


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


STRING = {'type': 'string'}
def array(items):
    return {'type': 'array', 'items': items}


DRAFT_SCHEMA = obj({'pack_id': STRING, 'authorship': STRING, 'manuscript': STRING,
                    'references': array(obj({'source_id': STRING, 'marker': STRING, 'entry': STRING})),
                    'claims': array(obj({'claim_id': STRING, 'section': STRING, 'text': STRING,
                                         'claim_type': STRING, 'scope_limit': STRING, 'source_ids': array(STRING),
                                         'dimension_id': STRING}))})
REVIEW_SCHEMA = obj({'content_sha256': STRING, 'decision': STRING, 'assessment': STRING,
                     'checks': obj({k: obj({'status': STRING, 'reason': STRING}) for k in REVIEW_CHECKS}),
                     'issues': array(obj({'location': STRING, 'reason': STRING, 'action': STRING}))})


def native_provider(role, request, folder):
    """Use the original separate, ephemeral Codex invocation adapter."""
    from codex_literature import cli_executable, invoke
    folder.mkdir(parents=True, exist_ok=False)
    schema = folder / 'schema.json'
    write(schema, REVIEW_SCHEMA if role == 'review' else DRAFT_SCHEMA)
    instruction = ('独立审稿。逐项核对源证据、理论增量、竞争解释、论证和语言；不得为通过而放宽标准。'
                   '仅全部实质检查通过时 accepted；否则 revise（给出具体定位和动作）或 rejected。'
                   if role == 'review' else
                   '依据冻结材料和原语言规则撰写完整定性论文；六节标题使用一、至六、的顺序，'
                   '摘要和结果、结论绑定真实矩阵。提供逐条主张及来源定位台账，不得虚构。'
                   '若有返修任务，按其逐项修改整个稿件，不得改变冻结结论与证据强度。')
    prompt = instruction + '\n' + json.dumps(request, ensure_ascii=False)
    code = invoke(cli_executable(), folder, prompt, schema, timeout=1800, model='gpt-6.2-sol')
    if code != 0:
        raise RuntimeError(f'Codex {role} 退出码 {code}；保存原始日志')
    response = load(folder / 'response.json')
    return response, native_receipt(folder)


def author_context(task):
    from s08_inputs07 import ROOT
    return {**task, 'pack_id': value_hash(task), 'source_catalog': catalog(task), 'language_texts': {
        name: (ROOT / rec['path']).read_text(encoding='utf-8-sig')
        for name, rec in task['language_style']['resources'].items() if name != 'profile'}}


def run_loop(task, work, provider=native_provider, context=None):
    """One initial draft plus at most two corrections; never accept on machine checks alone."""
    work = Path(work)
    work.mkdir(parents=True, exist_ok=False)
    write(work / 'writing_task.json', task)
    context = author_context(task) if context is None else context
    used = set(task.get('prior_invocations', [])) | {task.get('matrix_review', {}).get('invocation_id')}
    history, previous, feedback = [], None, None
    final_status = 'needs_review'
    revisions = task.get('writing_budget', {}).get('revisions', 2)
    if type(revisions) is not int or not 0 <= revisions <= 2:
        raise ValueError('定性返修预算超出原研究规则')
    try:
        for number in range(1, 2 + revisions):
            folder = work / f'attempt_{number:03d}'
            folder.mkdir()
            request = {'task': context, 'previous_draft': previous, 'revision_requirements': feedback}
            draft, author_receipt = provider('draft', request, folder / 'author')
            ident = author_receipt['invocation_id']
            if (not ident or ident in used or verify_locks(author_receipt['files'])
                    or native_receipt(folder / 'author') != author_receipt
                    or load(folder / 'author/response.json') != draft):
                raise ValueError('起草调用重复或凭证已变化')
            used.add(ident)
            intake = receive(task, draft)
            if previous is not None and draft['manuscript'] == previous['manuscript']:
                intake['errors'].append('返修稿未实际修改正文')
                intake['status'] = 'needs_revision'
            write(folder / 'intake.json', intake)
            write(folder / 'author_receipt.json', author_receipt)
            (folder / 'manuscript.md').write_text(draft['manuscript'], encoding='utf-8')
            row = {'attempt': number, 'intake': intake['status'], 'author_invocation': ident}
            history.append(row)
            previous = draft
            if intake['errors']:
                feedback = {'machine_errors': intake['errors']}
            else:
                response, receipt = provider('review', {'task': context, 'draft': draft,
                    'content_sha256': intake['content_sha256']}, folder / 'reviewer')
                signoff = independent_review(intake, response, receipt, used)
                used.add(signoff['invocation_id'])
                write(folder / 'quality_review.json', signoff)
                row.update(review=signoff['decision'], review_invocation=signoff['invocation_id'])
                if signoff['decision'] == 'accepted':
                    final_status = 'passed'
                    feedback = None
                    break
                if signoff['decision'] == 'rejected':
                    final_status = 'rejected'
                    break
                feedback = {'independent_review': signoff['issues']}
            write(work / 'checkpoint.json', {'status': 'needs_revision', 'history': history, 'feedback': feedback})
        else:
            final_status = 'needs_revision'
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
        final_status = 'blocked'
        feedback = {'error': str(exc)}
    report = {'status': final_status, 'scope': 'experimental', 'formal_eligible': False,
              'pack_id': value_hash(task), 'history': history, 'feedback': feedback,
              'business_quality_automatic': False, 'submission_enabled': False,
              'output_files': [file_lock(p) for p in sorted(work.rglob('*')) if p.is_file()]}
    write(work / 'qualitative_gate.json', report)
    return {**report, 'attempt_path': str(work)}


def publish_current(work):
    work = Path(work).resolve()
    write(work.parent / 'current_qualitative.json', {'attempt': work.name,
                                                    'gate': file_lock(work / 'qualitative_gate.json')})


def validate_delivery(work):
    work = Path(work).resolve()
    current = load(work.parent / 'current_qualitative.json')
    if current['attempt'] != work.name or current['gate'] != file_lock(work / 'qualitative_gate.json'):
        raise ValueError('只允许当前有效的定性稿件')
    if work.name.startswith('attempt_') and any(p.is_dir() and p.name > work.name for p in work.parent.glob('attempt_*')):
        raise ValueError('已有更新尝试，旧稿交付失效')
    report = load(work / 'qualitative_gate.json')
    task = load(work / 'writing_task.json')
    if report['pack_id'] != value_hash(task) or verify_locks(task['input_files'] + report['output_files']):
        raise ValueError('定性论文证据或产物已变化')
    if report['status'] != 'passed':
        return report
    if not report['history'] or report['history'][-1].get('review') != 'accepted':
        raise ValueError('缺最终独立通过记录')
    latest = report['history'][-1]
    folder = work / f"attempt_{latest['attempt']:03d}"
    draft = load(folder / 'author/response.json')
    intake = receive(task, draft)
    if intake != load(folder / 'intake.json') or draft['manuscript'] != (folder / 'manuscript.md').read_text(encoding='utf-8'):
        raise ValueError('最终稿件与技术门禁记录不一致')
    prior = set(task.get('prior_invocations', [])) | {task.get('matrix_review', {}).get('invocation_id')}
    for row in report['history']:
        for field in ('author_invocation', 'review_invocation'):
            ident = row.get(field)
            if ident and not (row == latest and field == 'review_invocation'):
                if ident in prior:
                    raise ValueError('独立调用重复')
                prior.add(ident)
    response = load(folder / 'reviewer/response.json')
    signoff = load(folder / 'quality_review.json')
    receipt = native_receipt(folder / 'reviewer')
    check = independent_review(intake, response, receipt, prior)
    # Validation may occur after the review date; preserve the original date.
    check['reviewed_at'] = signoff['reviewed_at']
    if check != signoff or signoff['decision'] != 'accepted':
        raise ValueError('最终独立审查与稿件不一致')
    return report


def export_delivery(work):
    report = validate_delivery(work)
    if report['status'] != 'passed':
        raise ValueError('未通过独立审查，不得交付论文')
    final = Path(work) / f"attempt_{report['history'][-1]['attempt']:03d}"
    return {'status': 'passed', 'destination': 'experimental_single_delivery', 'scope': 'experimental',
            'formal_eligible': False, 'submission_enabled': False,
            'files': {name: str(final / name) for name in ('manuscript.md', 'intake.json', 'quality_review.json')}}
