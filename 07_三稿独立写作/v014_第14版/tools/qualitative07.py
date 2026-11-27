"""V14 qualitative manuscript contracts; no promotion to a formal research run."""
from manuscript07 import parse_structure
from language07 import style_findings
from runtime import value_hash, verify_locks


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
