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

import os
import re
import sys

from io import StringIO
from typing import Generator, Match, Optional

from dbrownell_Common.Streams.Capabilities import Capabilities
from dbrownell_Common.Streams.DoneManager import DoneManager, Flags as DoneManagerFlags


# ----------------------------------------------------------------------
def ScrubDuration(
    content: str,
    *,
    keep_hours: bool = False,
    keep_minutes: bool = False,
    keep_seconds: bool = False,
) -> str:
    if keep_hours or keep_minutes or keep_seconds:
        # ----------------------------------------------------------------------
        def Replace(
            match: Match,
        ) -> str:
            hours = match.group("hours") if keep_hours else "??"
            minutes = match.group("minutes") if keep_minutes else "??"
            seconds = match.group("seconds") if keep_seconds else "??"

            return f"{hours}:{minutes}:{seconds}"

        # ----------------------------------------------------------------------

        replace_func = Replace
    else:
        replace_func = lambda _: "<scrubbed duration>"

    return re.sub(
        r"""(?#
            Hours                           )(?P<hours>\d+)(?#
            sep                             )\:(?#
            Minutes                         )(?P<minutes>\d+)(?#
            sep                             )\:(?#
            Seconds                         )(?P<seconds>\d+(?:\.\d+)?)(?#
            )""",
        replace_func,
        content,
    )


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

    content = ScrubDuration(
        sink.getvalue(),  # type: ignore
        keep_hours=keep_duration_hours,
        keep_minutes=keep_duration_minutes,
        keep_seconds=keep_duration_seconds,
    )

    # Remove any trailing whitespace
    content = "\n".join(line.rstrip() for line in content.split("\n"))

    assert expected_result is None or final_result == expected_result, (
        expected_result,
        final_result,
        content,
    )
    yield content


# ----------------------------------------------------------------------
def InitializeStreamCapabilities(
    stream=sys.stdout,
) -> None:
    """\
    Ensure that the provided stream outputs consistently within a variety of different environments.

    Usage within a test:
        @pytest.fixture(InitializeStreamCapabilities(), scope="session", autouse=True)

    """

    # Initialization can only happen once
    if hasattr(
        stream,
        Capabilities._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME,  # pylint: disable=protected-access
    ):
        return

    # Override any environment variables that might impact the way in which the output is generated
    os.environ[Capabilities.SIMULATE_TERMINAL_COLUMNS_ENV_VAR] = str(Capabilities.DEFAULT_COLUMNS)
    os.environ[Capabilities.SIMULATE_TERMINAL_INTERACTIVE_ENV_VAR] = "0"
    os.environ[Capabilities.SIMULATE_TERMINAL_COLORS_ENV_VAR] = "1"
    os.environ[Capabilities.SIMULATE_TERMINAL_HEADLESS_ENV_VAR] = "1"

    # Associate the capabilities with the stream
    Capabilities(
        columns=Capabilities.DEFAULT_COLUMNS,
        is_interactive=False,
        is_headless=True,
        supports_colors=True,
        stream=stream,
        no_column_warning=True,
    )
