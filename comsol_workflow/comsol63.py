"""COMSOL 6.3 adapters with separate read-only inspection and solve drivers."""
import json
from pathlib import Path


def jstr(value):
    return json.dumps(str(value), ensure_ascii=True)


def toolchain(root):
    root = Path(root).resolve()
    return {"root": str(root), "compiler": str(root / "bin/win64/comsolcompile.exe"),
            "batch": str(root / "bin/win64/comsolbatch.exe")}


def checks(case):
    m = case["model"]
    code = f'''
    String version = ModelUtil.getComsolVersion();
    if (!java.util.regex.Pattern.compile("(?:^|\\\\s)6\\\\.3(?:\\\\.|\\\\s|$)").matcher(version).find())
      throw new IllegalStateException("Expected COMSOL 6.3, got " + version);
    System.out.println("COMSOL_VERSION " + version);
    if (!Arrays.asList(model.study().tags()).contains({jstr(m['study_tag'])}))
      throw new IllegalArgumentException("Reviewed study tag is absent");
    if (!Arrays.asList(model.sol().tags()).contains({jstr(m['solver_tag'])}))
      throw new IllegalArgumentException("Reviewed solver sequence is absent");
    if (!{jstr(m['study_tag'])}.equals(model.sol({jstr(m['solver_tag'])}).study()))
      throw new IllegalArgumentException("Solver is not associated with reviewed study");
    if (!Arrays.asList(model.result().dataset().tags()).contains({jstr(m['dataset_tag'])}))
      throw new IllegalArgumentException("Reviewed dataset is absent");
    if (!"Solution".equals(model.result().dataset({jstr(m['dataset_tag'])}).getType()) ||
        !{jstr(m['solver_tag'])}.equals(model.result().dataset({jstr(m['dataset_tag'])}).getString("solution")))
      throw new IllegalArgumentException("Dataset must directly reference selected solution");
    if (!new TreeSet<String>(Arrays.asList(model.sol().tags())).equals(
        new TreeSet<String>(Arrays.asList(new String[]{{{', '.join(jstr(x) for x in m['clear_solution_tags'])}}}))))
      throw new IllegalArgumentException("Review all solution/store tags");
'''
    for physics in case["engineering"]["physics"]:
        if isinstance(physics, dict) and "component" in physics and "tag" in physics:
            component, tag = jstr(physics["component"]), jstr(physics["tag"])
            code += f'''
    if (!Arrays.asList(model.component().tags()).contains({component}) ||
        !Arrays.asList(model.component({component}).physics().tags()).contains({tag}))
      throw new IllegalArgumentException("Reviewed component/physics tag is absent");
'''
    for p in case["parameters"]:
        code += f'    if (!Arrays.asList(model.param().varnames()).contains({jstr(p["name"])})) throw new IllegalArgumentException("Override parameter is absent: {p["name"]}");\n'
    plot = case.get("postprocess", {}).get("field_plot")
    if plot:
        code += f'''
    if (!Arrays.asList(model.result().tags()).contains({jstr(plot['tag'])}))
      throw new IllegalArgumentException("Reviewed field plot is absent");
    if (!{jstr(m['dataset_tag'])}.equals(model.result({jstr(plot['tag'])}).getString("data")))
      throw new IllegalArgumentException("Field plot must use the reviewed dataset");
'''
    return code


IMPORTS = '''import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
'''


def generate_smoke(case, base, run_dir, token, recovery=None):
    from .scope import java_inventory_methods
    out = Path(run_dir).resolve() / "inspection"
    model_path = (Path(base) / case["model"]["path"]).resolve()
    loader = f'ModelUtil.loadRecovery("inspection", {jstr(recovery)})' if recovery else f'ModelUtil.loadCopy("inspection", {jstr(model_path)})'
    return IMPORTS + f'''
public class SmokeDriver {{
  public static Model run() {{
    try {{
      ModelUtil.showProgress({jstr(out/'progress.log')});
      Model model = {loader};
{checks(case)}
      String inventory = scopeInventory(model);
      System.out.println("WORKFLOW_DATA {token} inventory " + Base64.getEncoder().encodeToString(inventory.getBytes(StandardCharsets.UTF_8)));
      System.out.println("WORKFLOW_SMOKE_COMPLETED {token}");
      return model;
    }} catch (Exception e) {{ e.printStackTrace(System.out); throw new RuntimeException("WORKFLOW_SMOKE_FAILED", e); }}
  }}
  public static void main(String[] args) {{ run(); }}
{java_inventory_methods()}
}}
'''


def generate(case, base, run_dir, token, operation="solve", recovery=None):
    m = case["model"]
    out = Path(run_dir).resolve() / "results"
    if operation == "resume":
        if not recovery:
            raise ValueError("Resume requires a bound recovery snapshot")
        loader = f'ModelUtil.loadRecovery("workflow", {jstr(recovery)})'
        computation = f'''    System.out.println("WORKFLOW_RESUME_BEGIN {token}");
    model.sol({jstr(m['solver_tag'])}).continueRun();'''
    else:
        loader = f'ModelUtil.loadCopy("workflow", {jstr((Path(base)/m["path"]).resolve())})'
        statements=[]
        interval=case["execution"].get("recovery_interval_seconds")
        if interval is not None:
            statements.append(f'''    int recoveryConfigured=0;
    for(String feature:model.sol({jstr(m['solver_tag'])}).feature().tags())
      recoveryConfigured+=configureRecovery(model.sol({jstr(m['solver_tag'])}).feature(feature),{interval});
    if(recoveryConfigured==0) throw new IllegalStateException("No stationary/time solver supports the requested recovery interval");''')
        for p in case["parameters"]:
            expression=f"{p['value']}[{p['unit']}]" if p["unit"]!="1" else str(p["value"])
            statements.append(f"    model.param().set({jstr(p['name'])}, {jstr(expression)});")
        for tag in m["clear_solution_tags"]:
            statements.append(f"    model.sol({jstr(tag)}).clearSolutionData();")
        statements += [f'    System.out.println("WORKFLOW_SOLVE_BEGIN {token}");',f"    model.sol({jstr(m['solver_tag'])}).runAll();"]
        computation="\n".join(statements)
    columns=case["exports"]
    expressions=", ".join(jstr(c["expression"]) for c in columns)
    units=", ".join(jstr(c["unit"]) for c in columns)
    header=",".join(c["name"] for c in columns)
    postprocess=""
    table=case.get("postprocess",{}).get("table")
    if table:
        table_headers=", ".join(jstr(f"{c['name']} [{c['unit']}]") for c in columns)
        postprocess+=f'''
    String tableTag="wfTable";
    while(Arrays.asList(model.result().table().tags()).contains(tableTag)) tableTag+="x";
    model.result().table().create(tableTag,"Table");
    double[][] tableData=new double[data[0].length][data.length];
    for(int row=0;row<tableData.length;row++) for(int col=0;col<data.length;col++) tableData[row][col]=data[col][row];
    model.result().table(tableTag).setTableData(tableData);
    model.result().table(tableTag).setColumnHeaders(new String[]{{{table_headers}}});
    double[][] tableReadback=model.result().table(tableTag).getReal();
    String[] tableHeaders=model.result().table(tableTag).getColumnHeaders();
    StringWriter tableBuffer=new StringWriter();
    try(PrintWriter csv=new PrintWriter(tableBuffer)) {{
      for(int c=0;c<tableHeaders.length;c++) {{if(c>0)csv.print(',');csv.print(csvQuote(tableHeaders[c]));}} csv.println();
      for(double[] row:tableReadback) {{for(int c=0;c<row.length;c++) {{if(c>0)csv.print(',');csv.print(row[c]);}}csv.println();}}
      if(csv.checkError()) throw new IOException("Table CSV write failed");
    }}
    emit("table",tableBuffer.toString());
'''
    plot=case.get("postprocess",{}).get("field_plot")
    if plot:
        postprocess+=f'''
    model.result({jstr(plot['tag'])}).run();
    String imageTag="wfImage";
    while(Arrays.asList(model.result().export().tags()).contains(imageTag)) imageTag+="x";
    model.result().export().create(imageTag,{jstr(plot['tag'])},"Image");
    model.result().export(imageTag).set("imagetype","png");
    model.result().export(imageTag).set("pngfilename",{jstr(out/plot['filename'])});
    model.result().export(imageTag).set("unit","px");
    model.result().export(imageTag).set("width",1000);
    model.result().export(imageTag).set("height",700);
    model.result().export(imageTag).set("size","manualweb");
    model.result().export(imageTag).set("target","file");
    model.result().export(imageTag).run();
'''
    return IMPORTS + f'''
public class WorkflowDriver {{
  private static Model currentModel;
  private static int configureRecovery(SolverFeature feature,int seconds) {{
    int count=0;
    if("Stationary".equals(feature.getType()) || "Time".equals(feature.getType())) {{
      String advanced=null;
      for(String child:feature.feature().tags())
        if("Advanced".equals(feature.feature(child).getType())) {{advanced=child;break;}}
      if(advanced==null) {{
        advanced="wfRecovery";
        while(Arrays.asList(feature.feature().tags()).contains(advanced)) advanced+="x";
        feature.create(advanced,"Advanced");
      }}
      feature.feature(advanced).set("recoverysaveforce","manual");
      feature.feature(advanced).set("recoverysaveevery",seconds);
      feature.feature(advanced).set("recoverysavinginfo","oneveryiteration");
      count++;
    }}
    for(String child:feature.feature().tags()) count+=configureRecovery(feature.feature(child),seconds);
    return count;
  }}
  public static Model run() {{
    try {{ return execute(); }}
    catch(Exception e) {{e.printStackTrace(System.out);throw new RuntimeException("WORKFLOW_FAILED",e);}}
    finally {{ recordRecovery(); }}
  }}
  private static void recordRecovery() {{
    if(currentModel==null) return;
    try {{
      String directory=ModelUtil.getRecoveryDir(currentModel.tag());
      if(directory!=null && !directory.isEmpty()) {{
        emit("recovery",directory);
      }}
    }} catch(Exception e) {{System.out.println("WORKFLOW_RECOVERY_PATH_UNAVAILABLE "+e.getClass().getSimpleName());}}
  }}
  private static void emit(String kind,String value) {{
    System.out.println("WORKFLOW_DATA {token} "+kind+" "+Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8)));
  }}
  private static String csvQuote(String s) {{return "\\\""+s.replace("\\\"","\\\"\\\"")+"\\\"";}}
  private static Model execute() throws Exception {{
    ModelUtil.showProgress({jstr(out/'progress.log')});
    Model model={loader}; currentModel=model;
{checks(case)}
    recordRecovery();
{computation}
    if(model.sol({jstr(m['solver_tag'])}).isEmpty()) throw new IllegalStateException("Empty solution");
    String tag="wfEval";
    while(Arrays.asList(model.result().numerical().tags()).contains(tag)) tag+="x";
    model.result().numerical().create(tag,"EvalGlobal");
    model.result().numerical(tag).set("data",{jstr(m['dataset_tag'])});
    model.result().numerical(tag).set("expr",new String[]{{{expressions}}});
    model.result().numerical(tag).set("unit",new String[]{{{units}}});
    if(model.result().numerical(tag).isComplex()) throw new IllegalStateException("Real results required");
    double[][] data=model.result().numerical(tag).getReal();
    if(data.length!={len(columns)} || data[0].length==0) throw new IllegalStateException("Unexpected evaluation shape");
    for(double[] column:data) {{if(column.length!=data[0].length)throw new IllegalStateException("Ragged evaluation");
      for(double value:column)if(!Double.isFinite(value))throw new IllegalStateException("Non-finite result");}}
    StringWriter metricBuffer=new StringWriter();
    try(PrintWriter csv=new PrintWriter(metricBuffer)) {{
      csv.println({jstr(header)});
      for(int row=0;row<data[0].length;row++) {{
        for(int col=0;col<data.length;col++) {{if(col>0)csv.print(',');csv.print(data[col][row]);}}csv.println();
      }}
      if(csv.checkError())throw new IOException("Metric CSV write failed");
    }}
    emit("metrics",metricBuffer.toString());
{postprocess}
    model.save({jstr(out/'solved.mph')});
    System.out.println("WORKFLOW_COMPLETED {token} rows="+data[0].length);
    return model;
  }}
  public static void main(String[] args) {{run();}}
}}
'''


def commands(plan, run_dir, mode="solve"):
    run_dir=Path(run_dir).resolve(); chain=plan["toolchain"]
    name="SmokeDriver" if mode=="smoke" else "WorkflowDriver"
    out=run_dir/("inspection" if mode=="smoke" else "results")
    compile_cmd=[chain["compiler"],"-classpathadd",str(Path(chain["root"])/"plugins/*"),str(run_dir/f"{name}.java")]
    batch=[chain["batch"],"-inputfile",str(run_dir/f"{name}.class"),"-batchlog",str(out/"batch.log"),"-np",str(plan["cores"]),"-3drend","sw"]
    if mode=="smoke":
        batch += ["-nosave","-autosave","off"]
    else:
        batch += ["-outputfile",str(out/"solved.mph"),"-autosave","on","-recoverydir",str(run_dir/"recovery")]
    return [compile_cmd,batch]
