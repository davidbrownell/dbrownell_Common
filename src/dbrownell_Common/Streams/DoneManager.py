# ----------------------------------------------------------------------
# |
# |  DoneManager.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-19 10:50:59
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Contains functionality used with DoneManager objects"""

import datetime
import itertools
import os
import sys
import time
import traceback

from contextlib import contextmanager
from dataclasses import dataclass, field, InitVar
from enum import auto, Flag
from types import TracebackType
from typing import Any, Callable, Iterator, Optional, Protocol, Type as PythonType

from dbrownell_Common.ContextlibEx import ExitStack
from dbrownell_Common import TextwrapEx
from dbrownell_Common.Streams.Capabilities import Capabilities
from dbrownell_Common.Streams.StreamDecorator import StreamDecorator, TextWriterT


# ----------------------------------------------------------------------
DISPLAYED_EXCEPTION_ATTRIBUTE_NAME: str = "_done_manager_displayed_exception___"


# ----------------------------------------------------------------------
# |  Optional Functionality if typer is installed
try:
    _original_exception_hook = None  # pylint: disable=invalid-name

    # ----------------------------------------------------------------------
    def _ExceptionHook(
        exc_type: PythonType[BaseException],
        exc_value: BaseException,
        tb: Optional[TracebackType],
    ) -> Any:
        if getattr(exc_value, DISPLAYED_EXCEPTION_ATTRIBUTE_NAME, False):
            return

        assert _original_exception_hook is not None
        _original_exception_hook(exc_type, exc_value, tb)

    # ----------------------------------------------------------------------

    # This environment name is defined by typer. Setting it signals that typer
    # should not inject its own exception hook.
    os.environ["_TYPER_STANDARD_TRACEBACK"] = "1"

    # Monkey-patch typer's _original_except_hook if typer has already been imported
    if "typer" in sys.modules:
        typer = sys.modules["typer"]

        _original_exception_hook = (
            typer.main._original_except_hook  # pylint: disable=protected-access
        )  # pylint: disable=protected-access
        typer.main._original_except_hook = _ExceptionHook  # pylint: disable=protected-access
    else:
        _original_exception_hook = sys.excepthook
        sys.excepthook = _ExceptionHook

        import typer

    from click.exceptions import ClickException

    # ----------------------------------------------------------------------
    def ExitWithTyper(
        result: int,
    ) -> None:
        raise typer.Exit(result)

    # ----------------------------------------------------------------------
    def ShouldRaiseExceptionWithTyper(
        exception: Exception,
    ) -> bool:
        return isinstance(exception, (typer.Exit, typer.Abort, ClickException))

    # ----------------------------------------------------------------------

    Exit = ExitWithTyper
    ShouldRaiseException = ShouldRaiseExceptionWithTyper

except ImportError:
    # ----------------------------------------------------------------------
    class ExitException(Exception):
        """Exception generated in place of a call to sys.exit."""

        # ----------------------------------------------------------------------
        def __init__(
            self,
            result: int,
        ):
            self.result = result

            super(ExitException, self).__init__(
                "The process is returning with a result of '{}'.".format(result)
            )

    # ----------------------------------------------------------------------
    def ExitNoTyper(
        result: int,
    ):
        raise ExitException(result)

    # ----------------------------------------------------------------------
    def ShouldRaiseExceptionNoTyper(
        exception: Exception,  # pylint: disable=unused-argument
    ) -> bool:
        return False

    # ----------------------------------------------------------------------

    Exit = ExitNoTyper
    ShouldRaiseException = ShouldRaiseExceptionNoTyper


# ----------------------------------------------------------------------
# |  Optional functionality if rich is installed
try:
    import rich

    # ----------------------------------------------------------------------
    def ShowCursorWithRich(
        show: bool,
    ) -> None:
        rich.get_console().show_cursor(show)

    # ----------------------------------------------------------------------

    ShowCursor = ShowCursorWithRich

except ImportError:
    # ----------------------------------------------------------------------
    def ShowCursorNoRich(
        show: bool,  # pylint: disable=unused-argument
    ) -> None:
        pass

    # ----------------------------------------------------------------------

    ShowCursor = ShowCursorNoRich


# ----------------------------------------------------------------------
class DoneManagerException(Exception):
    """Exception whose call stack is not displayed when caught within an active DoneManager."""

    pass  # pylint: disable=unnecessary-pass


# ----------------------------------------------------------------------
class Flags(Flag):
    """Flags used to filter the output for a DoneManager"""

    VerboseFlag = auto()
    DebugFlag = auto()

    # Amalgamations
    Standard = 0
    Verbose = VerboseFlag
    Debug = VerboseFlag | DebugFlag

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        *,
        verbose: bool = False,
        debug: bool = False,
    ) -> "Flags":
        if debug:
            flag = cls.Debug
        elif verbose:
            flag = cls.Verbose
        else:
            flag = cls.Standard

        return flag


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Args:
    """Arguments provided when creating DoneManager instances"""

    # ----------------------------------------------------------------------
    # |
    # |  Public Data
    # |
    # ----------------------------------------------------------------------
    heading_param: InitVar[str]
    heading: str = field(init=False)

    done_suffix_or_suffixes: InitVar[
        None | Callable[[], Optional[str]] | list[Callable[[], Optional[str]]]
    ] = None
    done_suffixes: list[Callable[[], Optional[str]]] = field(init=False)

    prefix: None | str | Callable[[], Optional[str]] = field(kw_only=True, default=None)
    suffix: None | str | Callable[[], Optional[str]] = field(kw_only=True, default=None)

    line_prefix: Optional[StreamDecorator.PrefixOrSuffixT] = field(kw_only=True, default="  ")

    display: bool = field(kw_only=True, default=True)  # Display done information
    display_result: bool = field(kw_only=True, default=True)  # Display the result
    display_time: bool = field(kw_only=True, default=True)  # Display the time delta

    display_exceptions: bool = field(
        kw_only=True, default=True
    )  # Display exceptions when they are encountered; exceptions will percolate if not displayed.
    display_exception_details: bool = field(
        kw_only=True, default=False
    )  # Do not display exception details (such as the call stack)
    suppress_exceptions: bool = field(kw_only=False, default=False)  # Do not let exceptions propagate

    preserve_status: bool = field(kw_only=True, default=True)

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __post_init__(
        self,
        heading_param: str,
        done_suffix_or_suffixes: (None | Callable[[], Optional[str]] | list[Callable[[], Optional[str]]]),
    ) -> None:
        if done_suffix_or_suffixes is None:
            suffixes = []
        elif isinstance(done_suffix_or_suffixes, list):
            suffixes = done_suffix_or_suffixes
        else:
            suffixes = [
                done_suffix_or_suffixes,
            ]

        object.__setattr__(self, "done_suffixes", suffixes)

        if self.suppress_exceptions and not self.display_exceptions:
            raise Exception("Exceptions should not be suppressed when they are not displayed.")

        if not self.display:
            object.__setattr__(self, "line_prefix", None)

        heading = "{}{}".format(
            heading_param.rstrip("\n").rstrip("..."),
            "..." if self.display and heading_param and self.line_prefix else "",
        )

        object.__setattr__(self, "heading", heading)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class TopLevelArgs(Args):
    """Arguments when creating top-level/non-nested DoneManager instances"""

    # ----------------------------------------------------------------------
    flags: Flags = field(kw_only=True, default=Flags.Standard)
    num_cols: int = field(kw_only=True, default=Capabilities.DEFAULT_COLUMNS)


# ----------------------------------------------------------------------
@dataclass
class DoneManager:
    """Object that helps when writing nested output."""

    # ----------------------------------------------------------------------
    result: int = field(init=False, default=0)

    _stream: StreamDecorator

    flags: Flags = field(kw_only=True)
    heading: str = field(kw_only=True)
    preserve_status: bool = field(kw_only=True)

    num_cols: int = field(kw_only=True)

    _line_prefix: str = field(init=False)
    _status_line_prefix: str = field(init=False)
    _num_status_cols: int = field(init=False)

    _wrote_content: bool = field(init=False, default=False)
    _wrote_status: bool = field(init=False, default=False)
    _prev_status_content: list[str] = field(init=False, default_factory=list)

    # ----------------------------------------------------------------------
    @classmethod
    @contextmanager
    def Create(
        cls,
        stream: TextWriterT,
        *top_level_args,  # See `TopLevelArgs`
        **top_level_kwargs,  # See `TopLevelArgs`
    ) -> Iterator["DoneManager"]:
        args = TopLevelArgs(*top_level_args, **top_level_kwargs)

        with cls._CreateImpl(
            stream,
            args,
            flags=args.flags,
            num_cols=args.num_cols,
        ) as dm:
            try:
                yield dm
            finally:
                ShowCursor(True)

    # ----------------------------------------------------------------------
    @classmethod
    @contextmanager
    def CreateCommandLine(
        cls,
        stream: TextWriterT = sys.stdout,
        *,
        flags: Flags = Flags.Standard,
        display: bool = True,
        **kwargs,
    ) -> Iterator["DoneManager"]:
        """Creates a DoneManager instance suitable for use with command-line functionality."""

        if display:
            prefix = "\nResults: "
            suffix = "\n"
        else:
            prefix = ""
            suffix = ""

        with cls.Create(
            stream,
            "\n",
            line_prefix="",
            prefix=prefix,
            suffix=suffix,
            flags=flags,
            display=display,
            **kwargs,
        ) as dm:
            is_exceptional = False

            try:
                yield dm

            except:
                is_exceptional = True
                raise

            finally:
                if not is_exceptional:
                    Exit(dm.result)

    # ----------------------------------------------------------------------
    @property
    def is_verbose(self) -> bool:
        return bool(self.flags & Flags.VerboseFlag)

    @property
    def is_debug(self) -> bool:
        return bool(self.flags & Flags.DebugFlag)

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities.Get(self._stream)

    # ----------------------------------------------------------------------
    def isatty(self) -> bool:
        return self._stream.isatty()

    # ----------------------------------------------------------------------
    def ExitOnError(self) -> None:
        """Exits if the result is < 0"""

        if self.result < 0:
            Exit(self.result)

    # ----------------------------------------------------------------------
    def ExitOnWarning(self) -> None:
        """Exits if the result is > 0"""

        if self.result > 0:
            Exit(self.result)

    # ----------------------------------------------------------------------
    def WriteLine(
        self,
        content: str,
    ) -> None:
        """Writes a line without decoration; status information is preserved or cleared based on the `preserve_status` flag."""

        # ----------------------------------------------------------------------
        def CreateStandardText(
            value: str,
            *,
            supports_colors: bool = True,  # pylint: disable=unused-argument
            decorate_every_line: bool = False,  # pylint: disable=unused-argument
        ) -> str:
            return value

        # ----------------------------------------------------------------------

        self._WriteImpl(CreateStandardText, content)

    # ----------------------------------------------------------------------
    def WriteSuccess(
        self,
        content: str,
    ) -> None:
        """Writes a line decorated with a success prefix; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(TextwrapEx.CreateSuccessText, content)

    # ----------------------------------------------------------------------
    def WriteError(
        self,
        content: str,
        *,
        update_result: bool = True,
    ) -> None:
        """Writes a line decorated with an error prefix; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(TextwrapEx.CreateErrorText, content)

        if update_result and self.result >= 0:
            self.result = -1

    # ----------------------------------------------------------------------
    def WriteWarning(
        self,
        content: str,
        *,
        update_result: bool = True,
    ) -> None:
        """Writes a line decorated with a warning prefix; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(TextwrapEx.CreateWarningText, content)

        if update_result and self.result == 0:
            self.result = 1

    # ----------------------------------------------------------------------
    def WriteInfo(
        self,
        content: str,
    ) -> None:
        """Writes a line decorated with an info prefix; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(TextwrapEx.CreateInfoText, content)

    # ----------------------------------------------------------------------
    def WriteVerbose(
        self,
        content: str,
    ) -> None:
        """\
        Writes verbose content if the verbose flag is set. Use this functionality when you want
        only the first line to include the verbose decorator. Use `YieldVerboseStream` when you
        want every line to include the verbose decorator.

        Status information is preserved or cleared based on the `preserve_status` flag.
        """

        if self.is_verbose:
            self._WriteImpl(TextwrapEx.CreateVerboseText, content)

    # ----------------------------------------------------------------------
    def WriteDebug(
        self,
        content: str,
    ) -> None:
        """\
        Writes debug content if the debug flag is set. Use this functionality when you want
        only the first line to include the debug decorator. Use `YieldDebugStream` when you
        want every line to include the debug decorator.

        Status information is preserved or cleared based on the `preserve_status` flag.
        """

        if self.is_debug:
            self._WriteImpl(TextwrapEx.CreateDebugText, content)

    # ----------------------------------------------------------------------
    def WriteStatus(
        self,
        content: str,
    ) -> None:
        """\
        Writes status information; status information is temporal, and is replaced each time new
        status is added.
        """

        self._WriteStatus(content)

    # ----------------------------------------------------------------------
    def ClearStatus(self) -> None:
        """Clears any status information currently displayed"""

        if self._prev_status_content:
            self._WriteStatus("", update_prev_status=False)
            self._prev_status_content = []

    # ----------------------------------------------------------------------
    def PreserveStatus(self) -> None:
        """Persists any status information currently displayed so that it will not be overwritten"""

        if self._prev_status_content:
            # Move the cursor back to where it would be after writing the status messages normally.
            self._stream.write("\033[{}B".format(len(self._prev_status_content)))
            self._stream.write("\r")

            self._prev_status_content = []

    # ----------------------------------------------------------------------
    @contextmanager
    def Nested(
        self,
        *args,  # See `Args`
        **kwargs,  # See `Args`
    ) -> Iterator["DoneManager"]:
        """Creates a nested DoneManager"""

        with self.YieldStream() as stream:
            with self._CreateNestedImpl(stream, *args, **kwargs) as dm:
                yield dm

    # ----------------------------------------------------------------------
    @contextmanager
    def VerboseNested(
        self,
        *args,  # See `Args`
        **kwargs,  # See `Args`
    ) -> Iterator["DoneManager"]:
        """Creates a nested DoneManager if the verbose flag is set"""

        with self.YieldVerboseStream() as verbose_stream:
            with self._CreateNestedImpl(verbose_stream, *args, **kwargs) as dm:
                yield dm

    # ----------------------------------------------------------------------
    @contextmanager
    def DebugNested(
        self,
        *args,  # See `Args`
        **kwargs,  # See `Args`
    ) -> Iterator["DoneManager"]:
        """Creates a nested DoneManager if the debug flag is set"""

        with self.YieldDebugStream() as debug_stream:
            with self._CreateNestedImpl(debug_stream, *args, **kwargs) as dm:
                yield dm

    # ----------------------------------------------------------------------
    @contextmanager
    def YieldStream(self) -> Iterator[StreamDecorator]:
        """Provides scoped access to the underlying stream; writing to this stream will include line prefixes"""

        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

        yield self._stream
        self._stream.flush()

    # ----------------------------------------------------------------------
    @contextmanager
    def YieldVerboseStream(self) -> Iterator[StreamDecorator]:
        """\
        Provides scoped access to a verbose-version of the underlying stream; writing to this
        stream will include verbose line prefixes. Use this functionality when you want all
        lines to have the verbose prefix decorator. Use `WriteVerbose` when you only want the
        first line to include the decorator.
        """

        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

        if self.is_verbose:
            stream = StreamDecorator(
                self._stream,
                line_prefix=TextwrapEx.CreateVerbosePrefix(Capabilities.Get(self._stream).supports_colors),
                decorate_empty_lines=True,
            )
        else:
            stream = StreamDecorator(None)

        yield stream

        if stream.wrote_content:
            self._wrote_content = True
            stream.flush()

    # ----------------------------------------------------------------------
    @contextmanager
    def YieldDebugStream(self) -> Iterator[StreamDecorator]:
        """\
        Provides scoped access to a debug-version of the underlying stream; writing to this
        stream will include debug line prefixes. Use this functionality when you want all
        lines to have the debug prefix decorator. Use `WriteDebug` when you only want the
        first line to include the decorator.
        """

        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

        if self.is_debug:
            stream = StreamDecorator(
                self._stream,
                line_prefix=TextwrapEx.CreateDebugPrefix(Capabilities.Get(self._stream).supports_colors),
                decorate_empty_lines=True,
            )
        else:
            stream = StreamDecorator(None)

        yield stream

        if stream.wrote_content:
            self._wrote_content = True
            stream.flush()

    # ----------------------------------------------------------------------
    @contextmanager
    def YieldStdout(self) -> Iterator[StreamDecorator.YieldStdoutContext]:
        """\
        Provides scoped access to `sys.stdout` (if possible); writing to this stream will NOT include line prefixes.

        Note that the cursor should be restored to its original location (when yielded by
        this generator) when control is restored to this generator and the `persist_content`
        is set to False.
        """

        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

        is_interactive = self.capabilities.is_interactive

        with self._stream.YieldStdout() as context:
            try:
                if not self._wrote_content:
                    context.stream.write("\n")

                yield context

            finally:
                # We need to get the cursor back to where it was before we
                # yielded the stream. This logic depends upon if anything
                # had been written using this DoneManager before the stream
                # was yielded and if the caller wants to preserve anything
                # that was written.
                if context.stream is sys.stdout:
                    if is_interactive:
                        sys.stdout.write("\r")

                    if context.persist_content:
                        if self._wrote_content:
                            sys.stdout.write("\n")

                        sys.stdout.write(self._line_prefix)

                    elif is_interactive and not context.persist_content and not self._wrote_content:
                        # Move up a line, write the whitespace and heading
                        sys.stdout.write(
                            "\033[1A{}{}".format(self._line_prefix, self.heading),
                        )
                        sys.stdout.flush()

    # ----------------------------------------------------------------------
    def __post_init__(self):
        self._line_prefix = self._stream.GetCompleteLinePrefix(include_self=False)
        self._status_line_prefix = self._line_prefix + self._stream.GetLinePrefix(len(self._line_prefix))

        complete_line_prefix = self._stream.GetCompleteLinePrefix(include_self=True)
        len_complete_line_prefix = len(complete_line_prefix)

        assert self.num_cols > len_complete_line_prefix, (self.num_cols, len_complete_line_prefix)
        self._num_status_cols = self.num_cols - len_complete_line_prefix

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    class _CreateDecoratedTextT(Protocol):
        def __call__(
            self,
            value: str,
            *,
            supports_colors: bool = True,
            decorate_every_line: bool = False,
        ) -> str: ...  # pragma: no cover

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @classmethod
    @contextmanager
    def _CreateImpl(
        cls,
        stream: TextWriterT,
        args: Args,
        *,
        flags: Flags,
        num_cols: int,
    ) -> Iterator["DoneManager"]:
        if args.heading:
            stream.write(args.heading)
            stream.flush()

        instance = cls(
            StreamDecorator(
                stream,
                prefix="\n" if args.heading else "",
                line_prefix=args.line_prefix,
                decorate_empty_lines=False,
            ),
            flags=flags,
            heading=args.heading,
            preserve_status=args.preserve_status,
            num_cols=num_cols,
        )

        capabilities = Capabilities.Get(stream)

        if capabilities.supports_colors:
            success_color_on = TextwrapEx.SUCCESS_COLOR_ON
            error_color_on = TextwrapEx.ERROR_COLOR_ON
            warning_color_on = TextwrapEx.WARNING_COLOR_ON
            color_off = TextwrapEx.COLOR_OFF
        else:
            success_color_on = ""
            error_color_on = ""
            warning_color_on = ""
            color_off = ""

        time_delta: Optional[str] = None
        done_suffixes: list[Callable[[], Optional[str]]] = []

        if args.display_result:
            if capabilities.supports_colors:
                # ----------------------------------------------------------------------
                def DisplayResult() -> str:
                    if instance.result < 0:
                        color_on = error_color_on
                    elif instance.result > 0:
                        color_on = warning_color_on
                    else:
                        color_on = success_color_on

                    return "{}{}{}".format(color_on, instance.result, color_off)

                # ----------------------------------------------------------------------

                display_result_func = DisplayResult
            else:
                display_result_func = lambda: str(instance.result)

            done_suffixes.append(display_result_func)

        if args.display_time:
            done_suffixes.append(lambda: str(time_delta) if time_delta is not None else "<Unknown>")

        done_suffixes += args.done_suffixes

        start_time = time.perf_counter()

        # ----------------------------------------------------------------------
        def GetStringValue(
            value: None | str | Callable[[], Optional[str]],
        ) -> Optional[str]:
            if value is None:
                return None

            if isinstance(value, str):
                return value

            if callable(value):
                return value()

            assert False, value  # pragma: no cover

        # ----------------------------------------------------------------------
        def OnExit():
            instance._OnExit()  # pylint: disable=protected-access

            # Display the prefix
            prefix_value = GetStringValue(args.prefix)
            if prefix_value is not None:
                stream.write(prefix_value)

            # Display the content
            if args.display:
                suffixes: list[str] = []

                for done_suffix in done_suffixes:
                    result = done_suffix()
                    if result is not None:
                        suffixes.append(result)

                if suffixes:
                    content = "DONE! ({})\n".format(", ".join(suffixes))
                else:
                    content = "DONE!\n"

                stream.write(content)

            # Display the suffix
            suffix_value = GetStringValue(args.suffix)
            if suffix_value is not None:
                stream.write(suffix_value)

        # ----------------------------------------------------------------------

        with ExitStack(OnExit):
            try:
                yield instance

            except Exception as ex:
                if ShouldRaiseException(ex):
                    raise

                if instance.result >= 0:
                    instance.result = -1

                if (
                    args.display_exceptions
                    # Do not display an exception that has already been displayed
                    and not getattr(ex, DISPLAYED_EXCEPTION_ATTRIBUTE_NAME, False)
                ):
                    object.__setattr__(ex, DISPLAYED_EXCEPTION_ATTRIBUTE_NAME, True)

                    if not isinstance(ex, DoneManagerException) and (
                        flags & Flags.Debug or args.display_exception_details
                    ):
                        exception_content = traceback.format_exc()
                    else:
                        exception_content = str(ex)

                    if instance._stream.col_offset != 0:
                        instance._stream.write("\n")

                    instance._stream.write(
                        TextwrapEx.CreateErrorText(
                            exception_content,
                            supports_colors=capabilities.supports_colors,
                        ),
                    )

                    instance._stream.write("\n")

                if not args.suppress_exceptions:
                    raise

            finally:
                current_time = time.perf_counter()

                assert start_time <= current_time, (start_time, current_time)

                time_delta = str(datetime.timedelta(seconds=current_time - start_time))

    # ----------------------------------------------------------------------
    @contextmanager
    def _CreateNestedImpl(
        self,
        stream: StreamDecorator,
        *args,
        **kwargs,
    ) -> Iterator["DoneManager"]:
        if "preserve_status" not in kwargs:
            kwargs["preserve_status"] = False

        with self.__class__._CreateImpl(  # pylint: disable=protected-access
            stream,
            Args(*args, **kwargs),
            flags=self.flags,
            num_cols=self.num_cols,
        ) as dm:
            try:
                yield dm
            finally:
                if (dm.result < 0 and self.result >= 0) or (dm.result > 0 and self.result == 0):
                    self.result = dm.result

    # ----------------------------------------------------------------------
    def _WriteImpl(
        self,
        create_text_func: "DoneManager._CreateDecoratedTextT",
        content: str,
    ) -> None:
        if self._prev_status_content:
            self._WriteStatus("", update_prev_status=False)

        content = create_text_func(
            content,
            supports_colors=Capabilities.Get(self._stream).supports_colors,
        )

        if not content.endswith("\n"):
            content += "\n"

        self._stream.write(content)
        self._wrote_content = True

        if self._prev_status_content:
            self._WriteStatus(self._prev_status_content, update_prev_status=False)

    # ----------------------------------------------------------------------
    def _WriteStatus(
        self,
        content: str | list[str],
        *,
        update_prev_status: bool = True,
    ) -> None:
        if not self.capabilities.is_interactive:
            return

        ShowCursor(not bool(content))

        # Prepare the content
        lines: list[str] = []
        blank_lines: list[str] = []

        if isinstance(content, list):
            lines = content
            assert not update_prev_status
        else:
            content_lines = content.split("\n")

            if not content_lines[-1]:
                del content_lines[-1]

            for line in content_lines:
                line = "{}{}".format(self._status_line_prefix, line)
                line = TextwrapEx.BoundedLJust(line, self._num_status_cols)

                lines.append("\r{}\n".format(line))

            if len(self._prev_status_content) > len(lines):
                blank_lines += [
                    "\r{}\n".format("".ljust(self._num_status_cols)),
                ] * (len(self._prev_status_content) - len(lines))

        # Write the content
        for line in itertools.chain(lines, blank_lines):
            self._stream.write(line)

        # Move the cursor up to the position that it would be in to write a standard message
        self._stream.write("\033[{}A\r".format(len(lines) + len(blank_lines)))

        self._wrote_status = True

        if update_prev_status:
            self._prev_status_content = lines

    # ----------------------------------------------------------------------
    def _OnExit(self) -> None:
        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

            if self.capabilities.is_interactive and not self._wrote_content and self._wrote_status:
                # Move up a line and recreate the heading
                self._stream.write("\033[1A\r{}{}".format(self._line_prefix, self.heading))
                self._stream.flush()
