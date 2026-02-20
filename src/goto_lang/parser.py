"""Parser for the goto-only language."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import re


BARE_LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FILE_REFERENCE_PATTERN = re.compile(
    r"^(?P<file>[A-Za-z0-9_./-]+\.goto)(?::(?P<label>[A-Za-z_][A-Za-z0-9_]*))?$"
)
GOTO_STATEMENT_PATTERN = re.compile(
    r"^(?P<prefix>(?:(?:do|please|not)\s+)*)"
    r"(?:(?P<unless>unless)\s+(?P<unless_expression>.+?)\s+)?"
    r"(?P<goto>goto|go\s+to)(?:\s+(?P<expression>.+))?$",
    re.IGNORECASE,
)


class ParseError(ValueError):
    """Raised when source code is not valid goto language code."""


@dataclass(frozen=True)
class ParsedLine:
    """Represents one parsed line in the source program."""

    index: int
    raw: str
    label: str | None = None
    is_goto: bool = False
    goto_target: str | None = None
    should_jump: bool | None = None


def _resolve_expression(
    expression: str, line_no: int, allow_file_reference: bool = False
) -> str:
    """Evaluate an expression and convert the result into a label string.

    Args:
        expression: Expression used in a label declaration or goto target.
        line_no: Source line number used for parse error messaging.
        allow_file_reference: Whether file-based goto references are accepted.

    Returns:
        str: Stringified expression result used as the normalized label.

    Raises:
        ParseError: If the expression cannot be evaluated.
    """

    if BARE_LABEL_PATTERN.match(expression):
        return expression

    if allow_file_reference:
        match = FILE_REFERENCE_PATTERN.match(expression)
        if match:
            return expression

        parts = expression.split()
        if (
            len(parts) == 2
            and FILE_REFERENCE_PATTERN.match(parts[0])
            and BARE_LABEL_PATTERN.match(parts[1])
        ):
            return f"{parts[0]}:{parts[1]}"

    return _safe_eval_expression(expression, line_no)


def _safe_eval_value(expression: str, line_no: int) -> object:
    """Evaluate a constrained expression and return its resolved value.

    Supported syntax includes constants, string concatenation, numeric
    arithmetic, and unary +/- operators. Any unsupported syntax is rejected
    with a line-aware parse error.

    Args:
        expression: Expression used in a label declaration or goto target.
        line_no: Source line number used for parse error messaging.

    Returns:
        Evaluated expression result.

    Raises:
        ParseError: If the expression uses unsupported syntax.
    """

    def invalid_expression_error() -> ParseError:
        return ParseError(f"Invalid expression on line {line_no}: '{expression}'.")

    def eval_node(node: ast.AST) -> object:
        """Recursively evaluate a supported AST node."""

        if isinstance(node, ast.Expression):
            return eval_node(node.body)

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool, type(None))):
                return node.value
            raise invalid_expression_error()

        if isinstance(node, ast.UnaryOp):
            value = eval_node(node.operand)
            if isinstance(node.op, ast.UAdd):
                if isinstance(value, (int, float)):
                    return +value
                raise invalid_expression_error()
            if isinstance(node.op, ast.USub):
                if isinstance(value, (int, float)):
                    return -value
                raise invalid_expression_error()
            raise invalid_expression_error()

        if isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            op = node.op

            if isinstance(op, ast.Add):
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left + right
                raise invalid_expression_error()
            if isinstance(op, ast.Sub):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left - right
                raise invalid_expression_error()
            if isinstance(op, ast.Mult):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left * right
                raise invalid_expression_error()
            if isinstance(op, ast.Div):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left / right
                raise invalid_expression_error()
            if isinstance(op, ast.FloorDiv):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left // right
                raise invalid_expression_error()
            if isinstance(op, ast.Mod):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left % right
                raise invalid_expression_error()
            if isinstance(op, ast.Pow):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left**right
                raise invalid_expression_error()
            raise invalid_expression_error()

        raise invalid_expression_error()

    try:
        tree = ast.parse(expression, mode="eval")
        return eval_node(tree)
    except ParseError:
        raise
    except Exception as exc:
        raise invalid_expression_error() from exc


def _safe_eval_expression(expression: str, line_no: int) -> str:
    """Evaluate a constrained expression and return its string value.

    Args:
        expression: Expression used in a label declaration or goto target.
        line_no: Source line number used for parse error messaging.

    Returns:
        Stringified expression result used as the normalized label.
    """

    return str(_safe_eval_value(expression, line_no))


def parse_program(source: str) -> list[ParsedLine]:
    """Parse source code into normalized program lines.

    Blank lines and comments beginning with ``#`` are ignored.
    A non-empty line can be either:

    - ``<expression>:``
    - ``goto <expression>`` (also ``go to <expression>``, any case)

    Optional modifier words may appear before goto:

    - ``do``
    - ``please``
    - ``not``
    - ``unless <expression>``

    The first two are accepted as no-ops. ``unless`` suppresses a jump when
    the expression evaluates to ``True``. The number of ``not`` modifiers then
    toggles jump behavior: an odd count negates it, and an even count leaves
    it unchanged.

    Args:
        source: Raw program source code.

    Returns:
        Ordered list of parsed lines.

    Raises:
        ParseError: If source contains invalid syntax.
    """

    parsed: list[ParsedLine] = []
    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.endswith(":"):
            expression = line[:-1].strip()
            label = _resolve_expression(expression, line_no)
            parsed.append(ParsedLine(index=line_no, raw=raw_line, label=label))
            continue

        goto_match = GOTO_STATEMENT_PATTERN.match(line)
        if goto_match:
            prefix_words = goto_match.group("prefix").lower().split()
            expression = (goto_match.group("expression") or "").strip()
            unless_expression = goto_match.group("unless_expression")
            target = (
                _resolve_expression(expression, line_no, allow_file_reference=True)
                if expression
                else None
            )
            base_should_jump = True
            if unless_expression is not None:
                base_should_jump = _safe_eval_value(unless_expression, line_no) is not True

            if prefix_words.count("not") % 2 == 1:
                should_jump = not base_should_jump
            else:
                should_jump = base_should_jump
            parsed.append(
                ParsedLine(
                    index=line_no,
                    raw=raw_line,
                    is_goto=True,
                    goto_target=target,
                    should_jump=should_jump,
                )
            )
            continue

        raise ParseError(
            f"Unexpected statement on line {line_no}: '{raw_line}'. "
            "Only labels and goto statements are allowed."
        )

    return parsed
