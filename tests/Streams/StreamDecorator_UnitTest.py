# ----------------------------------------------------------------------
# |
# |  StreamDecorator_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-05 15:03:43
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for StreamDecorator.py."""

import re

from typing import Optional

import pytest

from dbrownell_Common.Streams.StreamDecorator import StreamDecorator
from dbrownell_Common.Streams.TextWriter import TextWriter


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class FakeStream(TextWriter):
    # ----------------------------------------------------------------------
    def __init__(
        self,
        fileno: int,
        isatty: bool = False,
    ):
        self.content: list[Optional[str]] = []
        self._fileno = fileno
        self._isatty = isatty

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
# |  Public Functions
# |
# ----------------------------------------------------------------------
def test_Empty():
    stream = StreamDecorator(None)

    assert stream.col_offset == 0
    assert stream.has_stdout is False
    assert stream.has_streams is False
    assert stream.wrote_content is False
    assert stream.isatty() is False
    assert stream.fileno() == 0

    stream.write("test")
    assert stream.col_offset == len("test")
    assert stream.wrote_content is True

    stream.flush()
    assert stream.col_offset == len("test")

    assert list(stream.EnumStreams()) == []

    assert stream.GetLinePrefix(0) == ""
    assert stream.GetCompleteLinePrefix() == ""

    stream.close()


# ----------------------------------------------------------------------
def test_SingleSimpleStream():
    fake = FakeStream(123)
    stream = StreamDecorator(fake)

    assert stream.col_offset == 0
    assert stream.has_stdout is False
    assert stream.has_streams is True
    assert stream.wrote_content is False
    assert stream.isatty() is False
    assert stream.fileno() == fake.fileno()
    assert fake.content == []

    assert list(stream.EnumStreams()) == [
        fake,
    ]
    assert stream.GetLinePrefix(0) == ""
    assert stream.GetCompleteLinePrefix() == ""

    # "test"
    stream.write("test")
    assert stream.col_offset == len("test")
    assert stream.wrote_content is True
    assert fake.content == [
        "test",
    ]

    # "\n"
    stream.write("\n")
    assert stream.col_offset == 0
    assert stream.wrote_content is True
    assert fake.content == ["test", "\n"]

    # "test2"
    stream.write("test2")
    assert stream.col_offset == len("test2")
    assert stream.wrote_content is True
    assert fake.content == [
        "test",
        "\n",
        "test2",
    ]

    # flush
    stream.flush()
    assert stream.col_offset == len("test2")
    assert stream.wrote_content is True
    assert fake.content == ["test", "\n", "test2", None]

    # ""
    stream.write("")
    assert stream.col_offset == len("test2")
    assert fake.content == ["test", "\n", "test2", None]

    # "abc\nd"
    stream.write("abc\nd")
    assert stream.col_offset == 1
    assert fake.content == ["test", "\n", "test2", None, "abc", "\n", "d"]

    # "e\nfgh\n"
    stream.write("e\nfgh\n")
    assert stream.col_offset == 0
    assert fake.content == ["test", "\n", "test2", None, "abc", "\n", "d", "e", "\n", "fgh", "\n"]


# ----------------------------------------------------------------------
def test_SingleStreamWithLinePrefixAndSuffix():
    fake = FakeStream(123)
    stream = StreamDecorator(
        fake,
        "__prefix__",
        "__suffix__",
    )

    stream.write("Hello world!\n")
    assert stream.col_offset == 0
    assert stream.wrote_content is True
    assert fake.content == ["__prefix__", "Hello world!", "__suffix__", "\n"]

    stream.write("more")
    assert stream.col_offset == len("__prefix__more")
    assert stream.wrote_content is True
    assert fake.content == ["__prefix__", "Hello world!", "__suffix__", "\n", "__prefix__", "more"]

    stream.flush()
    assert stream.col_offset == len("__prefix__more")
    assert stream.wrote_content is True
    assert fake.content == [
        "__prefix__",
        "Hello world!",
        "__suffix__",
        "\n",
        "__prefix__",
        "more",
        None,
    ]

    stream.close()
    assert fake.content == [
        "__prefix__",
        "Hello world!",
        "__suffix__",
        "\n",
        "__prefix__",
        "more",
        None,
        None,
    ]


# ----------------------------------------------------------------------
def test_SingleStreamWithSuffixFunctor():
    fake = FakeStream(123)
    stream = StreamDecorator(
        fake,
        line_suffix=lambda x: "__suffix__({})".format(x),
    )

    stream.write("one\n")
    assert stream.col_offset == 0
    assert fake.content == ["one", "__suffix__(3)", "\n"]

    stream.write("more\n")
    assert stream.col_offset == 0
    assert fake.content == ["one", "__suffix__(3)", "\n", "more", "__suffix__(4)", "\n"]


# ----------------------------------------------------------------------
def test_SingleComplicatedStream():
    fake = FakeStream(123)

    stream = StreamDecorator(
        fake,
        "__prefix__",
        "__suffix__",
        "STREAM\nHEADER\n",
        "STREAM\nFOOTER\n",
    )

    assert stream.col_offset == 0
    assert fake.content == []

    stream.write("Hello world!")
    assert stream.col_offset == len("__prefix__Hello world!")
    assert fake.content == ["STREAM\nHEADER\n", "__prefix__", "Hello world!"]

    stream.write("\nWith Newline\n")
    assert stream.col_offset == 0
    assert fake.content == [
        "STREAM\nHEADER\n",
        "__prefix__",
        "Hello world!",
        "__suffix__",
        "\n",
        "__prefix__",
        "With Newline",
        "__suffix__",
        "\n",
    ]

    stream.write("no newline before suffix")
    assert stream.col_offset == len("__prefix__no newline before suffix")
    assert fake.content == [
        "STREAM\nHEADER\n",
        "__prefix__",
        "Hello world!",
        "__suffix__",
        "\n",
        "__prefix__",
        "With Newline",
        "__suffix__",
        "\n",
        "__prefix__",
        "no newline before suffix",
    ]

    stream.close()
    assert stream.col_offset == 0
    assert fake.content == [
        "STREAM\nHEADER\n",
        "__prefix__",
        "Hello world!",
        "__suffix__",
        "\n",
        "__prefix__",
        "With Newline",
        "__suffix__",
        "\n",
        "__prefix__",
        "no newline before suffix",
        "STREAM\nFOOTER\n",
        None,
    ]


# ----------------------------------------------------------------------
def test_ExceptionsOnClosed():
    fake = FakeStream(123)

    stream = StreamDecorator(fake)
    stream.close()

    exception = re.escape("Instance is closed.")

    with pytest.raises(Exception, match=exception):
        stream.write("test")

    with pytest.raises(Exception, match=exception):
        stream.flush()

    with pytest.raises(Exception, match=exception):
        stream.close()


# ----------------------------------------------------------------------
def test_MultipleStreams():
    fake1 = FakeStream(123)
    fake2 = FakeStream(456)

    stream = StreamDecorator([fake1, fake2], line_prefix="# ")

    stream.write("Hello world!\n")
    assert fake1.content == ["# ", "Hello world!", "\n"]
    assert fake2.content == ["# ", "Hello world!", "\n"]


# ----------------------------------------------------------------------
def test_GetLinePrefix():
    assert StreamDecorator(FakeStream(123)).GetLinePrefix(0) == ""
    assert (
        StreamDecorator(FakeStream(123), line_prefix=lambda x: "__prefix__({})".format(x)).GetLinePrefix(0)
        == "__prefix__(0)"
    )


# ----------------------------------------------------------------------
def test_DecorateEmptyLines():
    fake = FakeStream(123)
    stream = StreamDecorator(
        fake,
        "__prefix__",
        "__suffix__",
        decorate_empty_lines=False,
    )

    stream.write("Hello\n\nWorld\n")
    assert stream.col_offset == 0
    assert fake.content == [
        "__prefix__",
        "Hello",
        "__suffix__",
        "\n",
        "\n",
        "__prefix__",
        "World",
        "__suffix__",
        "\n",
    ]

    fake = FakeStream(123)

    stream = StreamDecorator(
        fake,
        "__prefix__",
        "__suffix__",
        decorate_empty_lines=True,
    )

    stream.write("Hello\n\nWorld\n")
    assert stream.col_offset == 0
    assert fake.content == [
        "__prefix__",
        "Hello",
        "__suffix__",
        "\n",
        "__prefix__",
        "__suffix__",
        "\n",
        "__prefix__",
        "World",
        "__suffix__",
        "\n",
    ]


# ----------------------------------------------------------------------
def test_GetCompleteLinePrefixNoNested():
    stream = StreamDecorator(FakeStream(123), "__prefix__")

    assert stream.GetCompleteLinePrefix() == "__prefix__"
    assert stream.GetCompleteLinePrefix(include_self=False) == ""


# ----------------------------------------------------------------------
def test_Nested():
    fake = FakeStream(123)
    stream = StreamDecorator(
        StreamDecorator(
            fake,
            "__prefix__(inner)",
            "__suffix__(inner)",
        ),
        "__prefix__(outer)",
        "__suffix__(outer)",
    )

    assert stream.GetCompleteLinePrefix() == "__prefix__(inner)__prefix__(outer)"
    assert stream.GetCompleteLinePrefix(include_self=False) == "__prefix__(inner)"

    assert stream.col_offset == 0
    assert fake.content == []

    stream.write("Hello world!\nabc")
    assert stream.col_offset == len("__prefix__(outer)abc")
    assert fake.content == [
        "__prefix__(inner)",
        "__prefix__(outer)",
        "Hello world!",
        "__suffix__(outer)",
        "__suffix__(inner)",
        "\n",
        "__prefix__(inner)",
        "__prefix__(outer)",
        "abc",
    ]
