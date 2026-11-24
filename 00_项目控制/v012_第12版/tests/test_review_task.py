import hashlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from review_task import prepare_review_task, STAGES


class ReviewTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.work = root / 'runs' / 'demo'
        self.work.mkdir(parents=True)
        self.state = {'run_id': 'demo', 'status': 'preliminary_review', 'theme': 'Question', 'question': None}
        self.put('run_manifest.json', {'run_id': 'demo'})
        self.put('initial/literature_matrix.json', {})
        self.put('initial/theories.json', {})
        self.put('merged_literature.json', {})
        self.put('staged_topic.json', self.state)
        for name in ('policy.json', 'prompt.md'):
            (root / name).write_text('{}')
        self.schema = root / 'schema.json'
        self.schema.write_text('{}')
        self.h = types.SimpleNamespace(ROOT=root, RUNS=root/'runs', V3_POLICY=root/'policy.json', V3_SEARCH_PROMPT=root/'prompt.md', doctor=lambda: None, state_of=lambda _: dict(self.state), sha=lambda p: hashlib.sha256(p.read_bytes()).hexdigest(), read=lambda p: json.loads(p.read_text()), original_command=lambda *a: a, original_call=self.original)
        self.contract = types.SimpleNamespace(heritage=self.h, run_mode=types.SimpleNamespace(verified_run=lambda _: {'run_id': 'demo'}), _digest=lambda v: hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest(), _atomic_json=self.write, freeze_packet=lambda p, **k: {'snapshot_sha256':'candidate'}, verify_snapshot=lambda *a,**k: None)
        self.addCleanup(patch.stopall)
        patch.dict(sys.modules, {'task_packet': self.contract}).start()
        patch('review_task.__file__', str(root/'tools'/'review_task.py')).start()
        (root/'schemas').mkdir()
        (root/'schemas'/'review_result.schema.json').write_text('{}')

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def put(self, name, value):
        self.write(self.work/name, value)

    def original(self, args):
        final = self.state['status'] == 'final_review' or self.state.get('review_phase') == 'final'
        return json.dumps({'status':self.state['status'], 'question':self.state.get('question'), 'evidence_sha256':'digest', 'papers':str(self.work/('merged_literature.json' if final else 'initial/literature_matrix.json')), 'theories':str(self.work/'initial/theories.json'), 'review_scope':'Original scope'})

    def stage(self, name):
        self.state['status'] = name
        self.put('staged_topic.json', self.state)

    def task(self):
        result = prepare_review_task('demo')
        return result, json.loads((self.work/result['context_path']).read_text())

    def test_three_stages(self):
        for stage, (kind, _) in STAGES.items():
            self.stage(stage)
            result, ctx = self.task()
            self.assertEqual(ctx['review_kind'], kind)
            self.assertEqual(result['task_packet']['stage_id'], stage)
            self.assertFalse(result['dispatch_authorized'])
            self.assertEqual(result['task_packet']['time_budget_seconds'], 0)
            self.assertEqual(result['task_packet']['search_levels'], [])
            self.assertIn('merged_literature.json' if stage=='final_review' else 'initial/literature_matrix.json', ctx['evidence_scope']['allowed_ids'])

    def test_not_due(self):
        self.stage('frozen')
        with self.assertRaises(ValueError): self.task()

    def test_missing_required(self):
        self.state['reality_first']=True
        self.stage('design_review')
        with self.assertRaises(OSError): self.task()

    def test_wrong_original_path(self):
        original = json.loads(self.original(None))
        original['papers'] = str(self.work/'merged_literature.json')
        self.h.original_call=lambda _: json.dumps(original)
        with self.assertRaises(ValueError): self.task()

    def test_original_evidence_required(self):
        original = json.loads(self.original(None)); original.pop('evidence_sha256')
        self.h.original_call=lambda _: json.dumps(original)
        with self.assertRaises(ValueError): self.task()

    def test_pending_material(self):
        self.state['qual_search_receipts']=True
        self.stage('design_review')
        self.put('qualitative/attempt_001/conversion.json', {})
        result, ctx = self.task()
        self.assertIn('attempt_001', ctx['evidence_scope']['excluded_or_pending_ids'])
        self.assertNotIn('attempt_001', ctx['evidence_scope']['allowed_ids'])

    def test_state_mutation(self):
        original = self.original
        def mutate(args):
            response=original(args)
            self.state['question']='changed'
            return response
        self.h.original_call=mutate
        with self.assertRaises(ValueError): self.task()

    def test_context_stable(self):
        a,_=self.task(); b,_=self.task()
        self.assertEqual(a,b)


if __name__ == '__main__': unittest.main()
