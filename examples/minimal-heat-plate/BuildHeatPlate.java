import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.Arrays;

/** Build and save an UNSOLVED COMSOL 6.3 verification model. */
public class BuildHeatPlate {
  public static Model run() {
    try {
      return build();
    } catch (Exception error) {
      error.printStackTrace(System.err);
      throw new RuntimeException("HEAT_PLATE_BUILD_FAILED: " + error.getClass().getName()
          + ": " + error.getMessage(), error);
    }
  }

  private static Model build() throws Exception {
    String version = ModelUtil.getComsolVersion();
    if (!java.util.regex.Pattern.compile("(?:^|\\s)6\\.3(?:\\.|\\s|$)").matcher(version).find()) {
      throw new IllegalStateException("COMSOL 6.3 required, found " + version);
    }
    audit("BUILD_ONLY_COMSOL_VERSION " + version);
    Model model = ModelUtil.create("heatplate");
    model.label("Minimal heat plate - UNSOLVED verification example");
    model.comments("New verification example, not the user's original research model. "
        + "Build only: no study or solver execution. Approval is required before solving.");
    model.param().set("L", "0.01[m]", "Plate length; geometry and mesh dependent");
    model.param().set("L_geom", "L", "Indirect geometry dependency for scope checks");
    model.param().set("H", "0.005[m]", "Plate height");
    model.param().set("T_cold", "293.15[K]", "Left temperature");
    model.param().set("T_hot", "303.15[K]", "Right temperature; physics scalar");
    model.param().set("k_plate", "1[W/(m*K)]", "Isotropic conductivity");
    model.param().set("rho_plate", "1000[kg/m^3]", "Density");
    model.param().set("Cp_plate", "1000[J/(kg*K)]", "Specific heat capacity");

    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 2);
    model.component("comp1").geom("geom1").lengthUnit("m");
    model.component("comp1").geom("geom1").create("r1", "Rectangle");
    model.component("comp1").geom("geom1").feature("r1")
        .set("size", new String[]{"L_geom", "H"});
    model.component("comp1").geom("geom1").run();
    audit("BUILD_ONLY_GEOMETRY_READY");

    double length = model.param().evaluate("L_geom");
    double height = model.param().evaluate("H");
    double eps = 1e-9;
    box(model, "left", -eps, eps, -eps, height + eps);
    box(model, "right", length - eps, length + eps, -eps, height + eps);
    int[] left = model.component("comp1").selection("left").entities(1);
    int[] right = model.component("comp1").selection("right").entities(1);
    audit("BOUNDARY_SELECTION left=" + Arrays.toString(left)
        + " right=" + Arrays.toString(right));
    if (left.length != 1 || right.length != 1 || left[0] == right[0]) {
      throw new IllegalStateException("Coordinate selections must select distinct single boundaries");
    }
    model.component("comp1").selection().create("plate", "Explicit");
    model.component("comp1").selection("plate").geom("geom1", 2);
    model.component("comp1").selection("plate").all();
    int domains = model.component("comp1").selection("plate").entities(2).length;
    if (domains != 1) throw new IllegalStateException("Expected one rectangular domain");
    audit("DOMAIN_SELECTION count=" + domains);

    model.component("comp1").material().create("mat1", "Common");
    model.component("comp1").material("mat1").label("Homogeneous verification material");
    model.component("comp1").material("mat1").selection().named("plate");
    model.component("comp1").material("mat1").propertyGroup("def")
        .set("thermalconductivity", new String[]{"k_plate", "0", "0", "0", "k_plate", "0", "0", "0", "k_plate"});
    model.component("comp1").material("mat1").propertyGroup("def").set("density", "rho_plate");
    model.component("comp1").material("mat1").propertyGroup("def").set("heatcapacity", "Cp_plate");

    model.component("comp1").physics().create("ht", "HeatTransfer", "geom1");
    model.component("comp1").physics("ht").selection().named("plate");
    model.component("comp1").physics("ht").feature("init1").set("Tinit", "T_cold");
    model.component("comp1").physics("ht").create("cold", "TemperatureBoundary", 1);
    model.component("comp1").physics("ht").feature("cold").selection().named("left");
    model.component("comp1").physics("ht").feature("cold").set("T0", "T_cold");
    model.component("comp1").physics("ht").create("hot", "TemperatureBoundary", 1);
    model.component("comp1").physics("ht").feature("hot").selection().named("right");
    model.component("comp1").physics("ht").feature("hot").set("T0", "T_hot");
    audit("BUILD_ONLY_PHYSICS_READY");
    // The default Heat Transfer thermal insulation remains on the other boundaries.

    model.component("comp1").mesh().create("mesh1");
    model.component("comp1").mesh("mesh1").feature("size").set("custom", "on");
    model.component("comp1").mesh("mesh1").feature("size").set("hmax", "L/12");
    model.component("comp1").mesh("mesh1").feature("size").set("hmin", "L/120");
    model.component("comp1").mesh("mesh1").create("ftri1", "FreeTri");
    model.component("comp1").mesh("mesh1").run();
    audit("BUILD_ONLY_MESH_READY");

    model.component("comp1").cpl().create("aveop1", "Average", "geom1");
    model.component("comp1").cpl("aveop1").selection().named("plate");
    model.study().create("std1");
    model.study("std1").create("stat", "Stationary");
    model.study("std1").setGenPlots(false);
    // Generates solver settings only; this does not run the solver.
    model.study("std1").showAutoSequences("sol");
    audit("BUILD_ONLY_SOLVER_CONFIGURED");
    if (!Arrays.asList(model.sol().tags()).contains("sol1") || !model.sol("sol1").isEmpty()) {
      throw new IllegalStateException("Expected an empty, configured sol1");
    }
    if (!Arrays.asList(model.result().dataset().tags()).contains("dset1")) {
      model.result().dataset().create("dset1", "Solution");
    }
    model.result().dataset("dset1").set("solution", "sol1");
    model.result().create("pgT", "PlotGroup2D");
    model.result("pgT").label("Temperature [K] - populate only after approved solve");
    model.result("pgT").set("data", "dset1");
    model.result("pgT").create("surf1", "Surface");
    model.result("pgT").feature("surf1").set("expr", "T");
    model.result("pgT").feature("surf1").set("unit", "K");
    model.result().table().create("tblMetrics", "Table");
    model.result().table("tblMetrics").label("Case and mean temperature - not yet evaluated");
    model.result().numerical().create("evalMetrics", "EvalGlobal");
    model.result().numerical("evalMetrics").set("data", "dset1");
    model.result().numerical("evalMetrics").set("expr", new String[]{"1", "comp1.aveop1(comp1.T)"});
    model.result().numerical("evalMetrics").set("unit", new String[]{"1", "K"});
    model.result().numerical("evalMetrics").set("descr", new String[]{"case_no", "Tmean_K"});
    model.result().numerical("evalMetrics").set("table", "tblMetrics");

    // COMSOL's save API works with its standard security policy. The caller must
    // choose an empty private working directory and reject an existing target.
    String output = "heat-plate.mph";
    model.save(output);
    audit("BUILD_ONLY_SAVED " + output);
    audit("BUILD_ONLY_UNSOLVED sol1.isEmpty=" + model.sol("sol1").isEmpty());
    return model;
  }

  private static void audit(String message) {
    System.out.println(message);
  }

  private static void box(Model model, String tag, double xmin, double xmax, double ymin, double ymax) {
    model.component("comp1").selection().create(tag, "Box");
    model.component("comp1").selection(tag).set("entitydim", 1);
    model.component("comp1").selection(tag).set("condition", "inside");
    model.component("comp1").selection(tag).set("xmin", xmin);
    model.component("comp1").selection(tag).set("xmax", xmax);
    model.component("comp1").selection(tag).set("ymin", ymin);
    model.component("comp1").selection(tag).set("ymax", ymax);
  }

  public static void main(String[] args) { run(); }
}
