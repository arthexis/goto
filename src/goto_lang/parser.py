"""Parser for the goto-only language."""

from __future__ import annotations

from dataclasses import dataclass
import re


BARE_LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
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


def _resolve_expression(expression: str, line_no: int) -> str:
    """Evaluate an expression and convert the result into a label string.

    Args:
        expression: Expression used in a label declaration or goto target.
        line_no: Source line number used for parse error messaging.

    Returns:
        str: Stringified expression result used as the normalized label.

    Raises:
        ParseError: If the expression cannot be evaluated.
    """

    if BARE_LABEL_PATTERN.match(expression):
        return expression

    try:
        return str(eval(expression))
    except Exception as exc:  # pragma: no cover
        raise ParseError(
            f"Invalid expression on line {line_no}: '{expression}'."
        ) from exc


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
            label = _resolve_expression(expression, line_no)
            parsed.append(ParsedLine(index=line_no, raw=raw_line, label=label))
            continue

        goto_match = GOTO_STATEMENT_PATTERN.match(line)
        if goto_match:
            prefix_words = goto_match.group("prefix").lower().split()
            expression = goto_match.group("expression").strip()
            target = _resolve_expression(expression, line_no)
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
            f"Unexpected statement on line {line_no}: '{raw_line}'. "
            "Only labels and goto statements are allowed."
        )

    return parsed
