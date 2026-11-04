import argparse
import json
from pathlib import Path
import sys

from .case import read_json, validate
from .comsol63 import toolchain
from .results import compare, diagnose
from .workflow import prepare, prepare_resume, execute, smoke, report, approval_template, verify_plan
from .approvals import keygen_interactive, approve_interactive


def parser():
    p = argparse.ArgumentParser(description="Reviewable COMSOL 6.3 workflow. smoke loads/inspects only; run requires signed human approval.")
    sub = p.add_subparsers(dest="command", required=True)
    q = sub.add_parser("init", help="Copy an intentionally incomplete case template")
    q.add_argument("directory")
    q = sub.add_parser("validate", help="Static manifest/unit/source checks; no COMSOL")
    q.add_argument("case")
    q = sub.add_parser("plan", help="Create an inert review bundle and pending approvals")
    q.add_argument("case")
    q.add_argument("--out", required=True)
    q.add_argument("--comsol-root")
    q.add_argument("--public-key", help="User-provisioned trusted Ed25519 public key")
    q = sub.add_parser("approval-template", help="Write a pending receipt; never approves")
    q.add_argument("run_dir")
    q.add_argument("--stage", choices=["assumptions", "solve", "resume"], required=True)
    q = sub.add_parser("approval-keygen", help="User-side TTY only: create an encrypted signing key")
    q.add_argument("--private-key", required=True)
    q.add_argument("--public-key", required=True)
    q = sub.add_parser("approve", help="User-side TTY only: sign one exact engineering or compute decision")
    q.add_argument("run_dir")
    q.add_argument("--stage", choices=["assumptions", "solve", "resume"], required=True)
    q.add_argument("--private-key", required=True)
    q.add_argument("--public-key", required=True)
    q.add_argument("--out", required=True)
    q.add_argument("--assumptions", help="Required signed parent receipt for solve/resume")
    q = sub.add_parser("smoke", aliases=["dry-run"], help="Native load/tag/scope inspection only; never solve or save an MPH")
    q.add_argument("run_dir")
    q = sub.add_parser("resume", help="Snapshot an interrupted run's recovery files into a new approval plan")
    q.add_argument("origin_dir")
    q.add_argument("--out", required=True)
    q.add_argument("--public-key")
    q.add_argument("--recovery-model", help="Actual model recovery subdirectory, inside the interrupted run's recovery root")
    q = sub.add_parser("run", help="Start the real solver only with two human approval receipts")
    q.add_argument("run_dir")
    q.add_argument("--assumptions", required=True)
    q.add_argument("--approval", required=True)
    q = sub.add_parser("report", help="Generate an evidence report, preserving unverified states")
    q.add_argument("run_dir")
    q = sub.add_parser("compare", help="Compare aligned CSVs; no interpolation")
    q.add_argument("actual")
    q.add_argument("reference")
    q.add_argument("--coordinate", required=True)
    q.add_argument("--atol", type=float, default=1e-6)
    q.add_argument("--rtol", type=float, default=1e-3)
    q.add_argument("--coordinate-atol", type=float, default=1e-9)
    q = sub.add_parser("diagnose", help="Read solver log hints; never automatically retries")
    q.add_argument("log")
    q = sub.add_parser("doctor", help="Inspect executable paths without starting COMSOL or checking a license")
    q.add_argument("--root", required=True)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            directory = Path(args.directory)
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / "case.json"
            template = Path(__file__).parent / "case.template.json"
            with target.open("x", encoding="utf-8") as out:
                out.write(template.read_text(encoding="utf-8"))
            result = {"case": str(target.resolve()), "status": "needs_engineering_input"}
        elif args.command == "validate":
            result = validate(read_json(args.case), Path(args.case).resolve().parent)
        elif args.command == "plan":
            plan = prepare(args.case, args.out, args.comsol_root, args.public_key)
            result = {"run_dir": plan["run_dir"], "review": str(Path(plan["run_dir"]) / "REVIEW.md"),
                      "approval_requests": str(Path(plan["run_dir"]) / "approval_requests"),
                      "digest": plan["content_digest"], "checks": plan["checks"], "status": "not_executed"}
        elif args.command == "approval-template":
            result = {"path": approval_template(args.run_dir, args.stage), "approved": False}
        elif args.command == "approval-keygen":
            result = keygen_interactive(args.private_key, args.public_key)
        elif args.command == "approve":
            plan, _ = verify_plan(args.run_dir)
            result = approve_interactive(plan, args.stage, args.private_key, args.out,
                                         args.public_key, parent_receipt=args.assumptions)
        elif args.command in ("smoke", "dry-run"):
            result = smoke(args.run_dir)
        elif args.command == "resume":
            plan = prepare_resume(args.origin_dir, args.out, args.public_key, args.recovery_model)
            result = {"run_dir": plan["run_dir"], "operation": "resume", "digest": plan["content_digest"],
                      "status": "not_executed", "checks": plan["checks"]}
        elif args.command == "run":
            result = execute(args.run_dir, args.assumptions, args.approval)
        elif args.command == "report":
            result = {"report": report(args.run_dir)}
        elif args.command == "compare":
            result = compare(args.actual, args.reference, args.coordinate, args.atol, args.rtol, args.coordinate_atol)
        elif args.command == "diagnose":
            result = diagnose(args.log)
        else:
            chain = toolchain(args.root)
            result = {"paths": chain, "exists": {name: Path(chain[name]).is_file() for name in ("compiler", "batch")},
                      "version_verified": False, "license_verified": False, "process_started": False}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        if result.get("valid") is False or result.get("passed") is False or result.get("status") == "failed":
            return 2
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
