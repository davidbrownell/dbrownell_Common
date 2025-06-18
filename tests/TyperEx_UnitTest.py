# ----------------------------------------------------------------------
# |
# |  TyperEx_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-15 19:22:36
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for TyperEx.py."""

import textwrap

from typing import Annotated

import pytest

from typer.testing import CliRunner
from typer_config.decorators import use_yaml_config

from dbrownell_Common.TyperEx import *


# ----------------------------------------------------------------------
class TestPythonCodeGenerator:
    # ----------------------------------------------------------------------
    def test_GenerateParametersStandard(self, _generator):
        results: list[str] = [
            'arg0: str=default_parameter_values["arg0"],',
            'arg1: int=default_parameter_values["arg1"],',
            'arg2: int=default_parameter_values["arg2"],',
            'arg3: int=default_parameter_values["arg3"],',
            'arg4: int=default_parameter_values["arg4"],',
        ]

        assert _generator.GenerateParameters() == "\n    ".join(results)
        assert _generator.GenerateParameters(indentation=2, skip_first_line=False) == "  {}".format(
            "\n  ".join(results)
        )
        assert (
            _generator.GenerateParameters(single_line=True) == " ".join(results)[:-1]
        )  # Remove trailing comma

    # ----------------------------------------------------------------------
    def test_GenerateArgumentsCommaDelimited(self, _generator):
        assert (
            _generator.GenerateArguments()
            == textwrap.dedent(
                """\
            arg0,
                arg1,
                arg2,
                arg3,
                arg4,
            """,
            ).rstrip()
        )

    # ----------------------------------------------------------------------
    def test_GenerateArgumentsSingleLine(self, _generator):
        assert _generator.GenerateArguments(single_line=True) == "arg0, arg1, arg2, arg3, arg4"

    # ----------------------------------------------------------------------
    def test_GenerateArgumentsDictArgs(self, _generator):
        assert (
            _generator.GenerateArguments(argument_type=PythonCodeGenerator.ArgumentTypes.DictArgs)
            == textwrap.dedent(
                """\
            "arg0": arg0,
                "arg1": arg1,
                "arg2": arg2,
                "arg3": arg3,
                "arg4": arg4,
            """,
            ).rstrip()
        )

    # ----------------------------------------------------------------------
    def test_GenerateArgumentsKeywordArgs(self, _generator):
        assert (
            _generator.GenerateArguments(argument_type=PythonCodeGenerator.ArgumentTypes.KeywordArgs)
            == textwrap.dedent(
                """\
            arg0=arg0,
                arg1=arg1,
                arg2=arg2,
                arg3=arg3,
                arg4=arg4,
            """,
            ).rstrip()
        )

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @pytest.fixture
    @staticmethod
    def _generator() -> PythonCodeGenerator:
        return PythonCodeGenerator.Create(
            {
                "arg0": str,
                "arg1": TypeDefinitionItem(int, typer.Option(10)),
                "arg2": (int, typer.Option()),
                "arg3": (int, typer.Option(help="This is the help")),
                "arg4": (int, typer.Option(20)),
            },
        )


# # ----------------------------------------------------------------------
# @pytest.mark.parametrize("func_name", ["MyFunc1", "MyFunc2"])
# class TestTyperDictArgument:
#     # ----------------------------------------------------------------------
#     def test_Standard(self, func_name, _app):
#         result = CliRunner().invoke(
#             _app, [func_name, "one:ONE", "two=123", "three:10", "three:20", "four=3.14"]
#         )
#
#         assert result.exit_code == 0
#         assert result.stdout == "{'one': 'ONE', 'two': 123, 'three': [10, 20], 'four': 3.14}\n"
#
#     # ----------------------------------------------------------------------
#     def test_DuplicatedValue(self, func_name, _app):
#         result = CliRunner().invoke(
#             _app,
#             [
#                 func_name,
#                 "one:ONE",
#                 "two=123",
#                 "three:10",
#                 "three:20",
#                 "four=3.14",
#                 "one=duplicated",
#             ],
#         )
#
#         assert result.exit_code == 0
#         assert result.stdout == "{'one': 'duplicated', 'two': 123, 'three': [10, 20], 'four': 3.14}\n"
#
#     # ----------------------------------------------------------------------
#     def test_OptionalValue(self, func_name, _app):
#         result = CliRunner().invoke(_app, [func_name, "one:ONE", "two=123", "three:10", "three:20"])
#
#         assert result.exit_code == 0
#         assert result.stdout == "{'one': 'ONE', 'two': 123, 'three': [10, 20]}\n"
#
#     # ----------------------------------------------------------------------
#     def test_ErrorWrongType(self, func_name, _app):
#         result = CliRunner().invoke(
#             _app, [func_name, "one:ONE", "two=123", "three:a", "three:20", "four=3.14"]
#         )
#
#         assert result.exit_code != 0
#         assert "'a' is not a valid integer" in result.stdout
#
#     # ----------------------------------------------------------------------
#     def test_ErrorMissingValue(self, func_name, _app):
#         result = CliRunner().invoke(_app, [func_name, "one:ONE", "three:10", "three:20"])
#
#         assert result.exit_code != 0
#         assert "A value must be provided for 'two'" in result.stdout
#
#     # ----------------------------------------------------------------------
#     def test_ErrorExtraValue(self, func_name, _app):
#         result = CliRunner().invoke(
#             _app,
#             [func_name, "one:ONE", "two=123", "three:10", "three:20", "four=3.14", "invalid=2"],
#         )
#
#         assert result.exit_code != 0
#         assert "'invalid' is not a valid key; valid keys are 'one', 'two', 'three', 'four'" in result.stdout
#
#     # ----------------------------------------------------------------------
#     # ----------------------------------------------------------------------
#     # ----------------------------------------------------------------------
#     @pytest.fixture
#     @staticmethod
#     def _app() -> typer.Typer:
#         app = typer.Typer()
#
#         typer_dict_argument = TyperDictArgument(
#             {
#                 "one": str,
#                 "two": (int, typer.Argument()),
#                 "three": (list[int], typer.Argument()),
#                 "four": (Optional[float], typer.Option(None)),
#             },
#         )
#
#         # ----------------------------------------------------------------------
#         @app.command("MyFunc1")
#         def MyFunc1(
#             key_value_args: Annotated[list[str], typer_dict_argument],
#         ) -> None:
#             print(PostprocessDictArgument(key_value_args))
#
#         # ----------------------------------------------------------------------
#         @app.command("MyFunc2")
#         def MyFunc2(
#             key_value_args: list[str] = typer_dict_argument,
#         ) -> None:
#             print(PostprocessDictArgument(key_value_args))
#
#         # ----------------------------------------------------------------------
#
#         return app


# ----------------------------------------------------------------------
class TestTyperDictOption:
    # ----------------------------------------------------------------------
    def test_Empty(self, _app):
        result = CliRunner().invoke(_app, [])

        assert result.exit_code == 0
        assert result.stdout == "{}\n"

    # ----------------------------------------------------------------------
    def test_PartialFill(self, _app):
        result = CliRunner().invoke(_app, ["--key-value-args", "one:ONE", "--key-value-args", "two:2"])

        assert result.exit_code == 0
        assert result.stdout == "{'one': 'ONE', 'two': 2}\n"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @pytest.fixture
    @staticmethod
    def _app() -> typer.Typer:
        app = typer.Typer()

        # # ----------------------------------------------------------------------
        # @app.command("MyFunc1")
        # def MyFunc1(
        #     key_value_args: list[str]=TyperDictOption(
        #         {
        #             "one": str,
        #             "two": int,
        #             "three": list[int],
        #             "four": (Optional[float], typer.Option(None)),
        #         },
        #         ...,
        #     ),
        # ):
        #     print(PostprocessDictArgument(key_value_args))

        # ----------------------------------------------------------------------
        @app.command("MyFunc2")
        def MyFunc2(
            key_value_args: Annotated[
                list[str],
                TyperDictOption(
                    {
                        "one": str,
                        "two": int,
                        "three": list[int],
                        "four": (Optional[float], typer.Option(None)),
                    },
                ),
            ] = [],
        ) -> None:
            print(PostprocessDictArgument(key_value_args))

        # ----------------------------------------------------------------------

        return app


# ----------------------------------------------------------------------
class TestProcessDynamicArgs:
    # ----------------------------------------------------------------------
    def test_SingleArg(self, _app):
        result = CliRunner().invoke(_app, ["10"])

        assert result.exit_code == 0
        assert result.stdout == textwrap.dedent(
            """\
            10
            False
            {}
            """,
        )

    # ----------------------------------------------------------------------
    def test_TwoArgs(self, _app):
        result = CliRunner().invoke(_app, ["10", "--arg2"])

        assert result.exit_code == 0
        assert result.stdout == textwrap.dedent(
            """\
            10
            True
            {}
            """,
        )

    # ----------------------------------------------------------------------
    def test_OneOptional(self, _app):
        result = CliRunner().invoke(_app, ["10", "--extra-args1", "99"])

        assert result.exit_code == 0
        assert result.stdout == textwrap.dedent(
            """\
            10
            False
            {'extra_args1': 99}
            """,
        )

    # ----------------------------------------------------------------------
    def test_TwoOptional(self, _app):
        result = CliRunner().invoke(_app, ["10", "--extra-args1", "99", "--extra-args2", "abc"])

        assert result.exit_code == 0
        assert result.stdout == textwrap.dedent(
            """\
            10
            False
            {'extra_args1': 99, 'extra_args2': 'abc'}
            """,
        )

    # ----------------------------------------------------------------------
    def test_ThreeOptional(self, _app):
        result = CliRunner().invoke(
            _app,
            [
                "10",
                "--extra-args1",
                "99",
                "--extra-args2",
                "abc",
                "--extra-args3",
                "1",
                "--extra-args3",
                "2",
                "--extra-args3",
                "3",
            ],
        )

        assert result.exit_code == 0
        assert result.stdout == textwrap.dedent(
            """\
            10
            False
            {'extra_args1': 99, 'extra_args2': 'abc', 'extra_args3': [1, 2, 3]}
            """,
        )

    # ----------------------------------------------------------------------
    def test_TyperConfig(self, _app, fs):
        fs.create_file(
            "config.yaml",
            contents=textwrap.dedent(
                """\
                arg1: 10
                extra-args1: 99
                extra-args2: "abc"
                extra-args3: [1, 2, 3]
                """,
            ),
        )

        result = CliRunner().invoke(
            _app,
            ["--config", "config.yaml"],
        )

        assert result.exit_code == 0, result.output
        assert result.stdout == textwrap.dedent(
            """\
            10
            False
            {'extra_args1': 99, 'extra_args2': 'abc', 'extra_args3': [1, 2, 3]}
            """,
        )

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @pytest.fixture
    @staticmethod
    def _app() -> typer.Typer:
        app = typer.Typer()

        # ----------------------------------------------------------------------
        @app.command(
            "MyFunc",
            context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        )
        @use_yaml_config()
        def MyFunc(
            ctx: typer.Context,
            arg1: Annotated[int, typer.Argument()],
            arg2: Annotated[bool, typer.Option("--arg2")] = False,
        ) -> None:
            # Normally, the following options would be generated dynamically
            type_definitions = {
                "extra_args1": (int, typer.Option(None, min=10, max=100)),
                "extra_args2": str,
                "extra_args3": (list[int], typer.Option(None, "--extra-args3")),
            }

            print(arg1)
            print(arg2)
            print(ProcessDynamicArgs(ctx, type_definitions))

        # ----------------------------------------------------------------------

        return app
