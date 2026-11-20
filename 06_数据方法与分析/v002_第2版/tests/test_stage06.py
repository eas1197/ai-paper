"""Synthetic cases only. Tests verify code, never a real study or G6 quality."""
from __future__ import annotations

import copy
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import stage06 as s6
import methods06 as methods
from common06 import ROOT, load, sha, value_hash, write
from data_adapters import LocalDatasetAdapter, merge_frames
from engines import StatsmodelsEngine
from pipeline06 import compare, estimate

STAMP = "2026-11-15T10:00:00+08:00"


class EngineTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        import pandas as pd
        rng = np.random.default_rng(67)
        self.frame = pd.DataFrame({"x": rng.normal(size=500)})
        self.frame["y"] = 2 + 3 * self.frame.x + rng.normal(size=500)
        self.engine = StatsmodelsEngine()
        self.spec = {"method_id": "OLS", "outcome": "y", "predictors": ["x"], "covariance": "HC1"}

    def test_ols_matches_independent_least_squares(self):
        import numpy as np
        result = self.engine.fit(self.frame, self.spec)
        expected = np.linalg.lstsq(np.column_stack([np.ones(len(self.frame)), self.frame.x]), self.frame.y, rcond=None)[0]
        np.testing.assert_allclose([r["estimate"] for r in result["parameters"]], expected, rtol=1e-12)
        self.assertTrue(result["diagnostics"]["converged"])
        for row in result["parameters"]:
            self.assertLess(row["ci_low"], row["estimate"])
            self.assertGreater(row["ci_high"], row["estimate"])

    def test_logit_poisson_and_nb_have_finite_inference(self):
        import numpy as np
        rng = np.random.default_rng(92)
        for method, y in (("BINARY_LOGIT", rng.binomial(1, 1 / (1 + np.exp(-self.frame.x)))),
                          ("POISSON", rng.poisson(np.exp(.2 + .3 * self.frame.x))),
                          ("NEGATIVE_BINOMIAL", rng.negative_binomial(2, 2 / (2 + np.exp(.3 * self.frame.x))))):
            with self.subTest(method=method):
                frame = self.frame.assign(y=y)
                result = self.engine.fit(frame, dict(self.spec, method_id=method))
                self.assertEqual(result["diagnostics"]["errors"], [])
                self.assertTrue(all(r["std_error"] > 0 for r in result["parameters"]))

    def test_ordered_and_multinomial(self):
        import numpy as np
        rng = np.random.default_rng(55)
        frame = self.frame.assign(y=np.digitize(self.frame.x + rng.logistic(size=len(self.frame)), [-.5, .8]))
        ordered = self.engine.fit(frame, dict(self.spec, method_id="ORDERED_LOGIT", intercept=False, outcome_levels=[0, 1, 2]))
        multi = self.engine.fit(frame, dict(self.spec, method_id="MULTINOMIAL_LOGIT", outcome_levels=[0, 1, 2]))
        self.assertTrue(ordered["diagnostics"]["converged"])
        self.assertTrue(multi["diagnostics"]["converged"])
        self.assertEqual(len(multi["parameters"]), 4)

    def test_zip_and_zinb_require_two_processes(self):
        import numpy as np
        rng = np.random.default_rng(154)
        x = self.frame.x.to_numpy()
        counts = rng.negative_binomial(1.5, 1.5 / (1.5 + np.exp(.5 + .4 * x)))
        y = np.where(rng.uniform(size=len(x)) < .3, 0, counts)
        for method in ("ZIP", "ZINB"):
            with self.subTest(method=method):
                with self.assertRaises(ValueError):
                    self.engine.fit(self.frame.assign(y=y), dict(self.spec, method_id=method))
                output = self.engine.fit(self.frame.assign(y=y), dict(self.spec, method_id=method,
                        inflation_predictors=["x"], zero_process_rationale="TEST distinct zero process", maxiter=500))
                self.assertTrue(output["parameters"])

    def test_reject_rank_deficient_binary_and_complex_survey(self):
        with self.assertRaises(ValueError):
            self.engine.fit(self.frame.assign(z=self.frame.x), dict(self.spec, predictors=["x", "z"]))
        with self.assertRaises(ValueError):
            self.engine.fit(self.frame, dict(self.spec, method_id="BINARY_LOGIT"))
        with self.assertRaises(ValueError):
            self.engine.fit(self.frame, dict(self.spec, survey_design={"weights": {"status": "specified", "value": "w"}}))

    def test_cluster_covariance_and_interaction(self):
        import numpy as np
        frame = self.frame.assign(g=np.repeat(range(50), 10), z=np.tile(range(10), 50))
        result = self.engine.fit(frame, dict(self.spec, predictors=["x", "z"], interactions=[["x", "z"]],
                                            covariance="cluster", cluster="g"))
        self.assertEqual(result["diagnostics"]["n_clusters"], 50)
        self.assertIn("x:z", [r["term"] for r in result["parameters"]])


class AdapterTests(unittest.TestCase):
    def test_dta_labels_metadata_and_special_missing_are_preserved(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "TEST.dta"
            pd.DataFrame({"q": [1., 2., -8., float("nan")]}).to_stata(file, write_index=False,
                    variable_labels={"q": "TEST label"}, value_labels={"q": {1: "yes", 2: "no", -8: "missing"}})
            digest = sha(file)
            metadata = LocalDatasetAdapter().read_metadata(file)
            self.assertEqual(metadata["columns"]["q"]["label"], "TEST label")
            self.assertEqual(metadata["columns"]["q"]["value_labels"]["-8"], "missing")
            frame = LocalDatasetAdapter().read_subset(file, ["q"])
            self.assertEqual(frame.q.iloc[2], -8)
            self.assertTrue(pd.isna(frame.q.iloc[3]))
            self.assertEqual(sha(file), digest)

    def test_null_and_duplicate_merge_keys_fail(self):
        import pandas as pd
        spec = {"on": ["pid"], "how": "left", "validate": "many_to_one"}
        with self.assertRaises(ValueError):
            merge_frames(pd.DataFrame({"pid": [None]}), pd.DataFrame({"pid": [None]}), spec)
        with self.assertRaises(pd.errors.MergeError):
            merge_frames(pd.DataFrame({"pid": [1, 2]}), pd.DataFrame({"pid": [1, 1], "q": [1, 2]}), spec)
        merged, report = merge_frames(pd.DataFrame({"pid": [1, 2]}), pd.DataFrame({"pid": [1], "q": [3]}), spec)
        self.assertEqual((len(merged), report["match_rows"], report["left_only_rows"]), (2, 1, 1))

    def test_replay_detects_changed_effect_and_sample(self):
        a = {"results": [{"model_id": "M1", "term": "x", "outcome": "y", "estimate": 1., "std_error": .1,
                         "ci_low": .8, "ci_high": 1.2, "p_value": .2, "n_obs": 100, "sample_version": "s"}],
             "sample_flow": [], "failures": []}
        self.assertTrue(compare(a, copy.deepcopy(a))["passed"])
        b = copy.deepcopy(a)
        b["results"][0]["estimate"] = 2
        self.assertFalse(compare(a, b)["passed"])

    def test_failed_model_and_missing_exclusions_are_retained(self):
        import numpy as np
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "TEST.csv"
            rng = np.random.default_rng(84)
            x, y = rng.normal(size=60), rng.normal(size=60)
            x[0] = -8
            pd.DataFrame({"x": x, "y": y}).to_csv(file, index=False)
            p = {"seed": 1, "datasets": [{"dataset_id": "D", "path": str(file), "keys": {}}], "primary_dataset": "D",
                 "variables": [{"variable_id": v, "dataset_id": "D", "source_variable": v, "special_missing": {"-8": "TEST missing"}}
                               for v in ("x", "y")], "joins": [], "sample_filters": [], "common_sample": True,
                 "survey_design": {}, "models": [{"model_id": "M1", "method_id": "OLS", "outcome": "y", "predictors": ["x"],
                 "analysis_role": "primary"}, {"model_id": "M2", "method_id": "POISSON", "outcome": "y", "predictors": ["x"],
                 "analysis_role": "robustness"}]}
            first = estimate(p, LocalDatasetAdapter(), StatsmodelsEngine(), "TEST_failures")
            self.assertEqual([m["model_id"] for m in first["models"]], ["M1"])
            self.assertEqual([m["model_id"] for m in first["failures"]], ["M2"])
            self.assertEqual(first["results"][0]["n_obs"], 59)
            self.assertTrue(compare(first, estimate(p, LocalDatasetAdapter(), StatsmodelsEngine(), "TEST_failures"))["passed"])

    def test_ne_filter_does_not_admit_missing_values(self):
        import pandas as pd
        from pipeline06 import prepare_frame
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "TEST.csv"
            pd.DataFrame({"x": [1, 2, -8]}).to_csv(file, index=False)
            p = {"datasets": [{"dataset_id": "D", "path": str(file)}], "primary_dataset": "D",
                 "variables": [{"variable_id": "x", "dataset_id": "D", "source_variable": "x", "special_missing": {"-8": "TEST"}}],
                 "sample_filters": [{"variable": "x", "op": "ne", "value": 2, "reason": "TEST a priori exclusion"}]}
            frame, audit = prepare_frame(p, LocalDatasetAdapter())
            self.assertEqual(frame.x.tolist(), [1])
            self.assertEqual(audit["sample_flow"][-1]["n_excluded"], 2)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        test_file = ROOT / "04_议题文献与现实/v004_第4版/tests/test_workflow.py"
        spec = importlib.util.spec_from_file_location("previous_workflow_tests06", test_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.previous = module.WorkflowTests()
        self.previous.setUp()
        self.addCleanup(self.previous.doCleanups)
        self.root = self.previous.root
        self.patch = patch.object(s6, "run_directory", lambda run_id: self.root / "runs" / run_id)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.pdf_patch = patch("providers.PdfReader.inspect", lambda self_, p: module.TestPdfReader().inspect(p))
        self.pdf_patch.start()
        self.addCleanup(self.pdf_patch.stop)
        self.output_patch = patch.object(methods, "project_output", lambda p: Path(p))
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)
        self.s5 = module.s5

    def make_library(self):
        refs = []
        for i, role in enumerate(("method_foundation", "empirical_example")):
            path = self.root / f"TEST_method{i}.pdf"
            text = f"TEST method {i} specification and table"
            path.write_bytes(b"%PDF-TEST\n" + text.encode())
            refs.append({"method_id": "OLS", "paper_id": f"P_METHOD_{i}", "title": f"TEST method article {i}",
                         "authors": ["TEST author"], "year": 2024, "source_url": "https://example.invalid/test",
                         "retrieved_at": STAMP, "access_basis": "TEST generated", "retain_allowed": True,
                         "reference_role": role, "pdf_path": str(path), "pdf_sha256": sha(path), "identity_basis": "TEST title",
                         "reader": "TEST reader", "read_at": STAMP, "read_status": "fulltext_read", "selection_reason": "TEST",
                         "method_evidence": [{"pdf_page": 1, "short_excerpt": f"TEST method {i}"}],
                         "table_evidence": [{"pdf_page": 1, "short_excerpt": "specification and table"}] if i else [],
                         "model_specification": "TEST OLS", "assumptions": "TEST", "diagnostics": "TEST", "table_structure": "TEST",
                         "reporting_rules": "TEST", "applicability": "TEST", "review_status": "verified", "verified_at": STAMP})
        source = self.root / "method_input.json"
        write(source, {"references": refs})
        initial = self.root / "library_initial"
        methods.build_library(source, initial)
        review = self.root / "library_review.json"
        write(review, dict(load(initial / "quality_review_request.json"), decision="accepted", reviewer="TEST reviewer",
                           reviewed_at=STAMP, assessment="TEST library branch"))
        target = self.root / "library"
        methods.build_library(source, target, review)
        self.assertEqual(methods.load_library(target, {"OLS"})[1], [])
        return target

    def fixture(self):
        import numpy as np
        import pandas as pd
        up = self.previous.passed04()
        inputs5, ann, file5 = self.previous.fixture05(up)
        library = self.make_library()
        data, side = self.root / "TEST_raw.csv", self.root / "TEST_codebook.json"
        rng = np.random.default_rng(1234)
        x = rng.normal(size=100)
        pd.DataFrame({"Q1": x, "Q2": 2 + 1.5 * x + rng.normal(size=100)}).to_csv(data, index=False)
        write(side, {"data_sha256": sha(data), "columns": {q: {"label": "TEST " + q, "value_labels": {"1": "TEST类别"},
                     "special_missing": {}} for q in ("Q1", "Q2")}})
        identity = self.root / "TEST_release.txt"
        identity.write_text("TEST generated original dataset release", encoding="utf-8")
        survey = ann["analysis_design"]["survey_design"]
        protocol = {"engine": "statsmodels", "seed": 42, "datasets": [{"dataset_id": "D_TEST", "name": "TEST_CF", "wave": "2024",
                    "path": str(data), "sha256": sha(data), "keys": {}, "metadata_sidecar": str(side),
                    "identity_status": "raw_original_verified", "identity_basis": "TEST generated original",
                    "identity_evidence": {"path": str(identity), "sha256": sha(identity), "locator": "TEST line 1",
                                         "short_excerpt": "TEST generated original dataset release"},
                    "access_basis": "TEST self generated", "review_status": "verified", "verified_at": STAMP}],
                    "primary_dataset": "D_TEST", "variables": [{"variable_id": "V_" + role, "dataset_id": "D_TEST",
                    "source_variable": q, "expected_label": "TEST " + q, "special_missing": {}, "transform": {"op": "identity"}}
                    for role, q in (("X", "Q1"), ("Y", "Q2"))],
                    "joins": [], "sample_filters": [], "common_sample": True, "missing_policy": "complete_case",
                    "survey_design": survey, "models": [{"model_id": "M1", "method_id": "OLS", "method_tags": [],
                    "outcome": "V_Y", "predictors": ["V_X"], "hypothesis_id": "H_TEST", "analysis_role": "primary",
                    "covariance": "HC1", "diagnostics_required": ["converged", "rank", "r_squared"]}],
                    "method_library": str(library), "diagnostics_plan": "TEST predefined checks", "robustness_plan": "TEST none justified",
                    "multiple_testing_policy": "TEST single family", "precision_plan": "TEST intervals"}
        file6 = self.root / "protocol.json"
        write(file6, protocol)
        ann["analysis_design"]["execution06_sha256"] = value_hash(protocol)
        write(file5, ann)
        first5 = self.s5.execute(self.s5.plan(inputs5, self.previous.config()))
        gate = load(Path(first5["attempt_path"]) / "gate_report.json")
        self.assertEqual(len(gate["errors"]), 1, gate["errors"])
        review5 = self.root / "review5.json"
        write(review5, dict(content_sha256=gate["content_sha256"], decision="accepted", reviewer="TEST reviewer",
                           reviewed_at=STAMP, assessment="TEST code gate only"))
        inputs5["quality_review"] = str(review5)
        second5 = self.s5.execute(self.s5.plan(inputs5, self.previous.config()))
        self.assertEqual(second5["status"], "passed", load(Path(second5["attempt_path"]) / "gate_report.json"))
        review6 = self.root / "protocol_review.json"
        write(review6, dict(content_sha256=value_hash(protocol), decision="accepted", reviewer="TEST reviewer",
                           reviewed_at=STAMP, assessment="TEST analysis protocol"))
        return {"run_id": "TEST_only", "base_dir": str(self.root), "phase": "prepare", "protocol": str(file6),
                "protocol_review": str(review6), "upstream": str(Path(second5["attempt_path"]) / "stage_manifest.json")}

    def test_empty_prepare_never_passes_and_export_blocked(self):
        result = s6.execute(s6.plan({"run_id": "TEST_empty", "base_dir": str(self.root)}))
        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(load(Path(result["attempt_path"]) / "analysis_plan.json")["frozen"])
        with self.assertRaises(ValueError):
            s6.export(result["attempt_path"])

    def test_prepare_analyze_approve_export_and_tamper(self):
        inputs = self.fixture()
        before = sha(self.root / "TEST_raw.csv")
        first = s6.execute(s6.plan(inputs))
        self.assertEqual(first["status"], "ready", load(Path(first["attempt_path"]) / "gate_report.json"))
        second = s6.execute(s6.plan(dict(inputs, phase="analyze", preflight=str(Path(first["attempt_path"]) / "stage_manifest.json"))))
        self.assertEqual(second["status"], "needs_review")
        second_work = Path(second["attempt_path"])
        self.assertTrue(load(second_work / "reproduction.json")["passed"])
        self.assertEqual(len(load(second_work / "bundle.json")["results"]), 2)
        with self.assertRaises(ValueError):
            s6.export(second_work)
        bad_review = self.root / "bad_result_review.json"
        write(bad_review, {"content_sha256": "TEST_wrong_hash", "decision": "accepted", "reviewer": "TEST",
                           "reviewed_at": STAMP, "assessment": "TEST invalid review"})
        with patch.object(StatsmodelsEngine, "fit", side_effect=AssertionError("review must not refit")):
            rejected = s6.execute(s6.plan({"run_id": "TEST_only", "phase": "approve", "source": str(second_work / "stage_manifest.json"),
                                         "quality_review": str(bad_review), "base_dir": str(self.root)}))
        self.assertEqual(rejected["status"], "needs_review")
        review = self.root / "result_review.json"
        write(review, dict(load(second_work / "quality_review_request.json"), decision="accepted", reviewer="TEST reviewer",
                           reviewed_at=STAMP, assessment="TEST only verifies code"))
        third = s6.execute(s6.plan({"run_id": "TEST_only", "phase": "approve", "source": str(second_work / "stage_manifest.json"),
                                   "quality_review": str(review), "base_dir": str(self.root)}))
        self.assertEqual(third["status"], "passed", load(Path(third["attempt_path"]) / "gate_report.json"))
        self.assertEqual(s6.validate(third["attempt_path"])["status"], "passed")
        self.assertEqual(sha(self.root / "TEST_raw.csv"), before)
        export = Path(s6.export(third["attempt_path"])["path"]).parent
        self.assertFalse(list(export.glob("*.pdf")))
        self.assertFalse(list(export.glob("*.dta")))
        with sqlite3.connect(Path(third["attempt_path"]) / "knowledge.sqlite") as db:
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(db.execute("SELECT count(*) FROM results").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT count(*) FROM variables").fetchone()[0], 2)
        # Data update invalidates the downstream attempt without rewriting its history.
        with (self.root / "TEST_raw.csv").open("a") as stream:
            stream.write("9,9\n")
        self.assertEqual(s6.validate(third["attempt_path"])["status"], "stale")

    def test_protocol_change_after_freeze_blocks_cases_and_model(self):
        inputs = self.fixture()
        protocol = load(inputs["protocol"])
        protocol["models"][0]["predictors"] = ["V_Y"]
        write(inputs["protocol"], protocol)
        with patch.object(LocalDatasetAdapter, "read_subset", side_effect=AssertionError("must not read cases")):
            first = s6.execute(s6.plan(inputs))
        self.assertEqual(first["status"], "needs_review")
        self.assertTrue(any("事前冻结" in e for e in load(Path(first["attempt_path"]) / "gate_report.json")["errors"]))

    def test_plan_change_concurrent_lock_and_old_attempt_are_blocked(self):
        inputs = {"run_id": "TEST_block", "base_dir": str(self.root)}
        planned = s6.plan(inputs)
        file = self.root / "TEST_changed.txt"
        file.write_text("a")
        planned["input_files"].append({"path": str(file), "sha256": sha(file)})
        file.write_text("b")
        with self.assertRaises(ValueError):
            s6.execute(planned)
        run = self.root / "runs/TEST_block"
        run.mkdir(parents=True)
        (run / ".research.lock").write_text("TEST active lock")
        with self.assertRaises(FileExistsError):
            s6.execute(s6.plan(inputs))
        self.assertEqual((run / ".research.lock").read_text(), "TEST active lock")

    def test_same_method_cannot_count_same_pdf_twice(self):
        library = self.make_library()
        records = load(library / "references.json")
        records[1].update(pdf_path=records[0]["pdf_path"], pdf_sha256=records[0]["pdf_sha256"],
                          method_evidence=records[0]["method_evidence"],
                          table_evidence=[{"pdf_page": 1, "short_excerpt": "specification and table"}])
        report = methods.verify_references(records, library, {"OLS"})
        self.assertTrue(any("两篇不同" in e for e in report["errors"]))
        self.assertFalse(methods.coverage_ok(records))

    def test_changed_protocol_after_main_start_cannot_be_confirmatory(self):
        inputs = self.fixture()
        run = self.root / "runs/TEST_only"
        event = {"protocol_sha256": "TEST_previous_protocol", "design_sha256": "TEST_previous_design"}
        (run / "analysis_history.jsonl").write_text(json.dumps(event) + "\n")
        result = s6.execute(s6.plan(inputs))
        report = load(Path(result["attempt_path"]) / "gate_report.json")
        self.assertEqual(result["status"], "needs_review")
        self.assertTrue(any("主分析已开始" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
