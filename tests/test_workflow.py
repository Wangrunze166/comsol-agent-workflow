"""Offline regression tests. Every model, tool, result and approval here is synthetic.

No test launches COMSOL. Mocked executor tests demonstrate control flow only;
they are not license checks, API validation or evidence of a real simulation.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from comsol_workflow.case import read_json, write_json, validate
from comsol_workflow.results import compare, diagnose, read_csv, validate_metrics
from comsol_workflow.units import check_quantity, parse_unit
from comsol_workflow.workflow import execute, invoke, prepare, report, verify_plan, verify_receipt


def synthetic_case():
    """A fabricated minimal case, never derived from a licensed COMSOL model."""
    return {
        "schema_version": 1, "case_id": "synthetic-control-flow",
        "title": "SYNTHETIC TEST ONLY — no real simulation",
        "provenance": {"kind": "synthetic_fixture", "sources": ["fabricated unittest fixture"]},
        "model": {"path": "synthetic.mph", "comsol_version": "6.3",
                  "solver_tag": "sol1", "study_tag": "std1", "dataset_tag": "dset1",
                  "clear_solution_tags": ["sol1"], "dependencies": ["synthetic-source.txt"]},
        "engineering": {
            "dimension": 3,
            **{name: {"policy": "preserve-reviewed-mph", "description": "synthetic test stub"}
               for name in ("geometry", "mesh", "solver")},
            "materials": ["synthetic"], "physics": ["synthetic"], "couplings": ["synthetic"],
            "boundary_conditions": ["synthetic"], "assumptions": ["SYNTHETIC; not engineering evidence"],
            "acceptance": ["Check fabricated CSV only"], "unresolved": [],
        },
        "validation": {name: "not_run" for name in (
            "mesh_independence", "time_step_independence", "conservation", "experimental_validation")},
        "parameters": [
            {"name": "T0", "value": 20, "unit": "degC", "quantity": "absolute_temperature", "source": "synthetic", "scope": "physics_scalar"},
            {"name": "lo", "value": 1, "unit": "mm", "quantity": "length", "source": "synthetic", "scope": "physics_scalar"},
            {"name": "hi", "value": 2, "unit": "mm", "quantity": "length", "source": "synthetic", "scope": "physics_scalar"},
        ],
        "constraints": [{"kind": "less_than", "left": "lo", "right": "hi"}],
        "execution": {"cores": 1, "timeout_seconds": 1},
        "exports": [
            {"name": "time_s", "expression": "t", "unit": "s", "quantity": "time"},
            {"name": "temperature_degC", "expression": "T", "unit": "degC", "quantity": "absolute_temperature"},
        ],
        "results": {"coordinate": "time_s", "expected_coordinates": [0, 1],
                    "coordinate_atol": 1e-9, "atol": 1e-6, "rtol": 1e-3,
                    "bounds": {"temperature_degC": [0, 100]}},
    }


class UnitTests(unittest.TestCase):
    def test_si_conversion_and_derived_dimensions(self):
        self.assertAlmostEqual(check_quantity(15, "mm", "length")[0], 0.015)
        self.assertEqual(check_quantity(1, "min", "time")[0], 60)
        self.assertEqual(parse_unit("W/(m*K)")[1], parse_unit("kg*m/(s^3*K)")[1])
        self.assertEqual(check_quantity(2, "ohm", "resistance")[0], 2)

    def test_absolute_celsius_and_temperature_difference_are_distinct(self):
        self.assertAlmostEqual(check_quantity(20, "degC", "absolute_temperature")[0], 293.15)
        self.assertEqual(check_quantity(-10, "K", "temperature_difference")[0], -10)
        with self.assertRaises(ValueError):
            check_quantity(28, "degC", "temperature_difference")
        with self.assertRaises(ValueError):
            check_quantity(1, "A/degC", "pi_proportional_gain")

    def test_below_absolute_zero_is_rejected(self):
        for value, unit in [(-0.001, "K"), (-274, "degC")]:
            with self.subTest(value=value, unit=unit), self.assertRaises(ValueError):
                check_quantity(value, unit, "absolute_temperature")

    def test_pi_and_derivative_gain_dimensions(self):
        self.assertEqual(check_quantity(-0.05, "A/K", "pi_proportional_gain")[0], -0.05)
        self.assertEqual(check_quantity(-0.005, "A/(K*s)", "pi_integral_gain")[0], -0.005)
        self.assertEqual(check_quantity(0, "A*s/K", "pid_derivative_gain")[0], 0)
        for unit, quantity in [("A/K", "pi_integral_gain"), ("A/(K*s^2)", "pid_derivative_gain")]:
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                check_quantity(0, unit, quantity)

    def test_nonfinite_boolean_and_nonpositive_geometry_are_rejected(self):
        for value in [True, float("nan"), float("inf"), 0, -1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                check_quantity(value, "mm", "length")

    def test_python_code_is_not_a_unit(self):
        for unit in ["__import__('os')", "m.__class__", "m[0]", "m**100", "m+K"]:
            with self.subTest(unit=unit), self.assertRaises(ValueError):
                parse_unit(unit)


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="comsol-synthetic-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.case_path = self.root / "case.json"
        self.run_dir = self.root / "run"
        self.model = self.root / "synthetic.mph"
        self.source = self.root / "synthetic-source.txt"
        self.model.write_bytes(b"SYNTHETIC: this is not an MPH file")
        self.source.write_text("SYNTHETIC source dependency", encoding="utf-8")
        self.tool_root = self.root / "synthetic-tools"
        for name in ("comsolcompile.exe", "comsolbatch.exe"):
            path = self.tool_root / "bin" / "win64" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"SYNTHETIC non-executable placeholder")
        self.case = synthetic_case()
        # A final safeguard in addition to mocking invoke: no subprocess may launch.
        self.popen_patch = patch("comsol_workflow.workflow.subprocess.Popen", side_effect=AssertionError("No process is permitted in offline tests"))
        self.popen = self.popen_patch.start()
        self.addCleanup(self.popen_patch.stop)

    def plan(self, execute_branch=False):
        if execute_branch:
            # Only bypass the provenance guard to test the separate run branch.
            # The title, sources, bytes, receipts and result remain visibly synthetic.
            self.case["provenance"]["kind"] = "user_model"
        write_json(self.case_path, self.case)
        return prepare(self.case_path, self.run_dir, self.tool_root)

    def receipt(self, plan, stage_name, **overrides):
        # This helper is not a real approval and is never used outside TemporaryDirectory.
        receipt = {"stage": stage_name, "content_digest": plan["content_digest"], "approved": True,
                   "approved_by": "SYNTHETIC TEST IDENTITY — NOT A HUMAN APPROVAL",
                   "approved_at": datetime.now(timezone.utc).isoformat(),
                   "decision_evidence": "fabricated unittest branch input, no human consent"}
        receipt.update(overrides)
        path = self.root / (stage_name + "-synthetic-receipt.json")
        write_json(path, receipt)
        return path

    def fake_successful_invocation(self, argv, cwd, log, timeout):
        """Fabricate outputs so the Python validation branch can be tested offline."""
        Path(log).write_text("SYNTHETIC PROCESS LOG; no process ran", encoding="utf-8")
        if "compile" in Path(argv[0]).name:
            (self.run_dir / "WorkflowDriver.class").write_bytes(b"SYNTHETIC bytecode placeholder")
        else:
            output = self.run_dir / "results"
            token = read_json(self.run_dir / "plan.json")["completion_token"]
            Path(log).write_text(f"SYNTHETIC PROCESS LOG; no process ran\nWORKFLOW_SOLVE_BEGIN {token}\n", encoding="utf-8")
            (output / "solved.mph").write_bytes(b"SYNTHETIC solved model placeholder")
            (output / "completed.ok").write_text(token)
            (output / "metrics.csv").write_text("time_s,temperature_degC\n0,20\n1,21\n", encoding="utf-8")
        return {"argv": argv, "exit_code": 0, "wall_seconds": 0}


class CaseValidationTests(TemporaryCase):
    def test_complete_synthetic_case_and_physical_constraint(self):
        self.assertTrue(validate(self.case, self.root)["valid"])
        self.case["parameters"][1]["value"] = 3
        checks = validate(self.case, self.root)
        self.assertFalse(checks["valid"])
        self.assertTrue(any("Constraint failed" in e for e in checks["errors"]))

    def test_unresolved_assumption_blocks_execution_readiness(self):
        self.case["engineering"]["unresolved"] = ["Unconfirmed outlet pressure"]
        self.assertFalse(validate(self.case, self.root)["valid"])

    def test_parameter_override_requires_explicit_physics_scope(self):
        del self.case["parameters"][0]["scope"]
        result = validate(self.case, self.root)
        self.assertFalse(result["valid"])
        self.assertTrue(any("scope=physics_scalar" in error for error in result["errors"]))
        self.case["parameters"][0]["scope"] = "geometry"
        self.assertFalse(validate(self.case, self.root)["valid"])

    def test_coordinate_only_manifest_is_not_a_physical_result(self):
        self.case["exports"] = self.case["exports"][:1]
        self.case["results"]["bounds"] = {}
        self.assertFalse(validate(self.case, self.root)["valid"])

    def test_passed_validation_requires_evidence(self):
        self.case["validation"]["conservation"] = "passed"
        checks = validate(self.case, self.root)
        self.assertFalse(checks["valid"])
        self.assertTrue(any("requires an evidence path" in e for e in checks["errors"]))

    def test_json_nan_is_rejected(self):
        self.case_path.write_text('{"value": NaN}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_json(self.case_path)


class GateTests(TemporaryCase):
    def test_plan_is_inert_and_requests_are_pending(self):
        plan = self.plan()
        self.assertTrue(plan["checks"]["valid"])
        for stage in ("assumptions", "solve"):
            receipt = read_json(self.run_dir / "approval_requests" / f"{stage}.json")
            self.assertIs(receipt["approved"], False)
            self.assertEqual(receipt["approved_by"], "")
        self.assertFalse((self.run_dir / "run.claim").exists())
        self.popen.assert_not_called()

    def test_fixture_can_never_launch_real_executor(self):
        plan = self.plan()
        with patch("comsol_workflow.workflow.invoke") as invoked:
            with self.assertRaisesRegex(ValueError, "Synthetic fixtures"):
                execute(self.run_dir, self.receipt(plan, "assumptions"), self.receipt(plan, "solve"))
            invoked.assert_not_called()

    def test_missing_and_pending_approvals_stop_before_process(self):
        self.plan(execute_branch=True)
        with patch("comsol_workflow.workflow.invoke") as invoked:
            with self.assertRaises(OSError):
                execute(self.run_dir, self.root / "missing.json", self.root / "missing-solve.json")
            with self.assertRaisesRegex(ValueError, "approval"):
                execute(self.run_dir, self.run_dir / "approval_requests/assumptions.json", self.run_dir / "approval_requests/solve.json")
            invoked.assert_not_called()
        self.assertFalse((self.run_dir / "run.claim").exists())

    def test_wrong_stage_stale_digest_and_missing_identity_are_rejected(self):
        plan = self.plan(execute_branch=True)
        cases = [
            {"stage": "solve"}, {"content_digest": "0" * 64},
            {"approved_by": ""}, {"decision_evidence": ""},
            {"approved_at": "2000-01-01T00:00:00"}, {"approved": "true"},
        ]
        for fields in cases:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                verify_receipt(self.receipt(plan, "assumptions", **fields), "assumptions", plan)

    def test_one_receipt_cannot_substitute_for_both_stages(self):
        plan = self.plan(execute_branch=True)
        assumptions = self.receipt(plan, "assumptions")
        with self.assertRaisesRegex(ValueError, "solve approval"):
            execute(self.run_dir, assumptions, assumptions)

    def test_solve_approval_cannot_precede_assumption_confirmation(self):
        plan = self.plan(execute_branch=True)
        assumptions = self.receipt(plan, "assumptions")
        solve = self.receipt(plan, "solve", approved_at=plan["created_at"])
        with self.assertRaisesRegex(ValueError, "follow assumption"):
            execute(self.run_dir, assumptions, solve)

    def test_approval_before_plan_or_in_future_is_rejected(self):
        plan = self.plan(execute_branch=True)
        times = [datetime.fromisoformat(plan["created_at"]) - timedelta(seconds=1),
                 datetime.now(timezone.utc) + timedelta(days=1)]
        for timestamp in times:
            with self.subTest(timestamp=timestamp), self.assertRaisesRegex(ValueError, "plan creation and now"):
                verify_receipt(self.receipt(plan, "assumptions", approved_at=timestamp.isoformat()), "assumptions", plan)

    def test_changed_model_dependency_case_and_driver_invalidate_plan(self):
        for target_name in ("model", "source", "case", "driver"):
            with self.subTest(target=target_name):
                self.run_dir = self.root / ("run-" + target_name)
                self.plan(execute_branch=True)
                target = {"model": self.model, "source": self.source, "case": self.case_path,
                          "driver": self.run_dir / "WorkflowDriver.java"}[target_name]
                original = target.read_bytes()
                target.write_bytes(original + b"\nSYNTHETIC modification after review")
                with self.assertRaisesRegex(ValueError, "changed"):
                    verify_plan(self.run_dir)
                target.write_bytes(original)

    def test_changed_plan_and_executor_are_rejected(self):
        self.plan(execute_branch=True)
        with patch("comsol_workflow.workflow.code_fingerprints", return_value={"changed": "hash"}):
            with self.assertRaisesRegex(ValueError, "Executor code changed"):
                verify_plan(self.run_dir)
        plan_path = self.run_dir / "plan.json"
        altered = read_json(plan_path)
        altered["cores"] = 2
        write_json(plan_path, altered)
        with self.assertRaisesRegex(ValueError, "Plan content changed"):
            verify_plan(self.run_dir)

    def test_mocked_execution_is_single_use_and_requires_engineering_review(self):
        plan = self.plan(execute_branch=True)
        assumptions, solve = self.receipt(plan, "assumptions"), self.receipt(plan, "solve")
        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", side_effect=self.fake_successful_invocation
        ) as invoked:
            result = execute(self.run_dir, assumptions, solve)
            self.assertEqual(result["status"], "execution_completed_engineering_review_required")
            self.assertTrue(result["comsol_solve_started"])
            self.assertEqual(invoked.call_count, 2)
            with self.assertRaises(FileExistsError):
                execute(self.run_dir, assumptions, solve)
            self.assertEqual(invoked.call_count, 2)
        self.popen.assert_not_called()
        text = (self.run_dir / "report.md").read_text(encoding="utf-8")
        self.assertIn("| conservation | not_run |", text)
        self.assertIn("not a proof of physical validity", text)

    def test_preexisting_bytecode_is_rejected_before_invocation(self):
        plan = self.plan(execute_branch=True)
        (self.run_dir / "WorkflowDriver.class").write_bytes(b"SYNTHETIC stale compiled output")
        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke"
        ) as invoked:
            with self.assertRaisesRegex(ValueError, "stale bytecode"):
                execute(self.run_dir, self.receipt(plan, "assumptions"), self.receipt(plan, "solve"))
            invoked.assert_not_called()
        self.assertFalse((self.run_dir / "run.claim").exists())

    def test_batch_launch_failure_does_not_claim_solver_started(self):
        plan = self.plan(execute_branch=True)

        def failed_launch(argv, cwd, log, timeout):
            if "compile" in Path(argv[0]).name:
                return self.fake_successful_invocation(argv, cwd, log, timeout)
            Path(log).write_text("SYNTHETIC launcher failed before Java entrypoint", encoding="utf-8")
            raise OSError("SYNTHETIC batch launch failure")

        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", side_effect=failed_launch
        ):
            result = execute(self.run_dir, self.receipt(plan, "assumptions"), self.receipt(plan, "solve"))
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["comsol_batch_attempted"])
        self.assertFalse(result["comsol_solve_started"])
        self.assertIn("solve started: False", (self.run_dir / "report.md").read_text(encoding="utf-8"))

    def test_model_changed_during_compilation_prevents_solve(self):
        plan = self.plan(execute_branch=True)

        def modifying_compiler(*args):
            value = self.fake_successful_invocation(*args)
            self.model.write_bytes(b"SYNTHETIC model changed while compiling")
            return value

        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", side_effect=modifying_compiler
        ) as invoked:
            result = execute(self.run_dir, self.receipt(plan, "assumptions"), self.receipt(plan, "solve"))
            self.assertEqual(result["status"], "failed")
            self.assertFalse(result["comsol_solve_started"])
            self.assertEqual(invoked.call_count, 1)

    def test_zero_exit_without_current_completion_marker_is_failure(self):
        plan = self.plan(execute_branch=True)

        def missing_marker(*args):
            value = self.fake_successful_invocation(*args)
            marker = self.run_dir / "results/completed.ok"
            if marker.exists():
                marker.write_text("stale-synthetic-token")
            return value

        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", side_effect=missing_marker
        ):
            result = execute(self.run_dir, self.receipt(plan, "assumptions"), self.receipt(plan, "solve"))
        self.assertEqual(result["status"], "failed")
        self.assertIn("completion marker", result["error"])
        self.assertIn("Status: **failed**", (self.run_dir / "report.md").read_text(encoding="utf-8"))

    def test_failed_compilation_is_not_reported_as_a_solve(self):
        plan = self.plan(execute_branch=True)
        with patch("comsol_workflow.workflow.platform.system", return_value="Windows"), patch(
            "comsol_workflow.workflow.invoke", return_value={"exit_code": 1, "wall_seconds": 0, "argv": ["SYNTHETIC"]}
        ):
            result = execute(self.run_dir, self.receipt(plan, "assumptions"), self.receipt(plan, "solve"))
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["comsol_solve_started"])
        self.assertIn("solve started: False", (self.run_dir / "report.md").read_text(encoding="utf-8"))

    def test_unexecuted_report_does_not_claim_success(self):
        self.plan()
        text = Path(report(self.run_dir)).read_text(encoding="utf-8")
        self.assertIn("Status: **not_executed**", text)
        self.assertIn("COMSOL invocation attempted: False", text)
        self.assertIn("| experimental_validation | not_run |", text)
        self.assertNotIn("Status: **execution_completed", text)


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="comsol-synthetic-csv-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def csv(self, filename, text):
        path = self.root / filename
        path.write_text(text, encoding="utf-8")
        return path

    def test_comparison_matches_named_columns_and_numerical_tolerance(self):
        actual = self.csv("actual.csv", "t,value\n0,10\n1,20.0001\n")
        reference = self.csv("reference.csv", "value,t\n10,0\n20,1\n")
        self.assertTrue(compare(actual, reference, "t", atol=0.001, rtol=0)["passed"])
        result = compare(actual, reference, "t", atol=0.000001, rtol=0)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failure_count"], 1)

    def test_coordinate_only_csv_comparison_is_rejected(self):
        actual = self.csv("actual.csv", "t\n0\n1\n")
        reference = self.csv("reference.csv", "t\n0\n1\n")
        with self.assertRaises(ValueError):
            compare(actual, reference, "t")

    def test_coordinate_mismatch_and_row_count_mismatch_are_not_interpolated(self):
        reference = self.csv("reference.csv", "t,value\n0,10\n1,20\n")
        for text in ["t,value\n0,10\n2,20\n", "t,value\n0,10\n", "t,value\n1,20\n0,10\n"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                compare(self.csv("actual.csv", text), reference, "t")

    def test_nan_infinity_duplicate_headers_and_ragged_rows_are_rejected(self):
        for text in ["t,value\n0,NaN\n", "t,value\n0,inf\n", "t,t\n0,1\n",
                     "t,value\n0\n", "t,value\n0,1,2\n", "t,value\n"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_csv(self.csv("invalid.csv", text))

    def test_approved_output_grid_and_bounds_are_checked(self):
        case = synthetic_case()
        path = self.csv("metrics.csv", "time_s,temperature_degC\n0,20\n1,21\n")
        self.assertTrue(validate_metrics(path, case)["passed"])
        path = self.csv("metrics.csv", "time_s,temperature_degC\n0,20\n2,101\n")
        result = validate_metrics(path, case)
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["issues"]), 2)

    def test_no_log_keywords_does_not_prove_convergence(self):
        log = self.csv("synthetic.log", "SYNTHETIC normal-looking log\n")
        result = diagnose(log)
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["convergence_status"], "requires_result_and_engineer_review")


class InvocationInterruptionTests(unittest.TestCase):
    def check_interruption(self, interruption, expected_reason):
        # Both Popen and taskkill are mocks. The fake PID never identifies a real process.
        process = Mock(pid=42424242)
        process.wait.side_effect = [interruption, 0]
        process.poll.return_value = None
        with tempfile.TemporaryDirectory(prefix="comsol-synthetic-interruption-") as folder:
            with patch("comsol_workflow.workflow.subprocess.Popen", return_value=process) as popen, patch(
                "comsol_workflow.workflow.subprocess.run", return_value=Mock(returncode=0)
            ) as stop_tree:
                with self.assertRaisesRegex(RuntimeError, expected_reason):
                    invoke(["SYNTHETIC-NOT-AN-EXECUTABLE"], folder, Path(folder) / "synthetic.log", 1)
            self.assertFalse(popen.call_args.kwargs["shell"])
            stop_tree.assert_called_once_with(
                ["taskkill", "/PID", "42424242", "/T", "/F"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            process.kill.assert_called_once_with()
            self.assertEqual(process.wait.call_count, 2)

    def test_timeout_stops_tree_and_raises_instead_of_success(self):
        self.check_interruption(subprocess.TimeoutExpired("SYNTHETIC", 1), "Timeout; process-tree stop")

    def test_keyboard_interrupt_stops_tree_and_raises_instead_of_success(self):
        self.check_interruption(KeyboardInterrupt(), "Interrupted; process-tree stop")


if __name__ == "__main__":
    unittest.main()
