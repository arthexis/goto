"""Parser for the goto-only language."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import math
import re
from typing import Callable


def _normalize_label_identifier(value: str) -> str:
    """Normalize user-provided label text for case-insensitive matching."""

    return " ".join(value.split()).lower()


BARE_LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FILE_REFERENCE_PATTERN = re.compile(
    r"^(?P<file>[A-Za-z0-9_./-]+\.goto)(?::(?P<label>[A-Za-z_][A-Za-z0-9_]*))?$"
)


def _is_word_char(character: str) -> bool:
    """Return whether a character should count as part of an identifier word."""

    return character.isalnum() or character == "_"


def _match_goto_statement(line: str) -> tuple[str, str | None] | None:
    """Find a goto/go to keyword outside of quoted strings."""

    in_single = False
    in_double = False
    escaped = False
    lowered = line.lower()

    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue

        if character == "\\":
            escaped = True
            continue

        if character == "'" and not in_double:
            in_single = not in_single
            continue

        if character == '"' and not in_single:
            in_double = not in_double
            continue

        if in_single or in_double:
            continue

        if lowered.startswith("goto", index):
            start = index
            end = index + 4
        elif lowered.startswith("go", index):
            whitespace_end = index + 2
            while whitespace_end < len(line) and line[whitespace_end].isspace():
                whitespace_end += 1
            if whitespace_end == index + 2 or not lowered.startswith("to", whitespace_end):
                continue
            start = index
            end = whitespace_end + 2
        else:
            continue

        if start > 0 and _is_word_char(line[start - 1]):
            continue
        if end < len(line) and _is_word_char(line[end]):
            continue

        prefix = line[:start].strip()
        expression = line[end:].strip() or None
        return prefix, expression

    return None


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
    expression: str,
    line_no: int,
    allow_file_reference: bool = False,
    user_function: Callable[[str], object] | None = None,
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
        return _normalize_label_identifier(expression)

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

    resolved = _safe_eval_expression(expression, line_no, user_function=user_function)
    if allow_file_reference and FILE_REFERENCE_PATTERN.match(resolved):
        return resolved
    return _normalize_label_identifier(resolved)


def _safe_eval_value(
    expression: str,
    line_no: int,
    user_function: Callable[[str], object] | None = None,
) -> object:
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

    custom_operator_value = _evaluate_custom_comparison(
        expression,
        line_no,
        user_function=user_function,
    )
    if custom_operator_value is not None:
        return custom_operator_value

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

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id != "user":
                raise invalid_expression_error()
            if node.keywords:
                raise invalid_expression_error()
            if len(node.args) > 1:
                raise ParseError(
                    f"Invalid expression on line {line_no}: 'user' accepts at most one argument."
                )
            if user_function is None:
                raise ParseError(
                    f"Invalid expression on line {line_no}: 'user' is unavailable in this context."
                )
            prompt = (
                "Which label would you like to go to? "
                if not node.args
                else str(eval_node(node.args[0]))
            )
            return user_function(prompt)

        raise invalid_expression_error()

    try:
        tree = ast.parse(expression, mode="eval")
        return eval_node(tree)
    except ParseError:
        raise
    except Exception as exc:
        raise invalid_expression_error() from exc


def _evaluate_custom_comparison(
    expression: str,
    line_no: int,
    user_function: Callable[[str], object] | None = None,
) -> bool | None:
    """Evaluate custom comparison operators when present in an expression."""

    operator_parts = _split_custom_operator(expression)
    if operator_parts is None:
        return None

    left_expression, operator, right_expression = operator_parts
    left_value = _evaluate_custom_operand(left_expression, line_no, user_function=user_function)
    right_value = _evaluate_custom_operand(right_expression, line_no, user_function=user_function)
    more_or_less = _more_or_less_same(left_value, right_value)
    if operator == "~=":
        return more_or_less
    return not more_or_less


def _evaluate_custom_operand(
    expression: str,
    line_no: int,
    user_function: Callable[[str], object] | None = None,
) -> object:
    """Resolve one operand of a custom comparison expression."""

    if BARE_LABEL_PATTERN.match(expression):
        return expression
    return _safe_eval_value(expression, line_no, user_function=user_function)


def _split_custom_operator(expression: str) -> tuple[str, str, str] | None:
    """Split an expression by the first top-level custom operator."""

    depth = 0
    in_single_quote = False
    in_double_quote = False

    for index, char in enumerate(expression):
        previous_char = expression[index - 1] if index > 0 else ""
        if char == "'" and not in_double_quote and previous_char != "\\":
            in_single_quote = not in_single_quote
            continue
        if char == '"' and not in_single_quote and previous_char != "\\":
            in_double_quote = not in_double_quote
            continue
        if in_single_quote or in_double_quote:
            continue

        if char == "(":
            depth += 1
            continue
        if char == ")":
            depth -= 1
            continue
        if depth != 0:
            continue

        candidate = expression[index : index + 2]
        if candidate in {"~=", "=~"}:
            left = expression[:index].strip()
            right = expression[index + 2 :].strip()
            if not left or not right:
                return None
            return left, candidate, right

    return None


def _more_or_less_same(left: object, right: object) -> bool:
    """Return whether two values are considered approximately equivalent."""

    if isinstance(left, str) and isinstance(right, str):
        normalized_left = " ".join(left.split()).casefold()
        normalized_right = " ".join(right.split()).casefold()
        return normalized_left == normalized_right

    if isinstance(left, (int, float)) and not isinstance(left, bool):
        if isinstance(right, (int, float)) and not isinstance(right, bool):
            return math.isclose(float(left), float(right), rel_tol=1e-09, abs_tol=1e-09)

    return left == right


def _safe_eval_expression(
    expression: str,
    line_no: int,
    user_function: Callable[[str], object] | None = None,
) -> str:
    """Evaluate a constrained expression and return its string value.

    Args:
        expression: Expression used in a label declaration or goto target.
        line_no: Source line number used for parse error messaging.

    Returns:
        Stringified expression result used as the normalized label.
    """

    return str(_safe_eval_value(expression, line_no, user_function=user_function))


def parse_program(
    source: str,
    user_function: Callable[[str], object] | None = None,
) -> list[ParsedLine]:
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
    pending_unless_expression: tuple[int, str] | None = None
    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.endswith(";"):
            line = line[:-1].rstrip()
            if not line:
                continue

        if line.endswith(":"):
            expression = line[:-1].strip()
            label = _resolve_expression(
                expression,
                line_no,
                user_function=user_function,
            )
            parsed.append(ParsedLine(index=line_no, raw=raw_line, label=label))
            continue

        goto_statement = _match_goto_statement(line)
        unless_only_match = re.match(r"^unless\s+(.+)$", line, re.IGNORECASE)
        if unless_only_match and goto_statement is None:
            pending_unless_expression = (line_no, unless_only_match.group(1).strip())
            continue

        if goto_statement is not None:
            prefix_text, expression = goto_statement
            unless_expression = _extract_unless_expression(prefix_text)
            if unless_expression is None and pending_unless_expression is not None:
                unless_expression = pending_unless_expression[1]
            pending_unless_expression = None
            target = (
                _resolve_expression(
                    expression,
                    line_no,
                    allow_file_reference=True,
                    user_function=user_function,
                )
                if expression is not None
                else None
            )
            prefix_words = _prefix_words_without_unless(prefix_text)
            base_should_jump = True
            if unless_expression is not None:
                base_should_jump = (
                    _safe_eval_value(
                        unless_expression,
                        line_no,
                        user_function=user_function,
                    )
                    is not True
                )

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

        parsed.append(ParsedLine(index=line_no, raw=raw_line))


    if pending_unless_expression is not None:
        raise ParseError(
            f"Unexpected statement on line {pending_unless_expression[0]}: 'unless' must be followed by a goto statement."
        )

    return parsed


def _extract_unless_expression(prefix_text: str) -> str | None:
    """Extract an `unless <expression>` segment from goto prefix text.

    Only an `unless` clause that appears at the end of prefix text is treated
    as a modifier; other words are ignored as no-op prefixes.
    """

    unless_match = re.search(r"\bunless\b\s+(.+)$", prefix_text, re.IGNORECASE)
    if unless_match is None:
        return None
    return unless_match.group(1).strip() or None


def _prefix_words_without_unless(prefix_text: str) -> list[str]:
    """Return prefix words with a trailing `unless` clause removed."""

    unless_match = re.search(r"\bunless\b\s+.+$", prefix_text, re.IGNORECASE)
    prefix_without_unless = (
        prefix_text[: unless_match.start()].strip() if unless_match else prefix_text
    )
    return prefix_without_unless.lower().split()
