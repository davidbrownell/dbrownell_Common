# ----------------------------------------------------------------------
# |
# |  ContextlibEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-19 07:08:25
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
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
