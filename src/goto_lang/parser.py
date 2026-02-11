"""Parser for the goto-only language."""

from __future__ import annotations

from dataclasses import dataclass
import re


LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ParseError(ValueError):
    """Raised when source code is not valid goto language code."""


@dataclass(frozen=True)
class ParsedLine:
    """Represents one parsed line in the source program."""

    index: int
    raw: str
    label: str | None = None
    goto_target: str | None = None


def _validate_label(name: str, line_no: int) -> None:
    """Validate a label name and raise :class:`ParseError` when invalid."""

    if not LABEL_PATTERN.match(name):
        raise ParseError(f"Invalid label name '{name}' on line {line_no}.")


def parse_program(source: str) -> list[ParsedLine]:
    """Parse source code into normalized program lines.

    Blank lines and comments beginning with ``#`` are ignored.
    A non-empty line can be either:

    - ``label:``
    - ``goto label``

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
            label = line[:-1].strip()
            _validate_label(label, line_no)
            parsed.append(ParsedLine(index=line_no, raw=raw_line, label=label))
            continue

        if line.startswith("goto "):
            target = line[5:].strip()
            _validate_label(target, line_no)
            parsed.append(
                ParsedLine(index=line_no, raw=raw_line, goto_target=target)
            )
            continue

        raise ParseError(
            f"Unexpected statement on line {line_no}: '{raw_line}'. "
            "Only labels and goto statements are allowed."
        )

    return parsed
