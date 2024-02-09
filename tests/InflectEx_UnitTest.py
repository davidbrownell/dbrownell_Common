# ----------------------------------------------------------------------
# |
# |  InflectEx_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-12 20:27:26
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for InflectEx.py"""

from dbrownell_Common.InflectEx import inflect


# ----------------------------------------------------------------------
def test_Simple():
    assert inflect.plural("test", 1) == "test"
    assert inflect.plural("test", 2) == "tests"
