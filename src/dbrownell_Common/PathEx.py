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
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Extensions to Path"""

import os
import tempfile

from pathlib import Path
from typing import Optional


# ----------------------------------------------------------------------
def CreateTempFileName(
    suffix: Optional[str]=None,
) -> Path:
    filename_handle, filename = tempfile.mkstemp(suffix=suffix)

    os.close(filename_handle)
    os.remove(filename)

    return Path(filename)


# ----------------------------------------------------------------------
def CreateTempDirectory(
    suffix: Optional[str]=None,
) -> Path:
    directory = CreateTempFileName(suffix=suffix)

    directory.mkdir(parents=True, exist_ok=True)

    return directory
