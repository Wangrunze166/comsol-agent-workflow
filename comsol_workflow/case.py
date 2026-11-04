"""Case manifest validation and source fingerprints; no COMSOL process is started."""
import hashlib
import json
import math
from pathlib import Path
import re
from .units import check_quantity, parse_unit, QUANTITIES

TAG = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def read_json(path):
    def reject(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=reject)


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def resolve_input(base, name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Input path must be nonempty")
    return (Path(base) / name).resolve()


def validate(case, base):
    errors, warnings = [], []
    warnings.append("Static checks do not verify MPH internals, boundary coverage, nonlinear convergence or physical validity.")
    try:
        if case["schema_version"] != 1:
            errors.append("schema_version must be 1")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", case["case_id"]):
            errors.append("case_id must use lowercase letters, digits and hyphens")
        if not case["title"] or not case["provenance"]["sources"]:
            errors.append("title and provenance.sources are required")
        if case["provenance"]["kind"] not in {"official_example", "user_model", "synthetic_fixture"}:
            errors.append("Unknown provenance kind")
        model = case["model"]
        if model["comsol_version"] != "6.3":
            errors.append("This executor supports COMSOL 6.3 only")
        for key in ("solver_tag", "study_tag", "dataset_tag"):
            if not TAG.fullmatch(model[key]):
                errors.append(f"model.{key} is not a valid tag")
        if not model["clear_solution_tags"] or model["solver_tag"] not in model["clear_solution_tags"]:
            errors.append("clear_solution_tags must include the selected solver to prevent stale-solution reuse")
        for tag in model["clear_solution_tags"]:
            if not TAG.fullmatch(tag):
                errors.append("Invalid solution tag")
        model_path = resolve_input(base, model["path"])
        if model_path.suffix.lower() != ".mph" or not model_path.is_file():
            errors.append(f"Reviewed MPH is missing: {model_path}")
        for dependency in model["dependencies"]:
            if not resolve_input(base, dependency).is_file():
                errors.append(f"Missing model dependency: {dependency}")
        engineering = case["engineering"]
        if engineering["dimension"] not in [1, 2, 3]:
            errors.append("engineering.dimension must be 1, 2 or 3")
        for section in ("geometry", "mesh", "solver"):
            if engineering[section]["policy"] != "preserve-reviewed-mph" or not engineering[section]["description"]:
                errors.append(f"engineering.{section} needs preserve-reviewed-mph and an evidence description")
        for section in ("materials", "physics", "couplings", "boundary_conditions", "assumptions", "acceptance"):
            if not engineering[section]:
                errors.append(f"engineering.{section} is required")
        if engineering["unresolved"]:
            errors.append("Resolve engineering.unresolved before execution")
        for validation_name in ("mesh_independence", "time_step_independence", "conservation", "experimental_validation"):
            state = case["validation"][validation_name]
            if state not in {"not_run", "planned", "passed", "failed", "not_applicable"}:
                errors.append(f"Unknown validation state for {validation_name}")
            if state == "passed" and not case["validation"].get("evidence", {}).get(validation_name):
                errors.append(f"validation.{validation_name}=passed requires an evidence path")
        for name, evidence in case["validation"].get("evidence", {}).items():
            if not resolve_input(base, evidence).is_file():
                errors.append(f"Missing validation evidence: {name}")
        names, values = set(), {}
        for parameter in case["parameters"]:
            name = parameter["name"]
            if not TAG.fullmatch(name) or name in names:
                errors.append(f"Invalid or duplicate parameter: {name}")
            names.add(name)
            if not parameter["source"]:
                errors.append(f"{name}: missing source")
            if parameter.get("scope") != "physics_scalar":
                errors.append(f"{name}: overrides require scope=physics_scalar; rebuild geometry/mesh in a reviewed MPH first")
            try:
                values[name] = check_quantity(parameter["value"], parameter["unit"], parameter["quantity"])
                if "min" in parameter and parameter["value"] < parameter["min"]:
                    errors.append(f"{name}: below engineering minimum")
                if "max" in parameter and parameter["value"] > parameter["max"]:
                    errors.append(f"{name}: above engineering maximum")
            except (ValueError, SyntaxError) as exc:
                errors.append(f"{name}: {exc}")
        for constraint in case["constraints"]:
            if constraint["kind"] != "less_than":
                errors.append("Only explicit less_than parameter constraints are supported")
                continue
            left, right = values[constraint["left"]], values[constraint["right"]]
            if left[1] != right[1] or left[0] >= right[0]:
                errors.append(f"Constraint failed: {constraint['left']} < {constraint['right']}")
        execution = case["execution"]
        if type(execution["cores"]) is not int or not 1 <= execution["cores"] <= 256:
            errors.append("execution.cores must be an integer from 1 to 256")
        if type(execution["timeout_seconds"]) is not int or not 1 <= execution["timeout_seconds"] <= 604800:
            errors.append("execution.timeout_seconds must be an integer from 1 to 604800")
        interval = execution.get("recovery_interval_seconds")
        if interval is not None and (type(interval) is not int or not 1 <= interval <= 3600):
            errors.append("execution.recovery_interval_seconds must be an integer from 1 to 3600")
        exports = case["exports"]
        columns = set()
        if not exports:
            errors.append("At least one scalar global expression is required")
        for column in exports:
            if not TAG.fullmatch(column["name"]) or column["name"] in columns:
                errors.append("Export column names must be unique identifiers")
            columns.add(column["name"])
            if not column["expression"].strip() or any(c in column["expression"] for c in '\r\n\x00'):
                errors.append("Export expressions must be nonempty single-line COMSOL expressions")
            _, dimension = parse_unit(column["unit"])
            if dimension != QUANTITIES[column["quantity"]]:
                errors.append(f"Export {column['name']} has incompatible units")
            if column["unit"] == "degC" and column["quantity"] != "absolute_temperature":
                errors.append("Export temperature differences must use K")
        expected = case["results"]
        if expected["coordinate"] not in columns:
            errors.append("results.coordinate must be an exported column")
        if len(columns) < 2:
            errors.append("Export at least one physical metric besides the coordinate")
        coordinates = expected["expected_coordinates"]
        if not coordinates or any(type(x) not in (float, int) or not math.isfinite(x) for x in coordinates):
            errors.append("results.expected_coordinates needs finite numeric values")
        elif any(b <= a for a, b in zip(coordinates, coordinates[1:])):
            errors.append("Expected coordinates must be strictly increasing")
        if type(expected["coordinate_atol"]) not in (float, int) or expected["coordinate_atol"] < 0 or not math.isfinite(expected["coordinate_atol"]):
            errors.append("coordinate_atol must be finite and nonnegative")
        if expected.get("reference_csv") and not resolve_input(base, expected["reference_csv"]).is_file():
            errors.append("Reference CSV is missing")
        for key in ("atol", "rtol"):
            if type(expected[key]) not in (float, int) or expected[key] < 0 or not math.isfinite(expected[key]):
                errors.append(f"results.{key} must be finite and nonnegative")
        for name, bounds in expected.get("bounds", {}).items():
            if name not in columns or len(bounds) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) for x in bounds) or bounds[0] > bounds[1]:
                errors.append(f"Invalid output bounds: {name}")
        for kind, config in case.get("postprocess", {}).items():
            if kind not in {"field_plot", "table"}:
                errors.append(f"Unsupported postprocess kind: {kind}")
                continue
            filename = config["filename"]
            extension = ".png" if kind == "field_plot" else ".csv"
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*" + re.escape(extension), filename) or filename in {"metrics.csv"}:
                errors.append(f"Unsafe or reserved postprocess filename: {filename}")
            if kind == "field_plot" and not TAG.fullmatch(config["tag"]):
                errors.append("Field plot tag must be a valid identifier")
    except (KeyError, TypeError, ValueError, SyntaxError) as exc:
        errors.append(f"Malformed or incomplete case: {exc}")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def input_files(case, base):
    names = [case["model"]["path"], *case["model"].get("dependencies", [])]
    reference = case.get("results", {}).get("reference_csv")
    if reference:
        names.append(reference)
    names.extend(case.get("validation", {}).get("evidence", {}).values())
    result = []
    for name in names:
        path = resolve_input(base, name)
        result.append({"path": str(path), "sha256": sha256(path) if path.is_file() else None})
    return result
