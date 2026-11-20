"""核对本次候选资源的来源、链接与计数；不将技术核对升级为科研验收。"""
from pathlib import Path
import csv, hashlib, json, platform, re, sys
from datetime import datetime, timezone, timedelta
from importlib.metadata import version
from annotations import PAPERS, ABSTRACT_NOTES

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[3]
NOW = datetime.now(timezone(timedelta(hours=8))).isoformat()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(name, value):
    (ROOT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')

def rows(name):
    with (ROOT/name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

corpus = rows('corpus20.csv')
sections = rows('structure_moves.csv')
abstracts = rows('abstract_sentences.csv')
evidence = [json.loads(line) for line in (ROOT/'evidence.jsonl').read_text(encoding='utf8').splitlines()]
eids = [row['evidence_id'] for row in evidence]
problems = []
inputs = []
for p,c in zip(PAPERS,corpus):
    source = Path(c['pdf_path'])
    actual = sha(source)
    if actual != c['pdf_sha256']:
        problems.append(f'{p["label"]}: original PDF hash changed')
    inputs.append(dict(role='selected_original_pdf',paper_id=c['paper_id'],path=str(source),sha256=actual))
    cache = Path('C:/Users/hou/Zotero/storage')/p['key']/'.zotero-ft-cache'
    inputs.append(dict(role='zotero_text_cache',paper_id=c['paper_id'],path=str(cache),sha256=sha(cache)))
    covered = set()
    for heading,a,b,*_ in p['sections']:
        if not 1 <= a <= b <= p['body_end']:
            problems.append(f'{p["label"]}: invalid section page range')
        covered.update(range(a,b+1))
    if covered != set(range(1,p['body_end']+1)):
        problems.append(f'{p["label"]}: uncovered body PDF page')
    ar = [r for r in abstracts if r['display_id']==p['label']]
    if len(ar)!=len(ABSTRACT_NOTES[p['label']]) or [int(r['sentence_no']) for r in ar]!=list(range(1,len(ar)+1)):
        problems.append(f'{p["label"]}: abstract alignment mismatch')

registry=json.loads((PROJECT/'00_项目控制/v002_第2版/module_registry.json').read_text(encoding='utf8'))
upstream_paths=[m['path']+'/manifest.json' for m in registry['modules'] if m['module_id'] in ('10','11')]
for name in ['AGENTS.md','基础要求.md','项目架构.md',
             '02_文章结构学习/v002_第2版/模块说明.md',
             '02_文章结构学习/v002_第2版/manifest.json',
             '00_项目控制/v002_第2版/module_registry.json']+upstream_paths:
    path = PROJECT/name
    if not path.exists():
        problems.append('missing configuration input: '+str(path))
    else:
        inputs.append(dict(role='requirements_or_upstream_manifest',path=str(path),sha256=sha(path)))

if len(corpus)!=20 or len(set(c['pdf_sha256'] for c in corpus))!=20:
    problems.append('20 unique PDFs not established')
if len(sections)!=117 or len(abstracts)!=96:
    problems.append('coding counts differ from current report')
if len(eids)!=len(set(eids)):
    problems.append('duplicate evidence ID')
for row in sections+abstracts:
    if row['evidence_id'] not in eids:
        problems.append('unresolved evidence reference '+row['evidence_id'])

config = dict(stage='02',module_version=2,attempt=2,resource_candidate_version=1,
    authorized_source_root='C:/Users/hou/Zotero/storage',source_access='read_only',
    target_journals=['中国社会科学','社会学研究'],target_count=20,
    selection='purposeful; both journals, quantitative empirical design, complete source PDFs',
    paragraph_status='automatic_candidates_not_semantically_reviewed',
    abstraction='sections and abstract sentences coded individually in current Codex conversation',
    sentence_boundary='Chinese full stop/question/exclamation or ASCII question mark; semicolons retained within sentence',
    external_network_used=False,originals_modified=False,random_seed=None,
    model=dict(provider='Codex desktop current conversation',exact_model_version='not_exposed_in_runtime',separate_api_calls=False),
    prompt_version='user_request_20261114_and_explicit_storage_expansion',
    status='needs_review',published=False)
write('run_config.json', config)

# Manifest will be written below; all other Markdown destinations must already exist.
link_n=0
for md in [ROOT/'阅读入口.md',ROOT/'structure_handbook.md',*sorted((ROOT/'reports').glob('*.md'))]:
    for dest in re.findall(r'\]\(<([^>]+)>\)',md.read_text(encoding='utf8')):
        link_n += 1
        path = Path(dest)
        if path.name!='run_manifest.json' and not path.exists():
            problems.append(f'broken local link: {md.name} -> {dest}')

audit=dict(checked_at=NOW,technical_checks_passed=not problems,problems=problems,
    unique_source_pdfs=len(set(c['pdf_sha256'] for c in corpus)),
    original_pdf_hashes_recalculated=True,section_units=len(sections),abstract_sentences=len(abstracts),
    evidence_records=len(evidence),markdown_local_links_checked=link_n,
    all_body_pdf_pages_in_section_ranges=True,
    abstract_sentence_alignment_checked=True,
    visual_checks=['P02/P04/P05/P07 first pages','P13 PDF19 rotated table','P15 PDF1 and PDF17: two abstract/body inconsistencies'],
    research_gate_status='needs_review',
    limitation='Source hash, page-range coverage and link checks do not establish paragraph semantics or full-text reading completion.')
write('technical_validation.json',audit)

scripts=[dict(path=str(p),sha256=sha(p)) for p in sorted((ROOT/'scripts').glob('*.py'))]
outputs=[dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(ROOT.rglob('*'))
         if p.is_file() and p.name!='run_manifest.json' and '__pycache__' not in p.parts]
manifest=dict(run_id='resource_structure_20261114',stage_id='02',attempt=2,module_version=2,schema_version=1,
    resource_candidate_version=1,status='needs_review',published=False,verified_at=NOW,
    input_files=inputs,config_sha256=sha(ROOT/'run_config.json'),
    root_requirements_sha256=sha(PROJECT/'基础要求.md'),
    upstream_manifest_hashes=[x for x in inputs if x['role']=='requirements_or_upstream_manifest'],
    prompt_and_model=config['model']|dict(prompt_version=config['prompt_version']),
    scripts=scripts,runtime=dict(python=sys.version,platform=platform.platform(),
        pdfplumber=version('pdfplumber'),pdfminer_six=version('pdfminer.six')),
    random_seed=None,output_files=outputs,gate_report=str(ROOT/'gate_report.json'),
    exceptions=['P15 abstract/body directions disagree for intergenerational companionship and public services',
                'P13 PDF19 is an inserted rotated table with no extracted text',
                'Paragraph candidates are not reviewed; no fulltext_read=complete certification'],
    certification='Technical audit only. No G2 passed resource snapshot was published.')
write('run_manifest.json',manifest)
print(json.dumps(audit,ensure_ascii=False))
if problems:
    raise SystemExit(1)
