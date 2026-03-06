"""Interpreter for the goto-only language."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Protocol
from urllib import request

from .parser import FILE_REFERENCE_PATTERN, ParseError, ParsedLine, parse_program


@dataclass(frozen=True)
class Statement:
    """Executable representation of a source line."""

    kind: str
    argument: tuple[str, ...] | None
    source_line: int
    output_text: str | None = None
    decision_text: str | None = None
    not_count: int = 0
    please: bool = False


@dataclass(frozen=True)
class Program:
    """Compiled goto language program."""

    statements: list[Statement]
    labels: dict[str, int]
    label_stack: tuple[str, ...]


@dataclass(frozen=True)
class TraceEvent:
    """One executed source location in an execution trace."""

    file: str
    line: int


@dataclass(frozen=True)
class ExecutionResult:
    """Result of a program execution."""

    terminated: bool
    steps: int
    instruction_pointer: int
    reason: str
    trace: list[TraceEvent]


class DecisionProvider(Protocol):
    """Provider used for yes/no and sigil prompts."""

    def ask_yes_no(self, prompt: str) -> bool:
        """Return True for yes and False for no."""

    def ask_value(self, context: str) -> str:
        """Return a value for a sigil context."""


@dataclass
class InteractiveProvider:
    """Prompt the user directly via stdin/stdout."""

    def ask_yes_no(self, prompt: str) -> bool:
        """Request a yes/no answer where ENTER defaults to yes."""

        print(f"{prompt} [Y/n]: ", end="", flush=True)
        answer = input().strip().lower()
        return answer in {"", "y", "yes"}

    def ask_value(self, context: str) -> str:
        """Request a text value from the user for a sigil."""

        print(f"Fill [{context}]: ", end="", flush=True)
        return input().strip()


@dataclass
class LLMProvider:
    """Use a remote or local LLM endpoint for decisions and values."""

    model: str
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1"

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send one chat-completions request and return the model text."""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }
        req = request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        with request.urlopen(req, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"].strip()

    def ask_yes_no(self, prompt: str) -> bool:
        """Ask the LLM for strict yes/no output."""

        answer = self._chat(
            "Respond with exactly YES or NO.",
            prompt,
        ).upper()
        return answer.startswith("Y")

    def ask_value(self, context: str) -> str:
        """Ask the LLM to provide a concise value for one sigil."""

        return self._chat("Provide a short plain-text answer.", context)


@dataclass
class ThreadState:
    """Mutable execution state for one runtime thread."""

    program: Program
    instruction_pointer: int
    current_path: Path | None
    label_stack: list[str]


@dataclass
class RuntimeContext:
    """Runtime shared context including sigil memory."""

    provider: DecisionProvider
    sigils: dict[str, str] = field(default_factory=dict)


class Interpreter:
    """Compiler and runtime for the goto language."""

    SIGIL_PATTERN = re.compile(r"\[([^\[\]]+)\]")

    def compile(self, source: str) -> Program:
        """Compile source code into a :class:`Program`."""

        parsed = parse_program(source)
        statements: list[Statement] = []
        labels: dict[str, int] = {}

        for line in parsed:
            self._append_statement(line, statements, labels)

        self._validate_goto_targets(statements, labels)
        return Program(statements=statements, labels=labels, label_stack=())

    def run(self, source: str, max_steps: int = 10_000, provider: DecisionProvider | None = None) -> ExecutionResult:
        """Execute source code with a step limit."""

        runtime_provider = provider or InteractiveProvider()
        program = self.compile(source)
        return self.run_program(program, max_steps=max_steps, provider=runtime_provider)

    def run_file(
        self,
        source_path: Path | str,
        max_steps: int = 10_000,
        provider: DecisionProvider | None = None,
    ) -> ExecutionResult:
        """Execute a program loaded from disk."""

        path = Path(source_path).resolve()
        source = path.read_text(encoding="utf-8")
        runtime_provider = provider or InteractiveProvider()
        program = self.compile(source)
        return self._run_with_context(program, max_steps=max_steps, current_path=path, context=RuntimeContext(provider=runtime_provider))

    def compile_file(self, source_path: Path | str) -> Program:
        """Compile a program loaded from disk."""

        path = Path(source_path).resolve()
        return self.compile(path.read_text(encoding="utf-8"))

    def run_program(self, program: Program, max_steps: int = 10_000, provider: DecisionProvider | None = None) -> ExecutionResult:
        """Execute a precompiled :class:`Program`."""

        runtime_provider = provider or InteractiveProvider()
        return self._run_with_context(program, max_steps=max_steps, context=RuntimeContext(provider=runtime_provider))

    def _interpolate_sigils(self, text: str, context: RuntimeContext) -> str:
        """Replace [sigils] with remembered or newly prompted values."""

        def replacer(match: re.Match[str]) -> str:
            key = " ".join(match.group(1).split())
            if key not in context.sigils:
                context.sigils[key] = context.provider.ask_value(key)
            return context.sigils[key]

        return self.SIGIL_PATTERN.sub(replacer, text)

    def _run_with_context(
        self,
        program: Program,
        max_steps: int,
        context: RuntimeContext,
        current_path: Path | None = None,
    ) -> ExecutionResult:
        """Execute a program, optionally allowing file-based goto targets."""

        last_instruction_pointer = 0
        steps = 0
        trace: list[TraceEvent] = []
        default_trace_file = str(current_path) if current_path is not None else "<memory>"
        threads: list[ThreadState] = [
            ThreadState(program=program, instruction_pointer=0, current_path=current_path, label_stack=list(program.label_stack))
        ]

        while threads:
            next_threads: list[ThreadState] = []
            for thread in threads:
                if steps >= max_steps:
                    return ExecutionResult(False, steps, thread.instruction_pointer, f"step limit reached ({max_steps})", trace)
                if thread.instruction_pointer >= len(thread.program.statements):
                    continue

                statement = thread.program.statements[thread.instruction_pointer]
                trace_file = str(thread.current_path) if thread.current_path is not None else default_trace_file
                trace.append(TraceEvent(file=trace_file, line=statement.source_line))
                last_instruction_pointer = thread.instruction_pointer
                steps += 1

                if statement.kind == "label":
                    assert statement.argument is not None
                    thread.label_stack.append(statement.argument[0])
                    thread.instruction_pointer += 1
                    next_threads.append(thread)
                    continue

                if statement.kind == "text":
                    if statement.output_text:
                        print(self._interpolate_sigils(statement.output_text, context))
                    thread.instruction_pointer += 1
                    next_threads.append(thread)
                    continue

                if statement.kind != "goto":
                    raise RuntimeError(f"Unknown statement kind '{statement.kind}'.")

                if statement.output_text:
                    print(self._interpolate_sigils(statement.output_text, context))

                question = statement.decision_text or f"Perform goto at line {statement.source_line}?"
                resolved_question = self._interpolate_sigils(question, context)
                should_jump = context.provider.ask_yes_no(resolved_question)

                if statement.not_count % 2 == 1:
                    should_jump = not should_jump

                if statement.please and not should_jump:
                    should_jump = not context.provider.ask_yes_no(
                        self._interpolate_sigils("PLEASE confirm skipping goto.", context)
                    )

                if not should_jump:
                    thread.instruction_pointer += 1
                    next_threads.append(thread)
                    continue

                targets = statement.argument
                if targets is None:
                    if not thread.label_stack:
                        raise ParseError(
                            f"Cannot execute targetless goto on line {statement.source_line} before any labels are encountered."
                        )
                    thread.label_stack.pop()
                    target = thread.label_stack[-1] if thread.label_stack else None
                    if target is None:
                        thread.instruction_pointer += 1
                        next_threads.append(thread)
                        continue
                    targets = (target,)

                for target in targets:
                    next_threads.append(self._jump_to_target(thread, target))

            threads = [thread for thread in next_threads if thread.instruction_pointer < len(thread.program.statements)]

        return ExecutionResult(True, steps, last_instruction_pointer, "completed", trace)

    def _jump_to_target(self, thread: ThreadState, target: str) -> ThreadState:
        """Return a thread state positioned at the target label."""

        current_path = thread.current_path
        external_target = self._parse_external_target(target)
        if external_target is not None:
            if current_path is None:
                raise ParseError("File-based goto requires execution from a file path.")
            new_program, new_ip, new_path = self._load_external_program(current_path, external_target[0], external_target[1])
            return type(thread)(program=new_program, instruction_pointer=new_ip, current_path=new_path, label_stack=list(thread.label_stack))

        return type(thread)(program=thread.program, instruction_pointer=thread.program.labels[target], current_path=current_path, label_stack=list(thread.label_stack))

    @staticmethod
    def _parse_external_target(target: str) -> tuple[str, str | None] | None:
        """Parse `<file>.goto` or `<file>.goto:<label>` goto targets."""

        match = FILE_REFERENCE_PATTERN.match(target)
        if not match:
            return None
        return match.group("file"), match.group("label")

    def _load_external_program(self, current_path: Path, file_target: str, label_target: str | None) -> tuple[Program, int, Path]:
        """Load a target file and compute the target instruction pointer."""

        target_path = (current_path.parent / file_target).resolve()
        target_program = self.compile(target_path.read_text(encoding="utf-8"))

        if label_target is None:
            return target_program, 0, target_path
        if label_target not in target_program.labels:
            raise ParseError(f"Unknown label '{label_target}' referenced in file '{file_target}'.")
        return target_program, target_program.labels[label_target], target_path

    @staticmethod
    def _append_statement(line: ParsedLine, statements: list[Statement], labels: dict[str, int]) -> None:
        """Append one parsed line into compiled statements."""

        if line.label is not None:
            if line.label in labels:
                raise ParseError(f"Duplicate label '{line.label}' found on line {line.index}.")
            labels[line.label] = len(statements)
            statements.append(Statement(kind="label", argument=(line.label,), source_line=line.index))
            return

        if line.is_goto:
            statements.append(
                Statement(
                    kind="goto",
                    argument=line.goto_targets,
                    source_line=line.index,
                    output_text=line.output_text,
                    decision_text=line.decision_text,
                    not_count=line.not_count,
                    please=line.please,
                )
            )
            return

        statements.append(Statement(kind="text", argument=None, source_line=line.index, output_text=line.output_text))

    @staticmethod
    def _validate_goto_targets(statements: list[Statement], labels: dict[str, int]) -> None:
        """Ensure each goto instruction references a known local label or file target."""

        for statement in statements:
            if statement.kind != "goto" or statement.argument is None:
                continue
            for target in statement.argument:
                if target in labels:
                    continue
                if Interpreter._parse_external_target(target) is not None:
                    continue
                raise ParseError(f"Unknown label '{target}' referenced on line {statement.source_line}.")
