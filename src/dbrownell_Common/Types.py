# ----------------------------------------------------------------------
# |
# |  Types.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-19 19:59:41
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Common type-related functionality"""

import sys

from typing import Optional, TypeVar


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
TypeT = TypeVar("TypeT")


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def extension(func):  # pylint: disable=invalid-name
    """\
    Decorator that indicates that the method is a method that is intended to be extended by derived
    classes to override functionality if necessary.

    This decorator does not add any functionality, but serves as documentation that communicates
    intentions behind how the class is intended to be used.
    """

    return func


# ----------------------------------------------------------------------
if sys.version_info[0] > 3 and sys.version_info[1] >= 12:
    from typing import override as override_impl

    override = override_impl
else:

    def override(func):  # pylint: disable=invalid-name
        """\
        Decorator that indicates that the method is a method that overrides an abstract- or extension-
        method in a base class.

        This decorator does not add any functionality, but serves as documentation that communicates
        intentions behind how the class is intended to be used.
        """

        return func


# ----------------------------------------------------------------------
def EnsureValid(
    value: Optional[TypeT],
) -> TypeT:
    """Ensures that an optional value is not None and return it."""

    if value is None:
        raise ValueError("Invalid value")

    return value


# ----------------------------------------------------------------------
def EnsureValidList(
    value: Optional[list[TypeT]],
) -> list[TypeT]:
    """Ensures that a list is None or not empty and returns a list."""

    if value is None:
        return []

    if not value:
        raise ValueError("Invalid value")

    return value
