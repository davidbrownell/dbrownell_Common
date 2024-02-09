# ----------------------------------------------------------------------
# |
# |  TextWriter_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-06 19:15:01
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for TextWriter.py."""

from dbrownell_Common.Streams.TextWriter import TextWriter


# ----------------------------------------------------------------------
class MyTextWriter(TextWriter):
    # ----------------------------------------------------------------------
    def isatty(self) -> bool:
        return False

    # ----------------------------------------------------------------------
    def write(
        self,
        content: str,
    ) -> int:
        return 0

    # ----------------------------------------------------------------------
    def flush(self) -> None:
        pass

    # ----------------------------------------------------------------------
    def close(self) -> None:
        pass


# ----------------------------------------------------------------------
def test_Standard():
    tw = MyTextWriter()

    assert tw.isatty() is False
    assert tw.write("test") == 0
