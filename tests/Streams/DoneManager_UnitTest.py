# ----------------------------------------------------------------------
# |
# |  DoneManager_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-06 19:17:30
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for DoneManager.py."""

import re
import sys
import textwrap

from io import StringIO
from typing import cast, Optional

import pytest

from dbrownell_Common import TextwrapEx
from dbrownell_Common.Streams.Capabilities import Capabilities
from dbrownell_Common.Streams.DoneManager import DoneManager, DoneManagerException, Flags
from dbrownell_Common.Streams.TextWriter import TextWriter


# ----------------------------------------------------------------------
def test_Simple():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing...") as dm:
        pass

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>)\n"


# ----------------------------------------------------------------------
def test_SimpleNoTrailingHeaderDots():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        pass

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>)\n"


# ----------------------------------------------------------------------
def test_SimpleTrailingHeaderNewline():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing...\n\n") as dm:
        pass

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>)\n"


# ----------------------------------------------------------------------
def test_DoneSuffixNone():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", None):
        pass

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>)\n"


# ----------------------------------------------------------------------
def test_DoneSuffixReturnString():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", lambda: "done_suffix"):
        pass

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>, done_suffix)\n"


# ----------------------------------------------------------------------
def test_DoneSuffixReturnNone():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", lambda: None):
        pass

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>)\n"


# ----------------------------------------------------------------------
def test_DoneSuffixes():
    sink = _CreateSink()

    with DoneManager.Create(
        sink,
        "Testing",
        [
            lambda: "one",
            lambda: None,
            lambda: "three",
            lambda: "four",
        ],
    ):
        pass

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>, one, three, four)\n"


# ----------------------------------------------------------------------
def test_PrefixAndSuffixString():
    sink = _CreateSink()

    with DoneManager.Create(
        sink,
        "Testing",
        prefix="*\n__prefix__*",
        suffix="*\n__suffix__*",
    ) as dm:
        dm.WriteError("Line 1\nLine 2\n")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          ERROR: Line 1
                 Line 2
        *
        __prefix__*DONE! (-1, <Scrubbed Time>)
        *
        __suffix__*""",
    )


# ----------------------------------------------------------------------
def test_PrefixAndSuffixCallable():
    wrote_content = False

    # ----------------------------------------------------------------------
    def Prefix() -> str:
        return "*\n__prefix__*"

    # ----------------------------------------------------------------------
    def Suffix() -> str:
        return "*\n__suffix__*" if wrote_content else ""

    # ----------------------------------------------------------------------

    # wrote_content == False
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", prefix=Prefix, suffix=Suffix) as dm:
        pass

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...*
        __prefix__*DONE! (0, <Scrubbed Time>)
        """,
    )

    # wrote_content == True
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", prefix=Prefix, suffix=Suffix) as dm:
        dm.WriteLine("Line 1")
        wrote_content = True

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Line 1
        *
        __prefix__*DONE! (0, <Scrubbed Time>)
        *
        __suffix__*""",
    )


# ----------------------------------------------------------------------
def test_LinePrefixString():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", line_prefix="****") as dm:
        dm.WriteLine("Line 1\nLine 2")
        dm.WriteLine("Line 3")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
        ****Line 1
        ****Line 2
        ****Line 3
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_NoDisplay():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", display=False):
        pass

    assert _Scrub(sink.getvalue()) == "Testing"


# ----------------------------------------------------------------------
def test_NoDisplayResult():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", display_result=False):
        pass

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (<Scrubbed Time>)\n"


# ----------------------------------------------------------------------
def test_NoDisplayTime():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", display_time=False):
        pass

    assert sink.getvalue() == "Testing...DONE! (0)\n"


# ----------------------------------------------------------------------
def test_WithErrorResult():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.result = -1

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (-1, <Scrubbed Time>)\n"


# ----------------------------------------------------------------------
def test_WithWarningResult():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.result = 123

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (123, <Scrubbed Time>)\n"


# ----------------------------------------------------------------------
def test_DisplayExceptions():
    # display_exceptions == True
    sink = _CreateSink()

    with pytest.raises(
        Exception,
        match=re.escape("The exception"),
    ):
        with DoneManager.Create(sink, "Testing"):
            raise Exception("The exception")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          ERROR: The exception
        DONE! (-1, <Scrubbed Time>)
        """,
    )

    # display_exceptions == False
    sink = _CreateSink()

    with pytest.raises(
        Exception,
        match=re.escape("The exception"),
    ):
        with DoneManager.Create(sink, "Testing", display_exceptions=False):
            raise Exception("The exception")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...DONE! (-1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_DisplayExceptionDetails():
    # display_exception_details == False
    sink = _CreateSink()

    with pytest.raises(
        Exception,
        match=re.escape("The exception"),
    ):
        with DoneManager.Create(sink, "Testing", display_exception_details=False):
            raise Exception("The exception")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          ERROR: The exception
        DONE! (-1, <Scrubbed Time>)
        """,
    )

    # display_exception_details == True
    sink = _CreateSink()

    with pytest.raises(
        Exception,
        match=re.escape("The exception"),
    ):
        with DoneManager.Create(sink, "Testing", display_exception_details=True):
            raise Exception("The exception")

    content = _Scrub(sink.getvalue())

    assert re.match(
        r"""(?#
        Header                  )Testing\.\.\.\n(?#
        Error                   )  ERROR: Traceback \(most recent call last\):\n(?#
        Traceback lines begin   )(?:(?#
          Traceback line        )         .+\n(?#
        Traceback lines end     ))+?(?#
        Last Traceback line     )         Exception: The exception\n+(?#
        Done                    )DONE! \(-1, <Scrubbed Time>\)\n(?#
        )""",
        content,
    ), content


# ----------------------------------------------------------------------
def test_DoneManagerException():
    sink = _CreateSink()

    with pytest.raises(
        DoneManagerException,
        match=re.escape("The exception"),
    ):
        with DoneManager.Create(sink, "Testing", display_exception_details=True):
            raise DoneManagerException("The exception")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          ERROR: The exception
        DONE! (-1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_NestedException():
    sink = _CreateSink()

    with pytest.raises(
        Exception,
        match=re.escape("The exception"),
    ):
        with DoneManager.Create(sink, "Testing") as dm:
            with dm.Nested("Nested"):
                raise Exception("The exception")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Nested...
            ERROR: The exception
          DONE! (-1, <Scrubbed Time>)
        DONE! (-1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_SuppressExceptions():
    # suppress_exceptions == False
    sink = _CreateSink()

    with pytest.raises(
        Exception,
        match=re.escape("The exception"),
    ):
        with DoneManager.Create(sink, "Testing", suppress_exceptions=False):
            raise Exception("The exception")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        textwrap.dedent(
            """\
            Testing...
              ERROR: The exception
            DONE! (-1, <Scrubbed Time>)
            """,
        ),
    )

    # suppress_exceptions == True
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", suppress_exceptions=True):
        raise Exception("The exception")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          ERROR: The exception
        DONE! (-1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_SuppressExceptionsNoDisplayExceptions():
    with pytest.raises(
        Exception,
        match=re.escape("Exceptions should not be suppressed when they are not displayed."),
    ):
        with DoneManager.Create(StringIO(), "Testing", display_exceptions=False, suppress_exceptions=True):
            pass


# ----------------------------------------------------------------------
def test_StandardFlags():
    with DoneManager.Create(_CreateSink(), "Testing", flags=Flags.Create(verbose=False, debug=False)) as dm:
        assert dm.is_verbose is False
        assert dm.is_debug is False


# ----------------------------------------------------------------------
def test_VerboseFlags():
    with DoneManager.Create(_CreateSink(), "Testing", flags=Flags.Create(verbose=True, debug=False)) as dm:
        assert dm.is_verbose is True
        assert dm.is_debug is False


# ----------------------------------------------------------------------
def test_DebugFlags():
    with DoneManager.Create(_CreateSink(), "Testing", flags=Flags.Create(verbose=False, debug=True)) as dm:
        assert dm.is_verbose is True
        assert dm.is_debug is True


# ----------------------------------------------------------------------
def test_Capabilities():
    sink = StringIO()
    capabilities = Capabilities(stream=sink)

    with DoneManager.Create(sink, "Testing") as dm:
        assert dm.capabilities is capabilities


# ----------------------------------------------------------------------
def test_isatty():
    with DoneManager.Create(_FakeStream(), "Testing") as dm:
        assert dm.isatty() is False

    with DoneManager.Create(_FakeStream(isatty=True), "Testing") as dm:
        assert dm.isatty() is True


# ----------------------------------------------------------------------
def test_WriteLine():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteLine("Line 1")
        dm.WriteLine("Line 2")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Line 1
          Line 2
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_WriteSuccess():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteSuccess("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          SUCCESS: Line 1
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_WriteSuccessWithColor():
    sink = _CreateSink(supports_colors=True)

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteSuccess("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          {color_on}SUCCESS:{color_off} Line 1
        DONE! ({color_on}0{color_off}, <Scrubbed Time>)
        """,
    ).format(
        color_on=TextwrapEx.SUCCESS_COLOR_ON,
        color_off=TextwrapEx.COLOR_OFF,
    )


# ----------------------------------------------------------------------
def test_WriteError():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteError("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          ERROR: Line 1
        DONE! (-1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_WriteErrorWithColor():
    sink = _CreateSink(supports_colors=True)

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteError("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          {color_on}ERROR:{color_off} Line 1
        DONE! ({color_on}-1{color_off}, <Scrubbed Time>)
        """,
    ).format(
        color_on=TextwrapEx.ERROR_COLOR_ON,
        color_off=TextwrapEx.COLOR_OFF,
    )


# ----------------------------------------------------------------------
def test_WriteWarning():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteWarning("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          WARNING: Line 1
        DONE! (1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_WriteWarningWithColor():
    sink = _CreateSink(supports_colors=True)

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteWarning("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          {color_on}WARNING:{color_off} Line 1
        DONE! ({color_on}1{color_off}, <Scrubbed Time>)
        """,
    ).format(
        color_on=TextwrapEx.WARNING_COLOR_ON,
        color_off=TextwrapEx.COLOR_OFF,
    )


# ----------------------------------------------------------------------
def test_WriteInfo():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteInfo("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          INFO: Line 1
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_WriteInfoWithColor():
    sink = _CreateSink(supports_colors=True)

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteInfo("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          {info_color_on}INFO:{color_off} Line 1
        DONE! ({success_color_on}0{color_off}, <Scrubbed Time>)
        """,
    ).format(
        info_color_on=TextwrapEx.INFO_COLOR_ON,
        success_color_on=TextwrapEx.SUCCESS_COLOR_ON,
        color_off=TextwrapEx.COLOR_OFF,
    )


# ----------------------------------------------------------------------
def WriteVerbose():
    # verbose == False
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteVerbose("Line 1")

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>)\n"

    # verbose == True
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", flags=Flags.Create(verbose=True)) as dm:
        dm.WriteVerbose("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          VERBOSE: Line 1
        DONE! (0, <Scrubbed Time>)
        """,
    )

    # verbose == True, with colors
    sink = _CreateSink(supports_colors=True)

    with DoneManager.Create(sink, "Testing", flags=Flags.Create(verbose=True)) as dm:
        dm.WriteVerbose("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          {verbose_color_on}VERBOSE:{color_off} Line 1
        DONE! ({success_color_on}0{color_off}, <Scrubbed Time>)
        """,
    ).format(
        verbose_color_on=TextwrapEx.VERBOSE_COLOR_ON,
        success_color_on=TextwrapEx.SUCCESS_COLOR_ON,
        color_off=TextwrapEx.COLOR_OFF,
    )


# ----------------------------------------------------------------------
def test_WriteDebug():
    # debug == False
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteDebug("Line 1")

    assert _Scrub(sink.getvalue()) == "Testing...DONE! (0, <Scrubbed Time>)\n"

    # debug == True
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", flags=Flags.Create(debug=True)) as dm:
        dm.WriteDebug("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          DEBUG: Line 1
        DONE! (0, <Scrubbed Time>)
        """,
    )

    # debug == True, with colors
    sink = _CreateSink(supports_colors=True)

    with DoneManager.Create(sink, "Testing", flags=Flags.Create(debug=True)) as dm:
        dm.WriteDebug("Line 1")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          {debug_color_on}DEBUG:{color_off} Line 1
        DONE! ({success_color_on}0{color_off}, <Scrubbed Time>)
        """,
    ).format(
        debug_color_on=TextwrapEx.DEBUG_COLOR_ON,
        success_color_on=TextwrapEx.SUCCESS_COLOR_ON,
        color_off=TextwrapEx.COLOR_OFF,
    )


# ----------------------------------------------------------------------
def test_AlignedMultilineOutput():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", flags=Flags.Create(debug=True, verbose=True)) as dm:
        content = "Line 1\nLine 2\n"

        dm.WriteLine(content)
        dm.WriteSuccess(content)
        dm.WriteError(content)
        dm.WriteWarning(content)
        dm.WriteInfo(content)
        dm.WriteVerbose(content)
        dm.WriteDebug(content)

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Line 1
          Line 2
          SUCCESS: Line 1
                   Line 2
          ERROR: Line 1
                 Line 2
          WARNING: Line 1
                   Line 2
          INFO: Line 1
                Line 2
          VERBOSE: Line 1
                   Line 2
          DEBUG: Line 1
                 Line 2
        DONE! (-1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_ErrorPrecedence():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteSuccess("Line 1")
        dm.WriteError("Line 2")
        dm.WriteWarning("Line 3")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          SUCCESS: Line 1
          ERROR: Line 2
          WARNING: Line 3
        DONE! (-1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_WarningPrecedence():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteSuccess("Line 1")
        dm.WriteWarning("Line 2")
        dm.WriteSuccess("Line 3")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          SUCCESS: Line 1
          WARNING: Line 2
          SUCCESS: Line 3
        DONE! (1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
class TestWriteStatus:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing") as dm:
            dm.WriteStatus("Line 1")

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",
            "  ",
            "\r  Line 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[1A\r",
            "  ",
            "\x1b[1B",
            "\r",
            "DONE! (0, <Scrubbed Time>)\n",
        ]

    # ----------------------------------------------------------------------
    def test_NoPreserveStatusFlag(self):
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing", preserve_status=False) as dm:
            dm.WriteStatus("Line 1")

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",  # 0 - 2
            "  ",
            "\r  Line 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",  # 3 - 5
            "  ",
            "\x1b[1A\r",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",  # 7 - 9
            "  ",
            "\x1b[1A\r",
            "  ",
            "\x1b[1A\rTesting...",
            None,
            "DONE! (0, <Scrubbed Time>)\n",  # 10 - 14
        ]

    # ----------------------------------------------------------------------
    def test_Truncated(self):
        num_cols = 20

        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing", num_cols=num_cols) as dm:
            dm.WriteStatus("This is a really long status line that should be truncated.")

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",
            "  ",
            "\r  This ...uncated.",
            "\n",
            "  ",
            "\x1b[1A\r",
            "  ",
            "\x1b[1B",
            "\r",
            "DONE! (0, <Scrubbed Time>)\n",
        ]

    # ----------------------------------------------------------------------
    def test_NotInteractive(self):
        stream = _FakeStream()

        with DoneManager.Create(stream, "Testing") as dm:
            dm.WriteStatus("Line 1\nLine 2")
            dm.WriteStatus("Line 3")

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "DONE! (0, <Scrubbed Time>)\n",
        ]

    # ----------------------------------------------------------------------
    def test_Nested(self):
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing") as dm:
            dm.WriteStatus("Line 1")

            with dm.Nested("Nested") as nested_dm:
                nested_dm.WriteStatus("Line 2\nLine 3")
                nested_dm.WriteStatus("Line 4")

            dm.WriteStatus("Line 5")

        stream.content[48] = _Scrub(cast(str, stream.content[48]))
        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",  # 0 - 2
            "  ",
            "\r  Line 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",  # 3 - 5
            "  ",
            "\x1b[1A\r",
            "  ",
            "\x1b[1B",
            "\r",
            "  ",
            "Nested...",
            None,
            "\n",  # 6 - 14
            "  ",
            "  ",
            "\r    Line 2".ljust(Capabilities.DEFAULT_COLUMNS - len("    ") + 1),
            "\n",  # 15 - 18
            "  ",
            "  ",
            "\r    Line 3".ljust(Capabilities.DEFAULT_COLUMNS - len("    ") + 1),
            "\n",  # 19 - 22
            "  ",
            "  ",
            "\x1b[2A\r",
            "  ",
            "  ",
            "\r    Line 4".ljust(Capabilities.DEFAULT_COLUMNS - len("    ") + 1),
            "\n",  # 23 - 29
            "  ",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("    ") + 1),
            "\n",  # 30 - 33
            "  ",
            "  ",
            "\x1b[2A\r",
            "  ",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("    ") + 1),
            "\n",  # 34 - 40
            "  ",
            "  ",
            "\x1b[1A\r",
            "  ",
            "  ",
            "\x1b[1A\r  Nested...",
            None,
            "DONE! (0, <Scrubbed Time>)",
            "\n",  # 41 - 49
            None,
            "  ",
            "\r  Line 5".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",  # 50 - 53
            "  ",
            "\x1b[1A\r",
            "  ",
            "\x1b[1B",
            "\r",
            "DONE! (0, <Scrubbed Time>)\n",  # 54 - 59
        ]

    # ----------------------------------------------------------------------
    def test_ClearStatus(self):
        # preserve_status == True
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing", preserve_status=True) as dm:
            dm.WriteStatus("Line 1\nLine 2")
            dm.ClearStatus()

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",  # 0 - 2
            "  ",
            "\r  Line 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",  # 3 - 5
            "  ",
            "\r  Line 2".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",  # 6 - 8
            "  ",
            "\x1b[2A\r",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",  # 9 - 13
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",  # 14 - 16
            "  ",
            "\x1b[2A\r",
            "DONE! (0, <Scrubbed Time>)\n",  # 17 - 19
        ]

        # preserve_status == False
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing", preserve_status=False) as dm:
            dm.WriteStatus("Line 1\nLine 2")
            dm.ClearStatus()

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",
            "  ",
            "\r  Line 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  Line 2".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "\x1b[1A\rTesting...",
            None,
            "DONE! (0, <Scrubbed Time>)\n",
        ]

    # ----------------------------------------------------------------------
    def test_PreserveStatus(self):
        # preserve_status == True
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing", preserve_status=True) as dm:
            dm.WriteStatus("Line 1\nLine 2")
            dm.PreserveStatus()

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",
            "  ",
            "\r  Line 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  Line 2".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "\x1b[2B",
            "\r",
            "DONE! (0, <Scrubbed Time>)\n",
        ]

        # preserve_status == False
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing", preserve_status=False) as dm:
            dm.WriteStatus("Line 1\nLine 2")
            dm.PreserveStatus()

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",
            "  ",
            "\r  Line 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  Line 2".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "\x1b[2B",
            "\r",
            "  ",
            "\x1b[1A\rTesting...",
            None,
            "DONE! (0, <Scrubbed Time>)\n",
        ]

    # ----------------------------------------------------------------------
    def test_ShortAndLongLines(self):
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing") as dm:
            dm.WriteStatus("Short 1\nShort 2")
            dm.WriteStatus("This is longer status 1\nThis is longer status 2\nThis is longer status 3")
            dm.WriteStatus("Again 1")

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",
            "  ",
            "\r  Short 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  Short 2".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "\r  This is longer status 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  This is longer status 2".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  This is longer status 3".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[3A\r",
            "  ",
            "\r  Again 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[3A\r",
            "  ",
            "\x1b[1B",
            "\r",
            "DONE! (0, <Scrubbed Time>)\n",
        ]

    # ----------------------------------------------------------------------
    def test_GroupedStatus(self):
        stream = _FakeStream(
            is_interactive=True,
        )

        with DoneManager.Create(stream, "Testing") as dm:
            dm.WriteLine("One")
            dm.WriteStatus("Status 1\nStatus 2")

            dm.WriteLine("Two")
            dm.WriteStatus("Status 3\nStatus 4")

            dm.ClearStatus()

        stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

        assert stream.content == [
            "Testing...",
            None,
            "\n",
            "  ",
            "One",
            "\n",
            "  ",
            "\r  Status 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  Status 2".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "Two",
            "\n",
            "  ",
            "\r  Status 1".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  Status 2".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "\r  Status 3".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r  Status 4".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\r".ljust(Capabilities.DEFAULT_COLUMNS - len("  ") + 1),
            "\n",
            "  ",
            "\x1b[2A\r",
            "DONE! (0, <Scrubbed Time>)\n",
        ]


# ----------------------------------------------------------------------
def test_SimpleNested():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing 1") as dm:
        with dm.Nested("Testing 2"):
            pass

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing 1...
          Testing 2...DONE! (0, <Scrubbed Time>)
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_ComplicatedNested():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing 1") as dm:
        dm.WriteLine("1.A")

        with dm.Nested("Testing 2") as this_dm:
            this_dm.WriteLine("2.A")

        dm.WriteLine("1.B")

        with dm.Nested("Testing 3") as this_dm:
            with this_dm.Nested("3.A") as nested_dm:
                nested_dm.WriteLine("3.A.A")

        dm.WriteLine("1.C")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing 1...
          1.A
          Testing 2...
            2.A
          DONE! (0, <Scrubbed Time>)
          1.B
          Testing 3...
            3.A...
              3.A.A
            DONE! (0, <Scrubbed Time>)
          DONE! (0, <Scrubbed Time>)
          1.C
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_NestedErrors():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        assert dm.result == 0

        with dm.Nested("Zero") as this_dm:
            this_dm.result = 1

        assert dm.result == 1

        with dm.Nested("One") as this_dm:
            this_dm.result = -1

        assert dm.result == -1

        with dm.Nested("Two") as this_dm:
            this_dm.result = -2

        with dm.Nested("Three") as this_dm:
            this_dm.result = 2

        assert dm.result == -1

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Zero...DONE! (1, <Scrubbed Time>)
          One...DONE! (-1, <Scrubbed Time>)
          Two...DONE! (-2, <Scrubbed Time>)
          Three...DONE! (2, <Scrubbed Time>)
        DONE! (-1, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_VerboseNested():
    # verbose == False
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteLine("Line 1")

        with dm.VerboseNested("Verbose") as verbose_dm:
            verbose_dm.WriteLine("Line 2")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Line 1
        DONE! (0, <Scrubbed Time>)
        """,
    )

    # verbose == True
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", flags=Flags.Create(verbose=True)) as dm:
        dm.WriteLine("Line 1")

        with dm.VerboseNested("Verbose") as verbose_dm:
            verbose_dm.WriteLine("Line 2")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Line 1
          VERBOSE: Verbose...
          VERBOSE:   Line 2
          VERBOSE: DONE! (0, <Scrubbed Time>)
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_Debug():
    # debug == False
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        dm.WriteLine("Line 1")

        with dm.DebugNested("Debug") as debug_dm:
            debug_dm.WriteLine("Line 2")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Line 1
        DONE! (0, <Scrubbed Time>)
        """,
    )

    # debug == True
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing", flags=Flags.Create(debug=True)) as dm:
        dm.WriteLine("Line 1")

        with dm.DebugNested("Debug") as debug_dm:
            debug_dm.WriteLine("Line 2")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Line 1
          DEBUG: Debug...
          DEBUG:   Line 2
          DEBUG: DONE! (0, <Scrubbed Time>)
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_YieldStream():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Testing") as dm:
        with dm.YieldStream() as stream:
            stream.write("Line 1\nLine 2")

        dm.WriteLine("Line 3")

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Testing...
          Line 1
          Line 2Line 3
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
class TestYieldVerboseStream:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        sink = _CreateSink()

        with DoneManager.Create(sink, "Testing") as dm:
            with dm.YieldVerboseStream() as stream:
                stream.write("Hello, world!")

        assert _Scrub(sink.getvalue()) == textwrap.dedent(
            """\
            Testing...DONE! (0, <Scrubbed Time>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_WithVerbose(self):
        sink = _CreateSink()

        with DoneManager.Create(sink, "Testing", flags=Flags.Create(verbose=True)) as dm:
            with dm.YieldVerboseStream() as stream:
                stream.write("Hello, world!")

        assert _Scrub(sink.getvalue()) == textwrap.dedent(
            """\
            Testing...
              VERBOSE: Hello, world!DONE! (0, <Scrubbed Time>)
            """,
        )


# ----------------------------------------------------------------------
class TestYieldDebugStream:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        sink = _CreateSink()

        with DoneManager.Create(sink, "Testing") as dm:
            with dm.YieldDebugStream() as stream:
                stream.write("Hello, world!")

        assert _Scrub(sink.getvalue()) == textwrap.dedent(
            """\
            Testing...DONE! (0, <Scrubbed Time>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_WithDebug(self):
        sink = _CreateSink()

        with DoneManager.Create(sink, "Testing", flags=Flags.Create(debug=True)) as dm:
            with dm.YieldDebugStream() as stream:
                stream.write("Hello, world!\n")

        assert _Scrub(sink.getvalue()) == textwrap.dedent(
            """\
            Testing...
              DEBUG: Hello, world!
            DONE! (0, <Scrubbed Time>)
            """,
        )


# ----------------------------------------------------------------------
class TestYieldStdout:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        with DoneManager.Create(sys.stdout, "Testing") as dm:
            with dm.YieldStdout() as context:
                assert context.stream is sys.stdout
                assert context.line_prefix == "  "
                assert context.persist_content is True

                context.stream.write("Hello, world!\n")

                # Verify that the text appears in sys.stdout

    # ----------------------------------------------------------------------
    def test_NoPreserve(self):
        with DoneManager.Create(sys.stdout, "Testing") as dm:
            with dm.YieldStdout() as context:
                context.stream.write("Hello, world!\n")

                context.persist_content = False

                # Verify that the text does not appear in sys.stdout


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
class _FakeStream(TextWriter):
    # ----------------------------------------------------------------------
    def __init__(
        self,
        *,
        fileno: int = 123,
        isatty: bool = False,
        is_headless: bool = True,
        is_interactive: bool = False,
        supports_colors: bool = False,
    ):
        self.content: list[Optional[str]] = []
        self._fileno = fileno
        self._isatty = isatty

        Capabilities(
            stream=self,
            is_headless=is_headless,
            is_interactive=is_interactive,
            supports_colors=supports_colors,
        )

    # ----------------------------------------------------------------------
    def isatty(self) -> bool:
        return self._isatty

    # ----------------------------------------------------------------------
    def write(
        self,
        content: str,
    ) -> int:
        self.content.append(content)
        return len(content)

    # ----------------------------------------------------------------------
    def flush(self) -> None:
        self.content.append(None)

    # ----------------------------------------------------------------------
    def fileno(self) -> int:
        return self._fileno

    # ----------------------------------------------------------------------
    def close(self) -> None:
        pass


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
def _CreateSink(
    supports_colors: bool = False,
) -> StringIO:
    sink = StringIO()

    Capabilities(
        stream=sink,
        is_headless=True,
        is_interactive=False,
        supports_colors=supports_colors,
    )

    return sink


# ----------------------------------------------------------------------
def _Scrub(
    content: str,
) -> str:
    return re.sub(
        r"\d+:\d{2}:\d{2}(?:\.\d+)?",
        "<Scrubbed Time>",
        content,
    )
