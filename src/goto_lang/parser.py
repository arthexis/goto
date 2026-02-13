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
    r"(?P<goto>goto|go\s+to)\s+"
    r"(?P<expression>.+)$",
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
    goto_target: str | None = None
    should_jump: bool | None = None


def _format_parse_error(
    message: str,
    *,
    line_no: int,
    source_line: str,
    span: tuple[int, int] | None = None,
) -> str:
    """Build a parse error message with source context.

    Args:
        message: Human-readable error summary.
        line_no: One-based source line number.
        source_line: Raw source text for the line that failed parsing.
        span: Optional ``(start, end)`` bounds for the problematic segment,
            expressed as zero-based character offsets into ``source_line``.

    Returns:
        A formatted parse error message that includes line number, source line,
        and optional caret markers for highlighted spans.
    """

    formatted = [f"{message} (line {line_no})", f"{line_no} | {source_line}"]
    if span is not None:
        start, end = span
        safe_start = max(0, min(start, len(source_line)))
        safe_end = max(safe_start + 1, min(max(end, safe_start + 1), len(source_line)))
        padding = " " * safe_start
        marker = "^" * (safe_end - safe_start)
        formatted.append(f"{' ' * len(str(line_no))} | {padding}{marker}")
    return "\n".join(formatted)


def _resolve_expression(
    expression: str,
    line_no: int,
    *,
    source_line: str,
    span: tuple[int, int] | None = None,
    allow_file_reference: bool = False,
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

        if ".goto" in expression:
            raise ParseError(
                _format_parse_error(
                    "Malformed file reference expression",
                    line_no=line_no,
                    source_line=source_line,
                    span=span,
                )
            )

    return _safe_eval_expression(
        expression,
        line_no,
        source_line=source_line,
        span=span,
    )


def _safe_eval_expression(
    expression: str,
    line_no: int,
    *,
    source_line: str,
    span: tuple[int, int] | None = None,
) -> str:
    """Evaluate a constrained expression and return its string value.

    Supported syntax includes constants, string concatenation, numeric
    arithmetic, and unary +/- operators. Any unsupported syntax is rejected
    with a line-aware parse error.

    Args:
        expression: Expression used in a label declaration or goto target.
        line_no: Source line number used for parse error messaging.

    Returns:
        Stringified expression result used as the normalized label.

    Raises:
        ParseError: If the expression uses unsupported syntax.
    """

    def invalid_expression_error() -> ParseError:
        return ParseError(
            _format_parse_error(
                "Invalid expression",
                line_no=line_no,
                source_line=source_line,
                span=span,
            )
        )

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
        return str(eval_node(tree))
    except ParseError:
        raise
    except Exception as exc:
        raise invalid_expression_error() from exc


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

    The first two are accepted as no-ops. The number of ``not`` modifiers
    controls whether a jump occurs: an odd count suppresses the jump, and an
    even count executes it.

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
            expression_start = raw_line.find(expression)
            label = _resolve_expression(
                expression,
                line_no,
                source_line=raw_line,
                span=(expression_start, expression_start + len(expression)),
            )
            parsed.append(ParsedLine(index=line_no, raw=raw_line, label=label))
            continue

        goto_match = GOTO_STATEMENT_PATTERN.match(line)
        if goto_match:
            prefix_words = goto_match.group("prefix").lower().split()
            expression = goto_match.group("expression").strip()
            expression_start = raw_line.find(expression)
            target = _resolve_expression(
                expression,
                line_no,
                source_line=raw_line,
                span=(expression_start, expression_start + len(expression)),
                allow_file_reference=True,
            )
            should_jump = prefix_words.count("not") % 2 == 0
            parsed.append(
                ParsedLine(
                    index=line_no,
                    raw=raw_line,
                    goto_target=target,
                    should_jump=should_jump,
                )
            )
            continue

        raise ParseError(
            _format_parse_error(
                "Unexpected statement. Only labels and goto statements are allowed.",
                line_no=line_no,
                source_line=raw_line,
            )
        )

    return parsed
