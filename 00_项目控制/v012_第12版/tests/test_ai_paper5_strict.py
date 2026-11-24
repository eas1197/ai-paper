"""Actual 3.x contracts are authoritative; no fake Chat source promotion."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import tempfile
from unittest import TestCase, main
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/"tools/ai_paper5_strict.py"
spec=importlib.util.spec_from_file_location("ai_paper5_strict",PATH)
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


def make_v15_fixture(root):
    import hashlib
    import json
    root = Path(root)
    work = root / "fixture_g06"
    output = work / "autonomous_writing" / "draft_0"
    matrix_dir = work / "qualitative_framework" / "attempt_001"
    output.mkdir(parents=True)
    matrix_dir.mkdir(parents=True)
    sys.path.insert(0, str(m.V32 / "tools"))
    sys.path.insert(0, str(m.V15.parent))
    from question_binding import evidence_digest
    from writing_plan import reviewed_dimension_sources

    core = "How is the fixture mechanism organized?"
    specific = "How does the fixture process operate?"
    method = "secondary_interviews"
    framework = {"core_question": core, "core_concept": "Fixture concept",
                 "dimensions": [{"id": "d0", "name": "Dimension", "deduction": "Fixture deduction"}]}
    material = {"material_id": "E", "url": "https://example.org/evidence",
                "locator": "Fixture source, paragraph 2", "kind": "official_rule"}
    receipt = {"framework_sha256": evidence_digest(framework), "materials": [material]}
    (matrix_dir / "framework.json").write_text(
        json.dumps(framework, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt_path = matrix_dir / "material_receipt.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt_sha = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    contract = {"core_question": core, "specific_question": specific, "method": method,
                "receipt_sha256": receipt_sha}
    matrix = {"question_binding": contract, "collection_sha256": evidence_digest(receipt),
              "framework_sha256": receipt["framework_sha256"],
              "rows": [{"dimension_id": "d0", "evidence": [material]}]}
    matrix_path = matrix_dir / "analysis_matrix_reviewed.json"
    matrix_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    topic_path = work / "s08_topic.json"
    topic = {"question": specific, "research_method": {"path": method}}
    topic_path.write_text(json.dumps(topic, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    chapters = []
    for chapter_id in ("problem", "framework", "case", "d0", "conclusion"):
        chapters.append({"id": chapter_id, "task": "Fixture chapter task",
                         "bridge": "Fixture chapter bridge", "sections": [{
                             "title": "Fixture section", "task": "Compare evidence",
                             "argument": "A tentative interpretation", "evidence_use": "Check source scope",
                             "source_ids": ["T", "E"], "paragraphs": ["Describe evidence", "Limit inference"]
                         }]})
    packet = {
        "method": method, "core_question": core, "specific_question": specific,
        "answer_strategy": "Compare bounded fixture observations",
        "question_binding": contract,
        "analysis_matrix": "qualitative_framework/attempt_001/analysis_matrix_reviewed.json",
        "sources": {
            "T": {"kind": "theory", "label": "Fixture theory", "locator": "Fixture literature"},
            "E": {"kind": "empirical", "label": "Fixture evidence",
                  "locator": material["locator"], "url": material["url"]},
        },
        "framework": {"prior_explanation": "Prior", "gap": "Gap", "theory_choice": "Theory",
                      "deduction": "Deduction", "increment": "Increment", "integration": "Integration",
                      "core_concept": "Fixture concept",
                      "dimensions": [{"id": "d0", "title": "Dimension", "deduction": "Fixture deduction"}]},
        "case": {"background": "Background", "selection": "Selection",
                 "materials": "Materials", "method": "Method"},
        "chapters": chapters,
    }
    packet_path = output / "plan_input.json"
    packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan_path = output / "论文写作方案.md"
    plan_path.write_text("# Fixture writing plan\n", encoding="utf-8")
    file_sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    admission = {
        "mode": "native_reviewed", "matrix_sha256": file_sha(matrix_path),
        "receipt_sha256": receipt_sha, "review_sha256": "fixture-review-hash",
        "eligible_material_ids": ["E"],
        "chapter_empirical_source_ids": reviewed_dimension_sources(packet, matrix, {"E"}),
        "question_binding": contract,
    }
    request = {
        "run_id": work.name, "run_mode": "dev", "formal_eligible": False,
        "method": method, "requested_deliverable": "plan", "status": "plan_prepared",
        "input_sha256": hashlib.sha256(json.dumps(packet, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        "plan_sha256": file_sha(plan_path), "topic_sha256": file_sha(topic_path),
        "analysis_matrix_sha256": file_sha(matrix_path), "review_status": "pass",
        "independent_review": {"answer": {"decision": "pass"}},
        "question_binding": contract, "material_admission": admission,
    }
    (output / "writing_plan_review_request.json").write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return packet_path


class StrictTests(TestCase):
    def test_real_v3_module_coverage_and_quantities(self):
        info=m.doctor()
        self.assertEqual(info["dev"],{"initial":5,"supplemental":5})
        self.assertEqual(info["formal"],{"initial":5,"supplemental":35})
        self.assertEqual(len(info["journals"]),9)
        self.assertTrue(info["sha256"]["codex_receipts"])

    def test_exact_original_controller_not_v10_or_v11(self):
        command=m.original_command("initial","paper_a")
        self.assertIn("v009_第9版/tools/staged_topic.py"," ".join(command))
        self.assertNotIn("ai_paper5_auto.py"," ".join(command))
        with self.assertRaises(ValueError):m.original_command("fake_gate","paper_a")

    def test_search_route_calls_authoritative_v3(self):
        with patch.object(m,"state_of",side_effect=[{"status":"initial"},{"status":"preliminary_review"}]):
            with patch.object(m,"original_call",return_value="original research output") as fn, \
                 patch.object(m,"codex_task",return_value={"task_snapshot":{"snapshot_sha256":"fixture"}}) as packet:
                result=m.status("paper_a",progress=True)
                packet.assert_called_once_with("paper_a","initial")
        self.assertEqual(result["action"],"original_native_literature_search")
        self.assertEqual(result["after"],"preliminary_review")
        self.assertEqual(fn.call_args.args[0][3],"initial")

    def test_original_06_07_and_events_are_not_reimplemented(self):
        cmd=m.original_material_command("audit_run",conversion="conversion.json")
        self.assertIn("v005_第5版/tools/qual_materials.py"," ".join(cmd))
        self.assertIn("--conversion",cmd)
        self.assertIn("v009_第9版/tools/resume_writing.py",
                      " ".join(m.original_writing_command("audit_run")))
        self.assertIn("v009_第9版/tools/event_protocol.py",
                      " ".join(m.original_event_command("audit_run","events.json")))
        with self.assertRaises(ValueError):m.original_material_command("audit_run")
        with self.assertRaises(ValueError):m.original_material_command("audit_run",review="a",matrix="b")

    def test_real_original_v3_init_and_prepare(self):
        import uuid
        import shutil
        run_id="strict_ci_"+uuid.uuid4().hex[:12]
        work=m.RUNS/run_id
        try:
            m.original_call(m.original_command("init",run_id,theme="教育分流"))
            self.assertEqual(m.state_of(run_id)["status"],"reality")
            prepared=m.original_call(m.original_command("prepare",run_id))
            self.assertIn("reality_task",prepared)
            self.assertEqual(m.status(run_id)["action"],"original_v3_requires_staged_evidence_or_independent_review")
        finally:
            if work.exists():shutil.rmtree(work)

    def test_chat_is_never_authorized_as_cli(self):
        info=m.doctor()
        task={"profile":"original_v3.2","source_mode":"chat_native_web",
              "policy_sha256":m.sha(m.V3_POLICY),"prompt_sha256":m.sha(m.NATIVE_PROMPT),
              "schema_sha256":m.sha(m.NATIVE_SCHEMA),"journals":info["journals"],
              "accepted":[],"target":5}
        sample={"title":"家庭资源与教育分流","authors":["作者甲"],"journal":"社会",
                "year":2024,"doi":"","metadata_url":"https://example.com/a",
                "abstract_url":"https://example.com/a","abstract_locator":"摘要",
                "abstract_excerpt":"家庭资源与教育分流的关联结果",
                "abstract_summary":"以家庭教育资源和学校分流为研究对象，分析不同群体进入不同教育轨道的机会和约束条件，说明资源差异可能在多个阶段影响教育路径，并进一步指出所发现的关联仍须在具体地区和学校制度背景下作谨慎理解，不能直接解释为未经证实的因果关系。",
                "relevance":"direct","relevance_reason":"研究教育分流机制"}
        result=m.audit_chat(task,{"papers":[sample,dict(sample,journal="社会科学")],
                                  "unverified":[],"search_notes":["真实搜索记录待核"]})
        self.assertFalse(result["native_cli_receipt"])
        self.assertFalse(result["formal_eligible"])
        self.assertEqual(result["provisional_count"],1)
        self.assertEqual(len(result["rejected"]),1)
        with self.assertRaises(ValueError):
            m.audit_chat(dict(task,source_mode="codex"),{"papers":[],"unverified":[],"search_notes":[]})

    def test_original_v009_direct_cli_init_prepare_without_wrapper(self):
        import uuid
        import shutil
        run_id="direct_cli_"+uuid.uuid4().hex[:12]
        work=m.RUNS/run_id
        try:
            init_result=subprocess.run(
                m.original_command("init",run_id,theme="教育分流"),
                cwd=m.ROOT,capture_output=True,text=True,timeout=90)
            self.assertEqual(init_result.returncode,0,init_result.stderr+init_result.stdout)
            self.assertEqual(m.state_of(run_id)["status"],"reality")
            prepare_result=subprocess.run(
                m.original_command("prepare",run_id),
                cwd=m.ROOT,capture_output=True,text=True,timeout=90)
            self.assertEqual(prepare_result.returncode,0,
                             prepare_result.stderr+prepare_result.stdout)
            self.assertIn("reality_task",prepare_result.stdout)
            self.assertEqual(m.status(run_id)["action"],
                             "original_v3_requires_staged_evidence_or_independent_review")
        finally:
            if work.exists():
                shutil.rmtree(work)

    def test_original_cli_help_smoke_without_v012_execution(self):
        modules=(m.V3_TOPIC,m.V3_EVENTS,m.MATERIAL,m.REVISION,m.V15,m.V16)
        for module in modules:
            with self.subTest(module=module.name):
                result=subprocess.run(
                    [sys.executable,"-B",str(module),"--help"],
                    cwd=m.ROOT,capture_output=True,text=True,timeout=45)
                self.assertEqual(result.returncode,0,
                                 str(module)+"\n"+result.stderr+result.stdout)
                self.assertIn("usage:",result.stdout.lower())

    def test_v012_adapters_route_to_original_v009_v005_v016_modules(self):
        topic=m.original_command("prepare","sample")
        self.assertEqual(Path(topic[2]),m.V3_TOPIC)

        materials=m.original_material_command("sample",conversion=Path("conversion.json"))
        self.assertEqual(Path(materials[2]),m.MATERIAL)

        writing=m.original_writing_command("sample")
        self.assertEqual(Path(writing[2]),m.REVISION)

        with tempfile.TemporaryDirectory() as temporary:
            packet=make_v15_fixture(Path(temporary))
            writer4=m.original_writer4_command(
                "prepare",packet=packet,
                workspace=packet.parent.parent.parent/"writer4_workspace",mode="exploratory")
            self.assertEqual(Path(writer4[2]),m.V16)
            self.assertEqual(writer4[3],"prepare")
            self.assertIn("--packet",writer4)
            self.assertIn("--workspace",writer4)
            self.assertIn("--mode",writer4)

        resume_source=Path(m.REVISION).read_text(encoding="utf-8-sig")
        self.assertIn("from material_adequacy import writing_material_status",resume_source)
        self.assertIn("from repair_materials import",resume_source)
        self.assertIn("from writing_plan import produce",resume_source)
        writer_source=Path(m.V16).read_text(encoding="utf-8-sig")
        self.assertIn("from writing_plan import render",writer_source)

    def test_resume_writing_cli_delegates_original_controller(self):
        with patch.object(m,"doctor",return_value={}), \
             patch.object(m,"frozen_route",return_value={"method":"online_qualitative"}), \
             patch.object(m,"original_call",return_value="reviewed_plan") as original:
            result=m.main(["resume-writing","--run-id","g03_fixture","--attempt","attempt_002"])
        self.assertEqual(result,0)
        original.assert_called_once_with(m.original_writing_command("g03_fixture", attempt="attempt_002"))

    def test_writer4_cli_dispatches_v016_through_original_adapter(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet=make_v15_fixture(Path(temporary))
            with patch.object(m,"doctor",return_value={}), \
                 patch.object(m,"original_call",side_effect=[
                     json.dumps({"method":"secondary_interviews","writer":"ai-writer 4.0 / v016"}),
                     "writer4 complete"]) as original:
                result=m.main(["writer4","--action","prepare","--packet",str(packet),
                               "--workspace",str(packet.parent.parent.parent/"writer4_workspace"),"--mode","exploratory"])
            self.assertEqual(result,0)
            self.assertEqual([call.args[0][3] for call in original.call_args_list],["route","prepare"])
            command=original.call_args.args[0]
            self.assertEqual(Path(command[2]),m.V16)
            self.assertEqual(command[3],"prepare")

    def test_g13_v012_prepare_real_writer_artifacts(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as temporary:
            packet=make_v15_fixture(Path(temporary))
            workspace=packet.parent.parent.parent/"writer4_workspace"
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(m.main(["writer4","--action","prepare","--packet",str(packet),
                                         "--workspace",str(workspace)]),0)
            result=json.loads(output.getvalue())["result"]
            prepared=json.loads(result["original_output"])
            self.assertEqual(prepared["status"],"awaiting_draft")
            manifest=json.loads((workspace/"writer_manifest.json").read_text(encoding="utf-8"))
            original=json.loads(packet.read_text(encoding="utf-8"))
            self.assertEqual(manifest["packet_sha256"],m.sha(packet))
            self.assertFalse(manifest["formal_eligible"])
            self.assertEqual(len(manifest["resource_sha256"]),13)
            self.assertEqual(len(manifest["task_ids"]),5)
            for task_id, chapter in zip(manifest["task_ids"], original["chapters"]):
                task=json.loads((workspace/"tasks"/(task_id+".json")).read_text(encoding="utf-8"))
                section=chapter["sections"][0]
                self.assertEqual(task["source_ids"],section["source_ids"])
                self.assertEqual(task["sources"],{key:original["sources"][key] for key in section["source_ids"]})
                self.assertEqual(task["paragraphs"],section["paragraphs"])
                self.assertTrue(task["style_rules"])
                self.assertTrue(task["v003_argument_rules"])
                self.assertTrue(task["instruction"])
            self.assertEqual(manifest["plan_sha256"],m.sha(workspace/"writing_plan_v15.md"))
            self.assertFalse((workspace/"writing_review_request.json").exists())

    def test_g19_v012_submit_real_original_writer(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as temporary:
            packet=make_v15_fixture(Path(temporary))
            run=packet.parent.parent.parent
            workspace=run/"writer4_workspace"
            draft=run/"draft.md"
            claims=run/"claims.json"
            base=["writer4","--packet",str(packet),"--workspace",str(workspace)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(base+["--action","prepare"]),0)
            manifest=json.loads((workspace/"writer_manifest.json").read_text(encoding="utf-8"))
            original=json.loads(packet.read_text(encoding="utf-8"))
            text=""
            paragraphs=[]
            coverage=[]
            entries=[]
            for task_id,chapter in zip(manifest["task_ids"],original["chapters"]):
                text+="## "+chapter["id"]+"\n\n"
                for number, _ in enumerate(chapter["sections"][0]["paragraphs"],1):
                    literal="测试材料："+task_id+"-"+str(number)+"。"
                    start=len(text)
                    text+=literal
                    cid=task_id+"-"+str(number)
                    paragraphs.append({"task_id":task_id,"paragraph_index":number,
                                       "exact_text":literal,"start":start,"end":len(text),"source_ids":["E"]})
                    coverage.append({"task_id":task_id,"paragraph_index":number,
                                     "status":"claims_registered","claim_ids":[cid]})
                    entries.append({"claim_id":cid,"task_id":task_id,"paragraph_index":number,
                                    "claim_type":"empirical","exact_text":literal,"source_ids":["E"],
                                    "source_locators":{"E":original["sources"]["E"]["locator"]},
                                    "scope":"Synthetic fixture only"})
                    text+="\n\n"
            draft.write_text(text,encoding="utf-8")
            ledger={"packet_sha256":manifest["packet_sha256"],"task_sha256":manifest["task_sha256"],
                    "paragraph_bindings":paragraphs,"coverage_inventory":coverage,
                    "claims":entries,"unsupported_claims":[]}
            def save_ledger():
                claims.write_text(json.dumps(ledger,ensure_ascii=False),encoding="utf-8")
            save_ledger()
            args=base+["--action","submit","--manuscript",str(draft),"--claims",str(claims)]
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(m.main(args),0)
            result=json.loads(output.getvalue())["result"]
            self.assertEqual(json.loads(result["original_output"])["status"],"exploratory_draft_awaiting_review")
            request_path=workspace/"writing_review_request.json"
            request=json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(request["manuscript_sha256"],m.sha(draft))
            self.assertEqual(request["claim_ledger_sha256"],m.sha(claims))
            self.assertEqual(request["draft_task_binding"]["paragraph_count"],10)
            self.assertEqual(request["claim_coverage"]["counts"]["empirical"],10)
            self.assertFalse(request["formal_pass"])
            self.assertEqual(request["independent_review"],"pending")
            self.assertTrue((workspace/"style_review.json").is_file())
            ledger["claims"][0]["source_locators"]["E"]="invented"
            save_ledger()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(args),2)
            request=json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(request["status"],"technical_revisions_needed")
            self.assertTrue(any("locator" in x for x in request["structural_errors"]))
            ledger["claims"][0]["source_locators"]["E"]=original["sources"]["E"]["locator"]
            save_ledger()
            # Remove a heading without moving the frozen paragraph offsets.
            draft.write_text(text.replace("## problem","-- problem",1),encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(m.main(args),2)
            request=json.loads(request_path.read_text(encoding="utf-8"))
            self.assertTrue(any("chapter count" in x for x in request["structural_errors"]))
            self.assertFalse(request["formal_pass"])

    def test_g16_adapter_requires_run_owned_draft_and_strict_task_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet=make_v15_fixture(Path(temporary))
            run=packet.parent.parent.parent
            workspace=run/"writer4_workspace"
            draft=run/"draft.md"
            claims=run/"claims.json"
            draft.write_text("Fixture",encoding="utf-8")
            claims.write_text("{}",encoding="utf-8")
            cmd=m.original_writer4_command("submit",packet=packet,workspace=workspace,
                                           manuscript=draft,claims=claims)
            self.assertIn("--require-task-binding",cmd)
            outside=Path(temporary)/"outside.md"
            outside.write_text("Fixture",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"inside the current research run"):
                m.original_writer4_command("submit",packet=packet,workspace=workspace,
                                           manuscript=outside,claims=claims)
            with self.assertRaisesRegex(ValueError,"inside the current research run"):
                m.original_writer4_command("prepare",packet=packet,workspace=Path(temporary)/"outside")

    def test_g12_v012_route_executes_original_writer_for_all_methods(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as temporary:
            packet=Path(temporary)/"route.json"
            for method, expected in (("secondary_interviews","ai-writer 4.0 / v016"),
                                     ("online_qualitative","ai-writer 4.0 / v016"),
                                     ("quantitative","main/v014/tools/stage07.py")):
                packet.write_text(json.dumps({"method":method}),encoding="utf-8")
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(m.main(["writer4","--action","route","--packet",str(packet)]),0)
                route=json.loads(output.getvalue())["result"]["writer_route"]
                self.assertEqual(route["method"],method)
                self.assertEqual(route["writer"],expected)

    def test_g12_wrong_original_route_stops_before_prepare(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet=make_v15_fixture(Path(temporary))
            with patch.object(m,"doctor",return_value={}), \
                 patch.object(m,"original_call",return_value=json.dumps(
                     {"method":"quantitative","writer":"main/v014/tools/stage07.py"})) as original:
                result=m.main(["writer4","--action","prepare","--packet",str(packet),
                               "--workspace",str(packet.parent.parent.parent/"writer4_workspace")])
            self.assertEqual(result,2)
            original.assert_called_once_with(m.original_writer4_command("route",packet=packet))

    def test_v15_handoff_blocks_missing_outputs_bad_sources_and_hash_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            valid=make_v15_fixture(root/"valid")
            receipt=m.validate_v15_writer_handoff(valid)
            self.assertEqual(receipt["chapter_empirical_source_ids"]["d0"],["E"])

            missing=make_v15_fixture(root/"missing")
            (missing.parent/"writing_plan_review_request.json").unlink()
            with self.assertRaisesRegex(ValueError,"output is incomplete"):
                m.validate_v15_writer_handoff(missing)

            changed_plan=make_v15_fixture(root/"changed_plan")
            with (changed_plan.parent/"论文写作方案.md").open("a",encoding="utf-8") as stream:
                stream.write("tampered\n")
            with self.assertRaisesRegex(ValueError,"plan hash mismatch"):
                m.validate_v15_writer_handoff(changed_plan)

            changed_source=make_v15_fixture(root/"changed_source")
            packet_data=json.loads(changed_source.read_text(encoding="utf-8"))
            packet_data["sources"]["E"]["locator"]="Wrong source locator"
            changed_source.write_text(json.dumps(packet_data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            request_path=changed_source.parent/"writing_plan_review_request.json"
            request=json.loads(request_path.read_text(encoding="utf-8"))
            request["input_sha256"]=__import__("hashlib").sha256(
                json.dumps(packet_data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            request_path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"source locator differs"):
                m.validate_v15_writer_handoff(changed_source)

            changed_matrix=make_v15_fixture(root/"changed_matrix")
            matrix_path=changed_matrix.parent.parent.parent/"qualitative_framework"/"attempt_001"/"analysis_matrix_reviewed.json"
            matrix_path.write_text(matrix_path.read_text(encoding="utf-8")+"\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"matrix hash mismatch"):
                m.validate_v15_writer_handoff(changed_matrix)

            changed_matrix_source=make_v15_fixture(root/"changed_matrix_source")
            matrix_path=changed_matrix_source.parent.parent.parent/"qualitative_framework"/"attempt_001"/"analysis_matrix_reviewed.json"
            matrix=json.loads(matrix_path.read_text(encoding="utf-8"))
            matrix["rows"][0]["evidence"][0]["locator"]="Tampered matrix locator"
            matrix_path.write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            request_path=changed_matrix_source.parent/"writing_plan_review_request.json"
            request=json.loads(request_path.read_text(encoding="utf-8"))
            new_matrix_sha=__import__("hashlib").sha256(matrix_path.read_bytes()).hexdigest()
            request["analysis_matrix_sha256"]=new_matrix_sha
            request["material_admission"]["matrix_sha256"]=new_matrix_sha
            request_path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"matrix source identity differs"):
                m.validate_v15_writer_handoff(changed_matrix_source)

    def test_writer4_preflight_stops_before_v016_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            packet=make_v15_fixture(Path(temporary))
            data=json.loads(packet.read_text(encoding="utf-8"))
            data["sources"]["E"]["locator"]="Tampered source"
            packet.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            request_path=packet.parent/"writing_plan_review_request.json"
            request=json.loads(request_path.read_text(encoding="utf-8"))
            request["input_sha256"]=__import__("hashlib").sha256(
                json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            request_path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            with patch.object(m,"doctor",return_value={}), patch.object(m,"original_call") as original:
                result=m.main(["writer4","--action","prepare","--packet",str(packet),
                               "--workspace",str(packet.parent.parent.parent/"writer4_workspace"),"--mode","exploratory"])
            self.assertEqual(result,2)
            original.assert_not_called()

    def test_archived_unreviewed_v15_output_is_not_forwarded_to_v016(self):
        packet=m.ROOT/"handoff_runs/bike_parking_20261122/autonomous_writing/draft_0/plan_input.json"
        with self.assertRaisesRegex(ValueError,"reviewed material admission is missing"):
            m.validate_v15_writer_handoff(packet)

    def test_v016_adapter_rejects_incomplete_dispatch_arguments(self):
        with self.assertRaisesRegex(ValueError,"workspace"):
            m.original_writer4_command("prepare",packet=Path("plan.json"))
        with self.assertRaisesRegex(ValueError,"manuscript and claims"):
            m.original_writer4_command("submit",packet=Path("plan.json"),
                                       workspace=Path("writer4"))
        with self.assertRaisesRegex(ValueError,"Unknown original v016"):
            m.original_writer4_command("unknown",packet=Path("plan.json"))

    def test_same_fixture_chat_native_run_is_separate_and_nonformal(self):
        base=m.ROOT/"handoff_runs"/"digital_mutual_aid_20261122"
        parent=m.read(base/"staged_topic.json")
        chat=m.read(base/"chat_native_20261122"/"Chat实验状态.json")
        self.assertEqual(parent["status"],"explanation_exchange")
        self.assertFalse(parent["formal_eligible"])
        self.assertEqual(chat["parent_staged_topic_status"],parent["status"])
        self.assertFalse(chat["parent_modified"])
        self.assertIsNone(chat["independent_model_invocation_id"])
        self.assertFalse(chat["independent_review_verified"])
        self.assertIsNone(chat["cli_tool_receipts"])
        self.assertEqual(chat["web_search_mode"],"ChatGPT native browsing, not Codex CLI")
        self.assertEqual(chat["final_gate"],
                         "not_passed_due_to_missing_independent_review_and_empirical_limitations")

    def test_chat_native_matrices_and_writing_plan_are_not_formal_v009_receipts(self):
        base=m.ROOT/"handoff_runs"/"digital_mutual_aid_20261122"/"chat_native_20261122"
        literature=m.read(base/"文献检索矩阵.json")
        materials=m.read(base/"经验材料与分析矩阵.json")
        writing=(base/"论文写作方案.md").read_text(encoding="utf-8-sig")
        self.assertEqual(literature["acquisition_mode"],"chat_native_web")
        self.assertFalse(literature["targets"]["formal"])
        self.assertEqual(materials["acquisition_mode"],"chat_native_web")
        self.assertEqual(materials["method"],
                         "public_secondhand_interview_and_reported_process_comparison")
        self.assertIn("未获独立审查放行",writing)
        self.assertIn("exploratory",writing.lower())

if __name__=="__main__":main()
