"""Conservative evidence checks; numerical agreement is separate from physics validation."""
import csv
import math
from pathlib import Path
import re


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames
        if not names or len(names) != len(set(names)):
            raise ValueError("CSV requires unique column names")
        rows = []
        for raw in reader:
            if set(raw) != set(names) or any(value is None for value in raw.values()):
                raise ValueError("CSV contains missing or extra columns")
            row = {name: float(raw[name]) for name in names}
            if not all(math.isfinite(v) for v in row.values()):
                raise ValueError("CSV contains NaN or infinity")
            rows.append(row)
        if not rows:
            raise ValueError("CSV has no data rows")
        return names, rows


def compare(actual, reference, coordinate, atol=1e-6, rtol=1e-3, coordinate_atol=1e-9):
    if any(not math.isfinite(x) or x < 0 for x in (atol, rtol, coordinate_atol)):
        raise ValueError("Comparison tolerances must be finite and nonnegative")
    names, rows = read_csv(actual)
    ref_names, ref_rows = read_csv(reference)
    if set(names) != set(ref_names) or coordinate not in names or len(rows) != len(ref_rows):
        raise ValueError("Comparison requires matching named columns, coordinate and row counts")
    if len(names) < 2:
        raise ValueError("Comparison requires at least one physical metric besides the coordinate")
    for dataset in (rows, ref_rows):
        if any(b[coordinate] <= a[coordinate] for a, b in zip(dataset, dataset[1:])):
            raise ValueError("Coordinates must be strictly increasing; no implicit sorting/interpolation")
    maxima = {name: 0.0 for name in names if name != coordinate}
    failures = []
    for i, (row, ref) in enumerate(zip(rows, ref_rows)):
        if abs(row[coordinate] - ref[coordinate]) > coordinate_atol:
            raise ValueError(f"Coordinate mismatch at row {i + 1}; no interpolation performed")
        for name in maxima:
            error = abs(row[name] - ref[name])
            maxima[name] = max(maxima[name], error)
            if error > atol + rtol * abs(ref[name]):
                failures.append({"row": i + 1, "column": name, "absolute_error": error})
    return {"kind": "numerical_reference_comparison", "passed": not failures,
            "rows": len(rows), "max_absolute_error": maxima, "failure_count": len(failures),
            "first_failures": failures[:20], "atol": atol, "rtol": rtol,
            "limitation": "Agreement does not establish mesh/time-step independence or experimental validity."}


def validate_metrics(path, case):
    names, rows = read_csv(path)
    if names != [c["name"] for c in case["exports"]]:
        raise ValueError("Result columns differ from the approved manifest")
    spec = case["results"]
    actual = [r[spec["coordinate"]] for r in rows]
    expected = spec["expected_coordinates"]
    issues = []
    if len(actual) != len(expected) or any(abs(a-b) > spec["coordinate_atol"] for a, b in zip(actual, expected)):
        issues.append("Output coordinates do not match the approved sweep/time grid")
    for name, bounds in spec.get("bounds", {}).items():
        if any(not bounds[0] <= row[name] <= bounds[1] for row in rows):
            issues.append(f"Result outside approved bounds: {name}")
    return {"passed": not issues, "rows": len(rows), "issues": issues}


def diagnose(path):
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    patterns = {
        "license": (r"license.*(?:error|fail|not available)|许可证.*(?:失败|不可用)", "Check required modules and license availability before rerun."),
        "memory": (r"out of memory|insufficient memory|内存不足", "Inspect DOFs and memory budget; assess mesh/solver changes before a new plan."),
        "singular": (r"singular matrix|void equation|奇异矩阵", "Inspect constraints, disconnected domains, material values and null spaces."),
        "nonlinear": (r"failed to converge|no convergence|不收敛|未收敛", "Inspect residual history, scaling, initial state and coupling; use reviewed continuation."),
        "time_step": (r"time.step.*(?:fail|error)|(?:Tfail|NLfail)", "Inspect final time and retry counters; failed attempts alone do not mean final failure."),
    }
    findings = []
    lines = text.splitlines()
    for key, (pattern, advice) in patterns.items():
        matches = [line[:400] for line in lines if re.search(pattern, line, re.I)]
        if matches:
            findings.append({"category": key, "evidence": matches[:5], "next_check": advice})
    return {"findings": findings, "convergence_status": "requires_result_and_engineer_review",
            "limitation": "Keyword hints only; no matches never proves convergence. Preserve the raw log."}
