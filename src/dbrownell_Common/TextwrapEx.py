# ----------------------------------------------------------------------
# |
# |  TextwrapEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-19 15:40:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Enhancements for the textwrap library."""

import math
import textwrap

from typing import Callable, Optional


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
# Normally, I'd use colorama for these values, but this package cannot have any
# external dependencies.
BRIGHT_RED_COLOR_ON                         = "\033[31;1m"  # Red / Bright
BRIGHT_GREEN_COLOR_ON                       = "\033[32;1m"  # Green / Bright
BRIGHT_YELLOW_COLOR_ON                      = "\033[33;1m"  # Yellow / Bright

BRIGHT_WHITE_COLOR_ON                       = "\033[37;1m"  # White / Bright
DIM_WHITE_COLOR_ON                          = "\033[;7m"    # Inverse video

# ----------------------------------------------------------------------
ERROR_COLOR_ON                              = BRIGHT_RED_COLOR_ON
INFO_COLOR_ON                               = DIM_WHITE_COLOR_ON
SUCCESS_COLOR_ON                            = BRIGHT_GREEN_COLOR_ON
WARNING_COLOR_ON                            = BRIGHT_YELLOW_COLOR_ON
VERBOSE_COLOR_ON                            = DIM_WHITE_COLOR_ON
DEBUG_COLOR_ON                              = BRIGHT_WHITE_COLOR_ON

# ----------------------------------------------------------------------
COLOR_OFF                                   = "\033[0m" # Reset


# ----------------------------------------------------------------------
def _CreateCustomPrefixFunc(
    header: str,
    color_value: str,
) -> Callable[
    [
        bool,                               # supports_colors
    ],
    str
]:
    # ----------------------------------------------------------------------
    def Impl(
        supports_colors: bool,
    ) -> str:
        if supports_colors:
            this_color_on = color_value
            this_color_off = COLOR_OFF
        else:
            this_color_on = ""
            this_color_off = ""

        return "{}{}:{} ".format(this_color_on, header, this_color_off)

    # ----------------------------------------------------------------------

    return Impl


# ----------------------------------------------------------------------
CreateErrorPrefix                           = _CreateCustomPrefixFunc("ERROR", ERROR_COLOR_ON)
CreateWarningPrefix                         = _CreateCustomPrefixFunc("WARNING", WARNING_COLOR_ON)
CreateInfoPrefix                            = _CreateCustomPrefixFunc("INFO", INFO_COLOR_ON)
CreateSuccessPrefix                         = _CreateCustomPrefixFunc("SUCCESS", SUCCESS_COLOR_ON)
CreateVerbosePrefix                         = _CreateCustomPrefixFunc("VERBOSE", VERBOSE_COLOR_ON)
CreateDebugPrefix                           = _CreateCustomPrefixFunc("DEBUG", DEBUG_COLOR_ON)

del _CreateCustomPrefixFunc


# ----------------------------------------------------------------------
def CreateErrorText(
    value: str,
    *,
    supports_colors: bool=True,
    decorate_every_line: bool=False,
) -> str:
    return _CreateText(CreateErrorPrefix, value, supports_colors=supports_colors, decorate_every_line=decorate_every_line)


# ----------------------------------------------------------------------
def CreateWarningText(
    value: str,
    *,
    supports_colors: bool=True,
    decorate_every_line: bool=False,
) -> str:
    return _CreateText(CreateWarningPrefix, value, supports_colors=supports_colors, decorate_every_line=decorate_every_line)


# ----------------------------------------------------------------------
def CreateInfoText(
    value: str,
    *,
    supports_colors: bool=True,
    decorate_every_line: bool=False,
) -> str:
    return _CreateText(CreateInfoPrefix, value, supports_colors=supports_colors, decorate_every_line=decorate_every_line)


# ----------------------------------------------------------------------
def CreateSuccessText(
    value: str,
    *,
    supports_colors: bool=True,
    decorate_every_line: bool=False,
) -> str:
    return _CreateText(CreateSuccessPrefix, value, supports_colors=supports_colors, decorate_every_line=decorate_every_line)


# ----------------------------------------------------------------------
def CreateVerboseText(
    value: str,
    *,
    supports_colors: bool=True,
    decorate_every_line: bool=False,
) -> str:
    return _CreateText(CreateVerbosePrefix, value, supports_colors=supports_colors, decorate_every_line=decorate_every_line)


# ----------------------------------------------------------------------
def CreateDebugText(
    value: str,
    *,
    supports_colors: bool=True,
    decorate_every_line: bool=False,
) -> str:
    return _CreateText(CreateDebugPrefix, value, supports_colors=supports_colors, decorate_every_line=decorate_every_line)


# ----------------------------------------------------------------------
def CreateStatusText(
    succeeded: Optional[int],
    failed: Optional[int],
    warnings: Optional[int],
    *,
    supports_colors: bool=True,
) -> str:
    """Returns text that contains information for the number of succeeded, failed, and warning items which is useful when displaying status information."""

    if supports_colors:
        success_on = SUCCESS_COLOR_ON
        failed_on = ERROR_COLOR_ON
        warning_on = WARNING_COLOR_ON
        color_off = COLOR_OFF
    else:
        success_on = ""
        failed_on = ""
        warning_on = ""
        color_off = ""

    parts: list[str] = []

    if succeeded is not None:
        if succeeded == 0:
            prefix = "0"
        else:
            prefix = "{}{}{}".format(success_on, succeeded, color_off)

        parts.append("{} succeeded".format(prefix))

    if failed is not None:
        if failed == 0:
            prefix = "0"
        else:
            prefix = "{}{}{}".format(failed_on, failed, color_off)

        parts.append("{} failed".format(prefix))

    if warnings is not None:
        if warnings == 0:
            prefix = "0"
        else:
            prefix = "{}{}{}".format(warning_on, warnings, color_off)

        parts.append("{} warnings".format(prefix))

    value = ", ".join(parts)

    return value


# ----------------------------------------------------------------------
def Indent(
    value: str,
    indentation: str | int,
    *,
    skip_first_line: bool=False,
) -> str:
    """Ensures that each line in the provided value contains  the specified indentation."""

    if isinstance(indentation, int):
        indentation = " " * indentation
    elif isinstance(indentation, str):
        # Nothing to do here
        pass
    else:
        assert False, indentation  # pragma: no cover

    if skip_first_line:
        is_first_line = True

        # ----------------------------------------------------------------------
        def ShouldIndent(_) -> bool:
            nonlocal is_first_line

            if is_first_line:
                is_first_line = False
                return False

            return True

        # ----------------------------------------------------------------------

        should_indent = ShouldIndent
    else:
        should_indent = lambda _: True

    assert isinstance(indentation, str), indentation
    return textwrap.indent(
        value,
        indentation,
        lambda content: not content.isspace() and should_indent(content),
    )


# ----------------------------------------------------------------------
def BoundedLJust(
    value: str,
    length: int,
) -> str:
    """\
    Returns a string that is length chars long. Content will be left-justified or
    trimmed (with an ellipsis) if necessary.
    """

    len_value = len(value)

    if len_value < length:
        value = value.ljust(length)
    elif len_value > length:
        chars_to_trim = (len_value - length + 3) / 2
        midpoint = math.floor(len_value / 2)

        # Ensure a consistent ellipsis placement
        if not length & 1 and not len_value & 1:
            midpoint -= 1

        value = "{}...{}".format(
            value[:(midpoint - math.floor(chars_to_trim))],
            value[(midpoint + math.ceil(chars_to_trim)):],
        )

    return value


# ----------------------------------------------------------------------
def CreateAnsiHyperLink(
    url: str,
    value: str,
) -> str:
    return "\033]8;;{}\033\\{}\033]8;;\033\\".format(url, value)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _CreateText(
    create_prefix_func: Callable[
        [
            bool,                           # supports_colors
        ],
        str
    ],
    value: str,
    *,
    supports_colors: bool,
    decorate_every_line: bool,
) -> str:
    prefix = create_prefix_func(supports_colors)

    if decorate_every_line:
        return Indent(value, prefix)

    # Put newlines before the header
    starting_index = 0

    while starting_index < len(value) and value[starting_index] == "\n":
        starting_index += 1

    return "{}{}".format(
        value[:starting_index],
        Indent(
            "{}{}".format(prefix, value[starting_index:]),
            # The indent is the length of the prefix without color decorations
            len(create_prefix_func(False)),
            skip_first_line=True,
        ),
    )
