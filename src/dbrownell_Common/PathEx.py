# ----------------------------------------------------------------------
# |
# |  PathEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-12 23:12:24
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Extensions to Path"""

import os
import tempfile

from pathlib import Path, PurePath
from typing import Optional


# ----------------------------------------------------------------------
def CreateTempFileName(
    suffix: Optional[str] = None,
) -> Path:
    filename_handle, filename = tempfile.mkstemp(suffix=suffix)

    os.close(filename_handle)
    os.remove(filename)

    return Path(filename)


# ----------------------------------------------------------------------
def CreateTempDirectory(
    suffix: Optional[str] = None,
) -> Path:
    directory = CreateTempFileName(suffix=suffix)

    directory.mkdir(parents=True, exist_ok=True)

    return directory


# ----------------------------------------------------------------------
def EnsureExists(
    path: Optional[Path],
) -> Path:
    if path is None:
        raise ValueError("Value is None")

    if not path.exists():
        raise ValueError("'{}' does not exist.".format(path))

    return path


# ----------------------------------------------------------------------
def EnsureFile(
    path: Optional[Path],
) -> Path:
    EnsureExists(path)
    assert path is not None

    if not path.is_file():
        raise ValueError("'{}' is not a file.".format(path))

    return path


# ----------------------------------------------------------------------
def EnsureDir(
    path: Optional[Path],
) -> Path:
    EnsureExists(path)
    assert path is not None

    if not path.is_dir():
        raise ValueError("'{}' is not a directory.".format(path))

    return path


# ----------------------------------------------------------------------
def IsDescendant(
    query: PurePath,
    root: PurePath,
) -> bool:
    """Returns True if `query` is a descendant of `root`."""

    try:
        for query_part, root_part in zip(query.parts[: len(root.parts)], root.parts, strict=True):
            if query_part != root_part:
                return False
    except ValueError:
        return False

    return True


# ----------------------------------------------------------------------
def CreateRelativePath(
    origin_path: PurePath,
    dest_path: PurePath,
) -> PurePath:
    """Returns a path to navigate from the origin to the destination."""

    len_origin_path_parts = len(origin_path.parts)
    len_dest_path_parts = len(dest_path.parts)

    # Find all of the path parts that match
    min_length = min(len_origin_path_parts, len_dest_path_parts)

    matching_index = 0

    while matching_index < min_length:
        if origin_path.parts[matching_index] != dest_path.parts[matching_index]:
            break

        matching_index += 1

    relative_path = PurePath(".")

    if matching_index < len_origin_path_parts:
        relative_path = relative_path.joinpath(
            *(
                [
                    "..",
                ]
                * (len_origin_path_parts - matching_index)
            )
        )

    if matching_index < len_dest_path_parts:
        relative_path = relative_path.joinpath(*dest_path.parts[matching_index:])

    return relative_path


# ----------------------------------------------------------------------
def GetCommonPath(
    *path_args: Path,
) -> Optional[Path]:
    paths = [path.resolve() for path in path_args]

    if len(paths) == 1:
        if paths[0].is_dir():
            return paths[0]

        return paths[0].parent

    part_index = 0

    while True:
        is_match = True

        if part_index > len(paths[0].parts) - 1:
            break

        for path in paths[1:]:
            if part_index > len(path.parts) - 1 or path.parts[part_index] != paths[0].parts[part_index]:
                is_match = False
                break

        if not is_match:
            break

        part_index += 1

    if part_index == 0:
        return None

    return Path(*paths[0].parts[:part_index])


# ----------------------------------------------------------------------
def GetSizeDisplay(
    path_or_num_bytes: Path | int,
):
    if isinstance(path_or_num_bytes, Path):
        num_bytes = float(path_or_num_bytes.stat().st_size)
    elif isinstance(path_or_num_bytes, int):
        num_bytes = float(path_or_num_bytes)
    else:
        assert False, path_or_num_bytes  # pragma: no cover

    if num_bytes < 1024.0:
        return "{} B".format(int(num_bytes))

    num_bytes /= 1024.0

    for unit in [
        "K",
        "M",
        "G",
        "T",
        "P",
        "E",
        "Z",
    ]:
        if num_bytes < 1024.0:
            return "{:.1f} {}B".format(num_bytes, unit)

        num_bytes /= 1024.0

    return "{:.1f} YiB".format(num_bytes)


# ----------------------------------------------------------------------
def GetUserDirectory() -> Path:
    if os.name == "nt":
        home_drive = os.getenv("HOMEDRIVE")
        home_path = os.getenv("HOMEPATH")

        if home_drive is not None and home_path is not None:
            return Path(home_drive) / home_path

        assert home_path is not None
        return Path(home_path)

    return Path(os.path.expanduser("~"))
