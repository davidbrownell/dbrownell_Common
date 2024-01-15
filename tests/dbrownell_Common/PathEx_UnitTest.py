# ----------------------------------------------------------------------
# |
# |  PathEx_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-12 23:13:51
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Unit tests for PathEx.py"""

from dbrownell_Common.PathEx import *


# ----------------------------------------------------------------------
def test_CreateTempFilename():
    temp_filename = CreateTempFileName()

    assert temp_filename.suffix == ""
    assert not temp_filename.exists()
    assert temp_filename.parent.is_dir()

    temp_filename = CreateTempFileName(".txt")

    assert temp_filename.suffix == ".txt"


# ----------------------------------------------------------------------
def test_CreateTempDirectory():
    temp_directory = CreateTempDirectory()

    assert temp_directory.is_dir()
