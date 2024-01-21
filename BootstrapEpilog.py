# ----------------------------------------------------------------------
# |
# |  BootstrapEpilog.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-18 15:26:50
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from dbrownell_Common import SubprocessEx
from dbrownell_Common.Streams.DoneManager import DoneManager, Flags as DoneManagerFlags

del sys.path[0]

# Parse the arguments
is_debug = False
is_force = False
is_verbose = False
is_package = False
no_cache = False

for arg in sys.argv[
    2:  # First arg is the script name, second arg is the name of the shell script to write to
]:
    if arg == "--debug":
        is_debug = True
    elif arg == "--force":
        is_force = True
    elif arg == "--verbose":
        is_verbose = True
    elif arg == "--package":
        is_package = True
    elif arg == "--no-cache":
        no_cache = True
    else:
        raise Exception("Unrecognized argument: {}".format(arg))

if is_debug:
    is_verbose = True

with DoneManager.Create(
    sys.stdout,
    "\n",
    line_prefix="",
    prefix="\nResults: ",
    suffix="\n",
    flags=DoneManagerFlags.Create(verbose=is_verbose, debug=is_debug),
) as dm:
    with dm.Nested("Running pip install...") as this_dm:
        with this_dm.YieldStream() as stream:
            this_dm.result = SubprocessEx.Stream(
                'pip install --disable-pip-version-check {} --editable ".[dev{}]"'.format(
                    "--no-cache-dir" if no_cache else "",
                    ", package" if is_package else "",
                ),
                stream,
            )

    sys.exit(dm.result)
