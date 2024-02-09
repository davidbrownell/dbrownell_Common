# ----------------------------------------------------------------------
# |
# |  ContextlibEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-19 07:08:25
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Enhancements to the contextlib package"""

from contextlib import contextmanager, ExitStack as ExitStackImpl
from typing import Any, Callable, Iterator


# ----------------------------------------------------------------------
@contextmanager
def ExitStack(
    *args: Callable[[], Any],
) -> Iterator[Any]:
    """Utility that invokes all of the provided functions when it goes out of scope."""

    with ExitStackImpl() as exit_stack:
        for arg in args:
            exit_stack.callback(arg)

        yield exit_stack
