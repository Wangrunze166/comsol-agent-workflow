"""COMSOL 6.3 Windows adapter. Source generation is inert; execution is gated elsewhere."""
import json
from pathlib import Path


def jstr(value):
    return json.dumps(str(value), ensure_ascii=True)


def toolchain(root):
    root = Path(root).resolve()
    return {"root": str(root), "compiler": str(root / "bin/win64/comsolcompile.exe"),
            "batch": str(root / "bin/win64/comsolbatch.exe")}


def generate(case, base, run_dir, token):
    """Keep geometry, materials, physics, mesh and sequence inside the reviewed MPH."""
    model = case["model"]
    out = Path(run_dir).resolve() / "results"
    statements = []
    for p in case["parameters"]:
        # Offsets: emit degC literally; COMSOL evaluates this as absolute temperature.
        expression = f"{p['value']}[{p['unit']}]" if p["unit"] != "1" else str(p["value"])
        statements.append(f"    if (!Arrays.asList(model.param().varnames()).contains({jstr(p['name'])})) throw new IllegalArgumentException(\"Override parameter is absent\");")
        statements.append(f"    model.param().set({jstr(p['name'])}, {jstr(expression)});")
    for tag in model["clear_solution_tags"]:
        statements.append(f"    model.sol({jstr(tag)}).clearSolutionData();")
    columns = case["exports"]
    expressions = ", ".join(jstr(c["expression"]) for c in columns)
    units = ", ".join(jstr(c["unit"]) for c in columns)
    header = ",".join(c["name"] for c in columns)
    # No shell interpolation, arbitrary Java snippets or model method execution.
    return f'''import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.TreeSet;

public class WorkflowDriver {{
  public static Model run() {{
    try {{ return execute(); }}
    catch (Exception e) {{ throw new RuntimeException("WORKFLOW_FAILED", e); }}
  }}
  private static Model execute() throws Exception {{
    String version = ModelUtil.getComsolVersion();
    if (!(version.equals("6.3") || version.startsWith("6.3.")))
      throw new IllegalStateException("Expected COMSOL 6.3, got " + version);
    System.out.println("COMSOL_VERSION " + version);
    ModelUtil.showProgress({jstr(out / 'progress.log')});
    Model model = ModelUtil.loadCopy("workflow", {jstr((Path(base) / model['path']).resolve())});
    if (!Arrays.asList(model.study().tags()).contains({jstr(model['study_tag'])}))
      throw new IllegalArgumentException("Reviewed study tag is absent");
    if (!Arrays.asList(model.sol().tags()).contains({jstr(model['solver_tag'])}))
      throw new IllegalArgumentException("Reviewed solver sequence is absent");
    if (!{jstr(model['study_tag'])}.equals(model.sol({jstr(model['solver_tag'])}).study()))
      throw new IllegalArgumentException("Solver sequence is not associated with the reviewed study");
    if (!Arrays.asList(model.result().dataset().tags()).contains({jstr(model['dataset_tag'])}))
      throw new IllegalArgumentException("Reviewed dataset is absent");
    if (!"Solution".equals(model.result().dataset({jstr(model['dataset_tag'])}).getType()) ||
        !{jstr(model['solver_tag'])}.equals(model.result().dataset({jstr(model['dataset_tag'])}).getString("solution")))
      throw new IllegalArgumentException("Dataset must directly reference the selected solution");
    if (!new TreeSet<String>(Arrays.asList(model.sol().tags())).equals(
        new TreeSet<String>(Arrays.asList(new String[]{{{', '.join(jstr(x) for x in model['clear_solution_tags'])}}}))))
      throw new IllegalArgumentException("Review all solution/store tags before clearing saved solutions");
{chr(10).join(statements)}
    // Preserve the complete reviewed staged sequence, including upstream flow.
    System.out.println("WORKFLOW_SOLVE_BEGIN {token}");
    model.sol({jstr(model['solver_tag'])}).runAll();
    if (model.sol({jstr(model['solver_tag'])}).isEmpty())
      throw new IllegalStateException("Solver returned an empty solution");
    String tag = "wfEval";
    while (Arrays.asList(model.result().numerical().tags()).contains(tag)) tag += "x";
    model.result().numerical().create(tag, "EvalGlobal");
    model.result().numerical(tag).set("data", {jstr(model['dataset_tag'])});
    model.result().numerical(tag).set("expr", new String[]{{{expressions}}});
    model.result().numerical(tag).set("unit", new String[]{{{units}}});
    if (model.result().numerical(tag).isComplex())
      throw new IllegalStateException("MVP supports real scalar results only; review complex-valued exports separately");
    double[][] data = model.result().numerical(tag).getReal();
    if (data.length != {len(columns)} || data[0].length == 0)
      throw new IllegalStateException("Unexpected global evaluation shape");
    for (double[] column : data) {{
      if (column.length != data[0].length) throw new IllegalStateException("Ragged evaluation");
      for (double value : column) if (!Double.isFinite(value))
        throw new IllegalStateException("Non-finite evaluation result");
    }}
    try (PrintWriter csv = new PrintWriter(new OutputStreamWriter(
        new FileOutputStream({jstr(out / 'metrics.csv')}), StandardCharsets.UTF_8))) {{
      csv.println({jstr(header)});
      for (int row = 0; row < data[0].length; row++) {{
        for (int col = 0; col < data.length; col++) {{
          if (col > 0) csv.print(',');
          csv.print(data[col][row]);
        }}
        csv.println();
      }}
      if (csv.checkError()) throw new IOException("CSV write failed");
    }}
    model.save({jstr(out / 'solved.mph')});
    try (PrintWriter marker = new PrintWriter({jstr(out / 'completed.ok')}, "UTF-8")) {{
      marker.println({jstr(token)});
      if (marker.checkError()) throw new IOException("Completion write failed");
    }}
    System.out.println("WORKFLOW_COMPLETED rows=" + data[0].length);
    return model;
  }}
  public static void main(String[] args) {{ run(); }}
}}
'''


def commands(plan, run_dir):
    run_dir = Path(run_dir).resolve()
    chain = plan["toolchain"]
    return [
        [chain["compiler"], "-classpathadd", str(Path(chain["root"]) / "plugins/*"), str(run_dir / "WorkflowDriver.java")],
        [chain["batch"], "-inputfile", str(run_dir / "WorkflowDriver.class"),
         "-outputfile", str(run_dir / "results/solved.mph"),
         "-batchlog", str(run_dir / "results/batch.log"), "-np", str(plan["cores"])],
    ]
