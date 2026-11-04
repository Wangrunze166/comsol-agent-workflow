"""Review bundles, human receipts and single-use execution records."""
from datetime import datetime, timezone
from pathlib import Path
import platform
import subprocess
import time
import uuid

from . import __version__
from .case import read_json, write_json, sha256, digest, validate, input_files
from .comsol63 import toolchain, generate, commands
from .results import compare, validate_metrics, diagnose, read_csv


def now():
    return datetime.now(timezone.utc).isoformat()


def code_fingerprints():
    return {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def prepare(case_path, run_dir, comsol_root=None):
    case_path, run_dir = Path(case_path).resolve(), Path(run_dir).resolve()
    case = read_json(case_path)
    checks = validate(case, case_path.parent)
    # A fresh directory prevents accidental approval/result reuse.
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError("Use a new empty run directory for every plan")
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "case.snapshot.json", case)
    inputs = input_files(case, case_path.parent)
    inputs.insert(0, {"path": str(case_path), "sha256": sha256(case_path)})
    token = uuid.uuid4().hex
    driver = generate(case, case_path.parent, run_dir, token)
    (run_dir / "WorkflowDriver.java").write_text(driver, encoding="utf-8")
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
              "", "## Acceptance", "", *[f"- {a}" for a in case['engineering']['acceptance']],
              "", "## Blocking issues", "", *[f"- {e}" for e in checks['errors']],
              "", "## Human gates", "",
              "1. Confirm assumptions and source-model review in the assumptions receipt.",
              "2. Separately approve this exact solve in the solve receipt, including runtime and outputs.",
              "The agent must transcribe an actual human decision, never generate consent.",
              "Receipts are local audit records, not cryptographic proof of identity."]
    (run_dir / "REVIEW.md").write_text("\n".join(review) + "\n", encoding="utf-8")
    plan = {
        "schema_version": 1, "workflow_version": __version__, "created_at": now(),
        "run_dir": str(run_dir), "case_base": str(case_path.parent),
        "input_files": inputs, "code_fingerprints": code_fingerprints(),
        "toolchain": chain, "cores": case["execution"]["cores"],
        "timeout_seconds": case["execution"]["timeout_seconds"], "completion_token": token,
        "checks": checks, "bundle_hashes": {n: sha256(run_dir / n) for n in ("case.snapshot.json", "WorkflowDriver.java", "REVIEW.md")},
    }
    plan["content_digest"] = digest(plan)
    write_json(run_dir / "plan.json", plan)
    for stage in ("assumptions", "solve"):
        approval_template(run_dir, stage)
    report(run_dir)
    return plan


def approval_template(run_dir, stage):
    if stage not in {"assumptions", "solve"}:
        raise ValueError("Unknown approval stage")
    run_dir = Path(run_dir)
    plan = read_json(run_dir / "plan.json")
    destination = run_dir / "approval_requests" / f"{stage}.json"
    destination.parent.mkdir(exist_ok=True)
    if destination.exists():
        raise ValueError("Approval template already exists; preserve it or use a new plan")
    write_json(destination, {"stage": stage, "content_digest": plan["content_digest"],
                            "approved": False, "approved_by": "", "approved_at": "",
                            "decision_evidence": "", "note": "Human decision required. Copy to a private approvals directory; preserve the digest."})
    return str(destination)


def verify_receipt(path, stage, plan):
    receipt = read_json(path)
    if receipt.get("stage") != stage or receipt.get("content_digest") != plan["content_digest"] or receipt.get("approved") is not True:
        raise ValueError(f"Missing, declined or stale {stage} approval")
    if not all(isinstance(receipt.get(k), str) and receipt[k].strip() for k in ("approved_by", "approved_at", "decision_evidence")):
        raise ValueError(f"{stage} receipt requires human identity, timestamp and decision evidence")
    timestamp = datetime.fromisoformat(receipt["approved_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("Approval timestamp must include a timezone")
    if not datetime.fromisoformat(plan["created_at"]) <= timestamp <= datetime.now(timezone.utc):
        raise ValueError("Approval timestamp must fall between plan creation and now")
    return receipt


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


def execute(run_dir, assumptions_path, solve_path):
    run_dir = Path(run_dir).resolve()
    plan, case = verify_plan(run_dir)
    assumptions = verify_receipt(assumptions_path, "assumptions", plan)
    solve = verify_receipt(solve_path, "solve", plan)
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
    write_json(result_dir / "assumptions.receipt.json", assumptions)
    write_json(result_dir / "solve.receipt.json", solve)
    state = {"status": "running", "started_at": now(), "real_comsol_attempted": False,
             "comsol_batch_attempted": False, "comsol_solve_started": False,
             "commands": [], "plan_digest": plan["content_digest"]}
    write_json(run_dir / "run-state.json", state)
    try:
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
        if (result_dir / "completed.ok").read_text().strip() != plan["completion_token"]:
            raise RuntimeError("Missing current-run completion marker")
        if not (result_dir / "solved.mph").is_file() or (result_dir / "solved.mph").stat().st_size == 0:
            raise RuntimeError("Solved MPH is missing or empty")
        state["output_checks"] = validate_metrics(result_dir / "metrics.csv", case)
        if not state["output_checks"]["passed"]:
            raise RuntimeError("Output validation failed")
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
        state["comsol_solve_started"] = any(
            f"WORKFLOW_SOLVE_BEGIN {plan['completion_token']}" in p.read_text(encoding="utf-8", errors="replace")
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
