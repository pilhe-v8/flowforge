import ast
import operator
from typing import Any


SAFE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.Gt: operator.gt,
    ast.LtE: operator.le,
    ast.GtE: operator.ge,
    ast.And: all,
    ast.Or: any,
    ast.Not: operator.not_,
    ast.In: lambda left, right: left in right,
}

SAFE_FUNCTIONS = {
    "len": len,
    "contains": lambda haystack, needle: needle in str(haystack),
    "starts_with": lambda s, prefix: str(s).startswith(str(prefix)),
    "is_empty": lambda x: x is None or x == "" or x == [] or x == {},
}


class SafeExprEvaluator:
    """
    Evaluates restricted boolean expressions from gate rules and fallback conditions.
    Supports: ==, !=, <, >, <=, >=, and, or, not, in, len(), contains(), starts_with(), is_empty()
    Does NOT use eval(). Uses AST parsing with a strict whitelist.
    """

    def __init__(self, variables: dict[str, Any]):
        # Flatten state: {step_id: {var: val}} -> {var: val}
        self.vars: dict[str, Any] = {}
        for step_id, step_data in variables.items():
            if isinstance(step_data, dict):
                self.vars.update(step_data)

    def evaluate(self, expr: str) -> bool:
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {expr!r}") from e
        return bool(self._eval_node(tree.body))

    def _eval_node(self, node: ast.expr) -> Any:
        if isinstance(node, ast.Compare):
            return self._eval_compare(node)
        elif isinstance(node, ast.BoolOp):
            return self._eval_boolop(node)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self._eval_node(node.operand)
        elif isinstance(node, ast.Name):
            return self.vars.get(node.id)
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Call):
            return self._eval_call(node)
        elif isinstance(node, ast.List):
            return [self._eval_node(e) for e in node.elts]
        elif isinstance(node, ast.IfExp):
            raise ValueError("Ternary expressions not allowed")
        else:
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")

    def _eval_compare(self, node: ast.Compare) -> bool:
        left = self._eval_node(node.left)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            right = self._eval_node(comparator)
            if isinstance(op, ast.In):
                result = result and (left in right)
            elif isinstance(op, ast.NotIn):
                result = result and (left not in right)
            elif type(op) in SAFE_OPS:
                result = result and SAFE_OPS[type(op)](left, right)
            else:
                raise ValueError(f"Unsupported operator: {type(op).__name__}")
            left = right
        return result

    def _eval_boolop(self, node: ast.BoolOp) -> bool:
        values = [self._eval_node(v) for v in node.values]
        if type(node.op) in SAFE_OPS:
            return SAFE_OPS[type(node.op)](values)
        raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

    def _eval_call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed")
        func_name = node.func.id
        if func_name not in SAFE_FUNCTIONS:
            raise ValueError(f"Unknown function: {func_name!r}")
        args = [self._eval_node(a) for a in node.args]
        if node.keywords:
            raise ValueError("Keyword arguments not allowed in expressions")
        return SAFE_FUNCTIONS[func_name](*args)
