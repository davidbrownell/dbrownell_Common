# ----------------------------------------------------------------------
# |
# |  Capabilities_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-31 21:35:58
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for Capabilities.py."""

import re
import sys

from unittest.mock import MagicMock as Mock

import pytest

from dbrownell_Common.Streams.Capabilities import *
from dbrownell_Common.Streams.StreamDecorator import StreamDecorator


# ----------------------------------------------------------------------
def test_DefaultConstruct():
    c = Capabilities(ignore_environment=True)

    assert c.columns == Capabilities.DEFAULT_COLUMNS
    assert c.is_headless is True
    assert c.is_interactive is False
    assert c.supports_colors is False

    assert c.explicit_columns is True
    assert c.explicit_is_headless is False
    assert c.explicit_is_interactive is False
    assert c.explicit_supports_colors is False


# ----------------------------------------------------------------------
def test_Initialize():
    columns = Mock()
    is_headless = Mock()
    is_interactive = Mock()
    supports_colors = Mock()

    c = Capabilities(
        columns=columns,
        is_headless=is_headless,
        is_interactive=is_interactive,
        supports_colors=supports_colors,
    )

    assert c.columns is columns
    assert c.is_headless is is_headless
    assert c.is_interactive is is_interactive
    assert c.supports_colors is supports_colors
    assert c.explicit_columns is True
    assert c.explicit_is_headless is True
    assert c.explicit_is_interactive is True
    assert c.explicit_supports_colors is True


# ----------------------------------------------------------------------
def test_WithStdout():
    # I'm not sure how to temporarily redirect sys.stdout here without screwing
    # up other tests running concurrently.
    assert Capabilities._processed_stdout is False

    columns = 100

    # Note that this will generate a warning
    c = Capabilities(
        stream=sys.stdout,
        columns=columns,
    )

    assert Capabilities._processed_stdout is True
    assert c.columns == columns


# ----------------------------------------------------------------------
def test_SetError():
    # Capabilities are associated with a StreamDecorator when it is created.
    stream = StreamDecorator(None)

    with pytest.raises(
        Exception,
        match=re.escape(
            "Capabilities are assigned to a stream when it is first created and cannot be changed; consider using the `Clone` method."
        ),
    ):
        Capabilities(stream=stream)


# ----------------------------------------------------------------------
def test_Clone():
    original_capabilities = Capabilities(is_headless=True)
    new_capabilities = original_capabilities.Clone()

    assert new_capabilities is not original_capabilities
    assert new_capabilities == original_capabilities


# ----------------------------------------------------------------------
def test_Compare():
    assert Capabilities() == Capabilities()
    assert Capabilities(ignore_environment=True) != Capabilities(is_headless=False)
    assert Capabilities(ignore_environment=True) < Capabilities(is_headless=False)
    assert Capabilities(is_headless=False) > Capabilities(ignore_environment=True)
    assert Capabilities(is_headless=False, is_interactive=True, supports_colors=False) < Capabilities(
        is_headless=False, is_interactive=True, supports_colors=True
    )
