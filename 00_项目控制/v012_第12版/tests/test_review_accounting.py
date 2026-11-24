import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from review_accounting import record_revision_round, _attempt_observations


class ReviewAccountingTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name)
        self.output=self.work/"matrix.json"
        self.output.write_text('{"value":2}')

    def test_round_categories_and_idempotence(self):
        args=dict(stage="matrix",round_key="original",before={"value":1},after={"value":2},
            output=self.output,substantive=True,local=True)
        self.assertEqual(record_revision_round(self.work,**args),record_revision_round(self.work,**args))
        rows=list((self.work/"revision_accounting").glob("*.json"))
        self.assertEqual(len(rows),1)
        self.assertTrue(json.loads(rows[0].read_text())["local"])
        self.assertTrue(json.loads(rows[0].read_text())["substantive"])

    def test_no_candidate_or_wait_as_round(self):
        (self.work/"review_waiting").mkdir()
        (self.work/"review_waiting"/"candidate.json").write_text("{}")
        self.assertEqual(_attempt_observations(self.work),([],[],[]))
        with self.assertRaises(ValueError):
            record_revision_round(self.work,stage="matrix",round_key="candidate",
                before={},after={},output=self.output,substantive=False,local=False)

    def attempt(self,num,login,events,valid=False):
        path=self.work/"autonomous_writing"/"matrix_review_1"/f"attempt_{num:03}"
        path.mkdir(parents=True)
        (path/"request.json").write_text(json.dumps({"model":"gpt-6.2-sol"}))
        (path/"login.json").write_text(json.dumps({"chatgpt":login}))
        (path/"events.jsonl").write_text("\n".join(json.dumps(e) for e in events))
        if valid:
            answer={"decision":"revise"}
            (path/"response.json").write_text(json.dumps(answer))
            (path/"validated.json").write_text(json.dumps({"answer":answer,
                "thread_id":events[0]["thread_id"],
                "response_sha256":hashlib.sha256((path/"response.json").read_bytes()).hexdigest()}))
        return path

    def test_retry_only_on_observed_subsequent_start(self):
        self.attempt(1,False,[])
        rounds,retries,_=_attempt_observations(self.work)
        self.assertEqual((len(rounds),len(retries)),(0,0))
        events=[{"type":"thread.started","thread_id":"fixture"},{"type":"turn.completed"}]
        self.attempt(2,True,events,True)
        rounds,retries,_=_attempt_observations(self.work)
        self.assertEqual((len(rounds),len(retries)),(1,1))
        self.attempt(3,True,events,True)
        self.assertEqual(len(_attempt_observations(self.work)[0]),1)

    def test_changed_request_is_not_retry(self):
        self.attempt(1,False,[])
        path=self.attempt(2,True,[{"type":"thread.started","thread_id":"fixture"},{"type":"turn.completed"}],True)
        (path/"request.json").write_text(json.dumps({"model":"gpt-6.2-sol","inputs":"new request"}))
        rounds,retries,_=_attempt_observations(self.work)
        self.assertEqual((len(rounds),len(retries)),(1,0))

    def test_bad_original_record_not_counted(self):
        path=self.attempt(1,True,[{"type":"thread.started","thread_id":"fixture"},{"type":"turn.completed"}],True)
        (path/"response.json").write_text("{}")
        rounds,retries,unknown=_attempt_observations(self.work)
        self.assertEqual((rounds,retries),([],[]))
        self.assertEqual(len(unknown),1)


if __name__=="__main__": unittest.main()
