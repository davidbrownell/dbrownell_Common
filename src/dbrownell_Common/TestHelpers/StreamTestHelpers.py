# ----------------------------------------------------------------------
# |
# |  StreamTestHelpers.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-02-14 10:28:55
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Test helpers for content found in ../Streams"""

import re

from io import StringIO
from typing import Generator, Match, Optional

from dbrownell_Common.Streams.Capabilities import Capabilities
from dbrownell_Common.Streams.DoneManager import DoneManager, Flags as DoneManagerFlags


# ----------------------------------------------------------------------
def GenerateDoneManagerAndContent(
    heading: str = "Heading",
    *,
    expected_result: Optional[int] = None,
    verbose: bool = False,
    debug: bool = False,
    keep_duration_hours: bool = False,
    keep_duration_minutes: bool = False,
    keep_duration_seconds: bool = False,
) -> Generator[DoneManager | str, None, None]:
    """\
    Generates a DoneManager followed by the content populated by the DoneManager.

    Example Usage:
        dm_and_sink = iter(GenerateDoneManagerAndContent())

        dm = cast(DoneManager, next(dm_and_sink))

        dm.WriteInfo("Content")

        content = cast(str, next(dm_and_sink))

        assert content == textwrap.dedent(
            '''\
            Heading...
              INFO: Content
            DONE! (0, <scrubbed duration>)
            ''',
        )
    """

    # Do not decorate the output, regardless of what environment variables specify
    sink = Capabilities.Set(
        StringIO(),
        Capabilities(
            is_headless=True,
            is_interactive=False,
            supports_colors=False,
        ),
    )

    with DoneManager.Create(
        sink,
        heading,
        flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        yield dm

        final_result = dm.result

    # Remove durations from the output, as they are going to vary from execution-to-execution
    if keep_duration_hours or keep_duration_minutes or keep_duration_seconds:
        # ----------------------------------------------------------------------
        def Replace(
            match: Match,
        ) -> str:
            hours = match.group("hours") if keep_duration_hours else "??"
            minutes = match.group("minutes") if keep_duration_minutes else "??"
            seconds = match.group("seconds") if keep_duration_seconds else "??"

            return f"{hours}:{minutes}:{seconds}"

        # ----------------------------------------------------------------------

        replace_func = Replace
    else:
        replace_func = lambda _: "<scrubbed duration>"

    content = re.sub(
        r"""(?#
            Hours                           )(?P<hours>\d+)(?#
            sep                             )\:(?#
            Minutes                         )(?P<minutes>\d+)(?#
            sep                             )\:(?#
            Seconds                         )(?P<seconds>\d+(?:\.\d+)?)(?#
            )""",
        replace_func,
        sink.getvalue(),  # type: ignore
    )

    # Remove any trailing whitespace
    content = "\n".join(line.rstrip() for line in content.split("\n"))

    assert expected_result is None or final_result == expected_result, (
        expected_result,
        final_result,
        content,
    )
    yield content
