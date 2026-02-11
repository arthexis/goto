# Goto Language

`goto-language` is a deliberately tiny programming language where the **only**
allowed constructs are:

- label definitions (`name:`)
- unconditional jumps (`goto name`)

It includes a parser, compiler/runtime, and CLI.

## Syntax

```text
start:
  goto loop
loop:
  goto loop
```

Rules:

1. Labels must match `[A-Za-z_][A-Za-z0-9_]*`.
2. `goto` targets must refer to an existing label.
3. Duplicate label definitions are not allowed.
4. Blank lines and lines beginning with `#` are ignored.

## Running

Install in editable mode:

```bash
pip install -e .
```

Run a program:

```bash
goto-lang examples/loop.goto --max-steps 20 --trace
```

Exit codes:

- `0`: program terminated by falling past the final statement.
- `1`: execution stopped due to step limit.
- `2`: parse/compile error.

## Design notes

Because the language has only labels and unconditional jumps, control flow is
explicit and there is no mutable state in the core language.
