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


def test_runtime_resolves_sigil_in_goto_expression() -> None:
    """Sigils can be acquired and reused while resolving goto expressions."""

    source = "start:\ngoto [n] + 1\n2:\n"
    provider = FakeProvider(yes_no_answers=[True], values={"n": "1"})

    result = Interpreter().run(source, provider=provider)

    assert result.terminated is True
    assert provider.asked_values == ["n"]


def test_runtime_goto_collapse_keeps_winner_threads(capsys) -> None:
    """Successful goto collapse replaces other running threads."""

    source = "start:\ngoto left, right\nleft:\nL\ngoto done\nright:\nR\ndone:\n"
    provider = FakeProvider(yes_no_answers=[True, True], values={})

    Interpreter().run(source, provider=provider)

    assert capsys.readouterr().out.splitlines() == ["L", "R"]


def test_runtime_unknown_target_prints_and_does_not_collapse(capsys) -> None:
    """Unknown goto targets emit output and let sibling threads continue."""

    source = "start:\ngoto missing, done\ndone:\nfinished\n"
    provider = FakeProvider(yes_no_answers=[True], values={})

    Interpreter().run(source, provider=provider)

    assert capsys.readouterr().out.splitlines() == ["missing", "finished"]


def test_runtime_walrus_assigns_sigil_during_goto_resolution(capsys) -> None:
    """Walrus assignment can mutate sigils while evaluating goto expressions."""

    source = "start:\ngoto (welcome := `Hello [name]!`)\nHello [welcome]\n"
    provider = FakeProvider(yes_no_answers=[True], values={"name": "Ada"})

    Interpreter().run(source, provider=provider)

    assert capsys.readouterr().out.splitlines() == ["hello ada!", "Hello Hello Ada!"]


def test_runtime_walrus_assignment_is_expression_only(capsys) -> None:
    """A bare walrus line stays plain text and does not mutate sigils."""

    source = "welcome := `Hello [name]!`\nHello [welcome]\n"
    provider = FakeProvider(yes_no_answers=[], values={"name": "Ada", "welcome": "Fallback"})

    Interpreter().run(source, provider=provider)

    assert provider.asked_values == ["name", "welcome"]
    assert capsys.readouterr().out.splitlines() == ["welcome := `Hello Ada!`", "Hello Fallback"]
