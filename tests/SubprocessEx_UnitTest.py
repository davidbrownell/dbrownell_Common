# ----------------------------------------------------------------------
# |
# |  SubprocessEx_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-25 13:17:39
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for SubprocessEx.py."""

import re
import textwrap

import pytest
from unittest.mock import MagicMock as Mock

from dbrownell_Common.SubprocessEx import *
from dbrownell_Common.Streams.Capabilities import Capabilities


# ----------------------------------------------------------------------
class TestRun:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        result = Run("echo Hello World!")

        assert result.returncode == 0
        assert result.output == "Hello World!\n"

        try:
            result.RaiseOnError()
        except Exception:
            assert False, "An exception should not have been raised"

    # ----------------------------------------------------------------------
    def test_Error(self):
        result = Run("this_command_does_not_exist")

        assert result.returncode != 0
        assert result.output != ""

        with pytest.raises(
            Exception,
            match=re.compile(
                textwrap.dedent(
                    """\
                    Command Line
                    ------------
                    this_command_does_not_exist

                    Output
                    ------
                    .+
                    """,
                ),
                re.DOTALL | re.MULTILINE,
            ),
        ):
            result.RaiseOnError()

    # ----------------------------------------------------------------------
    class TestColors:
        command_line = '''python -c "import sys; from dbrownell_Common.TextwrapEx import CreateErrorText; from dbrownell_Common.Streams.Capabilities import Capabilities; print(CreateErrorText('Hello!', supports_colors=Capabilities.Get(sys.stdout).supports_colors));"'''

        # ----------------------------------------------------------------------
        def test_ColorsTrue(self):
            result = Run(self.command_line, supports_colors=True)

            assert result.returncode == 0
            assert result.output == "\x1b[31;1mERROR:\x1b[0m Hello!\n"

        # ----------------------------------------------------------------------
        def test_ColorsFalse(self):
            result = Run(self.command_line, supports_colors=False)

            assert result.returncode == 0
            assert result.output == "ERROR: Hello!\n"

    # ----------------------------------------------------------------------
    def test_Unicode(self):
        result = Run('''python -c "print('🔥')"''')

        assert result.returncode == 0
        assert result.output == "🔥\n"

    # ----------------------------------------------------------------------
    def test_Env(self):
        if os.name.lower() == "nt":
            command_line = "echo _%MY_TEST_VAR%_"
            expected_not_set_output = "_%MY_TEST_VAR%_\n"
        else:
            command_line = "echo _${MY_TEST_VAR}_"
            expected_not_set_output = "__\n"

        # Var not set
        result = Run(command_line)

        assert result.returncode == 0
        assert result.output == expected_not_set_output

        # Var set
        result = Run(
            command_line,
            env={
                "MY_TEST_VAR": "The value",
            },
        )

        # assert result.returncode == 0
        assert result.output == "_The value_\n"


# ----------------------------------------------------------------------
class TestStream:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        mock = Mock()

        result = Stream("echo Hello World", mock)

        assert result == 0
        assert mock.write.call_count == len("Hello World\n")

    # ----------------------------------------------------------------------
    def test_LineDelimited(self):
        mock = Mock()

        result = Stream("echo Hello World", mock, line_delimited_output=True)

        assert result == 0

        assert mock.write.call_count == 2
        assert mock.write.call_args_list[0].args[0] == "Hello World\n"
        assert mock.write.call_args_list[1].args[0] == "\n"

        assert mock.flush.call_count == 1

    # ----------------------------------------------------------------------
    def test_LineDelimitedPartialContent(self):
        mock = Mock()

        result = Stream(
            '''python -c "import sys; sys.stdout.write('Hello\\nWorld')"''',
            mock,
            line_delimited_output=True,
        )

        assert result == 0

        assert mock.write.call_count == 2
        assert mock.write.call_args_list[0].args[0] == "Hello\n"
        assert mock.write.call_args_list[1].args[0] == "World\n"

        assert mock.flush.call_count == 1

    # ----------------------------------------------------------------------
    def test_Stdin(self):
        mock = Mock()

        result = Stream(
            '''python -c "import sys; sys.stdout.write(sys.stdin.read())"''',
            mock,
            stdin="Hello!",
            line_delimited_output=True,
        )

        assert result == 0

        assert mock.write.call_count == 1
        assert mock.write.call_args_list[0].args[0] == "Hello!\n"

        assert mock.flush.call_count == 1

    # ----------------------------------------------------------------------
    def test_AsciiEscape(self):
        mock = Mock()

        result = Stream('''python -c "print('\x1b[31;1mERROR:\x1b[0m Hello!')"''', mock)

        assert result == 0

        assert mock.write.call_count == 16
        assert mock.write.call_args_list[0].args[0] == "\x1b[31;1m"
        assert mock.write.call_args_list[1 + len("ERROR:")].args[0] == "\x1b[0m"
        assert mock.write.call_args_list[15].args[0] == "\n"

        assert mock.flush.call_count == 1

    # ----------------------------------------------------------------------
    def test_Unicode8(self):
        mock = Mock()

        result = Stream('''python -c "import sys; sys.stdout.write('🔥')"''', mock)

        assert result == 0

        assert mock.write.call_count == 1
        assert mock.write.call_args_list[0].args[0] == "🔥"

        assert mock.flush.call_count == 1

    # ----------------------------------------------------------------------
    def test_MultiByte(self):
        mock = Mock()

        result = Stream('''python -c "print('\u2082')"''', mock)

        assert result == 0

        assert mock.write.call_count == 2
        assert mock.write.call_args_list[0].args[0] == "₂"
        assert mock.write.call_args_list[1].args[0] == "\n"

        assert mock.flush.call_count == 1
