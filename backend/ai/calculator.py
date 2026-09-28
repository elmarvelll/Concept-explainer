"""A small, safe arithmetic expression evaluator — no `eval()`.

Parses the expression into a Python AST and walks it, only ever executing a
fixed allow-list of numeric operators. Anything else (names, function calls,
attribute access, subscripts, comprehensions, ...) is rejected before it can
run, so there's no code-injection surface the way a raw `eval()` would have.
"""

import ast
import operator
import re

# Percentages are rewritten into plain division before parsing (e.g. "15%"
# -> "(15/100)"), so by the time the AST walk runs, there's no special-casing
# needed for '%' as anything other than a number — deterministic regardless
# of what surrounds it in the expression. '%' immediately followed by
# another number (e.g. "7 % 3") is left alone and parsed as modulo instead —
# the two meanings share a symbol, so this is how they're disambiguated.
_PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%(?!\s*\d)")

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Guards against expressions that are syntactically valid but absurdly
# expensive to compute, like `9**9**9`.
MAX_EXPONENT = 1000


class CalculatorError(ValueError):
    """Raised for any invalid or unsafe expression."""


def _preprocess_percentages(expression: str) -> str:
    return _PERCENT_PATTERN.sub(r"(\1/100)", expression)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise CalculatorError(f"Unsupported value: {node.value!r}")

    if isinstance(node, ast.BinOp):
        op_fn = _BINARY_OPS.get(type(node.op))
        if op_fn is None:
            raise CalculatorError(f"Unsupported operator: {type(node.op).__name__}")

        left = _eval_node(node.left)
        right = _eval_node(node.right)

        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise CalculatorError("Exponent too large")

        try:
            return op_fn(left, right)
        except ZeroDivisionError as e:
            raise CalculatorError("Division by zero") from e

    if isinstance(node, ast.UnaryOp):
        op_fn = _UNARY_OPS.get(type(node.op))
        if op_fn is None:
            raise CalculatorError(f"Unsupported operator: {type(node.op).__name__}")
        return op_fn(_eval_node(node.operand))

    raise CalculatorError(f"Unsupported expression: {type(node).__name__}")


def evaluate(expression: str) -> float:
    """Safely evaluate a basic arithmetic expression (+, -, *, /, //, %, **,
    parentheses, decimals, percentages). Raises CalculatorError on anything
    invalid or unsupported — never raises from arbitrary code execution,
    since none can occur here."""
    if not expression or not expression.strip():
        raise CalculatorError("Empty expression")

    processed = _preprocess_percentages(expression)
    try:
        tree = ast.parse(processed, mode="eval")
    except SyntaxError as e:
        raise CalculatorError(f"Invalid expression: {e.msg}") from e

    return _eval_node(tree)
