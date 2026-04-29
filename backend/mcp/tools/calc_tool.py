"""
MCP Tool: Safe Calculator
==========================
Evaluates mathematical expressions safely using Python's AST module.
NEVER uses eval() — arbitrary code execution is impossible.

Supported Operations:
    - Basic arithmetic: +, -, *, /, //, %
    - Exponentiation: **
    - Mathematical functions: sqrt, abs, round, floor, ceil
    - Trigonometry: sin, cos, tan (radians)
    - Logarithms: log (base-10), log2, ln (natural log)
    - Constants: pi, e

Tools exposed:
    - calculate(expression)
"""

import ast
import math
import operator
import logging

logger = logging.getLogger(__name__)

# ============================================================
# Safe Operation Whitelist
# ============================================================

ALLOWED_OPERATORS = {
    ast.Add:       operator.add,
    ast.Sub:       operator.sub,
    ast.Mult:      operator.mul,
    ast.Div:       operator.truediv,
    ast.FloorDiv:  operator.floordiv,
    ast.Mod:       operator.mod,
    ast.Pow:       operator.pow,
    ast.USub:      operator.neg,   # unary minus
    ast.UAdd:      operator.pos,   # unary plus
}

ALLOWED_FUNCTIONS = {
    "sqrt":  math.sqrt,
    "abs":   abs,
    "round": round,
    "floor": math.floor,
    "ceil":  math.ceil,
    "sin":   math.sin,
    "cos":   math.cos,
    "tan":   math.tan,
    "asin":  math.asin,
    "acos":  math.acos,
    "atan":  math.atan,
    "log":   math.log10,    # log base 10
    "log2":  math.log2,
    "ln":    math.log,      # natural log
    "exp":   math.exp,
    "degrees": math.degrees,
    "radians": math.radians,
}

ALLOWED_CONSTANTS = {
    "pi": math.pi,
    "e":  math.e,
    "inf": math.inf,
    "tau": math.tau,
}


# ============================================================
# AST-based Safe Evaluator
# ============================================================

class SafeEvaluator(ast.NodeVisitor):
    """
    Walks an AST and evaluates only whitelisted node types.
    Any non-whitelisted node raises a ValueError.
    """

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise ValueError(f"Operator '{op_type.__name__}' is not allowed.")
        left = self.visit(node.left)
        right = self.visit(node.right)

        # Guard against division by zero
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise ZeroDivisionError("Division by zero is not allowed.")

        return ALLOWED_OPERATORS[op_type](left, right)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in ALLOWED_OPERATORS:
            raise ValueError(f"Unary operator '{op_type.__name__}' is not allowed.")
        operand = self.visit(node.operand)
        return ALLOWED_OPERATORS[op_type](operand)

    def visit_Call(self, node: ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only named function calls are allowed (no method calls).")

        func_name = node.func.id
        if func_name not in ALLOWED_FUNCTIONS:
            raise ValueError(
                f"Function '{func_name}' is not allowed. "
                f"Allowed: {', '.join(ALLOWED_FUNCTIONS.keys())}"
            )

        args = [self.visit(arg) for arg in node.args]
        return ALLOWED_FUNCTIONS[func_name](*args)

    def visit_Name(self, node: ast.Name):
        if node.id in ALLOWED_CONSTANTS:
            return ALLOWED_CONSTANTS[node.id]
        raise ValueError(
            f"Variable '{node.id}' is not allowed. "
            f"Allowed constants: {', '.join(ALLOWED_CONSTANTS.keys())}"
        )

    def visit_Constant(self, node: ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError(f"Only numeric constants are allowed, got: {type(node.value).__name__}")
        return node.value

    def generic_visit(self, node):
        raise ValueError(f"Unsupported AST node: {type(node).__name__}")


# ============================================================
# Tool Function
# ============================================================

def calculate(expression: str) -> dict:
    """
    Safely evaluate a mathematical expression.

    Args:
        expression: A math expression string (e.g., "sqrt(144) + 5 * 2")

    Returns:
        dict with result or detailed error message.

    Examples:
        calculate("25 * 48")          → {"result": 1200, "expression": "25 * 48"}
        calculate("sqrt(144)")         → {"result": 12.0, "expression": "sqrt(144)"}
        calculate("sin(pi / 2)")       → {"result": 1.0, "expression": "sin(pi / 2)"}
        calculate("__import__('os')")  → {"error": "..."}  (blocked)
    """
    if not expression or not expression.strip():
        return {"success": False, "error": "Expression cannot be empty."}

    expression = expression.strip()

    # Length guard
    if len(expression) > 500:
        return {"success": False, "error": "Expression is too long (max 500 characters)."}

    try:
        # Parse into AST
        tree = ast.parse(expression, mode="eval")

        # Evaluate safely
        evaluator = SafeEvaluator()
        result = evaluator.visit(tree)

        # Round floats to avoid floating-point noise
        if isinstance(result, float):
            result = round(result, 10)

        logger.info(f"Calculator: '{expression}' = {result}")
        return {"success": True, "expression": expression, "result": result}

    except ZeroDivisionError as e:
        return {"success": False, "expression": expression, "error": str(e)}

    except ValueError as e:
        logger.warning(f"Calculator blocked unsafe expression: '{expression}' — {e}")
        return {"success": False, "expression": expression, "error": str(e)}

    except SyntaxError as e:
        return {"success": False, "expression": expression, "error": f"Invalid syntax: {e.msg}"}

    except Exception as e:
        logger.error(f"Calculator unexpected error: {e}")
        return {"success": False, "expression": expression, "error": f"Calculation failed: {str(e)}"}
