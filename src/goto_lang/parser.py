"""Parser for the goto-only language."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import json
import re


def _normalize_label_identifier(value: str) -> str:
    """Normalize user-provided label text for case-insensitive matching."""

    return " ".join(value.split()).lower()


BARE_LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FILE_REFERENCE_PATTERN = re.compile(
    r"^(?P<file>[A-Za-z0-9_./-]+\.goto)(?::(?P<label>[A-Za-z_][A-Za-z0-9_]*))?$"
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
    output_text: str | None = None
    decision_text: str | None = None
    goto_targets: tuple[str, ...] | None = None
    not_count: int = 0
    please: bool = False


def _is_word_char(character: str) -> bool:
    """Return whether a character should count as part of an identifier word."""

    return character.isalnum() or character == "_"


def _match_goto_statement(line: str) -> tuple[str, str | None] | None:
    """Find a goto/go to keyword outside of quoted strings."""

    in_single = False
    in_double = False
    in_backtick = False
    escaped = False
    lowered = line.lower()

    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "'" and not in_double and not in_backtick:
            in_single = not in_single
            continue
        if character == '"' and not in_single and not in_backtick:
            in_double = not in_double
            continue
        if character == "`" and not in_single and not in_double:
            in_backtick = not in_backtick
            continue
        if in_single or in_double or in_backtick:
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


def _normalize_backtick_strings(expression: str, line_no: int) -> str:
    """Convert backtick-quoted strings to JSON double-quoted strings for AST parsing."""

    pieces: list[str] = []
    current: list[str] = []
    in_backtick = False
    escaped = False

    for character in expression:
        if in_backtick:
            if escaped:
                current.append(character)
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == "`":
                pieces.append(json.dumps("".join(current)))
                current = []
                in_backtick = False
                continue
            current.append(character)
            continue

        if character == "`":
            in_backtick = True
            continue
        pieces.append(character)

    if in_backtick:
        raise ParseError(f"Unterminated backtick string on line {line_no}: '{expression}'.")
    return "".join(pieces)


def _safe_eval_value(expression: str, line_no: int, sigils: dict[str, str] | None = None) -> object:
    """Evaluate constrained arithmetic/string expressions."""

    normalized_expression = _normalize_backtick_strings(expression, line_no)

    def invalid_expression_error() -> ParseError:
        return ParseError(f"Invalid expression on line {line_no}: '{expression}'.")

    def eval_node(node: ast.AST) -> object:
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (str, int, float, bool, type(None))):
                return node.value
            raise invalid_expression_error()
        if isinstance(node, ast.UnaryOp):
            value = eval_node(node.operand)
            if isinstance(node.op, ast.UAdd) and isinstance(value, (int, float)):
                return +value
            if isinstance(node.op, ast.USub) and isinstance(value, (int, float)):
                return -value
            raise invalid_expression_error()
        if isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            if isinstance(node.op, ast.Add):
                if isinstance(left, str) and isinstance(right, str):
                    return left + right
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    return left + right
            if isinstance(node.op, ast.Sub) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left - right
            if isinstance(node.op, ast.Mult) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left * right
            if isinstance(node.op, ast.Div) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left / right
            if isinstance(node.op, ast.FloorDiv) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left // right
            if isinstance(node.op, ast.Mod) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left % right
            if isinstance(node.op, ast.Pow) and isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left**right
            raise invalid_expression_error()
        if isinstance(node, ast.NamedExpr):
            if sigils is None:
                raise invalid_expression_error()
            if not isinstance(node.target, ast.Name):
                raise invalid_expression_error()
            key = " ".join(node.target.id.split())
            if not key:
                raise invalid_expression_error()
            value = eval_node(node.value)
            sigils[key] = str(value)
            return value
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and len(node.comparators) == 1:
            left = eval_node(node.left)
            right = eval_node(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.Lt):
                return left < right
            if isinstance(op, ast.LtE):
                return left <= right
            if isinstance(op, ast.Gt):
                return left > right
            if isinstance(op, ast.GtE):
                return left >= right
            if isinstance(op, ast.Eq):
                return left == right
            if isinstance(op, ast.NotEq):
                return left != right
            raise invalid_expression_error()
        raise invalid_expression_error()

    try:
        tree = ast.parse(normalized_expression, mode="eval")
        return eval_node(tree)
    except ParseError:
        raise
    except Exception as exc:
        raise invalid_expression_error() from exc


def resolve_expression(
    expression: str,
    line_no: int,
    allow_file_reference: bool = False,
    sigils: dict[str, str] | None = None,
) -> str:
    """Evaluate an expression and convert the result into a label string."""

    if BARE_LABEL_PATTERN.match(expression):
        return _normalize_label_identifier(expression)

    if allow_file_reference and FILE_REFERENCE_PATTERN.match(expression):
        return expression

    resolved = str(_safe_eval_value(expression, line_no, sigils=sigils))
    if allow_file_reference and FILE_REFERENCE_PATTERN.match(resolved):
        return resolved
    return _normalize_label_identifier(resolved)


def _split_goto_expressions(expression: str) -> list[str]:
    """Split goto expressions by commas and standalone `and`."""

    parts = [segment.strip() for segment in re.split(r",|\band\b", expression, flags=re.IGNORECASE)]
    cleaned = [part for part in parts if part]
    if not cleaned:
        raise ParseError("Invalid goto target list.")
    return cleaned


def _extract_modifiers_and_text(prefix_text: str) -> tuple[str, str | None, int, bool]:
    """Extract plain output text, unless decision text, not count, and please modifier."""

    unless_match = re.search(r"\bunless\b", prefix_text, re.IGNORECASE)
    plain_text = prefix_text
    decision_text = None
    if unless_match is not None:
        plain_text = prefix_text[: unless_match.start()].strip()
        decision_text = prefix_text[unless_match.end() :].strip() or None

    words = re.findall(r"\b\w+\b", prefix_text.lower())
    not_count = sum(1 for w in words if w == "not")
    please = "please" in words
    return plain_text.strip(), decision_text, not_count, please


def parse_program(source: str) -> list[ParsedLine]:
    """Parse source code into executable lines."""

    parsed: list[ParsedLine] = []
    for line_no, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.endswith(";"):
            line = line[:-1].rstrip()
            if not line:
                continue

        if line.endswith(":"):
            label = resolve_expression(line[:-1].strip(), line_no)
            parsed.append(ParsedLine(index=line_no, raw=raw_line, label=label))
            continue

        goto_statement = _match_goto_statement(line)
        if goto_statement is None:
            parsed.append(ParsedLine(index=line_no, raw=raw_line, output_text=line))
            continue

        prefix_text, expression = goto_statement
        output_text, decision_text, not_count, please = _extract_modifiers_and_text(prefix_text)
        target: tuple[str, ...] | None = None
        if expression is not None:
            target = tuple(_split_goto_expressions(expression))

        parsed.append(
            ParsedLine(
                index=line_no,
                raw=raw_line,
                is_goto=True,
                output_text=output_text or None,
                decision_text=decision_text,
                goto_targets=target,
                not_count=not_count,
                please=please,
            )
        )

    return parsed
