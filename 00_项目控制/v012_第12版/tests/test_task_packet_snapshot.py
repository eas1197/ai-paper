"""C04 snapshot versioning and dependency invalidation; offline fixtures only."""
import json
from pathlib import Path
import unittest

import test_task_packet_ownership as ownership
from test_task_packet_schema import packet
import task_packet


# Reuse the original-run fixture setup without inheriting its test methods.
class SnapshotTest(unittest.TestCase):
    setUp = ownership.TaskOwnershipTest.setUp

    def make_packet(self, **changes):
        work = self.root / "offline_fixture"
        path = work / "fixture/input.json"
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            path.write_text('{"input": 1}', encoding="utf-8")
        sample = dict(packet(), input_files=[{"path": "fixture/input.json",
                     "sha256": task_packet.heritage.sha(path)}],
                     output_schema={"kind": "inline", "schema": {"type": "object"}})
        sample.update(changes)
        return sample

    def freeze(self, sample, dependencies=()):
        return task_packet.freeze_packet(sample, current_run_id="offline_fixture",
                                         dependencies=dependencies)

    def verify(self, ref):
        return task_packet.verify_snapshot(ref, current_run_id="offline_fixture")

    def test_identical_packet_idempotent_and_input_change_rejected(self):
        sample = self.make_packet()
        ref = self.freeze(sample)
        self.assertEqual(self.freeze(sample), ref)
        self.assertEqual(self.verify(ref)["packet"], sample)
        path = self.root / "offline_fixture/fixture/input.json"
        path.write_text('{"input": 2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash changed"):
            self.verify(ref)
        updated = self.freeze(self.make_packet())
        self.assertNotEqual(ref, updated)
        with self.assertRaisesRegex(ValueError, "Superseded"):
            self.verify(ref)

    def test_question_and_policy_scope_change_invalidates_transitive_dependents(self):
        parent = self.freeze(self.make_packet())
        child = self.freeze(self.make_packet(task_id="child"), [parent])
        grandchild = self.freeze(self.make_packet(task_id="grandchild"), [child])
        unrelated = self.freeze(self.make_packet(task_id="unrelated"))
        revised = self.freeze(self.make_packet(research_question="Revised question",
                              source_scope={"journals": ["Revised scope"]}))
        self.assertNotEqual(parent, revised)
        for ref in (parent, child, grandchild):
            with self.assertRaisesRegex(ValueError, "Superseded"):
                self.verify(ref)
        self.verify(unrelated)
        with self.assertRaisesRegex(ValueError, "Historical"):
            self.freeze(self.make_packet())
        with self.assertRaisesRegex(ValueError, "Result does not belong"):
            task_packet.validate_result_snapshot({"task_snapshot": parent},
                current_run_id="offline_fixture", expected_reference=revised)
        task_packet.validate_result_snapshot({"task_snapshot": revised},
                current_run_id="offline_fixture", expected_reference=revised)

    def test_original_question_change_requires_new_snapshot(self):
        sample = self.make_packet()
        ref = self.freeze(sample)
        path = self.root / "offline_fixture/staged_topic.json"
        state = json.loads(path.read_text(encoding="utf-8"))
        state["question"] = "New original question"
        path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "question or search policy"):
            self.verify(ref)
        self.assertNotEqual(ref, self.freeze(sample))

    def test_policy_file_hash_change_and_path_escape_rejected(self):
        from unittest.mock import patch
        policy = self.root / "policy.json"
        policy.write_text("original", encoding="utf-8")
        with patch.object(task_packet.heritage, "V3_POLICY", policy):
            sample = self.make_packet()
            ref = self.freeze(sample)
            policy.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "question or search policy"):
                self.verify(ref)
            self.assertNotEqual(ref, self.freeze(sample))
        sample = self.make_packet(input_files=[{"path": "../policy.json", "sha256": "a" * 64}])
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.freeze(sample)

    def test_cycle_and_tampering_rejected(self):
        parent = self.freeze(self.make_packet())
        child = self.freeze(self.make_packet(task_id="child"), [parent])
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            self.freeze(self.make_packet(), [child])
        work = self.root / "offline_fixture"
        path = task_packet._slot(work, parent["stage_id"], parent["task_id"]) / "versions" / (parent["snapshot_sha256"] + ".json")
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        snapshot["packet"]["purpose"] = "changed"
        path.write_text(json.dumps(snapshot), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.verify(parent)


if __name__ == "__main__":
    unittest.main()
