# ----------------------------------------------------------------------
# |
# |  TextwrapEx_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-24 00:55:41
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for TextwrapEx.py."""

import pytest

from dbrownell_Common.TextwrapEx import *


# ----------------------------------------------------------------------
def test_Justify():
    assert Justify.Left.Justify("test", 10) == "test      "
    assert Justify.Center.Justify("test", 10) == "   test   "
    assert Justify.Right.Justify("test", 10) == "      test"


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
class TestCreateDecoratedText:
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
class TestCreateStatusText:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        assert (
            CreateStatusText(1, 2, 3)
            == "\x1b[32;1m1\x1b[0m succeeded, \x1b[31;1m2\x1b[0m failed, \x1b[33;1m3\x1b[0m warnings"
        )

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
class TestIndent:
    # ----------------------------------------------------------------------
    def test_WhitespacePrefix(self):
        assert (
            Indent(
                textwrap.dedent(
                    """\
                Line1

                Line3
                """,
                ),
                5,
            )
            == "     Line1\n\n     Line3\n"
        )

    # ----------------------------------------------------------------------
    def test_StringPrefix(self):
        assert (
            Indent(
                textwrap.dedent(
                    """\
                Line1

                Line3
                """,
                ),
                "***",
            )
            == "***Line1\n\n***Line3\n"
        )

    # ----------------------------------------------------------------------
    def test_SkipFirstLine(self):
        assert (
            Indent(
                textwrap.dedent(
                    """\
                Line1

                Line3
                """,
                ),
                "***",
                skip_first_line=True,
            )
            == "Line1\n\n***Line3\n"
        )


# ----------------------------------------------------------------------
def test_BoundedLJust():
    assert [
        BoundedLJust("test", 10),
        BoundedLJust("0123456789A", 10),
        BoundedLJust("0123456789AB", 10),
        BoundedLJust("0123456789A", 9),
        BoundedLJust("0123456789AB", 9),
        BoundedLJust("0123456789ABCDEFGHIJK", 13),
        BoundedLJust("0123456789ABCDEFGHIJKL", 13),
    ] == [
        "test      ",
        "012...789A",
        "012...89AB",
        "012...89A",
        "012...9AB",
        "01234...GHIJK",
        "01234...HIJKL",
    ]


# ----------------------------------------------------------------------
def test_CreateAnsiHyperlink():
    assert (
        CreateAnsiHyperLink("https://test.com", "Test Link")
        == "\x1b]8;;https://test.com\x1b\\Test Link\x1b]8;;\x1b\\"
    )


# ----------------------------------------------------------------------
class TestCreateTable:
    # ----------------------------------------------------------------------
    def test_Simple(self):
        assert CreateTable(
            ["One", "Two", "Three"],
            [
                ["AAAAA", "aaaaa", "1"],
                ["BBBBB", "bbbbb", "2"],
                ["CCCCCCCCC", "cccccccc", "3"],
            ],
        ) == textwrap.dedent(
            """\
            One        Two       Three
            ---------  --------  -----
            AAAAA      aaaaa     1
            BBBBB      bbbbb     2
            CCCCCCCCC  cccccccc  3
            """,
        )

    # ----------------------------------------------------------------------
    def test_Centered(self):
        assert CreateTable(
            ["One", "Two", "Three"],
            [
                ["AAAAA", "aaaaa", "1"],
                ["BBBBB", "bbbbb", "2"],
                ["CCCCCCCCC", "cccccccc", "3"],
            ],
            [Justify.Center, Justify.Center, Justify.Center],
        ) == textwrap.dedent(
            """\
               One       Two     Three
            ---------  --------  -----
              AAAAA     aaaaa      1
              BBBBB     bbbbb      2
            CCCCCCCCC  cccccccc    3
            """,
        )

    # ----------------------------------------------------------------------
    def test_Right(self):
        assert CreateTable(
            ["One", "Two", "Three"],
            [
                ["AAAAA", "aaaaa", "1"],
                ["BBBBB", "bbbbb", "2"],
                ["CCCCCCCCC", "cccccccc", "3"],
            ],
            [Justify.Right, Justify.Right, Justify.Right],
        ) == textwrap.dedent(
            """\
                  One       Two  Three
            ---------  --------  -----
                AAAAA     aaaaa      1
                BBBBB     bbbbb      2
            CCCCCCCCC  cccccccc      3
            """,
        )

    # ----------------------------------------------------------------------
    def test_Decorate(self):
        assert CreateTable(
            ["One", "Two", "Three"],
            [
                ["AAAAA", "aaaaa", "1"],
                ["BBBBB", "bbbbb", "2"],
                ["CCCCCCCCC", "cccccccc", "3"],
            ],
            [Justify.Right, Justify.Right, Justify.Right],
            lambda index, values: [values[0].lower(), values[1].upper(), values[2]],
        ) == textwrap.dedent(
            """\
                  One       Two  Three
            ---------  --------  -----
                aaaaa     AAAAA      1
                bbbbb     BBBBB      2
            ccccccccc  CCCCCCCC      3
            """,
        )

    # ----------------------------------------------------------------------
    def test_DecorateHeaders(self):
        assert CreateTable(
            ["One", "Two", "Three"],
            [
                ["AAAAA", "aaaaa", "1"],
                ["BBBBB", "bbbbb", "2"],
                ["CCCCCCCCC", "cccccccc", "3"],
            ],
            [Justify.Right, Justify.Right, Justify.Right],
            lambda index, values: [values[0].lower(), values[1].upper(), values[2]],
            decorate_headers=True,
        ) == textwrap.dedent(
            """\
                  one       TWO  Three
            ---------  --------  -----
                aaaaa     AAAAA      1
                bbbbb     BBBBB      2
            ccccccccc  CCCCCCCC      3
            """,
        )
