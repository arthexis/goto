"""Tests for goto language parsing."""

import pytest

from goto_lang.parser import ParseError, parse_program


def test_parse_valid_program() -> None:
    """Parser accepts labels and goto statements."""

    parsed = parse_program("start:\ngoto start\n")
    assert len(parsed) == 2
    assert parsed[0].label == "start"
    assert parsed[1].goto_target == "start"


def test_parse_unknown_statement_as_noop() -> None:
    """Parser accepts unknown statements as inert no-op lines."""

    parsed = parse_program("print hello")
    assert len(parsed) == 1
    assert parsed[0].is_goto is False
    assert parsed[0].label is None


def test_parse_label_expressions() -> None:
    """Parser resolves string concatenation and stringifies label values."""

    parsed = parse_program("\"a\" + \"b\":\n")
    assert parsed[0].label == "ab"


def test_parse_numeric_expressions() -> None:
    """Parser resolves numeric arithmetic expressions."""

    parsed = parse_program("start:\ngoto 10 * 2 + 5\n")
    assert parsed[1].goto_target == "25"


def test_parse_case_insensitive_goto_and_go_to() -> None:
    """Parser accepts goto spellings in any case, including 'go to'."""

    parsed = parse_program("start:\nGo To start\nGOTO start\n")
    assert parsed[1].goto_target == "start"
    assert parsed[2].goto_target == "start"


def test_parse_prefix_modifiers_update_jump_behavior() -> None:
    """Prefix modifiers are accepted and odd `not` disables a jump."""

    parsed = parse_program("start:\nplease do not goto start\ndo NOT not go to start\n")
    assert parsed[1].should_jump is False
    assert parsed[2].should_jump is True






def test_parse_allows_arbitrary_prefix_keywords_before_goto() -> None:
    """Parser ignores unrecognized prefix words before goto."""

    parsed = parse_program("start:\nquantum frobnicate not goto start\n")
    assert parsed[1].goto_target == "start"
    assert parsed[1].should_jump is False


def test_parse_unless_prefix_controls_jump_behavior() -> None:
    """Unless suppresses jump only when its expression evaluates to True."""

    parsed = parse_program("start:\nunless True goto start\nunless False goto start\n")
    assert parsed[1].should_jump is False
    assert parsed[2].should_jump is True




def test_unless_expression_with_goto_text_is_not_misparsed_as_goto() -> None:
    """Standalone unless expressions may contain the word `goto` in strings."""

    parsed = parse_program(
        'start:\nunless "goto x" ~= "y"\ngoto start\n'
    )

    assert parsed[1].is_goto is True
    assert parsed[1].goto_target == "start"
    assert parsed[1].should_jump is True

def test_parse_unless_with_more_or_less_operator() -> None:
    """Unless can use `~=` for approximate equality checks."""

    parsed = parse_program(
        'start:\nunless user("Loop forever?") ~= Negative goto start\n',
        user_function=lambda _prompt: "negative",
    )
    assert parsed[1].should_jump is False


def test_parse_unless_with_less_is_more_operator() -> None:
    """Unless can use `=~` for the inverse approximate comparison."""

    parsed = parse_program("start:\nunless 1 =~ 1 goto start\n")
    assert parsed[1].should_jump is True


def test_parse_not_with_unless_toggles_jump_behavior() -> None:
    """Not still toggles jump behavior when combined with unless."""

    parsed = parse_program("start:\nnot unless True goto start\nnot unless False goto start\n")
    assert parsed[1].should_jump is True
    assert parsed[2].should_jump is False


def test_parse_file_targets_with_or_without_label() -> None:
    """Parser accepts `goto file.goto` and `goto file.goto:label` targets."""

    parsed = parse_program("start:\ngoto next.goto\ngoto next.goto:entry\n")
    assert parsed[1].goto_target == "next.goto"
    assert parsed[2].goto_target == "next.goto:entry"


def test_parse_file_and_label_with_space_separator() -> None:
    """Parser normalizes `goto file.goto label` into colon form."""

    parsed = parse_program("start:\ngoto next.goto entry\n")
    assert parsed[1].goto_target == "next.goto:entry"


def test_reject_invalid_expression() -> None:
    """Parser raises when expressions cannot be evaluated."""

    with pytest.raises(ParseError, match="Invalid expression"):
        parse_program("goto unknown +")


def test_reject_dangerous_expression_calls() -> None:
    """Parser rejects expressions that attempt to execute code via calls."""

    with pytest.raises(ParseError, match="Invalid expression"):
        parse_program('goto __import__("os").system("echo hacked")')


def test_parse_targetless_goto() -> None:
    """Parser accepts goto without a target expression."""

    parsed = parse_program("entry:\ngoto\n")
    assert parsed[1].is_goto is True
    assert parsed[1].goto_target is None


def test_parse_user_function_is_supported_in_goto_expression() -> None:
    """Parser can resolve goto expressions that call the built-in user function."""

    parsed = parse_program(
        'entry:\ngoto user("name? ")\n',
        user_function=lambda prompt: "done" if prompt == "name? " else "",
    )
    assert parsed[1].goto_target == "done"


def test_parse_user_function_rejects_keyword_arguments() -> None:
    """Parser rejects user() calls that use keyword arguments."""

    with pytest.raises(ParseError, match="Invalid expression"):
        parse_program('goto user(prompt="x")', user_function=lambda prompt: prompt)


def test_parse_user_function_without_args_uses_default_prompt() -> None:
    """Parser provides a friendly default prompt for bare user() calls."""

    prompts: list[str] = []

    def fake_user(prompt: str) -> str:
        prompts.append(prompt)
        return "destination"

    parsed = parse_program("entry:\ngoto user()\n", user_function=fake_user)

    assert prompts == ["Which label would you like to go to? "]
    assert parsed[1].goto_target == "destination"


def test_parse_user_function_normalizes_whitespace_and_case() -> None:
    """Parser allows generous user input by normalizing case and whitespace."""

    parsed = parse_program(
        "entry:\nTARGET:\ngoto user()\n",
        user_function=lambda _prompt: "  tArGeT\n",
    )

    assert parsed[2].goto_target == "target"
