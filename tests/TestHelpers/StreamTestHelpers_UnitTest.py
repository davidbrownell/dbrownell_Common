# ----------------------------------------------------------------------
# |
# |  StreamTestHelpers_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-02-14 10:40:21
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for StreamTestHelpers.py"""

import textwrap

from typing import cast

import pytest

from dbrownell_Common.TestHelpers.StreamTestHelpers import *


# ----------------------------------------------------------------------
class TestScrubDuration:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        assert ScrubDuration(
            textwrap.dedent(
                """\
                    1:23:45
                    22:33:44
                    """,
            ),
        ) == textwrap.dedent(
            """\
                <scrubbed duration>
                <scrubbed duration>
                """,
        )

    # ----------------------------------------------------------------------
    def test_KeepHours(self):
        assert ScrubDuration(
            textwrap.dedent(
                """\
                    1:23:45
                    22:33:44
                    """,
            ),
            keep_hours=True,
        ) == textwrap.dedent(
            """\
                1:??:??
                22:??:??
                """,
        )

    # ----------------------------------------------------------------------
    def test_KeepMinutes(self):
        assert ScrubDuration(
            textwrap.dedent(
                """\
                    1:23:45
                    22:33:44
                    """,
            ),
            keep_minutes=True,
        ) == textwrap.dedent(
            """\
                ??:23:??
                ??:33:??
                """,
        )

    # ----------------------------------------------------------------------
    def test_KeepSeconds(self):
        assert ScrubDuration(
            textwrap.dedent(
                """\
                    1:23:45
                    22:33:44
                    """,
            ),
            keep_seconds=True,
        ) == textwrap.dedent(
            """\
                ??:??:45
                ??:??:44
                """,
        )

    # ----------------------------------------------------------------------
    def test_KeepAll(self):
        assert ScrubDuration(
            textwrap.dedent(
                """\
                    1:23:45
                    22:33:44
                    """,
            ),
            keep_hours=True,
            keep_minutes=True,
            keep_seconds=True,
        ) == textwrap.dedent(
            """\
                1:23:45
                22:33:44
                """,
        )


# ----------------------------------------------------------------------
class TestGenerateDoneManagerAndContent:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        dm_and_content = iter(GenerateDoneManagerAndContent())

        dm = cast(DoneManager, next(dm_and_content))

        dm.WriteInfo("Content")

        content = cast(str, next(dm_and_content))

        assert content == textwrap.dedent(
            """\
            Heading...
              INFO: Content
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_CustomHeading(self):
        dm_and_content = iter(GenerateDoneManagerAndContent("Custom Heading"))

        dm = cast(DoneManager, next(dm_and_content))

        dm.WriteLine("Line 1")

        content = cast(str, next(dm_and_content))

        assert content == textwrap.dedent(
            """\
            Custom Heading...
              Line 1
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_KeepHours(self):
        dm_and_content = iter(GenerateDoneManagerAndContent(keep_duration_hours=True))

        dm = cast(DoneManager, next(dm_and_content))

        dm.WriteInfo("Content")

        content = cast(str, next(dm_and_content))

        assert content == textwrap.dedent(
            """\
            Heading...
              INFO: Content
            DONE! (0, 0:??:??)
            """,
        )

    # ----------------------------------------------------------------------
    def test_KeepMinutes(self):
        dm_and_content = iter(GenerateDoneManagerAndContent(keep_duration_minutes=True))

        dm = cast(DoneManager, next(dm_and_content))

        dm.WriteInfo("Content")

        content = cast(str, next(dm_and_content))

        assert content == textwrap.dedent(
            """\
            Heading...
              INFO: Content
            DONE! (0, ??:00:??)
            """,
        )

    # ----------------------------------------------------------------------
    def test_ExpectedResult(self):
        expected_result = 123

        # ----------------------------------------------------------------------
        def Impl(
            provided_result: int,
        ):
            dm_and_content = iter(GenerateDoneManagerAndContent(expected_result=expected_result))

            dm = cast(DoneManager, next(dm_and_content))

            dm.result = provided_result

            return cast(str, next(dm_and_content))

        # ----------------------------------------------------------------------

        # Test 1
        with pytest.raises(AssertionError):
            Impl(0)

        # Test 2
        assert Impl(expected_result) == textwrap.dedent(
            """\
            Heading...DONE! (123, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_WriteVerbose(self):
        # ----------------------------------------------------------------------
        def Impl(
            verbose: bool,
        ) -> str:
            dm_and_content = iter(GenerateDoneManagerAndContent(verbose=verbose))

            dm = cast(DoneManager, next(dm_and_content))

            dm.WriteVerbose("Line 1")

            return cast(str, next(dm_and_content))

        # ----------------------------------------------------------------------

        assert Impl(False) == textwrap.dedent(
            """\
            Heading...DONE! (0, <scrubbed duration>)
            """,
        )

        assert Impl(True) == textwrap.dedent(
            """\
            Heading...
              VERBOSE: Line 1
            DONE! (0, <scrubbed duration>)
            """,
        )


# ----------------------------------------------------------------------
def test_InitializeStreamCapabilites():
    # It should be safe to call this multiple times
    InitializeStreamCapabilities()
    InitializeStreamCapabilities()

    assert True
