# ----------------------------------------------------------------------
# |
# |  TyperEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-15 14:41:06
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Extensions to the typer module"""

import re

from dataclasses import dataclass
from enum import auto, Enum
from types import NoneType
from typing import Any, Callable, ClassVar, Iterable, Optional, Type, TypeVar, Union

import typer

from typer import main as typer_main

from dbrownell_Common import TextwrapEx


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class TypeDefinitionItem:
    """Information used to generate a dynamic command line argument."""

    # ----------------------------------------------------------------------
    python_type: Type
    parameter_info: typer.models.ParameterInfo

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        python_type: Type,
        *,
        is_optional: bool = False,
        **param_info_kwargs,
    ) -> "TypeDefinitionItem":
        if is_optional or _IsOptionalPythonType(python_type):
            typer_param = typer.Option(None, **param_info_kwargs)
        else:
            typer_param = typer.Argument(..., **param_info_kwargs)

        return cls(python_type, typer_param)


# ----------------------------------------------------------------------
TypeDefinitionItemType = Union[  # pylint: disable=invalid-name
    TypeDefinitionItem,
    # Note that the following values are converted into TypeDefinitionItem instances
    Type,  # Python type annotation
    tuple[
        Type,
        typer.models.ParameterInfo,  # The OptionInfo itself
    ],
]


# ----------------------------------------------------------------------
TypeDefinitionsType = dict[str, TypeDefinitionItemType]


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class PythonCodeGenerator:
    """\
    Object able to generate python code based on the type definitions provided to it.

    Example:
        generator = PythonCodeGenerator.Create(
            {
                "arg1": TypeDefinitionItem(int, typer.Option(10)),
                "arg2": int,
                "arg3": (int, {"help": "This is the help"}),
                "arg4": (int, typer.Option(20)),
            },
            "custom_types_name",
        )

        python_code = textwrap.dedent(
            '''\
            @app.command()
            def DynamicFunc(
                {parameters}
            ):
                print({arguments})

            ''',
        ).format(
            parameters=generator.GenerateParameters(single_line=False),
            arguments=generator.GenerateArguments(single_line=True),
        )
    """

    # ----------------------------------------------------------------------
    class ArgumentTypes(Enum):
        """Indicates how the generation should generate the output."""

        CommaDelimited = auto()
        DictArgs = auto()
        KeywordArgs = auto()

    # ----------------------------------------------------------------------
    DEFAULT_OPTION_TYPE_VALUES_VAR_NAME: ClassVar[str] = "default_parameter_values"

    # ----------------------------------------------------------------------
    python_parameters: dict[str, str]
    python_type_values: dict[str, typer.models.ParameterInfo]

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        type_definitions: TypeDefinitionsType,
        option_type_values_var_name: str = DEFAULT_OPTION_TYPE_VALUES_VAR_NAME,
    ) -> "PythonCodeGenerator":
        parameters: dict[str, str] = {}
        types: dict[str, typer.models.ParameterInfo] = {}

        for k, v in type_definitions.items():
            python_type: None | Type | str = None
            parameter_info: Optional[typer.models.ParameterInfo] = None

            if isinstance(v, TypeDefinitionItem):
                python_type = v.python_type
                parameter_info = v.parameter_info
            elif isinstance(v, tuple):
                python_type, parameter_info = v
            else:
                python_type = v
                parameter_info = typer.Argument()

            assert python_type is not None
            assert parameter_info is not None

            python_type_name: Optional[str] = None

            if isinstance(python_type, str):
                if python_type.startswith("typing."):
                    python_type_name = python_type[len("typing.") :]
                else:
                    python_type_name = python_type
            else:
                python_type_name = python_type.__name__

            assert python_type_name is not None

            types[k] = parameter_info

            parameters[k] = '{name}: {python_type_name}={var_name}["{name}"]'.format(
                name=k,
                python_type_name=python_type_name,
                var_name=option_type_values_var_name,
            )

        return PythonCodeGenerator(parameters, types)

    # ----------------------------------------------------------------------
    def GenerateParameters(
        self,
        *,
        single_line: bool = False,
        indentation: int = 4,
        skip_first_line: bool = True,
    ) -> str:
        if single_line:
            return ", ".join(parameter for parameter in self.python_parameters.values())

        return TextwrapEx.Indent(
            "\n".join("{},".format(parameter) for parameter in self.python_parameters.values()),
            indentation,
            skip_first_line=skip_first_line,
        )

    # ----------------------------------------------------------------------
    def GenerateArguments(
        self,
        *,
        argument_type: "PythonCodeGenerator.ArgumentTypes" = ArgumentTypes.CommaDelimited,
        single_line: bool = False,
        indentation: int = 4,
        skip_first_line: bool = True,
    ) -> str:
        if argument_type == PythonCodeGenerator.ArgumentTypes.CommaDelimited:
            decorate_parameter_func = lambda value: value
        elif argument_type == PythonCodeGenerator.ArgumentTypes.DictArgs:
            decorate_parameter_func = lambda value: '"{value}": {value}'.format(value=value)
        elif argument_type == PythonCodeGenerator.ArgumentTypes.KeywordArgs:
            decorate_parameter_func = lambda value: "{value}={value}".format(value=value)
        else:
            assert False, argument_type  # pragma: no cover

        if single_line:
            return ", ".join(
                decorate_parameter_func(parameter) for parameter in self.python_parameters.keys()
            )

        return TextwrapEx.Indent(
            "\n".join(
                "{},".format(decorate_parameter_func(parameter))
                for parameter in self.python_parameters.keys()
            ),
            indentation,
            skip_first_line=skip_first_line,
        )


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def TyperDictArgument(
    type_definitions: TypeDefinitionsType,
    *,
    allow_any__: bool = False,  # Do not produce errors when key values are provided that are not defined in type_definitions
    **argument_info_kwargs,
) -> typer.models.ArgumentInfo:
    """\
    Creates a typer.models.ArgumentInfo instance that is able to process key-value-pairs provided
    on the command line as strings.

    Example:
        CODE:
            @app.command()
            def MyFunc(
                key_value_args: list[str]=TyperDictArgument(
                    ...,
                    dict(
                        one=str,
                        type=int,
                        three=list[int],
                        four=Optional[float],
                        five=(Optional[Path], dict(exists=True, resolve_path=True)),
                    ),
                ),
            ):
                the_dict = PostprocessDictArgument(key_value_args)

                print(the_dict)

        COMMAND LINE:
            MyFunc one:1 two:2 three:3 three:33
                -> {
                    "one": "1",
                    "two": 2,
                    "three": [3, 33],
                    "four": None,
                    "five": None,
                }

            MyFunc one:1 three:3 three: 33
                -> raises error, two is required

            MyFunc one:1 two:2 three:3 three:33 four:1.2345 five:.
                -> {
                    "one": "1",
                    "two": 2,
                    "three": [3, 33],
                    "four": 1.2345,
                    "five": Path("<your working directory here>"),
                }

            MyFunc
                -> raises error, one is required
    """

    return _TyperDictImpl(
        typer.models.ArgumentInfo,
        type_definitions,
        allow_any__,
        None,
        argument_info_kwargs,
    )


# ----------------------------------------------------------------------
def TyperDictOption(
    type_definitions: TypeDefinitionsType,
    *option_info_args,
    allow_any__: bool = False,  # Do not produce errors when key values are provided that are not defined in type_definitions
    **option_info_kwargs,
) -> typer.models.OptionInfo:
    """\
    Creates a typer.models.OptionInfo instance that is able to process key-value-pairs provided
    on the command line as strings.

    Example:
        CODE:
            @app.command()
            def MyFunc(
                key_value_args: list[str]=TyperDictOption(
                    ...,
                    dict(
                        one=str,
                        type=int,
                        three=list[int],
                        four=Optional[float],
                        five=(Optional[Path], dict(exists=True, resolve_path=True)),
                    ),
                ),
            ):
                the_dict = PostprocessDictArgument(key_value_args)

                print(the_dict)

        COMMAND LINE:
            MyFunc one:1 two:2 three:3 three:33
                -> {
                    "one": "1",
                    "two": 2,
                    "three": [3, 33],
                    "four": None,
                    "five": None,
                }

            MyFunc one:1 two:2 three:3 three:33 four:1.2345 five:.
                -> {
                    "one": "1",
                    "two": 2,
                    "three": [3, 33],
                    "four": 1.2345,
                    "five": Path("<your working directory here>"),
                }
    """

    return _TyperDictImpl(
        typer.models.OptionInfo,
        type_definitions,
        allow_any__,
        option_info_args,
        option_info_kwargs,
        force_optional=True,
    )


# ----------------------------------------------------------------------
def PostprocessDictArgument(
    args: Optional[list[Any]],
) -> dict[str, Any]:
    """\
    Converts data that is plumbed through `TyperDictArgument` or `TyperDictOption` into
    a dictionary, as expected.

    This postprocessing step is necessary to ensure that the data (that doesn't look like
    what typer expects it to) makes it through the typer engine mechanics without losing
    anything along the way.

    This function is necessary because the entire solution is a bit of a hack.
    """

    if args is None:
        return {}

    assert len(args) == 1
    assert isinstance(args[0], dict)
    return args[0]


# ----------------------------------------------------------------------
def ProcessDynamicArgs(
    ctx: typer.Context,
    type_definitions: TypeDefinitionsType,
) -> dict[str, Any]:
    """\
    Process arguments that have been dynamically generated.

    Example:
        app = typer.Typer()

        @app.command(
            name="MyFunc",
            context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        )
        def MyFunc(
            ctx: typer.Context,
            arg1: int=typer.Argument(...),
            arg2: bool=typer.Option(False, "--arg2"),
        ) -> None:
            # Normally, the following arguments would be generated dynamically
            type_definitions = {
                "extra_args1": (int, dict(min=10, max=100)),
                "extra_args2": str,
                "extra_args3": (list[int], typer.Option(None, "--extra-args3")),
            }

            extra_args = ProcessDynamicArgs(ctx, type_definitions)
    """

    click_params = _TypeDefinitionItemsToClickParams(
        ResolveTypeDefinitions(
            type_definitions,
            force_optional=True,
        ),
    )

    # Group the arguments
    arguments: list[tuple[str, Optional[str]]] = []

    for arg in ctx.args:
        if arg.startswith("-"):
            arg = arg.lstrip("-")

            arguments.append((arg, None))
        else:
            # The value should be associated with a keyword encountered prior
            if not arguments or arguments[-1][-1] is not None:
                raise typer.BadParameter("Got unexpected extra argument ({})".format(arg))

            arguments[-1] = (arguments[-1][0], arg)

    # default_map is populated by typer-config
    if ctx.default_map:
        # Create a set of all argument names associated with dynamic values.
        dynamic_names: set[str] = set()

        for typer_info, _ in click_params.values():
            for dynamic_name in typer_info.opts or []:
                dynamic_names.add(dynamic_name.removeprefix("--"))

        # Read dynamic arguments
        for k, v in ctx.default_map.items():
            if k in dynamic_names:
                arguments.append((k, v))

    # Invoke the dynamic functionality
    return _ProcessArgumentsImpl(click_params, arguments, ctx=ctx)


# ----------------------------------------------------------------------
def ResolveTypeDefinitions(
    type_definitions: TypeDefinitionsType,
    *,
    force_optional: bool = False,
) -> dict[str, TypeDefinitionItem]:
    # ----------------------------------------------------------------------
    def ResolveItem(
        item: TypeDefinitionItemType,
    ) -> TypeDefinitionItem:
        type_definition_item: Optional[TypeDefinitionItem] = None

        if isinstance(item, TypeDefinitionItem):
            type_definition_item = item
        elif isinstance(item, tuple):
            python_type, parameter_info = item

            type_definition_item = TypeDefinitionItem(python_type, parameter_info)
        else:
            type_definition_item = TypeDefinitionItem.Create(
                item,
                is_optional=force_optional,
            )

        assert type_definition_item is not None

        if force_optional and not isinstance(type_definition_item.parameter_info, typer.models.OptionInfo):
            raise Exception("Optional types must be defined as typer.Option instances.")

        return type_definition_item

    # ----------------------------------------------------------------------

    results: dict[str, TypeDefinitionItem] = {}

    for k, v in type_definitions.items():
        results[k] = ResolveItem(v)

    return results


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
def _TypeDefinitionItemsToClickParams(
    type_definitions: dict[str, TypeDefinitionItem],
) -> dict[str, tuple[Any, Callable[..., Any]]]:
    return {
        k: typer_main.get_click_param(
            typer.models.ParamMeta(
                name=k,
                default=v.parameter_info,
                annotation=v.python_type,
            ),
        )
        for k, v in type_definitions.items()
    }


# ----------------------------------------------------------------------
_TyperT = TypeVar("_TyperT", typer.models.ArgumentInfo, typer.models.OptionInfo)
_TyperDictImplRegex = re.compile(
    r"""(?#
    Start of Line                           )^(?#
    Key                                     )(?P<key>(?:\\[:=]|[^:=])+)(?#
    Optional Value Begin                    )(?:(?#
        Sep                                 )\s*[:=]\s*(?#
        Value                               )(?P<value>.+)(?#
    Optional Value End                      ))?(?#
    End of Line                             )$(?#
    )""",
)


def _TyperDictImpl(
    typer_type: Type[_TyperT],
    type_definitions: TypeDefinitionsType,
    allow_unknown: bool,
    args: Optional[tuple[str, ...]],
    kwargs: dict[str, Any],
    *,
    force_optional: bool = False,
) -> _TyperT:
    click_params = _TypeDefinitionItemsToClickParams(
        ResolveTypeDefinitions(
            type_definitions,
            force_optional=force_optional,
        ),
    )

    # Prepare the result
    original_callback = kwargs.pop("callback", None)

    # ----------------------------------------------------------------------
    def NewCallback(
        ctx: typer.Context,
        param: typer.CallbackParam,
        values: list[str],
    ) -> list[dict[str, Any]]:
        arguments: list[tuple[str, Optional[str]]] = []

        for value in values:
            match = _TyperDictImplRegex.match(value)
            if not match:
                raise typer.BadParameter(
                    "'{}' is not a valid dictionary parameters; expected '<key>:<value>' or '<key> = <value>'.".format(
                        value,
                    ),
                )

            key = match.group("key").replace("\\:", ":").replace("\\=", "=")
            value = (match.group("value") or "").replace("\\:", ":").replace("\\=", "=")

            arguments.append((key, value))

        results = _ProcessArgumentsImpl(
            click_params,
            arguments,
            ctx=ctx,
            allow_unknown=allow_unknown,
        )

        # Invoke the original callback
        if original_callback:
            original_callback(ctx, param, results)

        # Convert the results to a list to make it through the typer plumbing
        # unchanged (since the original type was decorated as a list)
        return [
            results,
        ]

    # ----------------------------------------------------------------------

    return typer_type(
        **{
            **kwargs,
            **{
                "default": ...,
                "callback": NewCallback,
                "param_decls": args,
            },
        },
    )


# ----------------------------------------------------------------------
def _ProcessArgumentsImpl(
    click_params: dict[str, tuple[Any, Callable[..., Any]]],
    arguments: Iterable[tuple[str, Optional[str]]],
    *,
    ctx: Optional[typer.Context],
    allow_unknown: bool = False,
) -> dict[str, Any]:
    # Create information to map from the argument keyword to the result name
    argument_to_result_names: dict[str, str] = {}

    for result_name, (click_param, _) in click_params.items():
        for opt in click_param.opts:
            if opt.startswith("--"):
                opt = opt[2:]

            assert opt not in argument_to_result_names, opt
            argument_to_result_names[opt] = result_name

    results: dict[str, Any] = {}

    # Group the argument values
    for key, value in arguments:
        result_name = argument_to_result_names.get(key, None)  # type: ignore
        if result_name is None:
            if not allow_unknown:
                if not click_params:
                    error_context = "custom arguments are not supported"
                else:
                    error_context = "valid keys are {}".format(
                        ", ".join("'{}'".format(name) for name in argument_to_result_names),
                    )

                raise typer.BadParameter("'{}' is not a valid key; {}.".format(key, error_context))

            result_name = key

        result_value = results.get(result_name, None)

        if result_value is not None:
            if isinstance(result_value, list):
                result_value.append(value)
            else:
                results[result_name] = [result_value, value]
        else:
            results[result_name] = value

    # Convert the values
    does_not_exist = object()

    for param_name, param_info in click_params.items():
        # For some reason, typer uses 2 different techniques to indicate that a type
        # is a list (one technique is used with Arguments, the other is used for Options).
        is_list = param_info[0].nargs == -1 or param_info[0].multiple

        param_results = results.get(param_name, does_not_exist)
        if param_results is does_not_exist:
            if param_info[0].required:
                param_results = None
            else:
                if param_info[0].default is None:
                    param_results = [] if is_list else None
                else:
                    results[param_name] = param_info[0].default

                continue

        if param_results is None:
            if isinstance(param_info[0].default, bool):
                param_results = not param_info[0].default
            else:
                raise typer.BadParameter("A value must be provided for '{}'.".format(param_name))

        if is_list:
            if not isinstance(param_results, list):
                param_results = [
                    param_results,
                ]
        else:
            if isinstance(param_results, list):
                # Take the last value
                param_results = param_results[-1]

        param_results = param_info[0].process_value(ctx, param_results)

        if param_info[1] is not None:
            param_results = param_info[1](param_results)

        results[param_name] = param_results

    return results


# ----------------------------------------------------------------------
def _IsOptionalPythonType(
    python_type: Type,
) -> bool:
    return (
        # The type was defined as a union and one of the union values is None
        getattr(python_type, "__origin__", None) is Union
        and any(value is NoneType for value in python_type.__args__)  # type: ignore
    )
