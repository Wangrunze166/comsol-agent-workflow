"""Deliberately small SI unit grammar. Never evaluate COMSOL expressions in Python."""
import ast
import math

ZERO = (0, 0, 0, 0, 0)
# Dimensions: mass, length, time, electric current, thermodynamic temperature.
UNITS = {
    "kg": (1, (1, 0, 0, 0, 0)), "g": (.001, (1, 0, 0, 0, 0)),
    "m": (1, (0, 1, 0, 0, 0)), "mm": (.001, (0, 1, 0, 0, 0)),
    "um": (1e-6, (0, 1, 0, 0, 0)), "cm": (.01, (0, 1, 0, 0, 0)),
    "s": (1, (0, 0, 1, 0, 0)), "min": (60, (0, 0, 1, 0, 0)),
    "h": (3600, (0, 0, 1, 0, 0)), "A": (1, (0, 0, 0, 1, 0)),
    "mA": (.001, (0, 0, 0, 1, 0)), "K": (1, (0, 0, 0, 0, 1)),
    "Hz": (1, (0, 0, -1, 0, 0)), "N": (1, (1, 1, -2, 0, 0)),
    "Pa": (1, (1, -1, -2, 0, 0)), "kPa": (1000, (1, -1, -2, 0, 0)),
    "J": (1, (1, 2, -2, 0, 0)), "W": (1, (1, 2, -3, 0, 0)),
    "V": (1, (1, 2, -3, -1, 0)), "ohm": (1, (1, 2, -3, -2, 0)),
}
QUANTITIES = {
    "dimensionless": ZERO, "length": (0, 1, 0, 0, 0),
    "area": (0, 2, 0, 0, 0), "volume": (0, 3, 0, 0, 0),
    "time": (0, 0, 1, 0, 0), "frequency": (0, 0, -1, 0, 0),
    "velocity": (0, 1, -1, 0, 0), "current": (0, 0, 0, 1, 0),
    "absolute_temperature": (0, 0, 0, 0, 1), "temperature_difference": (0, 0, 0, 0, 1),
    "power": (1, 2, -3, 0, 0), "pressure": (1, -1, -2, 0, 0),
    "resistance": (1, 2, -3, -2, 0), "voltage": (1, 2, -3, -1, 0),
    "density": (1, -3, 0, 0, 0), "heat_capacity": (0, 2, -2, 0, -1),
    "thermal_conductivity": (1, 1, -3, 0, -1),
    "pi_proportional_gain": (0, 0, 0, 1, -1),
    "pi_integral_gain": (0, 0, -1, 1, -1),
    "pid_derivative_gain": (0, 0, 1, 1, -1),
}


def parse_unit(unit):
    if not isinstance(unit, str) or len(unit) > 100:
        raise ValueError("Unit must be a short string")
    if unit == "degC":
        return 1.0, QUANTITIES["absolute_temperature"]
    tree = ast.parse(unit.replace("^", "**"), mode="eval").body

    def visit(node):
        if isinstance(node, ast.Name) and node.id in UNITS:
            return UNITS[node.id]
        if isinstance(node, ast.Constant) and type(node.value) is int and node.value == 1:
            return 1.0, ZERO
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)):
            a, da = visit(node.left)
            b, db = visit(node.right)
            sign = 1 if isinstance(node.op, ast.Mult) else -1
            return a * b ** sign, tuple(x + sign*y for x, y in zip(da, db))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            exponent = node.right
            sign = 1
            if isinstance(exponent, ast.UnaryOp) and isinstance(exponent.op, ast.USub):
                sign, exponent = -1, exponent.operand
            if not isinstance(exponent, ast.Constant) or type(exponent.value) is not int or abs(exponent.value) > 8:
                raise ValueError("Unit exponents must be integers from -8 to 8")
            a, da = visit(node.left)
            power = sign * exponent.value
            return a ** power, tuple(x * power for x in da)
        raise ValueError("Unsupported unit syntax; use SI symbols, *, /, parentheses, ^integer")
    return visit(tree)


def check_quantity(value, unit, quantity):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("Parameter must have a finite numeric value; expressions stay in reviewed MPH")
    scale, dimension = parse_unit(unit)
    if quantity not in QUANTITIES or dimension != QUANTITIES[quantity]:
        raise ValueError(f"Unit {unit!r} does not match quantity {quantity!r}")
    if unit == "degC" and quantity != "absolute_temperature":
        raise ValueError("degC is an offset temperature; use K for differences and gains")
    result = value * scale + (273.15 if unit == "degC" else 0)
    if quantity == "absolute_temperature" and result < 0:
        raise ValueError("Temperature below absolute zero")
    if quantity in {"length", "area", "volume", "time", "density", "heat_capacity", "thermal_conductivity", "resistance"} and result <= 0:
        raise ValueError(f"{quantity} must be positive")
    return result, dimension
