import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import submission as s

class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=s.ROOT)
        self.db=Path(self.tmp.name)/'ledger.sqlite'
        self.pool=[{'journal_id':f'T{i:03d}','journal_name':f'Fixture{i}','quota_group':'CSSCI' if i<10 else 'PKU'} for i in range(20)]
    def tearDown(self):self.tmp.cleanup()
    def insert(self, sid, state='ready_to_send',family='fixture'):
        db=s.ledger(self.db);db.execute('INSERT INTO submissions VALUES(?,?,?,?,?,?)',(sid,family,'test',state,'fixture.json',s.now()));db.close()
    def test_seed_and_order_reproducible(self):
        a=s.sample_candidates(self.pool,123);b=s.sample_candidates(list(reversed(self.pool)),123)
        self.assertEqual(a,b);self.assertEqual(len({p['journal_id'] for p in a}),10)
        self.assertEqual(sum(p['quota_group']=='CSSCI' for p in a),5)
    def test_insufficient_pool_cannot_pad(self):
        with self.assertRaises(ValueError):s.sample_candidates(self.pool[:12],123)
    def test_duplicate_journal_blocks_sampling(self):
        with self.assertRaises(ValueError):s.sample_candidates(self.pool+[self.pool[0]],123)
    def test_disabled_stage_has_no_workspace_or_network(self):
        self.assertEqual(s.execute(s.plan({'enabled':False}))['status'],'skipped')
    def test_only_one_active_per_family(self):
        self.insert('first');self.insert('second')
        s.transition('first','sending',{},self.db)
        with self.assertRaises(ValueError):s.transition('second','sending',{},self.db)
    def test_unknown_delivery_blocks_next(self):
        self.insert('first');self.insert('second')
        s.transition('first','sending',{},self.db);s.transition('first','delivery_unknown',{},self.db)
        with self.assertRaises(ValueError):s.transition('second','sending',{},self.db)
    def test_timeout_cannot_be_treated_as_rejection(self):
        self.insert('first','under_review')
        with self.assertRaises(ValueError):s.transition('first','rejected',{'reason':'90 days elapsed'},self.db)
    def test_active_submission_cannot_be_superseded(self):
        self.insert('first','under_review')
        with self.assertRaises(ValueError):s.transition('first','superseded',{'reason':'new attempt'},self.db)
    def test_accepted_family_stops_other_versions(self):
        self.insert('first','accepted');self.insert('second')
        with self.assertRaises(ValueError):s.transition('second','sending',{},self.db)
    def test_rejected_with_receipt_unlocks_next(self):
        self.insert('first','under_review');self.insert('second')
        p=Path(self.tmp.name)/'receipt.json';p.write_text('{"fixture":"rejected"}',encoding='utf-8')
        s.transition('first','rejected',{'files':[s.lock(p)],'reference':'fixture receipt','recorded_by':'unit test'},self.db)
        self.assertEqual(s.transition('second','sending',{},self.db)['state'],'sending')
    def test_pending_predecessor_cannot_be_skipped(self):
        self.insert('first','prepared');self.insert('second')
        with self.assertRaises(ValueError):s.transition('second','sending',{},self.db)
    def test_approval_hash_must_match_body_and_recipient(self):
        p=Path(self.tmp.name)/'package.json';a=Path(self.tmp.name)/'approval.json'
        s.write(p,{'content_sha256':'stale','recipient':'changed@example.org'})
        s.write(a,{'content_sha256':'stale','approved':True})
        with self.assertRaises(ValueError):s.send(p,a,{},transport=lambda m:self.fail('must never send'))
    def test_different_families_can_be_active(self):
        self.insert('a',family='family_a');self.insert('b',family='family_b')
        s.transition('a','sending',{},self.db)
        self.assertEqual(s.transition('b','sending',{},self.db)['state'],'sending')

if __name__=='__main__':unittest.main()
