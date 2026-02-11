# goto-lang

`goto-lang` is an intentionally tiny programming language where the only two constructs are:

1. Labels: `name:`
2. Jumps: `goto name`

That is enough to express loops and state transitions.

## Syntax

- Blank lines are ignored.
- Lines starting with `#` are comments.
- `label_name:` declares a label.
- `goto label_name` jumps to a label.

Identifiers must start with a letter or underscore, followed by letters, numbers, or underscores.

## Example

```txt
start:
  goto loop

loop:
  goto loop
```

Run with a maximum step limit so infinite loops are detected:

```bash
goto-lang example.goto --max-steps 20
```

## CLI

```bash
goto-lang program.goto             # run program and print trace
goto-lang program.goto --print-normalized
```

## Development

```bash
python -m pytest
```
