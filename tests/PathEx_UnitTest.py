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

import re

from pathlib import Path

import pytest

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


# ----------------------------------------------------------------------
def test_EnsureExists():
    this_file = Path(__file__)

    # Exists
    assert EnsureExists(this_file) == this_file

    # None
    with pytest.raises(
        ValueError,
        match=re.escape("Value is None"),
    ):
        EnsureExists(None)

    # Does not exist
    filename = this_file.parent / "Does Not Exist.txt"

    with pytest.raises(
        ValueError,
        match=re.escape("'{}' does not exist.".format(filename)),
    ):
        EnsureExists(filename)


# ----------------------------------------------------------------------
def test_EnsureFile():
    this_file = Path(__file__)

    # Exists
    assert EnsureFile(this_file) == this_file

    # None
    with pytest.raises(
        ValueError,
        match=re.escape("Value is None"),
    ):
        EnsureFile(None)

    # Does not exist
    filename = this_file.parent / "Does Not Exist.txt"

    with pytest.raises(
        ValueError,
        match=re.escape("'{}' does not exist.".format(filename)),
    ):
        EnsureFile(filename)

    # Not a file
    with pytest.raises(
        ValueError,
        match=re.escape("'{}' is not a file.".format(this_file.parent)),
    ):
        EnsureFile(this_file.parent)


# ----------------------------------------------------------------------
def test_EnsureDir():
    this_file = Path(__file__)

    # Exists
    assert EnsureDir(this_file.parent) == this_file.parent

    # None
    with pytest.raises(
        ValueError,
        match=re.escape("Value is None"),
    ):
        EnsureDir(None)

    # Does not exist
    filename = this_file.parent / "Does Not Exist"

    with pytest.raises(
        ValueError,
        match=re.escape("'{}' does not exist.".format(filename)),
    ):
        EnsureDir(filename)

    # Not a directory
    with pytest.raises(
        ValueError,
        match=re.escape("'{}' is not a directory.".format(this_file)),
    ):
        EnsureDir(this_file)


# ----------------------------------------------------------------------
def test_IsDescendant():
    assert IsDescendant(Path("/a/b/c"), Path("/a/b/c")) is True
    assert IsDescendant(Path("/a/b/c"), Path("/x/y/z")) is False
    assert IsDescendant(Path("/a/b/c/d/e/f"), Path("/a/b/c")) is True
    assert IsDescendant(Path("/a/b"), Path("/a/b/c")) is False


# ----------------------------------------------------------------------
def test_CreateRelativePath():
    assert CreateRelativePath(PurePath("/a/b"), PurePath("/a/c")) == PurePath("../c")
    assert CreateRelativePath(PurePath("/a/b/c"), PurePath("/a/b/d/e")) == PurePath("../d/e")
    assert CreateRelativePath(PurePath("/a/b/c"), PurePath("/x/y/z")) == PurePath("../../../x/y/z")


# ----------------------------------------------------------------------
def test_GetSizeDisplay():
    assert GetSizeDisplay(1000) == "1000.0 B"
    assert GetSizeDisplay(10000) == "9.8 KB"
    assert GetSizeDisplay(100000) == "97.7 KB"
    assert GetSizeDisplay(1000000) == "976.6 KB"
    assert GetSizeDisplay(10000000) == "9.5 MB"
    assert GetSizeDisplay(100000000) == "95.4 MB"
    assert GetSizeDisplay(1000000000) == "953.7 MB"
    assert GetSizeDisplay(10000000000) == "9.3 GB"
    assert GetSizeDisplay(100000000000000000) == "88.8 PB"
    assert GetSizeDisplay(1000000000000000000000) == "867.4 EB"
    assert GetSizeDisplay(10000000000000000000000000) == "8.3 YiB"
    assert GetSizeDisplay(1000000000000000000000000000000) == "827180.6 YiB"
    assert GetSizeDisplay(Path(__file__)) != ""
