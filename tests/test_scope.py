"""Synthetic dependency-audit regressions. These tests never launch COMSOL."""
import unittest

from comsol_workflow.scope import evaluate_scope


def inventory():
    return {"schema_version": 1,
            "parameters": [{"name": "Tleft", "expression": "293.15[K]"},
                           {"name": "width", "expression": "10[mm]"},
                           {"name": "half_width", "expression": "width/2"},
                           {"name": "fine_size", "expression": "half_width/20"}],
            "properties": [{"path": "components/c1/geometry/g1/rectangle/size",
                            "scope": "geometry", "value_type": "StringArray",
                            "expressions": ["width", "20[mm]"]},
                           {"path": "components/c1/mesh/m1/size/hmax",
                            "scope": "mesh", "value_type": "String",
                            "expressions": ["fine_size"]}],
            "incomplete": [], "unsupported": [], "functions": [],
            "scanned": {"components": 1, "geometries": 1, "meshes": 1, "features": 2}}


class ScopeAuditTests(unittest.TestCase):
    def test_direct_and_transitive_dependencies_ignore_claimed_scope(self):
        result = evaluate_scope(inventory(), [{"name": "width", "scope": "physics_scalar"}])
        self.assertFalse(result["passed"])
        self.assertEqual({hit["scope"] for hit in result["hits"]}, {"geometry", "mesh"})
        mesh = next(hit for hit in result["hits"] if hit["scope"] == "mesh")
        self.assertEqual(mesh["dependency_path"], ["width", "half_width", "fine_size"])

    def test_unreferenced_physics_parameter_passes_supported_inventory(self):
        result = evaluate_scope(inventory(), [{"name": "Tleft", "scope": "physics_scalar"}])
        self.assertTrue(result["passed"])
        self.assertTrue(result["checked"])

    def test_identifier_matching_is_not_substring_matching(self):
        data = inventory()
        data["parameters"] += [{"name": "foo", "expression": "2"},
                               {"name": "foobar", "expression": "3"}]
        data["properties"][0]["expressions"] = ["foobar*2"]
        self.assertTrue(evaluate_scope(data, [{"name": "foo"}])["passed"])
        data["properties"][0]["expressions"] = ["root.foo * 2"]
        self.assertFalse(evaluate_scope(data, [{"name": "foo"}])["passed"])

    def test_named_selection_dependency_blocks_override(self):
        data = inventory()
        data["properties"].append({"path": "components/c1/selections/box/xmax",
                                   "scope": "selection", "value_type": "String",
                                   "expressions": ["Tleft/1[K]*1[mm]"]})
        self.assertFalse(evaluate_scope(data, [{"name": "Tleft"}])["passed"])

    def test_dynamic_solution_lookup_and_unknown_scoped_value_fail_closed(self):
        for expression in ["withsol('sol1', T)", "comp1.unresolved", "custom_geometry(1)"]:
            with self.subTest(expression=expression):
                data = inventory()
                data["properties"][0]["expressions"] = [expression]
                result = evaluate_scope(data, [{"name": "Tleft"}])
                self.assertFalse(result["passed"])
                self.assertTrue(result["unsupported"])

    def test_local_math_and_unit_tokens_are_supported(self):
        data = inventory()
        data["parameters"].append({"name": "unrelated", "expression": "abs(width)/2"})
        data["properties"][0]["expressions"] = ["max(1[mm],root.width)"]
        self.assertTrue(evaluate_scope(data, [{"name": "Tleft"}])["passed"])

    def test_missing_enumeration_coverage_blocks_override(self):
        data = inventory()
        del data["scanned"]
        self.assertFalse(evaluate_scope(data, [{"name": "Tleft"}])["passed"])

    def test_unused_complete_function_does_not_block_a_supported_override(self):
        data = inventory()
        data["functions"].append({"name": "generated_heat_fn", "type": "Analytic",
                                  "arguments": ["T"], "expression": "T^4"})
        self.assertTrue(evaluate_scope(data, [{"name": "Tleft"}])["passed"])

    def test_declared_function_cannot_shadow_builtin_math_to_bypass_audit(self):
        data = inventory()
        data["functions"].append({"name": "sin", "type": "Analytic",
                                  "arguments": ["x"], "expression": "Tleft*x"})
        data["properties"][0]["expressions"] = ["sin(1)"]
        result = evaluate_scope(data, [{"name": "Tleft"}])
        self.assertFalse(result["passed"])
        self.assertTrue(result["unsupported"])

    def test_function_reference_and_unreadable_function_definition_fail_closed(self):
        data = inventory()
        data["functions"].append({"name": "shape", "type": "Analytic",
                                  "arguments": [], "expression": "Tleft"})
        data["properties"][0]["expressions"] = ["shape"]
        self.assertFalse(evaluate_scope(data, [{"name": "Tleft"}])["passed"])
        data = inventory()
        data["functions"].append({"name": "unreadable", "type": "Analytic"})
        self.assertFalse(evaluate_scope(data, [{"name": "Tleft"}])["passed"])

    def test_getter_failure_or_unsupported_indirection_blocks_all_overrides(self):
        for field in ["incomplete", "unsupported"]:
            with self.subTest(field=field):
                data = inventory()
                data[field].append({"path": "some/feature", "reason": "cannot prove dependencies"})
                result = evaluate_scope(data, [{"name": "Tleft"}])
                self.assertFalse(result["passed"])
                self.assertTrue(result[field])

    def test_no_override_preserves_model_without_claiming_dependency_proof(self):
        data = inventory()
        data["unsupported"].append({"path": "functions", "reason": "outside supported scope"})
        result = evaluate_scope(data, [])
        self.assertTrue(result["passed"])
        self.assertFalse(result["checked"])
        self.assertIn("not proved", result["proof_scope"])
        self.assertTrue(result["unsupported"])

    def test_absent_override_and_malformed_inventory_fail_closed(self):
        self.assertFalse(evaluate_scope(inventory(), [{"name": "unknown"}])["passed"])
        for broken in [None, {}, {"schema_version": 2}]:
            with self.subTest(inventory=broken):
                self.assertFalse(evaluate_scope(broken, [{"name": "Tleft"}])["passed"])

    def test_conflicting_groups_and_malformed_properties_fail_closed(self):
        data = inventory()
        data["parameters"].append({"name": "Tleft", "expression": "2[K]"})
        self.assertFalse(evaluate_scope(data, [{"name": "Tleft"}])["passed"])
        data = inventory()
        data["properties"].append({"path": "missing-expression"})
        self.assertFalse(evaluate_scope(data, [{"name": "Tleft"}])["passed"])

    def test_malformed_override_list_cannot_masquerade_as_no_overrides(self):
        for broken in [None, {}, [None], [{"name": 23}]]:
            with self.subTest(parameters=broken):
                self.assertFalse(evaluate_scope(inventory(), broken)["passed"])


if __name__ == "__main__":
    unittest.main()
