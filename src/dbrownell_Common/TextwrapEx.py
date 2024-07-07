# ----------------------------------------------------------------------
# |
# |  TextwrapEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-19 15:40:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Enhancements for the textwrap library."""

import math
import textwrap

from enum import auto, Enum
from typing import Callable, Optional


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
# Normally, I'd use colorama for these values, but this package cannot have any
# external dependencies.
BRIGHT_RED_COLOR_ON = "\033[31;1m"  # Red / Bright
BRIGHT_GREEN_COLOR_ON = "\033[32;1m"  # Green / Bright
BRIGHT_YELLOW_COLOR_ON = "\033[33;1m"  # Yellow / Bright

BRIGHT_WHITE_COLOR_ON = "\033[37;1m"  # White / Bright
DIM_WHITE_COLOR_ON = "\033[;7m"  # Inverse video

# ----------------------------------------------------------------------
ERROR_COLOR_ON = BRIGHT_RED_COLOR_ON
INFO_COLOR_ON = DIM_WHITE_COLOR_ON
SUCCESS_COLOR_ON = BRIGHT_GREEN_COLOR_ON
WARNING_COLOR_ON = BRIGHT_YELLOW_COLOR_ON
VERBOSE_COLOR_ON = DIM_WHITE_COLOR_ON
DEBUG_COLOR_ON = BRIGHT_WHITE_COLOR_ON

# ----------------------------------------------------------------------
COLOR_OFF = "\033[0m"  # Reset


# ----------------------------------------------------------------------
class Justify(Enum):
    """Line justification"""

    # ----------------------------------------------------------------------
    Left = auto()
    Center = auto()
    Right = auto()

    # ----------------------------------------------------------------------
    def Justify(
        self,
        value: str,
        padding: int,
    ) -> str:
        if self == Justify.Left:
            return value.ljust(padding)

        if self == Justify.Center:
            return value.center(padding)

        if self == Justify.Right:
            return value.rjust(padding)

        assert False, self  # pragma: no cover


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def _CreateCustomPrefixFunc(
    header: str,
    color_value: str,
) -> Callable[
    [
        bool,
    ],
    str,
]:  # supports_colors
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
CreateErrorPrefix = _CreateCustomPrefixFunc("ERROR", ERROR_COLOR_ON)
CreateWarningPrefix = _CreateCustomPrefixFunc("WARNING", WARNING_COLOR_ON)
CreateInfoPrefix = _CreateCustomPrefixFunc("INFO", INFO_COLOR_ON)
CreateSuccessPrefix = _CreateCustomPrefixFunc("SUCCESS", SUCCESS_COLOR_ON)
CreateVerbosePrefix = _CreateCustomPrefixFunc("VERBOSE", VERBOSE_COLOR_ON)
CreateDebugPrefix = _CreateCustomPrefixFunc("DEBUG", DEBUG_COLOR_ON)

del _CreateCustomPrefixFunc


# ----------------------------------------------------------------------
def CreateErrorText(
    value: str,
    *,
    supports_colors: bool = True,
    decorate_every_line: bool = False,
) -> str:
    return _CreateText(
        CreateErrorPrefix,
        value,
        supports_colors=supports_colors,
        decorate_every_line=decorate_every_line,
    )


# ----------------------------------------------------------------------
def CreateWarningText(
    value: str,
    *,
    supports_colors: bool = True,
    decorate_every_line: bool = False,
) -> str:
    return _CreateText(
        CreateWarningPrefix,
        value,
        supports_colors=supports_colors,
        decorate_every_line=decorate_every_line,
    )


# ----------------------------------------------------------------------
def CreateInfoText(
    value: str,
    *,
    supports_colors: bool = True,
    decorate_every_line: bool = False,
) -> str:
    return _CreateText(
        CreateInfoPrefix,
        value,
        supports_colors=supports_colors,
        decorate_every_line=decorate_every_line,
    )


# ----------------------------------------------------------------------
def CreateSuccessText(
    value: str,
    *,
    supports_colors: bool = True,
    decorate_every_line: bool = False,
) -> str:
    return _CreateText(
        CreateSuccessPrefix,
        value,
        supports_colors=supports_colors,
        decorate_every_line=decorate_every_line,
    )


# ----------------------------------------------------------------------
def CreateVerboseText(
    value: str,
    *,
    supports_colors: bool = True,
    decorate_every_line: bool = False,
) -> str:
    return _CreateText(
        CreateVerbosePrefix,
        value,
        supports_colors=supports_colors,
        decorate_every_line=decorate_every_line,
    )


# ----------------------------------------------------------------------
def CreateDebugText(
    value: str,
    *,
    supports_colors: bool = True,
    decorate_every_line: bool = False,
) -> str:
    return _CreateText(
        CreateDebugPrefix,
        value,
        supports_colors=supports_colors,
        decorate_every_line=decorate_every_line,
    )


# ----------------------------------------------------------------------
def CreateStatusText(
    succeeded: Optional[int],
    failed: Optional[int],
    warnings: Optional[int],
    *,
    supports_colors: bool = True,
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
    skip_first_line: bool = False,
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
            value[: (midpoint - math.floor(chars_to_trim))],
            value[(midpoint + math.ceil(chars_to_trim)) :],
        )

    return value


# ----------------------------------------------------------------------
def CreateAnsiHyperLink(
    url: str,
    value: str,
) -> str:
    return "\033]8;;{}\033\\{}\033]8;;\033\\".format(url, value)


# ----------------------------------------------------------------------
def CreateTable(
    headers: list[str],
    all_values: list[list[str]],
    col_justifications: list[Justify] | None = None,
    decorate_values_func: Callable[[int, list[str]], list[str]] | None = None,
    on_col_sizes_calculated: Callable[[list[int]], None] | None = None,
    col_padding: str = "  ",
    *,
    decorate_headers: bool = False,
) -> str:
    """Prints a table with the provided headers and values."""

    assert col_justifications is None or len(col_justifications) == len(headers)
    assert decorate_headers is False or decorate_values_func

    col_justifications = col_justifications or [Justify.Left] * len(headers)
    decorate_values_func = decorate_values_func or (lambda _, row: row)
    on_col_sizes_calculated = on_col_sizes_calculated or (lambda _: None)

    # Calculate the col sizes
    col_sizes = [len(header) for header in headers]

    # Get the column size for each row
    for row in all_values:
        assert len(row) == len(headers)
        for index, col_value in enumerate(row):
            col_sizes[index] = max(len(col_value), col_sizes[index])

    on_col_sizes_calculated(col_sizes)

    # Create the template
    row_template = col_padding.join(
        "{{:<{}}}".format(col_size) if col_size != 0 else "{}" for col_size in col_sizes
    )

    # Create the rows
    rows: list[str] = []

    # ----------------------------------------------------------------------
    def CreateRow(
        index: int,
        values: list[str],
    ) -> None:
        decorated_values: list[str] = []

        for col_justification, col_value, col_size in zip(col_justifications, values, col_sizes):
            decorated_values.append(col_justification.Justify(col_value, col_size))

        if index >= 0 or decorate_headers:
            decorated_values = decorate_values_func(index, decorated_values)

        rows.append(row_template.format(*decorated_values).rstrip())

    # ----------------------------------------------------------------------

    CreateRow(-2, headers)
    CreateRow(-1, ["-" * col_size for col_size in col_sizes])

    for index, values in enumerate(all_values):
        CreateRow(index, values)

    return "\n".join(rows) + "\n"


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _CreateText(
    create_prefix_func: Callable[
        [
            bool,  # supports_colors
        ],
        str,
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
