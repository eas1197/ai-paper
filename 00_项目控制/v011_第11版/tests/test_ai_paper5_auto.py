"""Offline checks: no network, model token, or fake research content required."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

CODE = Path(__file__).resolve().parents[1] / 'tools/ai_paper5_auto.py'
spec = importlib.util.spec_from_file_location('ai_paper5_auto', CODE)
auto = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = auto
spec.loader.exec_module(auto)


class TinyCore:
    STAGES = ('topic_candidates', 'reality', 'event_comparison')
    def start(self, work, run_id):
        Path(work).mkdir()
        auto.save_json(Path(work) / 'manifest.json', {'run_id':run_id,'stages':{},'stage_order':list(self.STAGES)})
    def status(self, work):
        m = auto.read_json(Path(work)/'manifest.json')
        return {'recorded':list(m['stages']), 'technical_complete':len(m['stages']) == len(self.STAGES)}
    def ingest(self, work, stage, path):
        m = auto.read_json(Path(work)/'manifest.json')
        assert stage == self.STAGES[len(m['stages'])]
        m['stages'][stage] = {'data':auto.read_json(path)}
        auto.save_json(Path(work)/'manifest.json', m)


class FakeAI:
    def __init__(self, no_search=False, fail_once=False):
        self.calls=[]
        self.no_search=no_search
        self.fail_once=fail_once
    def invoke(self, stage, prompt, directory, needs_web):
        self.calls.append(stage)
        if self.fail_once and len(self.calls)==1:
            raise RuntimeError('interrupted model execution')
        data = {
            'topic_candidates': {'candidates':[{'title':'A'},{'title':'B'}],'selected':'A'},
            'reality': {'sources':[{'url':'https://example.org/paper'}], 'phenomenon':'description'},
            'event_comparison': {'events':[{'id':'e1'},{'id':'e2'}]}
        }[stage]
        dst=directory/'result.json'
        auto.save_json(dst,data)
        return auto.Result(dst, 0 if self.no_search else 1, 'independent-execution-id-not-a-review')


class DriverTests(unittest.TestCase):
    def test_continuous_run_and_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)/'study'
            agent=FakeAI(fail_once=True)
            engine=auto.AutoRunner(TinyCore(),agent,max_calls=10,max_attempts=2)
            final=engine.run(work,'test-01')
            self.assertEqual(final['technical']['recorded'],list(TinyCore.STAGES))
            self.assertEqual(final['calls'],4)
            self.assertEqual(agent.calls,['topic_candidates','topic_candidates','reality','event_comparison'])
            self.assertEqual(engine.run(work,'test-01')['calls'],4)
    def test_no_search_evidence_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)/'study'
            with self.assertRaisesRegex(RuntimeError, 'Native web-search'):
                auto.AutoRunner(TinyCore(),FakeAI(no_search=True),max_attempts=1).run(work,'test-02')
            self.assertEqual(auto.read_json(work/'manifest.json')['stages'],{})
    def test_invalid_method_and_fake_read(self):
        with self.assertRaisesRegex(ValueError, 'qualitative only'):
            auto.validate_extra('research_design', {'method':'quantitative'})
        with self.assertRaisesRegex(ValueError, 'actually read'):
            auto.validate_extra('literature_initial', {'articles':[{'read_status':'url_found'}]*5})
    def test_adversarial_is_not_independent(self):
        with self.assertRaisesRegex(ValueError, 'same_model_adversarial'):
            auto.validate_extra('explanation_exchange', {'review_mode':'independent_review'})
        with self.assertRaisesRegex(ValueError, 'not independently verified'):
            auto.validate_extra('writing_review', {'reviewer_mode':'independent_review'})
    def test_real_codex_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError, 'CLI unavailable'):
                auto.CodexAdapter(codex='nonexistent-codex-executable').invoke('reality','',Path(folder),True)

if __name__=='__main__':
    unittest.main()
