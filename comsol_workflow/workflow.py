"""Review bundles, human receipts and single-use execution records."""
from datetime import datetime, timezone
import base64
from pathlib import Path
import platform
import shutil
import subprocess
import time
import uuid

from . import __version__
from .case import read_json, write_json, sha256, digest, validate, input_files
from .comsol63 import toolchain, generate, generate_smoke, commands
from .approvals import public_key_binding, verify_signed_receipt
from .scope import evaluate_scope
from .results import compare, validate_metrics, diagnose, read_csv


def now():
    return datetime.now(timezone.utc).isoformat()


def code_fingerprints():
    return {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def prepare(case_path, run_dir, comsol_root=None, approval_public_key=None,
            operation="solve", recovery_source=None, origin=None):
    case_path, run_dir = Path(case_path).resolve(), Path(run_dir).resolve()
    case = read_json(case_path)
    checks = validate(case, case_path.parent)
    # A fresh directory prevents accidental approval/result reuse.
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError("Use a new empty run directory for every plan")
    run_dir.mkdir(parents=True, exist_ok=True)
    if operation not in {"solve", "resume"}:
        raise ValueError("Unknown plan operation")
    recovery = None
    if operation == "resume":
        source = Path(recovery_source).resolve() if recovery_source else None
        if not source or not source.is_dir() or not any(p.is_file() for p in source.rglob("*")):
            raise ValueError("Recovery source must be a nonempty model recovery directory")
        if any(p.is_symlink() or not p.resolve().is_relative_to(source) for p in source.rglob("*")):
            raise ValueError("Recovery snapshot cannot contain symbolic links or escaping junctions")
        snapshot = run_dir / "checkpoint"
        shutil.copytree(source, snapshot)
        recovery = {"source_directory": str(source), "snapshot_directory": str(snapshot), "origin": origin}
    write_json(run_dir / "case.snapshot.json", case)
    inputs = input_files(case, case_path.parent)
    inputs.insert(0, {"path": str(case_path), "sha256": sha256(case_path)})
    if recovery:
        inputs.extend({"path": str(p), "sha256": sha256(p)} for p in sorted(snapshot.rglob("*")) if p.is_file())
    key = public_key_binding(approval_public_key) if approval_public_key else None
    if key:
        inputs.append({"path": key["path"], "sha256": key["sha256"]})
    token = uuid.uuid4().hex
    recovery_path = recovery["snapshot_directory"] if recovery else None
    driver = generate(case, case_path.parent, run_dir, token, operation, recovery_path)
    (run_dir / "WorkflowDriver.java").write_text(driver, encoding="utf-8")
    (run_dir / "SmokeDriver.java").write_text(generate_smoke(case, case_path.parent, run_dir, token, recovery_path), encoding="utf-8")
    chain = toolchain(comsol_root) if comsol_root else None
    if not chain:
        checks["errors"].append("COMSOL root not supplied; plan is review-only")
    else:
        for name in ("compiler", "batch"):
            path = Path(chain[name])
            if not path.is_file():
                checks["errors"].append(f"Missing COMSOL tool: {path}")
            inputs.append({"path": str(path), "sha256": sha256(path) if path.is_file() else None})
    checks["valid"] = not checks["errors"]
    review = [f"# Review: {case['title']}", "", "This plan has not launched COMSOL.", "",
              "## Engineering assumptions", "", *[f"- {a}" for a in case["engineering"]["assumptions"]],
              "", "## Scope", "", "Geometry, materials, physics, mesh and solver sequence are inherited from the reviewed MPH.",
              "Read case.snapshot.json, WorkflowDriver.java and the source model before approving.",
              f"Solver sequence: {case['model']['solver_tag']}; dataset: {case['model']['dataset_tag']}.",
              f"Resources: {case['execution']['cores']} cores, timeout {case['execution']['timeout_seconds']} s.",
              f"Recovery interval: {case['execution'].get('recovery_interval_seconds', 'COMSOL preferences')} seconds; snapshots only exist after COMSOL writes a checkpoint.",
              "", "## Acceptance", "", *[f"- {a}" for a in case['engineering']['acceptance']],
              "", "## Blocking issues", "", *[f"- {e}" for e in checks['errors']],
              "", "## Human gates", "",
              "1. Confirm assumptions and source-model review in the assumptions receipt.",
              "2. Separately approve this exact solve in the solve receipt, including runtime and outputs.",
              "The user signs each decision using an encrypted private key outside agent authority.",
              "Hand-edited approved=true receipts are rejected. Protect the pinned public key and verifier.",
              f"Operation: {operation}; approval key: {key['keyid'] if key else 'NOT PROVISIONED; execution is blocked'}."]
    (run_dir / "REVIEW.md").write_text("\n".join(review) + "\n", encoding="utf-8")
    plan = {
        "schema_version": 1, "workflow_version": __version__, "created_at": now(),
        "run_dir": str(run_dir), "case_base": str(case_path.parent),
        "input_files": inputs, "code_fingerprints": code_fingerprints(),
        "toolchain": chain, "cores": case["execution"]["cores"],
        "timeout_seconds": case["execution"]["timeout_seconds"], "completion_token": token,
        "operation": operation, "recovery": recovery, "approval_public_key": key,
        "checks": checks, "bundle_hashes": {n: sha256(run_dir / n) for n in ("case.snapshot.json", "WorkflowDriver.java", "SmokeDriver.java", "REVIEW.md")},
    }
    plan["content_digest"] = digest(plan)
    write_json(run_dir / "plan.json", plan)
    for stage in ("assumptions", operation):
        approval_template(run_dir, stage)
    report(run_dir)
    return plan


def approval_template(run_dir, stage):
    if stage not in {"assumptions", "solve", "resume"}:
        raise ValueError("Unknown approval stage")
    run_dir = Path(run_dir)
    plan = read_json(run_dir / "plan.json")
    destination = run_dir / "approval_requests" / f"{stage}.json"
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        raise ValueError("Approval template already exists; preserve it or use a new plan")
    write_json(destination, {"stage": stage, "content_digest": plan["content_digest"],
                            "approved": False, "approved_by": "", "approved_at": "",
                            "decision_evidence": "", "note": "This is a request, not an accepted receipt. Use the interactive approve command to produce an Ed25519 signature."})
    return str(destination)


def verify_receipt(path, stage, plan, parent_receipt=None):
    binding = plan.get("approval_public_key")
    if not binding:
        raise ValueError("A user-provisioned approval public key is required; create a new signed-approval plan")
    return verify_signed_receipt(path, stage, plan, binding["path"], parent_receipt=parent_receipt)


def verify_plan(run_dir):
    run_dir = Path(run_dir).resolve()
    plan = read_json(run_dir / "plan.json")
    expected_digest = plan.pop("content_digest")
    if digest(plan) != expected_digest:
        raise ValueError("Plan content changed; create a new plan and obtain new approvals")
    plan["content_digest"] = expected_digest
    if str(run_dir) != plan["run_dir"]:
        raise ValueError("Plan moved; regenerate paths and approvals")
    if plan["code_fingerprints"] != code_fingerprints():
        raise ValueError("Executor code changed since review")
    for name, expected in plan["bundle_hashes"].items():
        if sha256(run_dir / name) != expected:
            raise ValueError(f"Review bundle changed: {name}")
    for item in plan["input_files"]:
        if item["sha256"] is None or not Path(item["path"]).is_file() or sha256(item["path"]) != item["sha256"]:
            raise ValueError(f"Input missing or changed: {item['path']}")
    if plan.get("recovery"):
        snapshot = Path(plan["recovery"]["snapshot_directory"])
        expected = {item["path"] for item in plan["input_files"] if Path(item["path"]).is_relative_to(snapshot)}
        actual = {str(p) for p in snapshot.rglob("*") if p.is_file()}
        if actual != expected or any(p.is_symlink() or not p.resolve().is_relative_to(snapshot) for p in snapshot.rglob("*")):
            raise ValueError("Recovery snapshot file set changed after review")
    if not plan["checks"]["valid"]:
        raise ValueError("Plan contains blocking issues")
    case = read_json(run_dir / "case.snapshot.json")
    if not validate(case, plan["case_base"])["valid"]:
        raise ValueError("Case no longer passes static checks")
    if case["provenance"]["kind"] == "synthetic_fixture":
        raise ValueError("Synthetic fixtures cannot launch COMSOL")
    return plan, case


def invoke(argv, cwd, log, timeout):
    started = time.monotonic()
    with Path(log).open("w", encoding="utf-8") as output:
        process = subprocess.Popen(argv, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, shell=False)
        try:
            code = process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as interrupted:
            # Stop Windows descendants as well as the launcher, retaining native logs.
            killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)
            reason = "Timeout" if isinstance(interrupted, subprocess.TimeoutExpired) else "Interrupted"
            raise RuntimeError(f"{reason}; process-tree stop exit={killed.returncode}. Check native logs and remaining COMSOL processes.")
    return {"argv": argv, "exit_code": code, "wall_seconds": time.monotonic() - started}


def smoke(run_dir):
    """Compile/run only the separate load-and-inspect driver; never solve or save MPH."""
    run_dir = Path(run_dir).resolve()
    plan, case = verify_plan(run_dir)
    if platform.system() != "Windows":
        raise ValueError("Native COMSOL smoke checks require Windows")
    directory = run_dir / "inspection"
    record_path = directory / "inspection-state.json"
    if record_path.exists():
        cached = read_json(record_path)
        if cached.get("status") != "passed" or cached.get("plan_digest") != plan["content_digest"]:
            raise ValueError("Prior inspection failed or changed; create a new plan")
        required = {"compile.log", "launcher.log", "batch.log", "scope-inventory.json", "smoke.ok"}
        if not required.issubset(cached.get("artifacts", {})):
            raise ValueError("Inspection evidence is incomplete; create a new plan")
        for name, expected in cached["artifacts"].items():
            if Path(name).name != name:
                raise ValueError("Invalid inspection artifact path")
            if sha256(directory / name) != expected:
                raise ValueError("Inspection evidence changed; create a new plan")
        if (directory / "smoke.ok").read_text().strip() != plan["completion_token"]:
            raise ValueError("Inspection token differs from this plan")
        if f"WORKFLOW_SMOKE_COMPLETED {plan['completion_token']}" not in (directory / "launcher.log").read_text(encoding="utf-8", errors="replace"):
            raise ValueError("Native inspection completion evidence is missing")
        overrides = [] if plan.get("operation") == "resume" else case["parameters"]
        cached["scope"] = evaluate_scope(read_json(directory / "scope-inventory.json"), overrides)
        if not cached["scope"]["passed"]:
            raise ValueError("Cached parameter scope is unsafe or incomplete")
        return cached
    if directory.exists() or (run_dir / "SmokeDriver.class").exists():
        raise ValueError("Unrecorded inspection artifacts exist; create a new plan")
    directory.mkdir()
    state = {"status": "running", "started_at": now(), "plan_digest": plan["content_digest"],
             "mode": "load_and_inspect_only", "solve_requested": False, "commands": []}
    write_json(record_path, state)
    try:
        compile_cmd, inspect_cmd = commands(plan, run_dir, "smoke")
        compiled = invoke(compile_cmd, run_dir, directory / "compile.log", min(plan["timeout_seconds"], 300))
        state["commands"].append(compiled)
        if compiled["exit_code"] or not (run_dir / "SmokeDriver.class").is_file():
            raise RuntimeError("Smoke driver compilation failed")
        verify_plan(run_dir)
        inspected = invoke(inspect_cmd, run_dir, directory / "launcher.log", min(plan["timeout_seconds"], 300))
        state["commands"].append(inspected)
        if any(not (directory / name).is_file() for name in ("launcher.log", "batch.log")):
            raise RuntimeError("Required native inspection log is missing")
        logs = (directory / "launcher.log").read_text(encoding="utf-8", errors="replace")
        if inspected["exit_code"] or f"WORKFLOW_SMOKE_COMPLETED {plan['completion_token']}" not in logs:
            raise RuntimeError("COMSOL load/inspection failed")
        capture_payloads(logs, plan["completion_token"], directory, {"inventory": "scope-inventory.json"})
        (directory / "smoke.ok").write_text(plan["completion_token"] + "\n", encoding="utf-8")
        inventory = read_json(directory / "scope-inventory.json")
        overrides = [] if plan.get("operation") == "resume" else case["parameters"]
        state["scope"] = evaluate_scope(inventory, overrides)
        if not state["scope"]["passed"]:
            raise RuntimeError("Parameter scope is unsafe or incomplete; inspect scope-inventory.json")
        verify_plan(run_dir)
        state["status"] = "passed"
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = str(exc)
    finally:
        state["finished_at"] = now()
        state["artifacts"] = {p.name: sha256(p) for p in directory.iterdir() if p.is_file() and p != record_path}
        write_json(record_path, state)
    return state


def capture_payloads(logs, token, destination, filenames):
    """Persist token-bound UTF-8 payloads without weakening COMSOL's Java policy.

    Java writes to its existing stdout only. The trusted host chooses filenames;
    model output cannot supply filesystem destinations. Repeated identical
    recovery records are accepted; conflicting records fail closed.
    """
    prefix = f"WORKFLOW_DATA {token} "
    found = {}
    for line in logs.splitlines():
        if not line.startswith(prefix):
            continue
        kind, encoded = line[len(prefix):].split(" ", 1)
        if kind not in filenames:
            continue
        value = base64.b64decode(encoded, validate=True).decode("utf-8")
        if kind in found and found[kind] != value:
            raise ValueError(f"Conflicting native payload: {kind}")
        found[kind] = value
    for kind, filename in filenames.items():
        if kind not in found:
            raise ValueError(f"Native output payload missing: {kind}")
        (Path(destination) / filename).write_text(found[kind], encoding="utf-8")
    return found


def prepare_resume(origin_dir, run_dir, approval_public_key=None, recovery_model=None):
    """Snapshot an interrupted run's recovery files into a separately approved plan."""
    origin_dir = Path(origin_dir).resolve()
    plan, _ = verify_plan(origin_dir)
    state = read_json(origin_dir / "run-state.json")
    if state.get("status") != "failed" or not state.get("comsol_solve_started"):
        raise ValueError("Resume requires a recorded interrupted/failed solve, not a completed or unstarted run")
    root = (origin_dir / "recovery").resolve()
    if recovery_model is None:
        marker = origin_dir / "results/recovery-model-path.txt"
        if not marker.is_file():
            raise ValueError("Recovery path was not recorded; inspect the recovery root and supply --recovery-model")
        recovery_model = marker.read_text(encoding="utf-8-sig").strip()
    source = Path(recovery_model).resolve()
    if not source.is_relative_to(root):
        raise ValueError("Recovery source must be inside the failed run's recorded recovery root")
    key = approval_public_key or (plan.get("approval_public_key") or {}).get("path")
    return prepare(plan["input_files"][0]["path"], run_dir, plan["toolchain"]["root"], key,
                   operation="resume", recovery_source=source,
                   origin={"run_dir": str(origin_dir), "content_digest": plan["content_digest"],
                           "state_sha256": sha256(origin_dir / "run-state.json")})


def execute(run_dir, assumptions_path, solve_path):
    run_dir = Path(run_dir).resolve()
    plan, case = verify_plan(run_dir)
    assumptions = verify_receipt(assumptions_path, "assumptions", plan)
    operation = plan.get("operation", "solve")
    solve = verify_receipt(solve_path, operation, plan, parent_receipt=assumptions_path)
    if datetime.fromisoformat(solve["approved_at"].replace("Z", "+00:00")) < datetime.fromisoformat(assumptions["approved_at"].replace("Z", "+00:00")):
        raise ValueError("Solve approval must follow assumption confirmation")
    if platform.system() != "Windows":
        raise ValueError("COMSOL 6.3 execution is implemented for Windows only; offline tooling is portable")
    if (run_dir / "run.claim").exists():
        raise FileExistsError("This plan was already attempted; use a new run directory")
    if (run_dir / "WorkflowDriver.class").exists():
        raise ValueError("Compiled output already exists; use a fresh plan to avoid stale bytecode")
    # Atomic single-use claim; a failed or interrupted run requires a fresh plan.
    with (run_dir / "run.claim").open("x", encoding="utf-8") as claim:
        claim.write(now())
    result_dir = run_dir / "results"
    if result_dir.exists():
        raise ValueError("Results directory already exists; use a new plan")
    result_dir.mkdir()
    shutil.copyfile(assumptions_path, result_dir / "assumptions.receipt.json")
    shutil.copyfile(solve_path, result_dir / f"{operation}.receipt.json")
    (run_dir / "recovery").mkdir()
    state = {"status": "running", "started_at": now(), "real_comsol_attempted": False,
             "comsol_batch_attempted": False, "comsol_solve_started": False,
             "operation": operation, "recovery_root": str(run_dir / "recovery"),
             "commands": [], "plan_digest": plan["content_digest"]}
    write_json(run_dir / "run-state.json", state)
    try:
        state["real_comsol_attempted"] = True
        write_json(run_dir / "run-state.json", state)
        state["inspection"] = smoke(run_dir)
        if state["inspection"]["status"] != "passed":
            raise RuntimeError("Native smoke/scope check failed; solve was not started")
        compile_cmd, solve_cmd = commands(plan, run_dir)
        state["real_comsol_attempted"] = True
        write_json(run_dir / "run-state.json", state)
        compilation = invoke(compile_cmd, run_dir, result_dir / "compile.log", min(plan["timeout_seconds"], 300))
        state["commands"].append(compilation)
        if compilation["exit_code"] != 0 or not (run_dir / "WorkflowDriver.class").is_file():
            raise RuntimeError("COMSOL Java compilation failed")
        # Catch a changed source/model while compilation ran, before the expensive solve.
        verify_plan(run_dir)
        state["comsol_batch_attempted"] = True
        write_json(run_dir / "run-state.json", state)
        solved = invoke(solve_cmd, run_dir, result_dir / "launcher.log", plan["timeout_seconds"])
        state["commands"].append(solved)
        if solved["exit_code"] != 0:
            raise RuntimeError("COMSOL batch returned nonzero")
        for required_log in ("launcher.log", "batch.log"):
            if not (result_dir / required_log).is_file():
                raise RuntimeError(f"Required native log missing: {required_log}")
        logs = "\n".join((result_dir / name).read_text(encoding="utf-8", errors="replace") for name in ("launcher.log", "batch.log"))
        expected_begin = "WORKFLOW_RESUME_BEGIN" if operation == "resume" else "WORKFLOW_SOLVE_BEGIN"
        if f"{expected_begin} {plan['completion_token']}" not in logs or f"WORKFLOW_COMPLETED {plan['completion_token']} rows=" not in logs:
            raise RuntimeError("Current-run begin/completion evidence missing from native logs")
        destinations = {"metrics": "metrics.csv"}
        if case.get("postprocess", {}).get("table"):
            destinations["table"] = case["postprocess"]["table"]["filename"]
        capture_payloads((result_dir / "launcher.log").read_text(encoding="utf-8", errors="replace"), plan["completion_token"], result_dir, destinations)
        (result_dir / "completed.ok").write_text(plan["completion_token"] + "\n", encoding="utf-8")
        if not (result_dir / "solved.mph").is_file() or (result_dir / "solved.mph").stat().st_size == 0:
            raise RuntimeError("Solved MPH is missing or empty")
        state["output_checks"] = validate_metrics(result_dir / "metrics.csv", case)
        if not state["output_checks"]["passed"]:
            raise RuntimeError("Output validation failed")
        for kind, config in case.get("postprocess", {}).items():
            artifact = result_dir / config["filename"]
            if not artifact.is_file() or not artifact.stat().st_size:
                raise RuntimeError(f"Postprocessing artifact missing: {kind}")
            if kind == "field_plot" and artifact.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError("Field export is not a PNG")
            if kind == "table":
                names, rows = read_csv(artifact)
                if len(rows) != state["output_checks"]["rows"] or len(names) != len(case["exports"]):
                    raise RuntimeError("COMSOL table export shape differs from approved metrics")
        reference = case["results"].get("reference_csv")
        if reference:
            spec = case["results"]
            state["comparison"] = compare(result_dir / "metrics.csv", Path(plan["case_base"]) / reference,
                                          spec["coordinate"], spec["atol"], spec["rtol"], spec["coordinate_atol"])
            if not state["comparison"]["passed"]:
                raise RuntimeError("Numerical reference comparison failed")
        state["status"] = "execution_completed_engineering_review_required"
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = str(exc)
    finally:
        state["finished_at"] = now()
        if (result_dir / "launcher.log").is_file():
            try:
                capture_payloads((result_dir / "launcher.log").read_text(encoding="utf-8", errors="replace"), plan["completion_token"], result_dir, {"recovery": "recovery-model-path.txt"})
            except (ValueError, OSError) as exc:
                state["recovery_note"] = str(exc)
        state["comsol_solve_started"] = any(
            any(f"{marker} {plan['completion_token']}" in p.read_text(encoding="utf-8", errors="replace") for marker in ("WORKFLOW_SOLVE_BEGIN", "WORKFLOW_RESUME_BEGIN"))
            for p in (result_dir / "launcher.log", result_dir / "batch.log") if p.is_file())
        state["artifacts"] = {str(p.relative_to(run_dir)): sha256(p) for p in result_dir.iterdir() if p.is_file()}
        for name in ("progress.log", "batch.log", "launcher.log"):
            if (result_dir / name).is_file():
                state.setdefault("diagnostics", {})[name] = diagnose(result_dir / name)
        write_json(run_dir / "run-state.json", state)
        report(run_dir)
    return state


def report(run_dir):
    run_dir = Path(run_dir)
    plan = read_json(run_dir / "plan.json")
    case = read_json(run_dir / "case.snapshot.json")
    state_path = run_dir / "run-state.json"
    state = read_json(state_path) if state_path.exists() else {"status": "not_executed", "real_comsol_attempted": False, "comsol_solve_started": False}
    lines = [f"# {case['title']}", "", f"Status: **{state['status']}**", "",
             f"Plan digest: `{plan['content_digest']}`", "",
             f"COMSOL invocation attempted: {state['real_comsol_attempted']}; solve started: {state.get('comsol_solve_started', False)}.", "",
             "## Evidence", "", "- Configuration: case.snapshot.json", "- Review: REVIEW.md",
             "- Generated executor: WorkflowDriver.java", "- Input fingerprints: plan.json", ""]
    if state.get("error"):
        lines += [f"Execution error: {state['error']}", ""]
    if state_path.exists():
        lines += ["Run details, command exit codes, checks, diagnostics and artifact hashes: run-state.json.", ""]
    inspection_path = run_dir / "inspection/inspection-state.json"
    if inspection_path.exists():
        inspected = read_json(inspection_path)
        lines += [f"Load-only smoke: **{inspected['status']}**; details: inspection/inspection-state.json.",
                  "The smoke driver does not run a solver, rebuild geometry/mesh or save an MPH.", ""]
    lines += [f"Operation: {plan.get('operation', 'solve')}; signed approvals: Ed25519, bound to the reviewed plan and parent receipt.", ""]
    if state.get("status") == "execution_completed_engineering_review_required":
        _, rows = read_csv(run_dir / "results/metrics.csv")
        lines += ["## Numerical outputs", "", f"Rows: {len(rows)}. Values are at the approved exported coordinates.", "",
                  "| Metric | Unit | First | Last | Minimum at exported points | Maximum at exported points |",
                  "|---|---|---:|---:|---:|---:|"]
        for column in case["exports"]:
            values = [row[column["name"]] for row in rows]
            lines.append(f"| {column['name']} | {column['unit']} | {values[0]:.9g} | {values[-1]:.9g} | {min(values):.9g} | {max(values):.9g} |")
        comparison = state.get("comparison")
        lines += ["", f"Reference comparison: {comparison['passed'] if comparison else 'not run; reference not supplied'}.", ""]
        plot = case.get("postprocess", {}).get("field_plot")
        table = case.get("postprocess", {}).get("table")
        if plot:
            lines += [f"![COMSOL field export](results/{plot['filename']})", ""]
        if table:
            lines += [f"[COMSOL table readback CSV](results/{table['filename']})", ""]
    lines += ["## Engineering validation", "", "These are declared case states, not inferred from an exit code.", "",
              "| Check | State |", "|---|---|"]
    for key, value in case["validation"].items():
        if key != "evidence":
            lines.append(f"| {key} | {value} |")
    lines += ["", "## Limits", "", "A successful numerical run is not a proof of physical validity.",
              "Reference agreement, mesh/time-step independence, conservation and experimental validation are separate claims.",
              "Unexecuted or missing checks remain unverified. Field-plot review and engineering acceptance require a human.",
              "", "## Blocking plan issues", "", *[f"- {error}" for error in plan['checks']['errors']]]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(run_dir / "report.md")
