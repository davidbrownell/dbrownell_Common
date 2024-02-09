# ----------------------------------------------------------------------
# |
# |  SubprocessEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-22 11:07:58
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Enhancements for the subprocess library."""

import copy
import os
import subprocess
import textwrap

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, cast, IO, Optional

from dbrownell_Common.ContextlibEx import ExitStack
from dbrownell_Common.Streams.Capabilities import Capabilities
from dbrownell_Common.Streams.StreamDecorator import TextWriterT


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
@dataclass
class RunResult:
    """Result of running a process."""

    # ----------------------------------------------------------------------
    returncode: int
    output: str

    error_command_line: Optional[str] = field(default=None)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.error_command_line is None or self.returncode != 0

    # ----------------------------------------------------------------------
    def RaiseOnError(self) -> None:
        if self.returncode != 0:
            assert self.error_command_line is not None

            raise Exception(
                textwrap.dedent(
                    """\
                    Command Line
                    ------------
                    {}

                    Output
                    ------
                    {}
                    """,
                ).format(
                    self.error_command_line.rstrip(),
                    self.output.rstrip(),
                ),
            )


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def Run(
    command_line: str,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    *,
    supports_colors: Optional[bool] = None,
) -> RunResult:
    """Runs a command line and returns the result."""

    env_args: dict[str, str] = {
        Capabilities.SIMULATE_TERMINAL_INTERACTIVE_ENV_VAR: "0",
        Capabilities.SIMULATE_TERMINAL_HEADLESS_ENV_VAR: "1",
    }

    if supports_colors is not None:
        env_args[Capabilities.SIMULATE_TERMINAL_COLORS_ENV_VAR] = "1" if supports_colors else "0"

    result = subprocess.run(
        command_line,
        check=False,
        cwd=cwd,
        env=_SetEnvironment(env, **env_args),
        shell=True,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
    )

    content = result.stdout.decode("utf-8")
    content = content.replace("\r\n", "\n")

    return RunResult(
        result.returncode,
        content,
        command_line if result.returncode != 0 else None,
    )


# ----------------------------------------------------------------------
# pylint: disable=too-many-locals
def Stream(
    command_line: str,
    stream: TextWriterT,
    cwd: Optional[Path] = None,
    env: Optional[dict[str, str]] = None,
    *,
    stdin: Optional[str] = None,
    line_delimited_output: bool = False,  # Set to True to buffer lines
    is_headless: Optional[bool] = None,
    is_interactive: Optional[bool] = None,
    supports_colors: Optional[bool] = None,
) -> int:
    output_func = cast(Callable[[str], None], stream.write)
    flush_func = stream.flush

    capabilities = Capabilities.Get(stream)

    # Windows seems to want to interpret '\r\n' as '\n\n' when output is redirected to a file. Work
    # around that issue as best as we can.
    convert_newlines = False

    if capabilities.is_interactive:
        # Windows must always convert newlines
        convert_newlines = os.name.lower() == "nt"

    if convert_newlines:
        newline_original_output_func = output_func

        # ----------------------------------------------------------------------
        def NewlineOutput(
            content: str,
        ) -> None:
            newline_original_output_func(content.replace("\r\n", "\n"))

        # ----------------------------------------------------------------------

        output_func = NewlineOutput

    if line_delimited_output:
        line_delimited_original_output_func = output_func
        line_delimited_original_flush_func = flush_func

        cached_content: list[str] = []

        # ----------------------------------------------------------------------
        def LineDelimitedOutput(
            content: str,
        ) -> None:
            if content.endswith("\n"):
                content = "{}{}".format("".join(cached_content), content)
                cached_content[:] = []

                line_delimited_original_output_func(content)
            else:
                cached_content.append(content)

        # ----------------------------------------------------------------------
        def LineDelimitedFlush() -> None:
            if cached_content:
                content = "".join(cached_content)
                cached_content[:] = []
            else:
                content = ""

            if not content.endswith("\n"):
                content += "\n"

            line_delimited_original_output_func(content)
            line_delimited_original_flush_func()

        # ----------------------------------------------------------------------

        output_func = LineDelimitedOutput
        flush_func = LineDelimitedFlush

    if is_headless is None:
        is_headless = capabilities.is_headless
    if is_interactive is None:
        is_interactive = capabilities.is_interactive
    if supports_colors is None:
        supports_colors = capabilities.supports_colors

    with subprocess.Popen(
        command_line,
        cwd=cwd,
        env=_SetEnvironment(
            env,
            **{
                "PYTHONUNBUFFERED": "1",
                "COLUMNS": capabilities.columns,
                Capabilities.SIMULATE_TERMINAL_HEADLESS_ENV_VAR: "1" if is_headless else "0",
                Capabilities.SIMULATE_TERMINAL_INTERACTIVE_ENV_VAR: "1" if is_interactive else "0",
                Capabilities.SIMULATE_TERMINAL_COLORS_ENV_VAR: "1" if supports_colors else "0",
            },
        ),
        shell=True,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ) as result:
        try:
            with ExitStack(flush_func):
                if stdin is not None:
                    assert result.stdin is not None

                    result.stdin.write(stdin.encode("utf-8"))
                    result.stdin.flush()
                    result.stdin.close()

                assert result.stdout is not None

                _ReadStateMachine.Execute(
                    result.stdout,
                    output_func,
                    convert_newlines=convert_newlines,
                )

                result_code = result.wait() or 0

        except IOError:  # pragma: no cover
            result_code = -1  # pragma: no cover

        return result_code


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
class _ReadStateMachine:
    """Reads content produced by a stream, ensuring and ansi escape sequences are properly grouped."""

    # ----------------------------------------------------------------------
    @classmethod
    def Execute(
        cls,
        input_stream: IO[bytes],
        output_func: Callable[[str], None],
        *,
        convert_newlines: bool,
    ) -> None:
        machine = cls(
            input_stream,
            convert_newlines=convert_newlines,
        )

        while True:
            if machine._buffered_input is not None:
                input_data = machine._buffered_input
                machine._buffered_input = None
            else:
                stream_data = machine._input_stream.read(1)
                if not stream_data:
                    break

                assert isinstance(stream_data, (str, bytes)), stream_data
                input_data = ord(stream_data)

            result = machine._process_func(input_data)
            if result is None:
                continue

            output_func(machine._ToString(result))

        if machine._buffered_output:
            output_func(machine._ToString(machine._buffered_output))

    # ----------------------------------------------------------------------
    def __init__(
        self,
        input_stream: IO[bytes],
        *,
        convert_newlines: bool,
    ):
        self._input_stream = input_stream
        self._convert_newlines = convert_newlines

        self._process_func: Callable[[int], Optional[list[int]]] = self._ProcessStandard

        self._buffered_input: Optional[int] = None
        self._buffered_output: list[int] = []

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    _a = ord("a")
    _z = ord("z")
    _A = ord("A")
    _Z = ord("Z")

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @classmethod
    def _IsAsciiLetter(
        cls,
        value: int,
    ) -> bool:
        return (cls._a <= value <= cls._z) or (cls._A <= value <= cls._Z)  # pragma: no cover

    # ----------------------------------------------------------------------
    def _IsNewlineish(
        self,
        value: int,
    ) -> bool:
        return self._convert_newlines and value in [
            10,  # '\r'
            13,  # '\n'
        ]

    # ----------------------------------------------------------------------
    @staticmethod
    def _IsEscape(
        value: int,
    ) -> bool:
        return value == 27

    # ----------------------------------------------------------------------
    @staticmethod
    def _ToString(
        value: list[int],
    ) -> str:
        if len(value) == 1:
            return chr(value[0])

        result = bytearray(value)

        # Attempt to decode as utf-8
        try:
            return result.decode("utf-8")
        except (UnicodeDecodeError, LookupError):  # pragma: no cover
            pass  # pragma: no cover

        raise Exception("The content '{}' could not be decoded.".format(result))  # pragma: no cover

    # ----------------------------------------------------------------------
    def _ProcessStandard(
        self,
        value: int,
    ) -> Optional[list[int]]:
        assert not self._buffered_output

        if self.__class__._IsEscape(value):  # pylint: disable=protected-access
            self._process_func = self._ProcessEscape
            self._buffered_output.append(value)

            return None

        if self._IsNewlineish(value):
            self._process_func = self._ProcessLineReset
            self._buffered_output.append(value)

            return None

        if value >> 6 == 0b11:
            # This is the first char of a multi-byte sequence
            self._process_func = self._ProcessMultiByte
            self._buffered_output.append(value)

            return None

        return [
            value,
        ]

    # ----------------------------------------------------------------------
    def _ProcessEscape(
        self,
        value: int,
    ) -> Optional[list[int]]:
        assert self._buffered_output
        self._buffered_output.append(value)

        if not self.__class__._IsAsciiLetter(value):  # pylint: disable=protected-access
            return None

        self._process_func = self._ProcessStandard

        return self._FlushBufferedOutput()

    # ----------------------------------------------------------------------
    def _ProcessLineReset(
        self,
        value: int,
    ) -> Optional[list[int]]:
        assert self._buffered_output

        if self._IsNewlineish(value):
            self._buffered_output.append(value)
            return None

        self._process_func = self._ProcessStandard

        assert self._buffered_input is None
        self._buffered_input = value

        return self._FlushBufferedOutput()

    # ----------------------------------------------------------------------
    def _ProcessMultiByte(
        self,
        value: int,
    ) -> Optional[list[int]]:
        assert self._buffered_output

        if value >> 6 == 0b10:
            # Continuation char
            self._buffered_output.append(value)
            return None

        self._process_func = self._ProcessStandard

        assert self._buffered_input is None
        self._buffered_input = value

        return self._FlushBufferedOutput()

    # ----------------------------------------------------------------------
    def _FlushBufferedOutput(self) -> Optional[list[int]]:
        assert self._buffered_output

        content = self._buffered_output
        self._buffered_output = []

        return content


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
def _SetEnvironment(
    env: Optional[dict[str, str]],
    **kwargs: Any,
) -> dict[str, str]:
    if env is None:
        env = copy.deepcopy(os.environ)  # type: ignore

    assert env is not None

    for k, v in kwargs.items():
        env[k] = str(v) if not isinstance(v, str) else v

    if "PYTHONIOENCODING" not in env:
        env["PYTHONIOENCODING"] = "utf-8"

    if "COLUMNS" not in env:
        env["COLUMNS"] = str(Capabilities.DEFAULT_COLUMNS)

    return env
