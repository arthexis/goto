"""Tests for goto language execution."""

from dataclasses import dataclass, field

from goto_lang.interpreter import DecisionProvider, Interpreter


@dataclass
class FakeProvider(DecisionProvider):
    """Deterministic provider for runtime tests."""

    yes_no_answers: list[bool]
    values: dict[str, str]
    asked_yes_no: list[str] = field(default_factory=list)
    asked_values: list[str] = field(default_factory=list)

    def ask_yes_no(self, prompt: str) -> bool:
        """Return the next configured yes/no answer."""

        self.asked_yes_no.append(prompt)
        return self.yes_no_answers.pop(0)

    def ask_value(self, context: str) -> str:
        """Return configured sigil value by context."""

        self.asked_values.append(context)
        return self.values[context]


def test_runtime_prints_text_and_uses_sigil_only_once(capsys) -> None:
    """Sigil values are cached and reused without re-asking."""

    source = "Hello [name]\nAgain [name]\n"
    provider = FakeProvider(yes_no_answers=[], values={"name": "Ada"})

    result = Interpreter().run(source, provider=provider)

    assert result.terminated is True
    assert provider.asked_values == ["name"]
    assert capsys.readouterr().out.splitlines() == ["Hello Ada", "Again Ada"]


def test_runtime_uses_unless_text_for_decision_and_jumps() -> None:
    """Text after unless is used for jump decision prompt."""

    source = "start:\nprint this unless jump now goto end\nmid\nend:\n"
    provider = FakeProvider(yes_no_answers=[True], values={})

    result = Interpreter().run(source, provider=provider)

    assert result.terminated is True
    assert provider.asked_yes_no == ["jump now"]


def test_runtime_not_negates_decision_and_please_reconfirms_skip() -> None:
    """`not` inverts decision and `please` requires skip reconfirmation."""

    source = "start:\nplease not goto end\nnext\nend:\n"
    provider = FakeProvider(yes_no_answers=[True, False], values={})

    Interpreter().run(source, provider=provider)

    assert provider.asked_yes_no[0].startswith("Perform goto")
    assert provider.asked_yes_no[1] == "PLEASE confirm skipping goto."
