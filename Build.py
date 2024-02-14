# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-23 12:50:20
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Builds functionality for this python module."""

import sys

from pathlib import Path

import typer

from dbrownell_Common import PathEx
from dbrownell_DevTools.RepoBuildTools import Python as RepoBuildTools
from typer.core import TyperGroup


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # pylint: disable=missing-class-docstring
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app = typer.Typer(
    cls=NaturalOrderGrouper,
    help=__doc__,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
this_dir = PathEx.EnsureDir(Path(__file__).parent)
src_dir = PathEx.EnsureDir(this_dir / "src" / "dbrownell_Common")
tests_dir = PathEx.EnsureDir(this_dir / "tests")


# ----------------------------------------------------------------------
Black = RepoBuildTools.BlackFuncFactory(this_dir, app)
Pylint = RepoBuildTools.PylintFuncFactory(src_dir, app)
Pytest = RepoBuildTools.PytestFuncFactory(
    tests_dir, "dbrownell_Common", app, default_min_coverage=80.0
)
UpdateVersion = RepoBuildTools.UpdateVersionFuncFactory(
    src_dir.parent, src_dir / "__init__.py", app
)
Package = RepoBuildTools.PackageFuncFactory(this_dir, app)
Publish = RepoBuildTools.PublishFuncFactory(this_dir, app)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(app())
