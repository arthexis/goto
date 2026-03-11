"""CI coverage tests for curated goto example programs."""

from dataclasses import dataclass, field
from pathlib import Path

from goto_lang.interpreter import DecisionProvider, Interpreter


@dataclass
class StaticProvider(DecisionProvider):
    """Deterministic answers for CI program execution."""

    yes_no_answers: list[bool]
    values: dict[str, str]
    asked_yes_no: list[str] = field(default_factory=list)
    asked_values: list[str] = field(default_factory=list)

    def ask_yes_no(self, prompt: str) -> bool:
        """Return next configured yes/no answer."""

        self.asked_yes_no.append(prompt)
        return self.yes_no_answers.pop(0)

    def ask_value(self, context: str) -> str:
        """Return configured sigil value."""

        self.asked_values.append(context)
        return self.values[context]


def test_ci_example_programs_compile() -> None:
    """All curated CI example programs compile successfully."""

    interpreter = Interpreter()
    example_dir = Path("examples/ci")

    for source_path in sorted(example_dir.rglob("*.goto")):
        program = interpreter.compile_file(source_path)
        assert program.statements


def test_ci_warmup_program_runs(capsys) -> None:
    """Warmup script runs and prints expected output."""

    provider = StaticProvider(yes_no_answers=[True], values={})

    result = Interpreter().run_file("examples/ci/01_warmup.goto", provider=provider)

    assert result.terminated is True
    assert capsys.readouterr().out.splitlines() == [
        "Welcome to the jump gauntlet!",
        "Warmup complete.",
    ]


def test_ci_polite_rebellion_respects_not_and_please(capsys) -> None:
    """Polite rebellion script skips detour after confirmation."""

    provider = StaticProvider(yes_no_answers=[True, True, True], values={})

    result = Interpreter().run_file("examples/ci/03_polite_rebellion.goto", provider=provider)

    assert result.terminated is True
    assert capsys.readouterr().out.splitlines() == [
        "not please",
        "Stayed on the main quest.",
        "Politeness protocol complete.",
    ]


def test_ci_sigil_quest_resolves_runtime_values(capsys) -> None:
    """Sigil quest script resolves sigils in output and goto targets."""

    provider = StaticProvider(yes_no_answers=[True, True], values={"hero": "Rin", "door": "moon"})

    result = Interpreter().run_file("examples/ci/04_sigil_quest.goto", provider=provider)

    assert result.terminated is True
    assert provider.asked_values == ["hero", "door"]
    assert capsys.readouterr().out.splitlines() == [
        "Greetings, Rin!",
        "You chose moonlight.",
        "Quest logged for Rin.",
    ]


def test_ci_cross_file_maze_runs(capsys) -> None:
    """Cross-file maze script jumps into a sibling program."""

    provider = StaticProvider(yes_no_answers=[True, True], values={})

    result = Interpreter().run_file("examples/ci/maze/entry.goto", provider=provider)

    assert result.terminated is True
    assert capsys.readouterr().out.splitlines() == [
        "Packing snacks.",
        "Entered the side chamber.",
        "Treasure found.",
    ]
