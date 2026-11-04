"""Conservative parameter override audit; no COMSOL process is launched here.

The inventory describes stored Java API expressions, not a symbolic proof for
arbitrary COMSOL models. Unsupported indirection or unreadable properties block
all overrides. A reviewed model with no overrides may still be reused.
"""
import re


_IDENTIFIER = re.compile(r"(?<![\w])([A-Za-z_]\w*)", re.UNICODE)
_CALL = re.compile(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(")
_QUALIFIED = re.compile(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\b")
_LOCAL_MATH = frozenset("abs acos acosh asin asinh atan atan2 atanh ceil cos cosh exp floor if imag log log10 max min mod real round sign sin sinh sqrt tan tanh conj".split())


def _unsupported_expression(expression, path, definitions, declared_functions):
    """Reject solution lookups, custom operators and unresolved scoped values.

    Bare property values can be entity tags or enumerations, so they cannot be
    treated as unknown variable names. Global/component variable nodes are
    excluded by the inventory; model functions are rejected when referenced.
    """
    reasons = []
    called = set(_CALL.findall(expression))
    calls = (called - _LOCAL_MATH) | (called & declared_functions)
    if calls:
        reasons.append({"path": path, "reason": "Unsupported expression function/operator: " + ", ".join(sorted(calls))})
    qualified = {name for name in _QUALIFIED.findall(expression)
                 if not (name.startswith("root.") and name[5:] in definitions)}
    if qualified:
        reasons.append({"path": path, "reason": "Unresolved scoped expression: " + ", ".join(sorted(qualified))})
    # A function can also be chosen by a reference property rather than called
    # in a textual expression. Reject those references conservatively as well.
    references = (_names(expression) & declared_functions) - called
    if references:
        reasons.append({"path": path, "reason": "Referenced model function requires a dependency adapter: " + ", ".join(sorted(references))})
    return reasons


def _names(expression):
    return set(_IDENTIFIER.findall(expression))


def evaluate_scope(inventory, parameters):
    """Reject direct/transitive geometry, mesh or selection parameter changes.

    ``parameters`` is the case's override list. Its ``scope`` annotation is not
    evidence and has no influence on this decision. The caller must bind the
    inventory to the exact input model and loaded-file hash before using it.
    """
    issues, unsupported, hits = [], [], []
    overrides = []
    if not isinstance(parameters, list):
        parameters = []
        issues.append({"path": "parameters", "reason": "override list is invalid"})
        malformed_overrides = True
    else:
        malformed_overrides = False
    for parameter in parameters:
        if not isinstance(parameter, dict) or not isinstance(parameter.get("name"), str):
            issues.append({"path": "parameters", "reason": "override name is invalid"})
            malformed_overrides = True
        else:
            overrides.append(parameter["name"])
    if len(overrides) != len(set(overrides)):
        issues.append({"path": "parameters", "reason": "duplicate override name"})
    if not isinstance(inventory, dict) or inventory.get("schema_version") != 1:
        issues.append({"path": "inventory", "reason": "missing or unsupported inventory schema"})
        inventory = {}
    for field, destination in (("incomplete", issues), ("unsupported", unsupported)):
        value = inventory.get(field)
        if not isinstance(value, list) or any(not isinstance(x, dict) for x in value):
            issues.append({"path": field, "reason": "missing or invalid inventory field"})
        else:
            destination.extend(value)
    definitions = {}
    definitions_list = inventory.get("parameters")
    if not isinstance(definitions_list, list):
        issues.append({"path": "parameters", "reason": "parameter inventory is missing"})
        definitions_list = []
    for item in definitions_list:
        if (not isinstance(item, dict) or not isinstance(item.get("name"), str)
                or not isinstance(item.get("expression"), str)):
            issues.append({"path": "parameters", "reason": "invalid parameter definition"})
            continue
        name, expression = item["name"], item["expression"]
        if name in definitions and definitions[name] != expression:
            issues.append({"path": f"parameters/{name}", "reason": "conflicting parameter definitions"})
        definitions[name] = expression
    for name in overrides:
        if name not in definitions:
            issues.append({"path": f"parameters/{name}", "reason": "override is absent from loaded model"})
    functions, declared_functions = inventory.get("functions"), set()
    if not isinstance(functions, list):
        issues.append({"path": "functions", "reason": "function inventory is missing"})
        functions = []
    for function in functions:
        if (not isinstance(function, dict) or function.get("type") != "Analytic"
                or not isinstance(function.get("name"), str) or not function["name"]
                or not isinstance(function.get("expression"), str)
                or not isinstance(function.get("arguments"), list)
                or any(not isinstance(arg, str) for arg in function["arguments"])):
            issues.append({"path": "functions", "reason": "unreadable or unsupported function definition"})
            continue
        declared_functions.add(function["name"])
    scanned = inventory.get("scanned")
    if (not isinstance(scanned, dict) or any(type(scanned.get(name)) is not int or scanned[name] < 0
                                            for name in ("components", "geometries", "meshes", "features"))):
        issues.append({"path": "scanned", "reason": "missing or invalid enumeration coverage"})

    # Reverse edges: if B = 2*A then changing A also changes B. Keep a concrete
    # path so a rejection can explain which derived expression reaches a feature.
    dependents = {name: set() for name in definitions}
    for derived, expression in definitions.items():
        unsupported.extend(_unsupported_expression(expression, f"parameters/{derived}", definitions, declared_functions))
        for dependency in _names(expression) & definitions.keys():
            dependents[dependency].add(derived)
    affected = {}
    for name in sorted(set(overrides)):
        affected[name] = [name]
    pending = list(affected)
    for name in pending:
        for derived in sorted(dependents.get(name, ())):
            if derived not in affected:
                affected[derived] = affected[name] + [derived]
                pending.append(derived)

    properties = inventory.get("properties")
    if not isinstance(properties, list):
        issues.append({"path": "properties", "reason": "feature inventory is missing"})
        properties = []
    for prop in properties:
        if (not isinstance(prop, dict) or not isinstance(prop.get("path"), str)
                or prop.get("scope") not in {"geometry", "mesh", "selection"}
                or not isinstance(prop.get("expressions"), list)
                or any(not isinstance(value, str) for value in prop["expressions"])):
            issues.append({"path": "properties", "reason": "invalid feature property record"})
            continue
        for expression in prop["expressions"]:
            unsupported.extend(_unsupported_expression(expression, prop["path"], definitions, declared_functions))
            for name in sorted(_names(expression) & affected.keys()):
                hits.append({"path": prop["path"], "scope": prop["scope"],
                             "expression": expression, "parameter": name,
                             "dependency_path": affected[name]})

    has_overrides = bool(parameters) or malformed_overrides
    return {"passed": not malformed_overrides and (not has_overrides or not (hits or issues or unsupported)),
            "checked": has_overrides, "overrides": sorted(set(overrides)),
            "affected_parameters": sorted(affected), "hits": hits,
            "incomplete": issues, "unsupported": unsupported,
            "proof_scope": ("Stored geometry, mesh and named-selection expressions with global parameter dependencies; "
                            "not a proof of whole-model physics or arbitrary COMSOL expressions.")
                           if has_overrides else
                           "No parameter overrides: reviewed model reused; whole-model dependency safety is not proved."}


def java_inventory_methods():
    """Return inert COMSOL 6.3 methods for embedding in a load-only driver.

    Requires ``import com.comsol.model.*``. Entry point: scopeInventory(Model).
    The method never modifies a feature, builds a mesh, runs a study or saves.
    """
    return r'''
  @SuppressWarnings("unchecked")
  private static java.util.List<Object> scopeList(java.util.Map<String,Object> data, String key) {
    return (java.util.List<Object>)data.get(key);
  }
  @SuppressWarnings("unchecked")
  private static void scopeIncrement(java.util.Map<String,Object> data, String key) {
    java.util.Map<String,Object> counts = (java.util.Map<String,Object>)data.get("scanned");
    counts.put(key, ((Number)counts.get(key)).intValue() + 1);
  }
  private static java.util.Map<String,Object> scopeRecord(Object... fields) {
    java.util.Map<String,Object> result = new java.util.LinkedHashMap<String,Object>();
    for (int i=0; i<fields.length; i+=2) result.put((String)fields[i], fields[i+1]);
    return result;
  }
  private static void scopeIssue(java.util.List<Object> target, String path, String reason) {
    target.add(scopeRecord("path", path, "reason", reason));
  }
  private static String scopeError(Exception error) {
    return error.getClass().getSimpleName() + ": " + String.valueOf(error.getMessage());
  }
  private static String scopeJson(Object value) {
    if (value == null) return "null";
    if (value instanceof Number || value instanceof Boolean) return value.toString();
    if (value instanceof java.util.Map) {
      StringBuilder b = new StringBuilder("{"); boolean comma = false;
      for (Object entry : ((java.util.Map<?,?>)value).entrySet()) {
        java.util.Map.Entry<?,?> e = (java.util.Map.Entry<?,?>)entry;
        if (comma) b.append(','); comma = true;
        b.append(scopeJson(e.getKey().toString())).append(':').append(scopeJson(e.getValue()));
      }
      return b.append('}').toString();
    }
    if (value instanceof Iterable) {
      StringBuilder b = new StringBuilder("["); boolean comma = false;
      for (Object item : (Iterable<?>)value) {
        if (comma) b.append(','); comma = true; b.append(scopeJson(item));
      }
      return b.append(']').toString();
    }
    String s = value.toString(); StringBuilder b = new StringBuilder("\"");
    for (int i=0; i<s.length(); i++) {
      char c = s.charAt(i);
      if (c == '"' || c == '\\') b.append('\\').append(c);
      else if (c < 32 || c >= 127) b.append(String.format("\\u%04x", (int)c));
      else b.append(c);
    }
    return b.append('"').toString();
  }
  private static java.util.List<String> scopeStrings(PropFeature feature, String property, String type) throws Exception {
    // Numeric API types may still expose their stored expressions through the
    // string getters. Never fall back to evaluated getDouble()/getInt() values.
    int[] attempts = (type.contains("Matrix") ? new int[]{2,1,0} :
                      type.contains("Array") ? new int[]{1,2,0} : new int[]{0,1,2});
    for (int attempt : attempts) {
      try {
        java.util.List<String> values = new java.util.ArrayList<String>();
        if (attempt == 0) values.add(feature.getString(property));
        if (attempt == 1) {
          String[] a = feature.getStringArray(property);
          if (a == null) throw new IllegalStateException("null array");
          for (String v : a) values.add(v);
        }
        if (attempt == 2) {
          String[][] a = feature.getStringMatrix(property);
          if (a == null) throw new IllegalStateException("null matrix");
          for (String[] row : a) {
            if (row == null) throw new IllegalStateException("null row");
            for (String v : row) values.add(v);
          }
        }
        if (values.contains(null)) throw new IllegalStateException("null expression");
        return values;
      } catch (RuntimeException ex) { /* Try another documented string shape. */ }
    }
    throw new IllegalStateException("No readable stored string representation for " + type);
  }
  private static void scopeProperties(java.util.Map<String,Object> data, PropFeature feature, String path, String scope) {
    scopeIncrement(data, "features");
    try {
      for (String property : feature.properties()) {
        String p = path + "/" + property;
        try {
          String type = feature.getValueType(property);
          if (type == null || !java.util.Arrays.asList("Boolean", "String", "StringArray", "StringMatrix",
              "Int", "IntArray", "Double", "DoubleArray", "DoubleMatrix", "DoubleRowMatrix").contains(type))
            throw new IllegalStateException("unknown property type");
          scopeList(data, "properties").add(scopeRecord("path", p, "scope", scope, "value_type", type,
                                     "expressions", scopeStrings(feature, property, type)));
        } catch (Exception ex) {
          scopeIssue(scopeList(data, "incomplete"), p, "Cannot read stored property expression: " + scopeError(ex));
        }
      }
    } catch (Exception ex) {
      scopeIssue(scopeList(data, "incomplete"), path, "Cannot enumerate properties: " + scopeError(ex));
    }
  }
  private static void scopeFunction(java.util.Map<String,Object> data, FunctionFeature feature, String path) {
    try {
      String type = feature.getType();
      if (!"Analytic".equals(type)) {
        scopeIssue(scopeList(data, "unsupported"), path, "Function type requires a separate definition adapter: " + type);
        return;
      }
      String name = feature.getString("funcname");
      String expression = feature.getString("expr");
      String[] arguments = feature.getStringArray("args");
      if (name == null || name.isEmpty() || expression == null || arguments == null)
        throw new IllegalStateException("Incomplete analytic function definition");
      for (String argument : arguments) if (argument == null)
        throw new IllegalStateException("Null analytic argument");
      scopeList(data, "functions").add(scopeRecord("path", path, "tag", feature.tag(), "type", type,
          "name", name, "expression", expression, "arguments", java.util.Arrays.asList(arguments)));
    } catch (Exception ex) { scopeIssue(scopeList(data, "incomplete"), path, "Cannot read function definition: " + scopeError(ex)); }
  }
  private static void scopeGeometry(java.util.Map<String,Object> data, GeomSequence geom, String path, int depth) {
    if (depth > 128) { scopeIssue(scopeList(data, "incomplete"), path, "Geometry recursion limit"); return; }
    scopeIncrement(data, "geometries");
    try {
      // GeomSequence.func() is documented for parts only and throws on an
      // ordinary component geometry. Parts are already excluded separately.
      for (String tag : geom.feature().tags()) scopeGeomFeature(data, geom.feature(tag), path + "/" + tag, depth+1);
    } catch (Exception ex) { scopeIssue(scopeList(data, "incomplete"), path, "Cannot enumerate geometry: " + scopeError(ex)); }
  }
  private static void scopeGeomFeature(java.util.Map<String,Object> data, GeomFeature feature, String path, int depth) {
    if (depth > 128) { scopeIssue(scopeList(data, "incomplete"), path, "Geometry recursion limit"); return; }
    scopeProperties(data, feature, path, "geometry");
    try {
      String type = feature.getType();
      String lower = type.toLowerCase(java.util.Locale.ROOT);
      if (lower.contains("import") || lower.contains("livelink") || lower.contains("partinstance"))
        scopeIssue(scopeList(data, "unsupported"), path, "External/imported/part geometry requires a separate dependency adapter: " + type);
      for (String tag : feature.feature().tags()) scopeGeomFeature(data, feature.feature(tag), path + "/" + tag, depth+1);
      if ("WorkPlane".equals(type) || "PartInstance".equals(type))
        scopeGeometry(data, feature.geom(), path + "/geom", depth+1);
    } catch (Exception ex) { scopeIssue(scopeList(data, "incomplete"), path, "Cannot enumerate nested geometry: " + scopeError(ex)); }
  }
  private static void scopeMeshFeature(java.util.Map<String,Object> data, MeshFeature feature, String path, int depth) {
    if (depth > 128) { scopeIssue(scopeList(data, "incomplete"), path, "Mesh recursion limit"); return; }
    scopeProperties(data, feature, path, "mesh");
    try {
      String type = feature.getType();
      if (type.toLowerCase(java.util.Locale.ROOT).contains("import"))
        scopeIssue(scopeList(data, "unsupported"), path, "Imported mesh requires a separate dependency adapter");
      for (String tag : feature.feature().tags()) scopeMeshFeature(data, feature.feature(tag), path + "/" + tag, depth+1);
    } catch (Exception ex) { scopeIssue(scopeList(data, "incomplete"), path, "Cannot enumerate nested mesh: " + scopeError(ex)); }
  }
  static String scopeInventory(Model model) {
    java.util.Map<String,Object> data = scopeRecord("schema_version", 1,
        "parameters", new java.util.ArrayList<Object>(), "properties", new java.util.ArrayList<Object>(),
        "functions", new java.util.ArrayList<Object>(),
        "incomplete", new java.util.ArrayList<Object>(), "unsupported", new java.util.ArrayList<Object>(),
        "scanned", scopeRecord("components", 0, "geometries", 0, "meshes", 0, "features", 0));
    try {
      for (String name : model.param().varnames())
        scopeList(data, "parameters").add(scopeRecord("name", name, "expression", model.param().get(name)));
      for (String group : model.param().group().tags())
        for (String name : model.param().group(group).varnames())
          scopeList(data, "parameters").add(scopeRecord("name", name, "expression", model.param().group(group).get(name)));
    } catch (Exception ex) { scopeIssue(scopeList(data, "incomplete"), "parameters", "Cannot enumerate parameter definitions: " + scopeError(ex)); }
    try {
      for (String tag : model.func().tags()) scopeFunction(data, model.func(tag), "functions/" + tag);
      if (model.variable().tags().length > 0) scopeIssue(scopeList(data, "unsupported"), "variables", "Global variables require a separate dependency adapter");
    } catch (Exception ex) { scopeIssue(scopeList(data, "incomplete"), "global", "Cannot enumerate global indirection: " + scopeError(ex)); }
    java.util.Set<String> componentGeometries = new java.util.HashSet<String>();
    try {
      for (String ctag : model.component().tags()) {
        scopeIncrement(data, "components"); ModelNode component = model.component(ctag); String path = "components/" + ctag;
        try {
          for (String tag : component.func().tags()) scopeFunction(data, component.func(tag), path + "/functions/" + tag);
          if (component.variable().tags().length > 0) scopeIssue(scopeList(data, "unsupported"), path + "/variables", "Component variables require a separate dependency adapter");
          for (String tag : component.selection().tags())
            scopeProperties(data, component.selection(tag), path + "/selections/" + tag, "selection");
          for (String gtag : component.geom().tags()) {
            componentGeometries.add(gtag);
            scopeGeometry(data, component.geom(gtag), path + "/geometry/" + gtag, 0);
          }
          for (String mtag : component.mesh().tags()) {
            scopeIncrement(data, "meshes"); MeshSequence mesh = component.mesh(mtag);
            for (String tag : mesh.feature().tags()) scopeMeshFeature(data, mesh.feature(tag), path + "/mesh/" + mtag + "/" + tag, 0);
          }
        } catch (Exception ex) { scopeIssue(scopeList(data, "incomplete"), path, "Cannot enumerate component: " + scopeError(ex)); }
      }
      for (String tag : model.geom().tags())
        if (!componentGeometries.contains(tag)) scopeIssue(scopeList(data, "unsupported"), "geometry/" + tag, "Global part/geometry outside components requires a separate dependency adapter");
    } catch (Exception ex) { scopeIssue(scopeList(data, "incomplete"), "components", "Cannot enumerate components: " + scopeError(ex)); }
    return scopeJson(data);
  }
'''
