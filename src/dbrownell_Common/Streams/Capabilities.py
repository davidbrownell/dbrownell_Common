# ----------------------------------------------------------------------
# |
# |  Capabilities.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-18 15:40:51
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Contains the Capabilities object"""

import functools
import os
import sys
import textwrap

from typing import Any, Optional, TextIO

from dbrownell_Common.Streams.TextWriter import TextWriter


# ----------------------------------------------------------------------
TextWriterT = TextIO | TextWriter


# ----------------------------------------------------------------------
@functools.total_ordering
class Capabilities:
    """Capabilities of a stream."""

    # ----------------------------------------------------------------------
    # |
    # |  Public Types
    # |
    # ----------------------------------------------------------------------
    DEFAULT_COLUMNS: int = 180

    SIMULATE_TERMINAL_COLUMNS_ENV_VAR: str = "COLUMNS"
    SIMULATE_TERMINAL_INTERACTIVE_ENV_VAR: str = "SIMULATE_TERMINAL_CAPABILITIES_IS_INTERACTIVE"
    SIMULATE_TERMINAL_COLORS_ENV_VAR: str = "SIMULATE_TERMINAL_CAPABILITIES_SUPPORTS_COLORS"
    SIMULATE_TERMINAL_HEADLESS_ENV_VAR: str = "SIMULATE_TERMINAL_CAPABILITIES_IS_HEADLESS"

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(
        self,
        *,
        columns: Optional[int] = None,
        is_headless: Optional[bool] = None,
        is_interactive: Optional[bool] = None,
        supports_colors: Optional[bool] = None,
        stream: Optional[TextWriterT] = None,
        ignore_environment: bool = False,
    ):
        # columns
        explicit_columns = False

        if columns is not None:
            explicit_columns = True
        else:
            value = (
                os.getenv(self.__class__.SIMULATE_TERMINAL_COLUMNS_ENV_VAR)
                if not ignore_environment
                else None
            )
            if value is not None:
                columns = int(value)
                explicit_columns = True
            else:
                columns = self.__class__.DEFAULT_COLUMNS
                explicit_columns = True

        # is_interactive
        explicit_is_interactive = False

        if is_interactive is not None:
            explicit_is_interactive = True
        else:
            value = (
                os.getenv(self.__class__.SIMULATE_TERMINAL_INTERACTIVE_ENV_VAR)
                if not ignore_environment
                else None
            )
            if value is not None:
                is_interactive = value != "0"
                explicit_is_interactive = True
            else:
                is_interactive = stream is not None and stream.isatty()

        # is_headless
        explicit_is_headless = False

        if is_headless is not None:
            explicit_is_headless = True
        else:
            value = (
                os.getenv(self.__class__.SIMULATE_TERMINAL_HEADLESS_ENV_VAR)
                if not ignore_environment
                else None
            )
            if value is not None:
                is_headless = value != "0"
                explicit_is_headless = True
            else:
                is_headless = not is_interactive

        # supports_colors
        explicit_supports_colors = False

        if supports_colors is not None:
            explicit_supports_colors = True
        else:
            value = (
                os.getenv(self.__class__.SIMULATE_TERMINAL_COLORS_ENV_VAR) if not ignore_environment else None
            )
            if value is not None:
                supports_colors = value != "0"
                explicit_supports_colors = True
            else:
                supports_colors = is_interactive

        # Commit the values
        self.columns = columns
        self.is_headless = is_headless
        self.is_interactive = is_interactive
        self.supports_colors = supports_colors

        self.explicit_columns = explicit_columns
        self.explicit_is_headless = explicit_is_headless
        self.explicit_is_interactive = explicit_is_interactive
        self.explicit_supports_colors = explicit_supports_colors

    # ----------------------------------------------------------------------
    @staticmethod
    def Compare(
        this: "Capabilities",
        that: "Capabilities",
    ) -> int:
        for attribute_data in [
            "columns",
            ("is_headless", True),
            "is_interactive",
            "supports_colors",
        ]:
            if isinstance(attribute_data, tuple):
                attribute_name, invert = attribute_data
            else:
                attribute_name = attribute_data
                invert = False

            this_value = getattr(this, attribute_name)
            that_value = getattr(that, attribute_name)

            if this_value != that_value:
                if invert:
                    return 1 if this_value < that_value else -1

                return -1 if this_value < that_value else 1

        return 0

    # ----------------------------------------------------------------------
    def __lt__(
        self,
        other: "Capabilities",
    ) -> bool:
        return self.Compare(self, other) < 0

    # ----------------------------------------------------------------------
    def __eq__(
        self,
        other: "Capabilities",
    ) -> bool:
        return self.Compare(self, other) == 0

    # ----------------------------------------------------------------------
    @classmethod
    def IsSet(
        cls,
        stream: TextWriterT,
    ) -> bool:
        """Return True if the capabilities have been set for the stream."""
        return getattr(stream, cls._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME, None) is not None

    # ----------------------------------------------------------------------
    @classmethod
    def Get(
        cls,
        stream: TextWriterT,
    ) -> "Capabilities":
        current_capabilities = getattr(stream, cls._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME, None)
        if current_capabilities is not None:
            return current_capabilities

        return cls(stream=stream)

    # ----------------------------------------------------------------------
    @classmethod
    def Set(
        cls,
        stream: TextWriterT,
        capabilities: "Capabilities",
        *,
        no_column_warning: bool = False,
    ) -> TextWriterT:
        if getattr(stream, cls._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME, None) is not None:
            raise Exception(
                "Capabilities have already been applied to this stream; consider using the `Clone` method."
            )

        setattr(stream, cls._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME, capabilities)

        # Validate the settings for sys.stdout
        if stream is sys.stdout and cls._processed_stdout is False:
            try:
                import rich
                from rich.console import ConsoleDimensions

                if (
                    capabilities.explicit_columns
                    or capabilities.explicit_is_headless
                    or capabilities.explicit_is_interactive
                    or capabilities.explicit_supports_colors
                ):
                    rich_args = capabilities._GetRichConsoleArgs()

                    # Width needs to be set separately
                    width_arg = rich_args.pop("width", None)

                    rich.reconfigure(**rich_args)

                    if width_arg is not None:
                        console = rich.get_console()
                        console.size = ConsoleDimensions(width_arg, console.height)

                # Validate that the width is acceptable. This has to be done AFTER
                # the capabilities have been associated with the stream.
                if not no_column_warning:
                    console = rich.get_console()

                    if console.width < cls.DEFAULT_COLUMNS:
                        # Importing here to avoid circular imports
                        from dbrownell_Common import TextwrapEx
                        from dbrownell_Common.Streams.StreamDecorator import (
                            StreamDecorator,
                        )  # pylint: disable=cyclic-import

                        StreamDecorator(
                            sys.stdout,
                            line_prefix=TextwrapEx.CreateWarningPrefix(capabilities.supports_colors),
                        ).write(
                            textwrap.dedent(
                                """\


                                Output is configured for a width of '{}', but your terminal has a width of '{}'.

                                Some formatting may not appear as intended.


                                """,
                            ).format(
                                cls.DEFAULT_COLUMNS,
                                console.width,
                            ),
                        )

            except ImportError:  # pragma: no cover
                pass  # pragma: no cover

            cls._processed_stdout = True

        return stream

    # ----------------------------------------------------------------------
    def Clone(
        self,
        *,
        columns: Optional[int] = None,
        is_headless: Optional[bool] = None,
        is_interactive: Optional[bool] = None,
        supports_colors: Optional[bool] = None,
    ) -> "Capabilities":
        return self.__class__(
            columns=columns if columns is not None else self.columns,
            is_headless=is_headless if is_headless is not None else self.is_headless,
            is_interactive=is_interactive if is_interactive is not None else self.is_interactive,
            supports_colors=(supports_colors if supports_colors is not None else self.supports_colors),
        )

    # ----------------------------------------------------------------------
    try:
        from rich.console import Console

        def CreateRichConsole(
            self,
            file: Optional[TextWriterT] = None,
            *,
            width: Optional[int] = None,
        ) -> Console:
            """Creates a `rich` `Console` instance."""

            args = self._GetRichConsoleArgs()

            # Width needs to be set separately
            width_arg = width if width is not None else args.pop("width", None)

            args["file"] = file

            from rich.console import Console, ConsoleDimensions

            result = Console(**args)

            if width_arg is not None:
                result.size = ConsoleDimensions(width_arg, result.height)

            return result

    except ImportError:
        # This means that rich wasn't found, which is OK
        pass

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    _EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME: str = "__stream_capabilities"
    _processed_stdout: bool = False

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    def _GetRichConsoleArgs(self) -> dict[str, Any]:
        """Returns arguments suitable to instantiate a rich `Console` instance."""

        args: dict[str, Any] = {
            "legacy_windows": False,
        }

        if self.explicit_columns:
            args["width"] = self.columns

        if self.explicit_is_interactive:
            args["force_interactive"] = self.is_interactive

        if self.explicit_supports_colors:
            if self.supports_colors:
                # We can't be too aggressive in the selection of a color system
                # or else the content won't display if we over-reach.
                args["color_system"] = "standard"
            else:
                args["no_color"] = True

        return args
