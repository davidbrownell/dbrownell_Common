# ----------------------------------------------------------------------
# |
# |  ContextlibEx_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-19 16:20:35
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Unit tests for ContextlibEx.py"""

from dbrownell_Common.ContextlibEx import *


# ----------------------------------------------------------------------
def test_ExitStackEmpty():
    values = []
    with ExitStack():
        pass

    assert values == []


# ----------------------------------------------------------------------
def test_ExitStackSingle():
    values = []

    with ExitStack(
        lambda: values.append(1),
    ):
        assert values == []

    assert values == [
        1,
    ]


# ----------------------------------------------------------------------
def test_ExitStackMultiple():
    values = []

    with ExitStack(
        lambda: values.append(1),
        lambda: values.append(20),
    ):
        assert values == []

    assert values == [
        20,
        1,
    ]


# ----------------------------------------------------------------------
def test_ExitStackWithExceptions():
    values = []

    try:
        with ExitStack(
            lambda: values.append(1),
            lambda: values.append(20),
        ):
            assert values == []
            raise Exception()
    except Exception:
        pass

    assert values == [
        20,
        1,
    ]
