# ----------------------------------------------------------------------
# |
# |  StreamDecorator.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-18 18:11:38
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Contains the StreamDecorator object"""

import sys

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import auto, Enum
from functools import cached_property
from typing import Callable, Generator, Iterator, Optional

from dbrownell_Common.ContextlibEx import ExitStack
from dbrownell_Common.Streams.Capabilities import Capabilities, TextWriterT
from dbrownell_Common.Streams.TextWriter import TextWriter


# ----------------------------------------------------------------------
class StreamDecorator(TextWriter):
    """Stream-like object that supports line decoration with prefixes and suffixes."""

    # ----------------------------------------------------------------------
    # |
    # |  Public Types
    # |
    # ----------------------------------------------------------------------
    PrefixOrSuffixT = (
        None
        | str
        | Callable[
            [
                int,  # column offset
            ],
            str,
        ]
    )

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(
        self,
        stream_or_streams: None | TextWriterT | list[TextWriterT],
        line_prefix: "StreamDecorator.PrefixOrSuffixT" = None,
        line_suffix: "StreamDecorator.PrefixOrSuffixT" = None,
        prefix: "StreamDecorator.PrefixOrSuffixT" = None,
        suffix: "StreamDecorator.PrefixOrSuffixT" = None,
        *,
        decorate_empty_lines: bool = True,
    ):
        if stream_or_streams is None:
            streams = []
        elif isinstance(stream_or_streams, list):
            streams = stream_or_streams
        else:
            streams = [
                stream_or_streams,
            ]

        del stream_or_streams

        # ----------------------------------------------------------------------
        def PrefixOrSuffixTToCallable(
            value: StreamDecorator.PrefixOrSuffixT,
        ) -> Callable[[int], str]:
            if value is None:
                return lambda _: ""

            if isinstance(value, str):
                return lambda _: value

            if callable(value):
                return value

            assert False, value  # pragma: no cover

        # ----------------------------------------------------------------------

        self._streams = streams
        self._line_prefix_func = PrefixOrSuffixTToCallable(line_prefix)
        self._line_suffix_func = PrefixOrSuffixTToCallable(line_suffix)
        self._prefix_func = PrefixOrSuffixTToCallable(prefix)
        self._suffix_func = PrefixOrSuffixTToCallable(suffix)
        self._decorate_empty_lines = decorate_empty_lines

        self._state: StreamDecorator._State = StreamDecorator._State.Prefix
        self._col_offset = 0
        self._wrote_content = False

        self._isatty = any(getattr(stream, "isatty", lambda: False)() for stream in self._streams)

        # Set the capabilities for this stream
        if self._streams:
            lowest_capabilities: Optional[Capabilities] = None

            for stream in self._streams:
                capabilities = Capabilities.Get(stream)

                if lowest_capabilities is None or capabilities < lowest_capabilities:
                    lowest_capabilities = capabilities

            assert lowest_capabilities is not None

            capabilities = lowest_capabilities

        else:
            capabilities = Capabilities(ignore_environment=True)

        Capabilities.Set(self, capabilities)

    # ----------------------------------------------------------------------
    @property
    def col_offset(self) -> int:
        return self._col_offset

    @cached_property
    def has_stdout(self) -> bool:
        return any(
            stream is sys.stdout or (isinstance(stream, StreamDecorator) and stream.has_stdout)
            for stream in self._streams
        )

    @cached_property
    def has_streams(self) -> bool:
        return bool(self._streams)

    @property
    def wrote_content(self) -> bool:
        return self._wrote_content

    # ----------------------------------------------------------------------
    def isatty(self) -> bool:
        return self._isatty

    # ----------------------------------------------------------------------
    def fileno(self) -> int:
        return next((stream.fileno() for stream in self._streams if hasattr(stream, "fileno")), 0)  # type: ignore

    # ----------------------------------------------------------------------
    def write(
        self,
        content: str,
    ) -> int:
        if self._state == StreamDecorator._State.Closed:
            raise Exception("Instance is closed.")

        chars_written = 0

        if self._state == StreamDecorator._State.Prefix:
            self._write_raw(self._prefix_func(self._col_offset))
            self._state = StreamDecorator._State.Writing

        chars_written += self._write_content(content)

        return chars_written

    # ----------------------------------------------------------------------
    def flush(self) -> None:
        if self._state == StreamDecorator._State.Closed:
            raise Exception("Instance is closed.")

        for stream in self._streams:
            stream.flush()

    # ----------------------------------------------------------------------
    def close(self) -> None:
        if self._state == StreamDecorator._State.Closed:
            raise Exception("Instance is closed.")

        self._state = StreamDecorator._State.Suffix
        self._write_raw(self._suffix_func(self._col_offset))

        self.flush()

        self._state = StreamDecorator._State.Closed

        for stream in self._streams:
            stream.close()

    # ----------------------------------------------------------------------
    def EnumStreams(self) -> Generator[TextWriterT, None, None]:
        yield from self._streams

    # ----------------------------------------------------------------------
    def GetLinePrefix(
        self,
        column: int,
    ) -> str:
        return self._line_prefix_func(column)

    # ----------------------------------------------------------------------
    def GetCompleteLinePrefix(
        self,
        *,
        include_self: bool = True,
    ) -> str:
        prefixes = self._GetLinePrefixInfo(0, include_self=include_self)[1]

        return "".join(prefixes)

    # ----------------------------------------------------------------------
    @dataclass
    class YieldStdoutContext:
        stream: TextWriterT
        line_prefix: str
        persist_content: bool = field(kw_only=True)

    @contextmanager
    def YieldStdout(self) -> Iterator[YieldStdoutContext]:
        """Provides access to a stdout stream in a way that doesn't impact the indentation level maintained by a hierarchy of StreamDecorators."""

        line_prefix = self.GetCompleteLinePrefix()

        context = StreamDecorator.YieldStdoutContext(sys.stdout, line_prefix, persist_content=True)

        if not Capabilities.Get(self).is_interactive:
            with ExitStack(lambda: self.write("\n")):
                self.write("\n")
                yield context

            return

        if not self.has_stdout:
            raise Exception(
                "This functionality can only be used with streams that ultimately write to `sys.stdout`"
            )

        yield context

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    class _State(Enum):
        Prefix = auto()
        Writing = auto()
        Suffix = auto()
        Closed = auto()

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    def _write_content(
        self,
        content: str,
    ) -> int:
        chars_written = 0

        if not content:
            return chars_written

        for line, has_newline in self.__class__._EnumLines(  # pylint: disable=protected-access
            content
        ):  # pylint: disable=protected-access
            if self._col_offset == 0 and (line or self._decorate_empty_lines):
                chars_written += self._write_raw(self._line_prefix_func(self._col_offset))

            chars_written += self._write_raw(line)

            if has_newline:
                if self._col_offset != 0 or self._decorate_empty_lines:
                    chars_written += self._write_raw(self._line_suffix_func(self._col_offset))

                chars_written += self._write_raw("\n")

        return chars_written

    # ----------------------------------------------------------------------
    def _write_raw(
        self,
        content: str,
    ) -> int:
        if not content:
            return 0

        for stream in self._streams:
            try:
                stream.write(content)

            except UnicodeEncodeError as ex:
                wrote_content = False

                for decode_error_method in [
                    "surrogateescape",
                    "replace",
                    "backslashreplace",
                    "ignore",
                ]:
                    try:
                        decoded_content = content.encode("utf-8").decode("ascii", decode_error_method)
                        stream.write(decoded_content)

                        wrote_content = True
                        break
                    except UnicodeEncodeError:
                        pass

                if not wrote_content:
                    raise ex

        self._wrote_content = True

        # Find the last '\r' or '\n'
        len_content = len(content)
        index = len_content - 1

        while index >= 0:
            if content[index] in ("\r", "\n"):
                break

            index -= 1

        index += 1

        if index == 0:
            self._col_offset += len(content)
        else:
            self._col_offset = len(content[index:])

        return len(content)

    # ----------------------------------------------------------------------
    @staticmethod
    def _EnumLines(
        content: str,
    ) -> Generator[tuple[str, bool], None, None]:
        # Scenarios:
        #   '\n' => ['']
        #   'a' => ['a']
        #   'a\nb' => ['a', 'b']
        #   'a\nb\n' => ['a', 'b', '']

        lines: list[str] = content.split("\n")

        if len(lines) == 1:
            has_newline = not lines[0]

            yield lines[0], has_newline
            return

        if not lines[-1]:
            final_newline = True
            del lines[-1]
        else:
            final_newline = False

        last_index = len(lines) - 1

        for index, line in enumerate(lines):
            has_newline = index < last_index or final_newline

            yield line, has_newline

    # ----------------------------------------------------------------------
    def _GetLinePrefixInfo(
        self,
        column: int,
        *,
        include_self: bool,
    ) -> tuple[
        int,
        list[str],
    ]:  # column offset  # prefix values
        if not self._streams:
            return column, []

        if isinstance(self._streams[0], StreamDecorator):
            column, prefixes = self._streams[  # pylint: disable=protected-access
                0
            ]._GetLinePrefixInfo(  # pylint: disable=protected-access
                column, include_self=True
            )
        else:
            prefixes = []

        if include_self:
            prefix = self.GetLinePrefix(column)
            if prefix:
                prefixes.append(prefix)
                column += len(prefix)

        return column, prefixes
