# ----------------------------------------------------------------------
# |
# |  Types_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-19 20:12:18
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for Types.py"""

import re

import pytest

from dbrownell_Common.Types import *


# ----------------------------------------------------------------------
def test_ExtensionAndOverride():
    # ----------------------------------------------------------------------
    class MyObject:
        @extension
        def ExtensionMethod(self) -> str:
            return "extension"

        @override
        def OverrideMethod(self) -> str:
            return "override"

    # ----------------------------------------------------------------------

    obj = MyObject()

    assert obj.ExtensionMethod() == "extension"
    assert obj.OverrideMethod() == "override"


# ----------------------------------------------------------------------
def test_EnsureValid():
    assert EnsureValid(1) == 1

    with pytest.raises(
        ValueError,
        match=re.escape("Invalid value"),
    ):
        EnsureValid(None)


# ----------------------------------------------------------------------
def test_EnsureValidList():
    assert EnsureValidList(None) == []
    assert EnsureValidList([1, 2, 3]) == [1, 2, 3]

    with pytest.raises(
        ValueError,
        match=re.escape("Invalid value"),
    ):
        EnsureValidList([])
