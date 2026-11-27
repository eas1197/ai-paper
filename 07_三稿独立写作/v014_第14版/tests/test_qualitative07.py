"""Synthetic contract tests only; no research or model execution."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from test_stage07 import stage07
from runtime import value_hash
import qualitative07 as qual


def fixture():
    names = ['问题的提出', '文献回顾', '理论分析框架', '资料与方法', '经验发现', '讨论与结论']
    row = {'dimension_id': 'D1', 'status': 'tentative',
           'evidence': [{'material_id': 'M1', 'relation': 'support'}]}
    task = {'input_files': [], 'sections': [{'section': n} for n in names],
            'materials': [{'material_id': 'M1'}], 'literature': {'rows': []}, 'theories': [],
            'matrix': {'rows': [row]}, 'findings': [row]}
    headings = [f'{i}、{n}' for i, n in zip('一二三四五六', names)]
    sentence = '规则文本显示条件差异（材料一）。'
    text = '# 制度规则比较\n\n## 摘要\n' + sentence + '\n关键词：规则；条件；组织；比较\n'
    text += ''.join(f'\n## {h}\n{sentence}\n' for h in headings)
    text += '\n## 参考文献\n材料一：公开规则。\n'
    draft = {'pack_id': value_hash(task), 'authorship': 'fixture', 'manuscript': text,
             'references': [{'source_id': 'M1', 'marker': '（材料一）', 'entry': '材料一：公开规则。'}],
             'claims': [{'claim_id': str(i), 'section': h, 'text': sentence,
                         'claim_type': 'result', 'scope_limit': '书面规则', 'source_ids': ['M1'],
                         'dimension_id': 'D1'} for i, h in enumerate(['摘要', headings[4], headings[5]])]}
    return task, draft


class IntakeTest(unittest.TestCase):
    def test_structural_and_empirical_intake(self):
        task, draft = fixture()
        result = qual.receive(task, draft)
        self.assertEqual(result['status'], 'needs_review', result['errors'])

    def test_reject_wrong_dimension_and_forged_source(self):
        task, draft = fixture()
        altered = copy.deepcopy(draft)
        altered['claims'][0]['dimension_id'] = 'unknown'
        altered['claims'][1]['source_ids'] = ['unknown']
        self.assertEqual(qual.receive(task, altered)['status'], 'needs_revision')

    def test_reject_missing_section_and_wrong_pack(self):
        task, draft = fixture()
        draft['pack_id'] = 'wrong'
        draft['manuscript'] = draft['manuscript'].replace('## 五、经验发现', '## 删除')
        self.assertEqual(qual.receive(task, draft)['status'], 'needs_revision')


def review_fixture(folder, subject, decision='accepted', thread='fixture-review'):
    folder.mkdir(parents=True, exist_ok=True)
    result = {'content_sha256': subject['content_sha256'], 'decision': decision,
              'assessment': 'fixture only', 'checks': {k: {'status': 'pass', 'reason': 'fixture'} for k in qual.REVIEW_CHECKS},
              'issues': [] if decision == 'accepted' else [{'location': '摘要', 'reason': 'fixture', 'action': 'revise'}]}
    (folder / 'response.json').write_text(json.dumps(result), encoding='utf-8')
    (folder / 'prompt.txt').write_text(subject['content_sha256'], encoding='utf-8')
    (folder / 'events.jsonl').write_text('\n'.join(map(json.dumps, [{'type': 'thread.started', 'thread_id': thread},
                                    {'type': 'turn.completed'}])), encoding='utf-8')
    return result, qual.native_receipt(folder)


class ReviewTest(unittest.TestCase):
    def test_independent_review_and_reject_reused_or_tampered_receipt(self):
        task, draft = fixture()
        intake = qual.receive(task, draft)
        with tempfile.TemporaryDirectory() as folder:
            response, receipt = review_fixture(Path(folder), intake)
            self.assertEqual(qual.independent_review(intake, response, receipt, set())['decision'], 'accepted')
            with self.assertRaises(ValueError):
                qual.independent_review(intake, response, receipt, {'fixture-review'})
            response['assessment'] = 'changed'
            with self.assertRaises(ValueError):
                qual.independent_review(intake, response, receipt, set())


class LoopTest(unittest.TestCase):
    def test_review_revision_and_fresh_recheck(self):
        task, draft = fixture()
        calls = []
        def provider(role, request, folder):
            calls.append((role, request))
            ident = f'fixture-{len(calls)}'
            if role == 'review':
                return review_fixture(folder, request, 'revise' if len(calls) == 2 else 'accepted', ident)
            folder.mkdir(parents=True)
            response = copy.deepcopy(draft)
            if request['revision_requirements']:
                response['manuscript'] = response['manuscript'].replace('制度规则比较', '制度规则与条件比较')
            (folder / 'response.json').write_text(json.dumps(response), encoding='utf-8')
            (folder / 'prompt.txt').write_text('fixture only', encoding='utf-8')
            (folder / 'events.jsonl').write_text('\n'.join(map(json.dumps, [{'type': 'thread.started', 'thread_id': ident},
                                                 {'type': 'turn.completed'}])), encoding='utf-8')
            return response, qual.native_receipt(folder)
        with tempfile.TemporaryDirectory() as folder:
            result = qual.run_loop(task, Path(folder) / 'run', provider, context=task)
            self.assertEqual(result['status'], 'passed', result)
            self.assertEqual([r['review'] for r in result['history']], ['revise', 'accepted'])
            self.assertIn('independent_review', calls[2][1]['revision_requirements'])
            self.assertNotEqual(result['history'][0]['review_invocation'], result['history'][1]['review_invocation'])
