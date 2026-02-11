"""Goto Language package.

This package implements a tiny language where the only statement type is
``goto <label>`` and labels are declared as ``<label>:``.
"""

from .interpreter import ExecutionResult, Interpreter, Program, Statement
from .parser import ParseError, parse_program

__all__ = [
    "ExecutionResult",
    "Interpreter",
    "ParseError",
    "Program",
    "Statement",
    "parse_program",
]
