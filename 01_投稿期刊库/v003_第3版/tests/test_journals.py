"""Technical fixtures only; never a 100-journal research certification."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import journals as j
from journal_common import sha

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        p=self.base/'fixture.txt'; p.write_text('SYNTHETIC TECHNICAL FIXTURE',encoding='utf-8')
        self.e={'evidence_id':'E1','source_url':'https://example.org/fixture','retrieved_at':'2026-11-16',
                'locator':'fixture only','snapshot_path':'fixture.txt','sha256':sha(p),'authority':'publisher','kind':'full_guideline'}
        self.profile={'journal_id':'T1','journal_name':'Fixture1','quota_group':'CSSCI',
                      **{k:j.unknown('fixture unknown') for k in j.FIELDS},
                      'requirements':{k:j.unknown('fixture unknown') for k in j.REQUIREMENTS},
                      'guideline':{'evidence_ids':['E1'],'full_snapshot':True},
                      'indexing':{k:{'status':'verified','edition':v,'category':'source' if k=='CSSCI' else 'core',
                                     'evidence_ids':['E1'],'verified_at':'2026-11-16'} for k,v in j.REQUIRED_EDITIONS.items()}}
        for k,v in {'issn':'0000-0001','cn':'00-0001/C','official_url':'https://example.org',
                    'submission_channel':'system','submission_url':'https://example.org/login','quantitative_fit':'fixture only'}.items():
            self.profile[k]={'value':v,'evidence_ids':['E1'],'unknown_reason':None}
    def tearDown(self): self.tmp.cleanup()
    def bundle(self):
        rows=[]
        for i in range(100):
            p=copy.deepcopy(self.profile);p.update(journal_id=f'T{i}',journal_name=f'Fixture{i}',quota_group='CSSCI' if i<50 else 'PKU')
            p['issn']['value']=f'0000-{i:04d}';p['cn']['value']=f'00-{i:04d}/C';rows.append(p)
        return {'as_of':'2026-11-16','journals':rows,'evidence':[copy.deepcopy(self.e)],'test_fixture':True}
    def test_positive_contract_fixture(self):
        self.assertEqual(j.validate_bundle(self.bundle(),self.base)['status'],'passed')
    def test_old_cssci_edition_is_not_current(self):
        b=self.bundle();b['journals'][0]['indexing']['CSSCI']['edition']='2023-2024'
        self.assertEqual(j.validate_bundle(b,self.base)['status'],'needs_review')
    def test_unpublished_pku_2026_not_latest_published(self):
        b=self.bundle();b['journals'][50]['indexing']['PKU']['edition']='2026'
        self.assertEqual(j.validate_bundle(b,self.base)['status'],'needs_review')
    def test_extension_does_not_count_as_source(self):
        b=self.bundle();b['journals'][0]['indexing']['CSSCI']['category']='extended'
        self.assertEqual(j.validate_bundle(b,self.base)['verified_quota_counts']['CSSCI'],49)
    def test_same_journal_under_other_id_rejected(self):
        b=self.bundle();b['journals'][1]['journal_name']=b['journals'][0]['journal_name']
        self.assertEqual(j.validate_bundle(b,self.base)['status'],'needs_review')
    def test_same_issn_alias_rejected(self):
        b=self.bundle();b['journals'][1]['issn']=copy.deepcopy(b['journals'][0]['issn'])
        self.assertEqual(j.validate_bundle(b,self.base)['status'],'needs_review')
    def test_snippet_not_full_guideline(self):
        b=self.bundle();b['evidence'][0]['kind']='search_excerpt'
        self.assertEqual(j.validate_bundle(b,self.base)['status'],'needs_review')
    def test_contact_mail_not_email_submission(self):
        b=self.bundle();b['journals'][0]['submission_channel']['value']='email'
        self.assertEqual(j.validate_bundle(b,self.base)['status'],'needs_review')
    def test_third_party_cannot_verify_core(self):
        b=self.bundle();b['evidence'][0]['authority']='third_party'
        self.assertEqual(j.validate_bundle(b,self.base)['verified_quota_counts'],{'CSSCI':0,'PKU':0})
    def test_snapshot_tampering_rejected(self):
        (self.base/'fixture.txt').write_text('changed',encoding='utf-8')
        self.assertEqual(j.validate_bundle(self.bundle(),self.base)['status'],'needs_review')
    def test_missing_unknown_reason_rejected(self):
        b=self.bundle();b['journals'][0]['fees']['unknown_reason']=None
        self.assertEqual(j.validate_bundle(b,self.base)['status'],'needs_review')
    def test_cannot_lower_target(self):
        with self.assertRaises(ValueError):j.plan({'as_of':'2026-11-16'},{'distinct_target':99})

if __name__=='__main__':unittest.main()
