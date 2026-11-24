"""E15 offline native postcondition checks; synthetic fixtures only."""
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
import ai_paper5_strict as strict
import task_packet


class StageProductTest(unittest.TestCase):
    def setUp(self):
        self.run="e15_fixture_"+uuid.uuid4().hex
        self.work=strict.RUNS/self.run
        self.addCleanup(shutil.rmtree,self.work,ignore_errors=True)
        strict.original_call(strict.original_command("init",self.run,theme="Synthetic offline test"))
        self.packet={"phenomenon":"fixture","search_focus":"fixture","sources":[{"url":"https://example.org",
            "kind":"fixture","supports":"fixture","limits":"fixture"}]}

    def verify(self,operation,prior=None):
        script=("import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); "
                "from staged_topic import verify_stage_artifacts,load; work=Path(sys.argv[2]); "
                "verify_stage_artifacts(work,load(work/'staged_topic.json'),sys.argv[3],prior_stage=sys.argv[4])")
        return strict.original_call([sys.executable,"-B","-c",script,str(strict.V3_TOPIC.parent),
            str(self.work),operation,prior or ""],timeout=30)

    def test_real_original_reality_transition_and_tamper(self):
        report=self.work/"fixture_reality.json"
        strict.write(report,self.packet)
        strict.original_call(strict.original_command("reality",self.run,report=report))
        self.assertEqual(strict.state_of(self.run)["status"],"explanation_exchange")
        self.verify("reality")
        strict.write(self.work/"reality.json",{"phenomenon":"changed"})
        with self.assertRaisesRegex(RuntimeError,"artifact hash changed"):
            self.verify("reality")

    def test_missing_artifact_or_inconsistent_state(self):
        state=strict.state_of(self.run)
        state.update(status="initial",reality_sha256=task_packet._digest(self.packet))
        strict.write(self.work/"staged_topic.json",state)
        with self.assertRaises(RuntimeError): self.verify("reality")
        strict.write(self.work/"reality.json",self.packet)
        with self.assertRaisesRegex(RuntimeError,"transition inconsistent"): self.verify("reality")

    def test_literature_missing_receipt_stops(self):
        state=strict.state_of(self.run)
        state.update(status="preliminary_review",latest_search={"phase":"initial","collection_sha256":"fixture"})
        strict.write(self.work/"staged_topic.json",state)
        with self.assertRaises(RuntimeError): self.verify("initial")


if __name__=="__main__": unittest.main()
