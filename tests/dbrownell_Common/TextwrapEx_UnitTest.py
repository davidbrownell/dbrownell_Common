# ----------------------------------------------------------------------
# |
# |  TextwrapEx_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-24 00:55:41
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Unit tests for TextwrapEx.py."""

import pytest

from dbrownell_Common.TextwrapEx import *


# ----------------------------------------------------------------------
def test_CreateErrorPrefix():
    assert CreateErrorPrefix(False) == "ERROR: "
    assert CreateErrorPrefix(True) == "\x1b[31;1mERROR:\x1b[0m "


# ----------------------------------------------------------------------
def test_WarningPrefix():
    assert CreateWarningPrefix(False) == "WARNING: "
    assert CreateWarningPrefix(True) == "\x1b[33;1mWARNING:\x1b[0m "


# ----------------------------------------------------------------------
def test_InfoPrefix():
    assert CreateInfoPrefix(False) == "INFO: "
    assert CreateInfoPrefix(True) == "\x1b[;7mINFO:\x1b[0m "


# ----------------------------------------------------------------------
def test_SuccessPrefix():
    assert CreateSuccessPrefix(False) == "SUCCESS: "
    assert CreateSuccessPrefix(True) == "\x1b[32;1mSUCCESS:\x1b[0m "


# ----------------------------------------------------------------------
def test_VerbosePrefix():
    assert CreateVerbosePrefix(False) == "VERBOSE: "
    assert CreateVerbosePrefix(True) == "\x1b[;7mVERBOSE:\x1b[0m "


# ----------------------------------------------------------------------
def test_DebugPrefix():
    assert CreateDebugPrefix(False) == "DEBUG: "
    assert CreateDebugPrefix(True) == "\x1b[37;1mDEBUG:\x1b[0m "


# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "test_data",
    [
        ("ERROR", "31;1", CreateErrorText),
        ("WARNING", "33;1", CreateWarningText),
        ("INFO", ";7", CreateInfoText),
        ("SUCCESS", "32;1", CreateSuccessText),
        ("VERBOSE", ";7", CreateVerboseText),
        ("DEBUG", "37;1", CreateDebugText),
    ],
    ids=["error", "warning", "info", "success", "verbose", "debug"],
)
class TestCreateDecoratedText(object):
    # ----------------------------------------------------------------------
    def test_Standard(self, test_data):
        assert test_data[2]("test") == "\x1b[{}m{}:\x1b[0m test".format(test_data[1], test_data[0])

    # ----------------------------------------------------------------------
    def test_NoColors(self, test_data):
        assert test_data[2]("test", supports_colors=False) == "{}: test".format(test_data[0])

    # ----------------------------------------------------------------------
    def test_Multiline(self, test_data):
        assert test_data[2](
            textwrap.dedent(
                """\

                Line1
                    Line2

                Line3

                """,
            ),
        ) == textwrap.dedent(
            """\

            \x1b[{color}m{prefix}:\x1b[0m Line1
            {whitespace}     Line2

            {whitespace} Line3

            """,
        ).format(
            color=test_data[1],
            prefix=test_data[0],
            whitespace=" " * (len(test_data[0]) + 1),
        )

    # ----------------------------------------------------------------------
    def test_MultilineDecorateAllLines(self, test_data):
        assert test_data[2](
            textwrap.dedent(
                """\

                Line1
                    Line2

                Line3

                """,
            ),
            decorate_every_line=True,
        ) == textwrap.dedent(
            """\

            \x1b[{color}m{prefix}:\x1b[0m Line1
            \x1b[{color}m{prefix}:\x1b[0m     Line2

            \x1b[{color}m{prefix}:\x1b[0m Line3

            """,
        ).format(
            color=test_data[1],
            prefix=test_data[0],
        )


# ----------------------------------------------------------------------
class TestCreateStatusText(object):
    # ----------------------------------------------------------------------
    def test_Standard(self):
        assert CreateStatusText(1, 2, 3) == "\x1b[32;1m1\x1b[0m succeeded, \x1b[31;1m2\x1b[0m failed, \x1b[33;1m3\x1b[0m warnings"

    # ----------------------------------------------------------------------
    def test_StandardNoColor(self):
        assert CreateStatusText(1, 2, 3, supports_colors=False) == "1 succeeded, 2 failed, 3 warnings"

    # ----------------------------------------------------------------------
    def test_Zeroes(self):
        assert CreateStatusText(0, 0, 0) == "0 succeeded, 0 failed, 0 warnings"

    # ----------------------------------------------------------------------
    def test_NoSucceeded(self):
        assert CreateStatusText(None, 2, 3) == "\x1b[31;1m2\x1b[0m failed, \x1b[33;1m3\x1b[0m warnings"

    # ----------------------------------------------------------------------
    def test_NoFailed(self):
        assert CreateStatusText(1, None, 3) == "\x1b[32;1m1\x1b[0m succeeded, \x1b[33;1m3\x1b[0m warnings"

    # ----------------------------------------------------------------------
    def test_NoWarnings(self):
        assert CreateStatusText(1, 2, None) == "\x1b[32;1m1\x1b[0m succeeded, \x1b[31;1m2\x1b[0m failed"


# ----------------------------------------------------------------------
class TestIndent(object):
    # ----------------------------------------------------------------------
    def test_WhitespacePrefix(self):
        assert Indent(
            textwrap.dedent(
                """\
                Line1

                Line3
                """,
            ),
            5,
        ) == "     Line1\n\n     Line3\n"

    # ----------------------------------------------------------------------
    def test_StringPrefix(self):
        assert Indent(
            textwrap.dedent(
                """\
                Line1

                Line3
                """,
            ),
            "***",
        ) == "***Line1\n\n***Line3\n"

    # ----------------------------------------------------------------------
    def test_SkipFirstLine(self):
        assert Indent(
            textwrap.dedent(
                """\
                Line1

                Line3
                """,
            ),
            "***",
            skip_first_line=True,
        ) == "Line1\n\n***Line3\n"
