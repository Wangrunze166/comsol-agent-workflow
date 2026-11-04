"""Synthetic native protocol, smoke and recovery tests. Never launches COMSOL.

Every model, process log and signing key is fabricated inside TemporaryDirectory.
Passing these tests proves Python control flow only, not COMSOL API compatibility.
"""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from comsol_workflow.case import read_json, write_json, sha256
from comsol_workflow.workflow import capture_payloads, execute, prepare_resume, smoke, verify_plan
try:
    from . import test_workflow as fixtures
except ImportError:
    import test_workflow as fixtures


class NativePayloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="comsol-synthetic-protocol-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def capture(self, text, destinations=None):
        return capture_payloads(text, "synthetic-current-token", self.directory,
                                destinations or {"metrics": "metrics.csv"})

    def frame(self, kind="metrics", value="time,value\n0,1\n"):
        return fixtures.native_frame("synthetic-current-token", kind, value)

    def test_only_current_token_payload_is_persisted(self):
        logs = fixtures.native_frame("stale-token", "metrics", "WRONG") + "\n" + self.frame()
        self.capture(logs)
        self.assertEqual((self.directory / "metrics.csv").read_text(), "time,value\n0,1\n")

    def test_missing_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "payload missing"):
            self.capture(fixtures.native_frame("stale-token", "metrics", "WRONG"))
        self.assertFalse((self.directory / "metrics.csv").exists())

    def test_identical_repeated_payload_is_accepted_but_conflicts_fail(self):
        self.capture(self.frame() + "\n" + self.frame())
        with self.assertRaisesRegex(ValueError, "Conflicting native payload"):
            self.capture(self.frame() + "\n" + self.frame(value="different"))

    def test_malformed_base64_and_non_utf8_are_rejected(self):
        for encoded in ("!not-base64!", base64.b64encode(b"\xff").decode("ascii")):
            with self.subTest(encoded=encoded), self.assertRaises(ValueError):
                self.capture("WORKFLOW_DATA synthetic-current-token metrics " + encoded)
        self.assertFalse((self.directory / "metrics.csv").exists())

    def test_model_supplied_kind_cannot_select_filesystem_path(self):
        logs = self.frame(kind="../escaped.csv", value="UNTRUSTED") + "\n" + self.frame()
        self.capture(logs)
        self.assertEqual({path.name for path in self.directory.iterdir()}, {"metrics.csv"})


class SmokeTests(fixtures.TemporaryCase):
    def inspect(self, side_effect=None):
        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", side_effect=side_effect or self.fake_successful_invocation
        ) as invoked:
            result = smoke(self.run_dir)
        return result, invoked

    def test_load_only_smoke_needs_no_signature_and_never_calls_solver_driver(self):
        plan = self.plan(execute_branch=True)
        result, invoked = self.inspect()
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["solve_requested"])
        self.assertEqual(invoked.call_count, 2)
        batch = invoked.call_args_list[1].args[0]
        self.assertIn("-nosave", batch)
        self.assertEqual(batch[batch.index("-autosave") + 1], "off")
        self.assertTrue(any(Path(arg).name == "SmokeDriver.class" for arg in batch))
        self.assertFalse(any("WorkflowDriver" in arg for arg in batch))
        self.assertEqual((self.run_dir / "inspection/smoke.ok").read_text().strip(), plan["completion_token"])
        self.assertFalse((self.run_dir / "results").exists())
        self.assertFalse((self.run_dir / "run.claim").exists())
        self.popen.assert_not_called()

    def test_cached_smoke_requires_unchanged_native_evidence(self):
        self.plan(execute_branch=True)
        self.inspect()
        second, invoked = self.inspect()
        self.assertEqual(second["status"], "passed")
        invoked.assert_not_called()
        (self.run_dir / "inspection/scope-inventory.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            self.inspect()

    def test_fabricated_passed_status_without_evidence_cannot_skip_smoke(self):
        plan = self.plan(execute_branch=True)
        directory = self.run_dir / "inspection"
        directory.mkdir()
        write_json(directory / "inspection-state.json", {
            "status": "passed", "plan_digest": plan["content_digest"], "artifacts": {}})
        with self.assertRaisesRegex(ValueError, "evidence is incomplete"):
            self.inspect()

    def test_cached_scope_is_recomputed_instead_of_trusting_stored_pass(self):
        self.plan(execute_branch=True)
        self.inspect()
        directory = self.run_dir / "inspection"
        inventory_path = directory / "scope-inventory.json"
        inventory = read_json(inventory_path)
        inventory["properties"][0]["expressions"] = ["2*lo"]
        write_json(inventory_path, inventory)
        state = read_json(directory / "inspection-state.json")
        state["artifacts"]["scope-inventory.json"] = sha256(inventory_path)
        write_json(directory / "inspection-state.json", state)
        with self.assertRaisesRegex(ValueError, "scope is unsafe"):
            self.inspect()

    def test_geometry_reference_blocks_smoke_and_reuse(self):
        plan = self.plan(execute_branch=True)

        def unsafe_inventory(argv, cwd, log, timeout):
            result = self.fake_successful_invocation(argv, cwd, log, timeout)
            if "batch" in Path(argv[0]).name:
                inventory = fixtures.synthetic_inventory()
                inventory["properties"][0]["expressions"] = ["lo"]
                Path(log).write_text(fixtures.native_frame(plan["completion_token"], "inventory", json.dumps(inventory))
                                     + f"\nWORKFLOW_SMOKE_COMPLETED {plan['completion_token']}\n", encoding="utf-8")
            return result

        result, _ = self.inspect(unsafe_inventory)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["scope"]["hits"][0]["parameter"], "lo")
        with self.assertRaisesRegex(ValueError, "Prior inspection failed"):
            self.inspect()

    def test_wrong_smoke_completion_token_is_failure(self):
        self.plan(execute_branch=True)

        def stale_token(argv, cwd, log, timeout):
            result = self.fake_successful_invocation(argv, cwd, log, timeout)
            if "batch" in Path(argv[0]).name:
                Path(log).write_text("WORKFLOW_SMOKE_COMPLETED stale-token\n")
            return result

        result, _ = self.inspect(stale_token)
        self.assertEqual(result["status"], "failed")
        self.assertFalse((self.run_dir / "inspection/smoke.ok").exists())

    def test_smoke_requires_both_native_logs_before_first_pass(self):
        self.plan(execute_branch=True)

        def missing_batch_log(argv, cwd, log, timeout):
            result = self.fake_successful_invocation(argv, cwd, log, timeout)
            if "batch" in Path(argv[0]).name:
                (Path(log).parent / "batch.log").unlink()
            return result

        result, _ = self.inspect(missing_batch_log)
        self.assertEqual(result["status"], "failed")
        self.assertIn("log", result["error"].lower())


@unittest.skipUnless(fixtures.HAS_CRYPTO, "Install the approval extra to exercise signed execution")
class SignedExecutionTests(fixtures.TemporaryCase):
    def run_mocked(self, plan, side_effect=None):
        assumptions, approval = self.receipt(plan, "assumptions"), self.receipt(plan, plan["operation"])
        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", side_effect=side_effect or self.fake_successful_invocation
        ) as invoked:
            result = execute(self.run_dir, assumptions, approval)
        return result, invoked

    def test_signed_envelopes_are_preserved_byte_for_byte_for_audit(self):
        plan = self.plan(execute_branch=True)
        result, _ = self.run_mocked(plan)
        self.assertEqual(result["status"], "execution_completed_engineering_review_required")
        for stage in ("assumptions", "solve"):
            self.assertEqual((self.run_dir / "results" / f"{stage}.receipt.json").read_bytes(),
                             (self.root / f"{stage}-synthetic-receipt.json").read_bytes())

    def test_failed_scope_inspection_prevents_solver_compilation(self):
        plan = self.plan(execute_branch=True)

        def incomplete_inventory(argv, cwd, log, timeout):
            result = self.fake_successful_invocation(argv, cwd, log, timeout)
            if Path(log).parent.name == "inspection" and "batch" in Path(argv[0]).name:
                Path(log).write_text(fixtures.native_frame(plan["completion_token"], "inventory", "{}")
                                     + f"\nWORKFLOW_SMOKE_COMPLETED {plan['completion_token']}\n")
            return result

        result, invoked = self.run_mocked(plan, incomplete_inventory)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["comsol_solve_started"])
        self.assertFalse(result["comsol_batch_attempted"])
        self.assertEqual(invoked.call_count, 2)
        self.assertFalse((self.run_dir / "WorkflowDriver.class").exists())

    def test_missing_batch_log_cannot_be_reported_as_completed(self):
        plan = self.plan(execute_branch=True)

        def missing_log(argv, cwd, log, timeout):
            result = self.fake_successful_invocation(argv, cwd, log, timeout)
            if Path(log).parent.name == "results" and "batch" in Path(argv[0]).name:
                (Path(log).parent / "batch.log").unlink()
            return result

        result, _ = self.run_mocked(plan, missing_log)
        self.assertEqual(result["status"], "failed")
        self.assertIn("Required native log missing", result["error"])

    def test_requested_field_plot_and_table_are_recorded(self):
        self.case["postprocess"] = {"field_plot": {"tag": "pg1", "filename": "temperature.png"},
                                    "table": {"filename": "temperature.csv"}}
        plan = self.plan(execute_branch=True)
        result, _ = self.run_mocked(plan)
        self.assertEqual(result["status"], "execution_completed_engineering_review_required")
        self.assertIn(str(Path("results/temperature.csv")), result["artifacts"])
        self.assertIn(str(Path("results/temperature.png")), result["artifacts"])

    def test_invalid_field_export_is_failure(self):
        self.case["postprocess"] = {"field_plot": {"tag": "pg1", "filename": "temperature.png"}}
        plan = self.plan(execute_branch=True)

        def invalid_png(argv, cwd, log, timeout):
            result = self.fake_successful_invocation(argv, cwd, log, timeout)
            if Path(log).parent.name == "results" and "batch" in Path(argv[0]).name:
                (Path(log).parent / "temperature.png").write_bytes(b"SYNTHETIC invalid PNG")
            return result

        result, _ = self.run_mocked(plan, invalid_png)
        self.assertEqual(result["status"], "failed")
        self.assertIn("not a PNG", result["error"])


@unittest.skipUnless(fixtures.HAS_CRYPTO, "Install the approval extra to exercise signed recovery")
class RecoveryTests(fixtures.TemporaryCase):
    def failed_run(self, status="failed", started=True):
        plan = self.plan(execute_branch=True)
        write_json(self.run_dir / "run-state.json", {"status": status, "comsol_solve_started": started})
        directory = self.run_dir / "recovery/model-recovery"
        directory.mkdir(parents=True)
        (directory / "SYNTHETIC-checkpoint.mph").write_bytes(b"SYNTHETIC checkpoint; not an MPH file")
        (self.run_dir / "results").mkdir()
        (self.run_dir / "results/recovery-model-path.txt").write_text(str(directory), encoding="utf-8")
        return plan, directory

    def test_unstarted_or_completed_run_cannot_be_resumed(self):
        self.failed_run(started=False)
        for status, started in (("failed", False), ("execution_completed_engineering_review_required", True)):
            write_json(self.run_dir / "run-state.json", {"status": status, "comsol_solve_started": started})
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "recorded interrupted/failed solve"):
                prepare_resume(self.run_dir, self.root / "resume")

    def test_missing_recovery_marker_fails_without_guessing(self):
        self.failed_run()
        (self.run_dir / "results/recovery-model-path.txt").unlink()
        with self.assertRaisesRegex(ValueError, "Recovery path was not recorded"):
            prepare_resume(self.run_dir, self.root / "resume")

    def test_external_or_empty_recovery_directory_is_rejected(self):
        self.failed_run()
        outside = self.root / "external-recovery"
        outside.mkdir()
        (outside / "SYNTHETIC.mph").write_bytes(b"SYNTHETIC")
        with self.assertRaisesRegex(ValueError, "inside.*recovery root"):
            prepare_resume(self.run_dir, self.root / "resume-outside", recovery_model=outside)
        empty = self.run_dir / "recovery/empty"
        empty.mkdir()
        with self.assertRaisesRegex(ValueError, "nonempty"):
            prepare_resume(self.run_dir, self.root / "resume-empty", recovery_model=empty)

    def test_recovery_is_snapshotted_and_tampering_invalidates_new_plan(self):
        _, source = self.failed_run()
        resumed = self.root / "resume"
        plan = prepare_resume(self.run_dir, resumed)
        self.assertEqual(plan["operation"], "resume")
        checkpoint = resumed / "checkpoint/SYNTHETIC-checkpoint.mph"
        self.assertEqual(checkpoint.read_bytes(), (source / checkpoint.name).read_bytes())
        (source / checkpoint.name).write_bytes(b"SYNTHETIC source updated later")
        verify_plan(resumed)
        checkpoint.write_bytes(b"SYNTHETIC changed snapshot")
        with self.assertRaisesRegex(ValueError, "changed"):
            verify_plan(resumed)

    def test_resume_requires_fresh_stage_specific_signed_receipts(self):
        original, _ = self.failed_run()
        assumptions, approval = self.receipt(original, "assumptions"), self.receipt(original, "solve")
        resumed = self.root / "resume"
        plan = prepare_resume(self.run_dir, resumed)
        with patch("comsol_workflow.workflow.invoke") as invoked:
            with self.assertRaises(ValueError):
                execute(resumed, assumptions, approval)
            invoked.assert_not_called()
        self.run_dir = resumed
        fresh_assumptions = self.receipt(plan, "assumptions")
        wrong_stage = self.receipt(plan, "solve")
        with patch("comsol_workflow.workflow.invoke") as invoked:
            with self.assertRaisesRegex(ValueError, "stage|scope"):
                execute(resumed, fresh_assumptions, wrong_stage)
            invoked.assert_not_called()
        resume_receipt = self.receipt(plan, "resume")
        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", side_effect=self.fake_successful_invocation
        ):
            result = execute(resumed, fresh_assumptions, resume_receipt)
        self.assertEqual(result["status"], "execution_completed_engineering_review_required")
        self.assertEqual(result["operation"], "resume")
        self.assertFalse(result["inspection"]["scope"]["checked"])
        self.assertTrue(result["comsol_solve_started"])

    def test_unreviewed_added_recovery_file_blocks_execution_before_any_process(self):
        self.failed_run()
        resumed = self.root / "resume"
        plan = prepare_resume(self.run_dir, resumed)
        assumptions, approval = self.receipt(plan, "assumptions"), self.receipt(plan, "resume")
        added = resumed / "checkpoint/new-subdirectory/unreviewed.mph"
        added.parent.mkdir()
        added.write_bytes(b"SYNTHETIC added after approval")
        with patch("comsol_workflow.workflow.invoke") as invoked:
            with self.assertRaisesRegex(ValueError, "snapshot file set changed"):
                execute(resumed, assumptions, approval)
            invoked.assert_not_called()
        self.assertFalse((resumed / "run.claim").exists())

    def test_recovery_failure_does_not_fall_back_to_new_solve(self):
        self.failed_run()
        resumed = self.root / "resume"
        plan = prepare_resume(self.run_dir, resumed)
        self.run_dir = resumed

        def unavailable_recovery(argv, cwd, log, timeout):
            result = self.fake_successful_invocation(argv, cwd, log, timeout)
            if Path(log).parent.name == "inspection" and "batch" in Path(argv[0]).name:
                Path(log).write_text("SYNTHETIC loadRecovery failure; no solver started")
                result["exit_code"] = 1
            return result

        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", side_effect=unavailable_recovery
        ) as invoked:
            result = execute(resumed, self.receipt(plan, "assumptions"), self.receipt(plan, "resume"))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["comsol_solve_started"])
        self.assertEqual(invoked.call_count, 2)
        self.assertFalse((resumed / "WorkflowDriver.class").exists())


if __name__ == "__main__":
    unittest.main()
