# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-23 12:50:20
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Builds functionality for this python module."""

import re

from pathlib import Path
from typing import Optional

import typer

from typer.core import TyperGroup

from dbrownell_Common import SubprocessEx
from dbrownell_Common.Streams.DoneManager import DoneManager, DoneManagerException, Flags as DoneManagerFlags


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # pylint: disable=missing-class-docstring
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    help=__doc__,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
@app.command("Pylint", no_args_is_help=False)
def Pylint(
    min_score: float=typer.Option(9.5, "--min-score", min=0.0, max=10.0, help="Fail if the total score is less than this value."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Runs pylint on the python code."""

    with DoneManager.CreateCommandLine(
        flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        with dm.Nested("Running pylint...") as pylint_dm:
            command_line = 'pylint {}/src --fail-under {}'.format(Path(__file__).parent, min_score)

            pylint_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

            with pylint_dm.YieldStream() as stream:
                pylint_dm.result = SubprocessEx.Stream(command_line, stream)
                if pylint_dm.result != 0:
                    return


# ----------------------------------------------------------------------
@app.command("Test", no_args_is_help=False)
def Test(
    code_coverage: bool=typer.Option(False, "--code-coverage", help="Run tests with code coverage information."),
    benchmark: bool=typer.Option(False, "--benchmark", help="Run benchmark tests."),
    min_coverage: Optional[float]=typer.Option(None, "--min-coverage", min=0.0, max=100.0, help="Fail if code coverage percentage is less than this value."),
    pytest_args: Optional[str]=typer.Option(None, "--pytest-args", help="Additional arguments passed to pytest."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Tests the python code."""

    with DoneManager.CreateCommandLine(
        flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        if code_coverage:
            min_coverage = min_coverage or 90.0
        elif min_coverage:
            code_coverage = True

        assert (
            (code_coverage and min_coverage)
            or (not code_coverage and min_coverage is None)
        ), (code_coverage, min_coverage)

        with dm.Nested("Testing...") as test_dm:
            command_line = 'pytest {} {} --capture=no --verbose -vv {} tests/'.format(
                "--benchmark-skip" if not benchmark else "",
                "" if not code_coverage else "--cov=dbrownell_Common --cov-fail-under={} ".format(min_coverage),
                "" if not pytest_args else pytest_args,
            )

            test_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

            with test_dm.YieldStream() as stream:
                test_dm.result = SubprocessEx.Stream(
                    command_line,
                    stream,
                    is_headless=True,
                    is_interactive=False,
                    supports_colors=True,
                )
                if test_dm.result != 0:
                    return


# ----------------------------------------------------------------------
@app.command("UpdateVersion", no_args_is_help=False)
def UpdateVersion(
    auto_sem_ver_version: str=typer.Option("0.6.3", "--auto-sem-ver-version", help="Version of the autosemver image on dockerhub."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Updates the library version found in src/dbrownell_Common/__init__.py based on git changes."""

    with DoneManager.CreateCommandLine(
        flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        this_dir = Path(__file__).parent
        auto_sem_ver: Optional[str] = None

        with dm.Nested(
            "Calculating version...",
            lambda: "The version is '{}'".format(auto_sem_ver or "<Error>"),
        ) as version_dm:
            with version_dm.Nested("Pulling image...") as pull_dm:
                command_line = 'docker pull dbrownell/autosemver:{}'.format(auto_sem_ver_version)

                pull_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

                with pull_dm.YieldStream() as stream:
                    pull_dm.result = SubprocessEx.Stream(command_line, stream)
                    if pull_dm.result != 0:
                        return

            with version_dm.Nested("Running image...") as run_dm:
                command_line = 'docker run --rm -v "{}:/local" dbrownell/autosemver:{} --path /local --no-branch-name --no-metadata --quiet'.format(
                    this_dir,
                    auto_sem_ver_version,
                )

                run_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

                result = SubprocessEx.Run(command_line)

                run_dm.result = result.returncode
                if run_dm.result != 0:
                    run_dm.WriteLine(result.output)
                    return

                auto_sem_ver = result.output.strip()

        with dm.Nested("Updating the source..."):
            init_filename = this_dir / "src" / "dbrownell_Common" / "__init__.py"
            assert init_filename.is_file(), init_filename

            with init_filename.open(encoding="utf-8") as f:
                content = f.read()

            new_content = re.sub(
                r'^__version__ = ".+?"$',
                f'__version__ = "{auto_sem_ver}"',
                content,
                count=1,
                flags=re.MULTILINE,
            )

            with init_filename.open("w", encoding="utf-8") as f:
                f.write(new_content)


# ----------------------------------------------------------------------
@app.command("Package", no_args_is_help=False)
def Package(
    additional_args: list[str]=typer.Option([], "--arg", help="Additional arguments passed to the build command."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Builds the python package."""

    with DoneManager.CreateCommandLine(
        flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        with dm.Nested("Packaging...") as package_dm:
            command_line = "python -m build{}".format(
                "" if not additional_args else " {}".format(" ".join('"{}"'.format(arg) for arg in additional_args)),
            )

            package_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

            with package_dm.YieldStream() as stream:
                package_dm.result = SubprocessEx.Stream(command_line, stream)
                if package_dm.result != 0:
                    return


# ----------------------------------------------------------------------
@app.command("Publish", no_args_is_help=False)
def Publish(
    pypi_api_token: str=typer.Argument(..., help="API token as generated on PyPi.org or test.PyPi.org; this token should be scoped to this project only."),
    production: bool=typer.Option(False, "--production", help="Push to the production version of PyPi (PyPi.org); the test PyPi server is used by default (test.PyPi.org)."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Publishes the python package to PyPi."""

    with DoneManager.CreateCommandLine(
        flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        this_dir = Path(__file__).parent

        dist_dir = this_dir / "dist"
        if not dist_dir.is_dir():
            raise DoneManagerException(
                "The distribution directory '{}' does not exist. Please run this script with the 'Package' argument to create it.".format(
                    dist_dir,
                ),
            )

        if production:
            repository_url = "https://upload.PyPi.org/legacy/"
        else:
            repository_url = "https://test.PyPi.org/legacy/"

        with dm.Nested("Publishing to '{}'...".format(repository_url)) as publish_dm:
            command_line = 'twine upload --repository-url {} --username __token__ --password {} --non-interactive --disable-progress-bar {}"dist/*.whl"'.format(
                repository_url,
                pypi_api_token,
                "--verbose " if verbose else "",
            )

            publish_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

            with publish_dm.YieldStream() as stream:
                publish_dm.result = SubprocessEx.Stream(command_line, stream)
                if publish_dm.result != 0:
                    return


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
