"""Read-only discovery of language passages in the exact upstream 20-paper corpus.

Candidates are NOT evidence until the agent reviews the surrounding text and
records a decision. Offsets refer to the unmodified page text, not PDF geometry.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
UP = ROOT / '02_文章结构学习/v002_第2版/outputs/资源建设_20261114_attempt002'
OUT = BASE / 'outputs/资源建设_attempt001'
PATTERNS = {
    'concept': r'是指|指的是|定义为|所谓|区分为|界定',
    'tension': r'然而|但是|悖论|矛盾|值得.*关注',
    'literature': r'既有研究|已有研究|现有研究|现有文献|以往研究',
    'gap': r'忽视|尚未|不足|鲜有|局限|有待|缺乏',
    'hypothesis': r'假设[一二三四五六七八九123456789]|提出.*假设|预期',
    'measurement': r'测量|操作化|赋值|因变量|自变量|题目|指标',
    'result': r'模型[123456789一二三四五六七八九]|结果表明|结果显示|不显著|显著.*相关',
    'mechanism': r'中介|机制|路径|通过',
    'alternative': r'稳健|替代.*解释|选择性|内生性|排除|竞争',
    'boundary': r'局限|不足|未来.*研究|进一步.*研究|需要.*注意|值得.*注意|不能|尚不',
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    corpus = list(csv.DictReader((UP / 'corpus20.csv').open(encoding='utf-8-sig')))
    sections = list(csv.DictReader((UP / 'structure_moves.csv').open(encoding='utf-8-sig')))
    candidates = []
    inventory = []
    for paper in corpus:
        key = paper['paper_id'].removeprefix('zotero_')
        pagefile = UP / 'fulltext' / key / 'pages.json'
        pages = json.loads(pagefile.read_text(encoding='utf-8-sig'))
        pdf = Path(paper['pdf_path'])
        assert sha(pdf) == paper['pdf_sha256'], f'PDF changed: {key}'
        inventory.append({**paper, 'pages_path': pagefile.relative_to(ROOT).as_posix(),
                          'pages_sha256': sha(pagefile), 'pdf_hash_reverified': True})
        used = set()
        for move, pattern in PATTERNS.items():
            pool = []
            for page in pages[:int(paper['body_pdf_last_page'])]:
                text = page['text']
                for match in re.finditer(r'[^。！？]+[。！？]', text):
                    sentence = match.group()
                    clean = re.sub(r'\s+', '', sentence)
                    if not re.search(pattern, clean) or not 22 <= len(clean) <= 270:
                        continue
                    # Do not use the abstract on page 1. Prefer body pages for
                    # theoretical moves, later pages for result/boundary moves.
                    if page['pdf_page'] == 1:
                        continue
                    pos = page['pdf_page'] / int(paper['body_pdf_last_page'])
                    target = .8 if move in ('result', 'alternative', 'boundary') else (.55 if move == 'measurement' else .3)
                    score = -abs(pos - target) * 3
                    score += 2 if move == 'hypothesis' and re.search(r'假设[一二三四五六七八九123456789]', clean) else 0
                    score += 1 if move == 'boundary' and re.search(r'局限|不足|未来|不能|尚不', clean) else 0
                    score -= 3 if re.search(r'［|\[|参考文献|研究论', clean[:12]) else 0
                    if (page['pdf_page'], match.start()) in used:
                        score -= 10
                    pool.append((score, page, match))
            if not pool:
                continue
            _, page, match = max(pool, key=lambda v: v[0])
            used.add((page['pdf_page'], match.start()))
            sec = [s['section_title'] for s in sections if s['paper_id'] == paper['paper_id'] and int(s['page_start']) <= page['pdf_page'] <= int(s['page_end'])]
            candidates.append({
                'candidate_id': f"{paper['display_id']}_{move}", 'paper_id': paper['paper_id'],
                'display_id': paper['display_id'], 'move_candidate': move,
                'pdf_page': page['pdf_page'], 'section_candidates': sec,
                'char_start': match.start(), 'char_end': match.end(),
                'text': match.group(),
                'context_before': page['text'][max(0, match.start()-120):match.start()],
                'context_after': page['text'][match.end():match.end()+130],
                'pages_path': pagefile.relative_to(ROOT).as_posix(),
                'page_text_sha256': hashlib.sha256(page['text'].encode()).hexdigest(),
                'status': 'automatic_candidate_unreviewed',
            })
    (OUT / 'corpus_input_lock.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    # Intermediate candidate file stays distinct from certified evidence.
    (OUT / 'passage_candidates.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'papers': len(inventory), 'candidates': len(candidates)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
