# ----------------------------------------------------------------------
# |
# |  ExecuteTasks.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-12 20:04:41
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality to execute multiple tasks in parallel."""

import datetime
import multiprocessing
import shutil
import sys
import threading
import time
import traceback

from abc import abstractmethod, ABC
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, cast, Iterator, Optional, Protocol, TypeVar, Union
from unittest.mock import MagicMock

from rich.progress import Progress, TaskID, TimeElapsedColumn

from dbrownell_Common.ContextlibEx import ExitStack
from dbrownell_Common.InflectEx import inflect
from dbrownell_Common import PathEx
from dbrownell_Common.Streams.Capabilities import Capabilities
from dbrownell_Common.Streams.DoneManager import DoneManager
from dbrownell_Common import TextwrapEx


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
CATASTROPHIC_TASK_FAILURE_RESULT = -123

DISPLAY_COLUMN_WIDTH = int(Capabilities.DEFAULT_COLUMNS * 0.50)
STATUS_COLUMN_WIDTH = int(Capabilities.DEFAULT_COLUMNS * 0.30)


# ----------------------------------------------------------------------
class TransformException(Exception):
    """Exception raised when the Transform function encounters errors when processing a task."""

    pass  # pylint: disable=unnecessary-pass


# ----------------------------------------------------------------------
@dataclass
class TaskData:
    """Data associated with a single task."""

    # ----------------------------------------------------------------------
    display: str
    context: Any

    # Set this value if the task needs to be processed exclusively with respect to
    # other `TaskData` objects with the same execution lock.
    execution_lock: Optional[threading.Lock] = field(default=None)

    # The following values will be populated during task execution
    result: int = field(init=False)
    short_desc: Optional[str] = field(init=False)

    execution_time: datetime.timedelta = field(init=False)
    log_filename: Path = field(init=False)


# ----------------------------------------------------------------------
class Status(ABC):
    """Interface to set information about a single task."""

    # ----------------------------------------------------------------------
    @abstractmethod
    def SetTitle(
        self,
        title: str,
    ) -> None:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnProgress(
        self,
        zero_based_step: Optional[int],
        status: Optional[str],
    ) -> bool:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnInfo(
        self,
        value: str,
        *,
        verbose: bool = False,
    ) -> None:
        raise Exception("Abstract method")  # pragma: no cover


# ----------------------------------------------------------------------
class ExecuteTasksTypes:
    """Types used by ExecuteTasks."""

    # ----------------------------------------------------------------------
    class InitFuncType(Protocol):
        """Initializes a task for execution."""

        def __call__(
            self,
            context: Any,  # TaskData.context
        ) -> tuple[Path, "ExecuteTasksTypes.PrepareFuncType",]:  # (Log filename, PrepareFuncType)
            ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class PrepareFuncType(Protocol):
        """Prepares a task for execution."""

        def __call__(
            self,
            on_simple_status_func: Callable[
                [
                    str,  # Status
                ],
                None,
            ],
        ) -> Union[
            tuple[
                int,  # Number of steps to execute
                "ExecuteTasksTypes.ExecuteFuncType",
            ],
            "ExecuteTasksTypes.ExecuteFuncType",
        ]:
            ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class ExecuteFuncType(Protocol):
        """Executes a task."""

        def __call__(
            self,
            status: Status,
        ) -> Union[
            tuple[
                int,  # Return code
                Optional[str],  # Final status message
            ],
            int,  # Return code
        ]:
            ...  # pragma: no cover


# ----------------------------------------------------------------------
@dataclass
class TransformResultComplete:
    """Complex result returned by a transform function."""

    value: Any
    return_code: Optional[int] = field(default=None)
    short_desc: Optional[str] = field(default=None)


# ----------------------------------------------------------------------
TransformedType = TypeVar(  # pylint: disable=invalid-name, typevar-name-incorrect-variance
    "TransformedType", covariant=True
)


# ----------------------------------------------------------------------
class TransformTasksExTypes:
    """Types used by TransformTasksEx."""

    # ----------------------------------------------------------------------
    class PrepareFuncType(Protocol[TransformedType]):
        """Prepares a task for transformation."""

        def __call__(
            self,
            context: Any,  # TaskData.context
            on_simple_status_func: Callable[
                [
                    str,  # Status
                ],
                None,
            ],
        ) -> Union[
            tuple[
                int,  # Number of steps to execute
                "TransformTasksExTypes.TransformFuncType",
            ],
            "TransformTasksExTypes.TransformFuncType",
        ]:
            ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class TransformFuncType(Protocol[TransformedType]):
        """Transforms a task."""

        def __call__(
            self,
            status: Status,
        ) -> TransformResultComplete | TransformedType:
            ...  # pragma: no cover


# ----------------------------------------------------------------------
class TransformTasksTypes:
    """Types used by TransformTasks."""

    # ----------------------------------------------------------------------
    class TransformFuncType(Protocol[TransformedType]):
        """Transforms a task."""

        def __call__(
            self,
            context: Any,
            status: Status,
        ) -> TransformResultComplete | TransformedType:
            ...  # pragma: no cover


# ----------------------------------------------------------------------
class YieldQueueExecutorTypes:
    """Types used by YieldQueueExecutor."""

    # ----------------------------------------------------------------------
    class PrepareFuncType(Protocol):
        """Prepares a task for execution."""

        def __call__(
            self,
            on_simple_status_func: Callable[
                [
                    str,  # Status
                ],
                None,
            ],
        ) -> Union[
            tuple[
                int,  # Number of steps to execute
                "YieldQueueExecutorTypes.ExecuteFuncType",
            ],
            "YieldQueueExecutorTypes.ExecuteFuncType",
        ]:
            ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class ExecuteFuncType(Protocol):
        """Executes a task."""

        def __call__(
            self,
            status: Status,
        ) -> Optional[str]:  # Status message
            ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class EnqueueFuncType(Protocol):
        """Enqueues a task to execute."""

        def __call__(
            self,
            description: str,
            prepare_func: "YieldQueueExecutorTypes.PrepareFuncType",
        ) -> None:
            ...  # pragma: no cover


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def ExecuteTasks(
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData],
    init_func: ExecuteTasksTypes.InitFuncType,
    *,
    quiet: bool = False,
    max_num_threads: Optional[int] = None,
    refresh_per_second: Optional[float] = None,
) -> None:
    """Executes tasks that each output to individual log files."""

    with _GenerateStatusInfo(
        len(tasks),
        dm,
        desc,
        tasks,
        quiet=quiet,
        refresh_per_second=refresh_per_second,
    ) as (status_factories, on_task_complete_func):
        if max_num_threads == 1 or len(tasks) == 1:
            for task_data, status_factory in zip(tasks, status_factories):
                with ExitStack(status_factory.Stop):
                    _ExecuteTask(
                        desc,
                        task_data,
                        init_func,
                        status_factory,
                        on_task_complete_func,
                        is_debug=dm.is_debug,
                    )

            return

        with ThreadPoolExecutor(
            max_workers=max_num_threads,
        ) as executor:
            # ----------------------------------------------------------------------
            def Impl(
                task_data: TaskData,
                status_factory: "_StatusFactory",
            ) -> None:
                with ExitStack(status_factory.Stop):
                    _ExecuteTask(
                        desc,
                        task_data,
                        init_func,
                        status_factory,
                        on_task_complete_func,
                        is_debug=dm.is_debug,
                    )

            # ----------------------------------------------------------------------

            futures = [
                executor.submit(Impl, task_data, status_factory)
                for task_data, status_factory in zip(tasks, status_factories)
            ]

            for future in futures:
                future.result()


# ----------------------------------------------------------------------
def TransformTasksEx(
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData],
    prepare_func: TransformTasksExTypes.PrepareFuncType[TransformedType],
    *,
    quiet: bool = False,
    max_num_threads: Optional[int] = None,
    refresh_per_second: Optional[float] = None,
    no_compress_tasks: bool = False,
    return_exceptions: bool = False,
) -> list[
    Union[
        None,
        TransformedType,
        Exception,  # If `return_exceptions` is True and an exception was encountered
    ],
]:
    """Executes functions that return values; use this variation for tasks that are transformed in multiple steps or require custom preparation."""

    with _YieldTemporaryDirectory(dm) as temp_directory:
        cpu_count = multiprocessing.cpu_count()

        num_threads = min(len(tasks), cpu_count)
        if max_num_threads:
            num_threads = min(num_threads, max_num_threads)

        if no_compress_tasks or num_threads < cpu_count or num_threads == 1:
            impl_func = _TransformNotCompressed
        else:
            impl_func = _TransformCompressed

        return impl_func(
            temp_directory,
            dm,
            desc,
            tasks,
            prepare_func,
            quiet=quiet,
            num_threads=num_threads,
            refresh_per_second=refresh_per_second,
            return_exceptions=return_exceptions,
        )


# ----------------------------------------------------------------------
def TransformTasks(
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData],
    transform_func: TransformTasksTypes.TransformFuncType[TransformedType],
    *,
    quiet: bool = False,
    max_num_threads: Optional[int] = None,
    refresh_per_second: Optional[float] = None,
    no_compress_tasks: bool = False,
    return_exceptions: bool = False,
) -> list[
    Union[
        None,
        TransformedType,
        Exception,  # If `return_exceptions` is True and an exception was encountered
    ],
]:
    """Executes functions that return values; use this function for single-step tasks that do not require extensive preparation."""

    # ----------------------------------------------------------------------
    def Prepare(
        context: Any,
        on_simple_status_func: Callable[[str], None],  # pylint: disable=unused-argument
    ) -> TransformTasksExTypes.TransformFuncType:
        return lambda status: transform_func(context, status)

    # ----------------------------------------------------------------------

    return TransformTasksEx(
        dm,
        desc,
        tasks,
        Prepare,
        quiet=quiet,
        max_num_threads=max_num_threads,
        refresh_per_second=refresh_per_second,
        no_compress_tasks=no_compress_tasks,
        return_exceptions=return_exceptions,
    )


# ----------------------------------------------------------------------
@contextmanager
def YieldQueueExecutor(
    dm: DoneManager,
    desc: str,
    *,
    quiet: bool = False,
    max_num_threads: Optional[int] = None,
    refresh_per_second: Optional[float] = None,
) -> Iterator[YieldQueueExecutorTypes.EnqueueFuncType]:
    """Yields a callable that can be used to enqueue tasks executed by workers running across multiple threads."""

    with _YieldTemporaryDirectory(dm) as temp_directory:
        num_threads = max_num_threads or multiprocessing.cpu_count()

        with _GenerateStatusInfo(
            None,
            dm,
            desc,
            [TaskData("", thread_index) for thread_index in range(num_threads)],
            quiet=quiet,
            refresh_per_second=refresh_per_second,
        ) as (status_factories, on_task_complete_func):
            queue: list[tuple[str, YieldQueueExecutorTypes.PrepareFuncType]] = []
            queue_lock = threading.Lock()

            queue_semaphore = threading.Semaphore(0)
            quit_event = threading.Event()

            # ----------------------------------------------------------------------
            def Enqueue(
                description: str,
                prepare_func: YieldQueueExecutorTypes.PrepareFuncType,
            ) -> None:
                with queue_lock:
                    queue.append((description, prepare_func))
                    queue_semaphore.release()

            # ----------------------------------------------------------------------
            def Impl(
                thread_index: int,
            ) -> None:
                log_filename = temp_directory / "{:06}.log".format(thread_index)
                status_factory = status_factories[thread_index]

                with ExitStack(status_factory.Stop):
                    while True:
                        with queue_semaphore:
                            with queue_lock:
                                if not queue:
                                    assert quit_event.is_set()
                                    break

                                task_desc, prepare_func = queue.pop(0)

                            # ----------------------------------------------------------------------
                            def Init(  # pylint: disable=unused-argument
                                *args,
                                **kwargs,
                            ) -> tuple[
                                Path, ExecuteTasksTypes.PrepareFuncType
                            ]:  # pylint: disable=unused-argument
                                # ----------------------------------------------------------------------
                                def Prepare(
                                    on_simple_status_func: Callable[[str], None],
                                ) -> Union[
                                    tuple[int, ExecuteTasksTypes.ExecuteFuncType],
                                    ExecuteTasksTypes.ExecuteFuncType,
                                ]:
                                    prepare_result = prepare_func(on_simple_status_func)

                                    num_steps: Optional[int] = None
                                    execute_func: Optional[
                                        YieldQueueExecutorTypes.ExecuteFuncType
                                    ] = None

                                    if isinstance(prepare_result, tuple):
                                        num_steps, execute_func = prepare_result
                                    else:
                                        execute_func = prepare_result

                                    assert execute_func is not None

                                    # ----------------------------------------------------------------------
                                    def Execute(
                                        status: Status,
                                    ) -> tuple[int, Optional[str]]:
                                        return 0, execute_func(status)

                                    # ----------------------------------------------------------------------

                                    if num_steps is not None:
                                        return num_steps, Execute

                                    return Execute

                                # ----------------------------------------------------------------------

                                return log_filename, Prepare

                            # ----------------------------------------------------------------------

                            _ExecuteTask(
                                desc,
                                TaskData(task_desc, None),
                                Init,
                                status_factory,
                                on_task_complete_func,
                                is_debug=dm.is_debug,
                            )

            # ----------------------------------------------------------------------

            with ThreadPoolExecutor(
                max_workers=num_threads,
            ) as executor:
                futures = [
                    executor.submit(Impl, thread_index) for thread_index in range(num_threads)
                ]

                yield Enqueue

                quit_event.set()
                queue_semaphore.release(num_threads)

                for future in futures:
                    future.result()


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
class _InternalStatus(Status):
    # ----------------------------------------------------------------------
    @abstractmethod
    def SetNumSteps(
        self,
        num_steps: int,
    ) -> None:
        raise Exception("Abstract method")  # pragma: no cover


# ----------------------------------------------------------------------
class _StatusFactory(ABC):
    """Interface for object that is able to create Status objects."""

    # ----------------------------------------------------------------------
    @abstractmethod
    @contextmanager
    def CreateStatus(
        self,
        display: str,
    ) -> Iterator[_InternalStatus]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def Stop(self) -> None:
        raise Exception("Abstract method")  # pragma: no cover


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
@contextmanager
def _GenerateStatusInfo(
    num_tasks_display_value: Optional[int],
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData],
    *,
    quiet: bool,
    refresh_per_second: Optional[float],
) -> Iterator[tuple[list[_StatusFactory], Callable[[TaskData], None],],]:
    success_count = 0
    error_count = 0
    warning_count = 0

    count_lock = threading.Lock()

    # Create the heading
    if desc.endswith("..."):
        desc = desc[: -len("...")]

    heading = desc

    if num_tasks_display_value is not None:
        items_text = inflect.no("item", num_tasks_display_value)

        if heading:
            heading += " ({})".format(items_text)
        else:
            heading = items_text

    heading += "..."

    with dm.Nested(
        heading,
        [
            lambda: "{} succeeded".format(inflect.no("item", success_count)),
            lambda: "{} with errors".format(inflect.no("item", error_count)),
            lambda: "{} with warnings".format(inflect.no("item", warning_count)),
        ],
    ) as execute_dm:
        # ----------------------------------------------------------------------
        def OnTaskDataComplete(
            task_data: TaskData,
        ) -> tuple[int, int, int]:
            nonlocal success_count
            nonlocal error_count
            nonlocal warning_count

            with count_lock:
                if task_data.result < 0:
                    error_count += 1

                    if execute_dm.result >= 0:
                        execute_dm.result = task_data.result

                elif task_data.result > 0:
                    warning_count += 1

                    if execute_dm.result == 0:
                        execute_dm.result = task_data.result

                else:
                    success_count += 1

            return success_count, error_count, warning_count

        # ----------------------------------------------------------------------

        with (
            _GenerateProgressStatusInfo
            if dm.capabilities.is_interactive
            else _GenerateNoopStatusInfo
        )(
            num_tasks_display_value,
            execute_dm,
            tasks,
            OnTaskDataComplete,
            quiet=quiet,
            refresh_per_second=refresh_per_second,
        ) as value:
            yield value


# ----------------------------------------------------------------------
@contextmanager
def _GenerateProgressStatusInfo(
    num_tasks_display_value: Optional[int],
    dm: DoneManager,
    tasks: list[TaskData],
    on_task_complete_func: Callable[[TaskData], tuple[int, int, int]],
    *,
    quiet: bool,
    refresh_per_second: Optional[float],
) -> Iterator[tuple[list[_StatusFactory], Callable[[TaskData], None],],]:
    with dm.YieldStdout() as stdout_context:
        stdout_context.persist_content = False

        # Technically speaking, it would be more correct to use `stdout_context.stream` here
        # rather than referencing `sys.stdout` directly, but it is really hard to work with mocked
        # stream as mocks will create mocks for everything called on the mock. Use sys.stdout
        # directly to avoid that particular problem.
        assert stdout_context.stream is sys.stdout or isinstance(
            stdout_context.stream, MagicMock
        ), stdout_context.stream

        progress_bar = Progress(
            *Progress.get_default_columns(),
            TimeElapsedColumn(),
            "{task.fields[status]}",
            console=Capabilities.Get(sys.stdout).CreateRichConsole(sys.stdout),
            transient=True,
            refresh_per_second=refresh_per_second or 10,
        )

        # ----------------------------------------------------------------------
        def CreateDescription(
            value: str,
            *,
            indent: bool = True,
        ) -> str:
            return TextwrapEx.BoundedLJust(
                "{}{}{}".format(
                    stdout_context.line_prefix,
                    "  " if indent else "",
                    value,
                ),
                DISPLAY_COLUMN_WIDTH,
            )

        # ----------------------------------------------------------------------
        class StatusImpl(_InternalStatus):  # pylint: disable=missing-class-docstring
            # ----------------------------------------------------------------------
            def __init__(
                self,
                task_id: TaskID,
            ):
                self._task_id = task_id

                self._num_steps: Optional[int] = None
                self._current_step: Optional[int] = None

            # ----------------------------------------------------------------------
            def SetNumSteps(
                self,
                num_steps: int,
            ) -> None:
                assert self._num_steps is None
                assert self._current_step is None

                self._num_steps = num_steps
                self._current_step = 0

                progress_bar.update(
                    self._task_id,
                    completed=self._current_step,
                    refresh=False,
                    total=self._num_steps,
                )

            # ----------------------------------------------------------------------
            def SetTitle(
                self,
                title: str,
            ) -> None:
                progress_bar.update(
                    self._task_id,
                    description=CreateDescription(title),
                    refresh=False,
                )

            # ----------------------------------------------------------------------
            def OnProgress(
                self,
                zero_based_step: Optional[int],
                status: Optional[str],
            ) -> bool:
                if zero_based_step is not None:
                    assert self._num_steps is not None
                    self._current_step = zero_based_step

                status = status or ""

                if self._num_steps is not None:
                    assert self._current_step is not None

                    status = "({} of {}) {}".format(
                        self._current_step + 1,
                        self._num_steps,
                        status,
                    )

                status = TextwrapEx.BoundedLJust(status, STATUS_COLUMN_WIDTH)

                progress_bar.update(
                    self._task_id,
                    completed=self._current_step,
                    refresh=False,
                    status=status,
                )

                return True

            # ----------------------------------------------------------------------
            def OnInfo(
                self,
                value: str,
                *,
                verbose: bool = False,
            ) -> None:
                if verbose:
                    if not dm.is_verbose:
                        return

                    assert (
                        TextwrapEx.VERBOSE_COLOR_ON == "\033[;7m"
                    ), "Ensure that the colors stay in sync"
                    prefix = "[black on white]VERBOSE:[/] "
                else:
                    assert (
                        TextwrapEx.INFO_COLOR_ON == "\033[;7m"
                    ), "Ensure that the colors stay in sync"
                    prefix = "[black on white]INFO:[/] "

                progress_bar.print(
                    "{}{}{}".format(
                        stdout_context.line_prefix,
                        prefix,
                        value,
                    ),
                    highlight=False,
                )

                stdout_context.persist_content = True

        # ----------------------------------------------------------------------
        class StatusFactory(_StatusFactory):  # pylint: disable=missing-class-docstring
            # ----------------------------------------------------------------------
            def __init__(
                self,
                task_id: TaskID,
            ):
                self._task_id = task_id

            # ----------------------------------------------------------------------
            @contextmanager
            def CreateStatus(
                self,
                display: str,
            ) -> Iterator[_InternalStatus]:
                progress_bar.update(
                    self._task_id,
                    completed=0,
                    description=CreateDescription(display),
                    refresh=False,
                    status="",
                    total=None,
                    visible=not quiet,
                )

                progress_bar.start_task(self._task_id)
                with ExitStack(lambda: progress_bar.stop_task(self._task_id)):
                    yield StatusImpl(self._task_id)

            # ----------------------------------------------------------------------
            def Stop(self) -> None:
                progress_bar.update(
                    self._task_id,
                    refresh=False,
                    visible=False,
                )

        # ----------------------------------------------------------------------

        total_progress_id = progress_bar.add_task(
            CreateDescription(
                "" if num_tasks_display_value is None else "Total Progress",
                indent=False,
            ),
            status="",
            total=num_tasks_display_value,
            visible=not num_tasks_display_value is None,
        )

        # ----------------------------------------------------------------------
        def OnTaskComplete(
            task_data: TaskData,
        ) -> None:
            if not quiet and task_data.result != 0:
                if task_data.result < 0:
                    assert (
                        TextwrapEx.ERROR_COLOR_ON == "\033[31;1m"
                    ), "Ensure that the colors stay in sync"
                    color = "red"
                    header = "ERROR"
                else:
                    assert (
                        TextwrapEx.WARNING_COLOR_ON == "\033[33;1m"
                    ), "Ensure that the colors stay in sync"
                    color = "yellow"
                    header = "WARNING"

                progress_bar.print(
                    r"{prefix}[bold {color}]{header}:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                        prefix=stdout_context.line_prefix,
                        color=color,
                        header=header,
                        name=task_data.display,
                        result=task_data.result,
                        short_desc=" ({})".format(task_data.short_desc)
                        if task_data.short_desc
                        else "",
                        suffix=str(task_data.log_filename)
                        if dm.capabilities.is_headless
                        else "[link=file:///{}]View Log[/]".format(
                            task_data.log_filename.as_posix(),
                        ),
                    ),
                    highlight=False,
                )

                stdout_context.persist_content = True

            success_count, error_count, warning_count = on_task_complete_func(task_data)

            if Capabilities.Get(sys.stdout).supports_colors:
                success_on = TextwrapEx.SUCCESS_COLOR_ON
                error_on = TextwrapEx.ERROR_COLOR_ON
                warning_on = TextwrapEx.WARNING_COLOR_ON
                color_off = TextwrapEx.COLOR_OFF
            else:
                success_on = ""
                error_on = ""
                warning_on = ""
                color_off = ""

            parts: list[str] = []

            for color_on, count, suffix in [
                (success_on, success_count, "succeeded"),
                (error_on, error_count, "failed"),
                (warning_on, warning_count, inflect.no("warning", warning_count)),
            ]:
                if count == 0:
                    content = "0"
                else:
                    content = "{}{}{}".format(color_on, count, color_off)

                parts.append("{} {}".format(content, suffix))

            progress_bar.update(
                total_progress_id,
                advance=1,
                refresh=False,
                status=TextwrapEx.BoundedLJust(", ".join(parts), STATUS_COLUMN_WIDTH),
            )

        # ----------------------------------------------------------------------

        enqueueing_status = "{}Enqueueing tasks...".format(stdout_context.line_prefix)

        stdout_context.stream.write(enqueueing_status)
        stdout_context.stream.flush()

        status_factories: list[_StatusFactory] = []

        for task in tasks:
            status_factories.append(
                StatusFactory(
                    progress_bar.add_task(
                        CreateDescription(task.display),
                        start=False,
                        status="",
                        total=None,
                        visible=False,
                    ),
                ),
            )

        stdout_context.stream.write("\r{}\r".format(" " * len(enqueueing_status)))
        stdout_context.stream.flush()

        progress_bar.start()
        with ExitStack(progress_bar.stop):
            yield status_factories, OnTaskComplete


# ----------------------------------------------------------------------
@contextmanager
def _GenerateNoopStatusInfo(
    num_tasks_display_value: Optional[int],  # pylint: disable=unused-argument
    dm: DoneManager,
    tasks: list[TaskData],
    on_task_complete_func: Callable[[TaskData], tuple[int, int, int]],
    *,
    quiet: bool,
    refresh_per_second: Optional[float],  # pylint: disable=unused-argument
) -> Iterator[tuple[list[_StatusFactory], Callable[[TaskData], None],],]:
    # ----------------------------------------------------------------------
    class StatusImpl(_InternalStatus):  # pylint: disable=missing-class-docstring
        # ----------------------------------------------------------------------
        def SetNumSteps(self, *args, **kwargs) -> None:  # pylint: disable=unused-argument
            pass

        # ----------------------------------------------------------------------
        def SetTitle(self, *args, **kwargs) -> None:  # pylint: disable=unused-argument
            pass

        # ----------------------------------------------------------------------
        def OnProgress(self, *args, **kwargs) -> bool:  # pylint: disable=unused-argument
            return True

        # ----------------------------------------------------------------------
        def OnInfo(self, *args, **kwargs) -> None:  # pylint: disable=unused-argument
            pass

    # ----------------------------------------------------------------------
    class StatusFactory(_StatusFactory):  # pylint: disable=missing-class-docstring
        # ----------------------------------------------------------------------
        @contextmanager
        def CreateStatus(  # pylint: disable=unused-argument
            self,
            *args,
            **kwargs,
        ) -> Iterator[_InternalStatus]:
            yield StatusImpl()

        # ----------------------------------------------------------------------
        def Stop(self) -> None:
            pass

    # ----------------------------------------------------------------------
    def OnTaskComplete(
        task_data: TaskData,
    ) -> None:
        on_task_complete_func(task_data)

        if not quiet and task_data.result != 0:
            content = "{name}: {result}{short_desc} [{suffix}]\n".format(
                name=task_data.display,
                result=task_data.result,
                short_desc=" ({})".format(task_data.short_desc) if task_data.short_desc else "",
                suffix=str(task_data.log_filename)
                if dm.capabilities.is_headless
                else TextwrapEx.CreateAnsiHyperLink(
                    "file:///{}".format(task_data.log_filename.as_posix()),
                    "View Log",
                ),
            )

            if task_data.result < 0:
                dm.WriteError(content)
            else:
                dm.WriteWarning(content)

    # ----------------------------------------------------------------------

    yield (
        cast(list[_StatusFactory], [StatusFactory() for _ in tasks]),
        OnTaskComplete,
    )


# ----------------------------------------------------------------------
def _ExecuteTask(
    desc: str,
    task_data: TaskData,
    init_func: ExecuteTasksTypes.InitFuncType,
    status_factory: _StatusFactory,
    on_task_complete_func: Callable[[TaskData], None],
    *,
    is_debug: bool,
) -> None:
    with ExitStack(lambda: on_task_complete_func(task_data)):
        start_time = time.perf_counter()

        try:
            with status_factory.CreateStatus(task_data.display) as status:
                task_data.log_filename, prepare_func = init_func(task_data.context)

                # ----------------------------------------------------------------------
                def OnSimpleStatus(
                    value: str,
                ) -> None:
                    status.OnProgress(None, value)

                # ----------------------------------------------------------------------

                prepare_result = prepare_func(OnSimpleStatus)

                num_steps: Optional[int] = None
                execute_func: Optional[ExecuteTasksTypes.ExecuteFuncType] = None

                if isinstance(prepare_result, tuple):
                    num_steps, execute_func = prepare_result
                else:
                    execute_func = prepare_result

                assert execute_func is not None

                # ----------------------------------------------------------------------
                @contextmanager
                def AcquireExecutionLock():
                    if task_data.execution_lock is None:
                        yield
                        return

                    OnSimpleStatus("Waiting...")
                    with task_data.execution_lock:
                        yield

                # ----------------------------------------------------------------------

                with AcquireExecutionLock():
                    if num_steps is not None:
                        assert num_steps >= 0, num_steps
                        status.SetNumSteps(num_steps)

                    execute_result = execute_func(status)

                    if isinstance(execute_result, tuple):
                        task_data.result, task_data.short_desc = execute_result
                    else:
                        task_data.result = execute_result
                        task_data.short_desc = None

        except KeyboardInterrupt:  # pylint: disable=try-except-raise
            raise

        except Exception as ex:
            if is_debug:
                error = traceback.format_exc()
            else:
                error = str(ex)

            error = error.rstrip()

            if not hasattr(task_data, "log_filename"):
                # If here, this error has happened before we have received anything
                # from the initial callback. Create a log file and write the exception
                # information.
                task_data.log_filename = PathEx.CreateTempFileName()
                assert task_data.log_filename is not None

                with task_data.log_filename.open("w") as f:
                    f.write(error)

            else:
                with task_data.log_filename.open("a+") as f:
                    f.write("\n\n{}\n".format(error))

            if isinstance(ex, TransformException):
                result = 1
                short_desc = "{} failed".format(task_data.display)
            else:
                result = CATASTROPHIC_TASK_FAILURE_RESULT
                short_desc = "{} failed".format(desc)

            task_data.result = result
            task_data.short_desc = short_desc

        finally:
            assert hasattr(task_data, "result")
            assert hasattr(task_data, "short_desc")
            assert hasattr(task_data, "log_filename")

            task_data.execution_time = datetime.timedelta(seconds=time.perf_counter() - start_time)


# ----------------------------------------------------------------------
@contextmanager
def _YieldTemporaryDirectory(
    dm: DoneManager,
) -> Iterator[Path]:
    temp_directory = PathEx.CreateTempDirectory()

    # ----------------------------------------------------------------------
    def OnExit():
        # Remove the temp directory if everything worked as expected
        if dm.result == 0:
            shutil.rmtree(temp_directory)
            return

        if dm.capabilities.is_headless:
            dm.WriteInfo(
                "\nThe temporary working directory '{}' was preserved due to errors encountered while executing tasks.".format(
                    temp_directory
                )
            )
        else:
            dm.WriteInfo(
                "\nThe {} was preserved due to errors encountered while executing tasks.".format(
                    TextwrapEx.CreateAnsiHyperLink(
                        "file:///{}".format(temp_directory.as_posix()),
                        "temporary working directory",
                    ),
                ),
            )

    # ----------------------------------------------------------------------

    with ExitStack(OnExit):
        yield temp_directory


# ----------------------------------------------------------------------
def _TransformCompressed(
    temp_directory: Path,
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData],
    prepare_func: TransformTasksExTypes.PrepareFuncType[TransformedType],
    *,
    quiet: bool,
    num_threads: int,
    refresh_per_second: Optional[float],
    return_exceptions: bool,
) -> list[
    Union[
        None,
        TransformedType,
        Exception,  # If `return_exceptions` is True and an exception was encountered
    ],
]:
    assert num_threads > 1, num_threads

    all_results: list[None | TransformedType | Exception] = [
        None,
    ] * len(tasks)

    with _GenerateStatusInfo(
        len(tasks),
        dm,
        desc,
        [TaskData("", thread_index) for thread_index in range(num_threads)],
        quiet=quiet,
        refresh_per_second=refresh_per_second,
    ) as (status_factories, on_task_complete_func):
        task_index = 0
        task_index_lock = threading.Lock()

        # ----------------------------------------------------------------------
        def Impl(
            thread_index: int,
        ) -> None:
            nonlocal task_index

            log_filename = temp_directory / "{:06}.log".format(thread_index)
            status_factory = status_factories[thread_index]

            with ExitStack(status_factory.Stop):
                while True:
                    with task_index_lock:
                        this_task_index = task_index
                        task_index += 1

                    if this_task_index >= len(tasks):
                        break

                    task_data = tasks[this_task_index]

                    # ----------------------------------------------------------------------
                    def Init(
                        *args, **kwargs  # pylint: disable=unused-argument
                    ) -> tuple[Path, ExecuteTasksTypes.PrepareFuncType]:
                        # ----------------------------------------------------------------------
                        def Prepare(
                            on_simple_status_func: Callable[[str], None],
                        ) -> Union[
                            tuple[int, ExecuteTasksTypes.ExecuteFuncType],
                            ExecuteTasksTypes.ExecuteFuncType,
                        ]:
                            prepare_result = prepare_func(task_data.context, on_simple_status_func)

                            num_steps: Optional[int] = None
                            transform_func: Optional[TransformTasksExTypes.TransformFuncType] = None

                            if isinstance(prepare_result, tuple):
                                num_steps, transform_func = prepare_result
                            else:
                                transform_func = prepare_result

                            assert transform_func is not None

                            # ----------------------------------------------------------------------
                            def Execute(
                                status: Status,
                            ) -> tuple[int, Optional[str]]:
                                try:
                                    transform_result = transform_func(status)

                                    return_code = 0
                                    result: Any = None
                                    short_desc: Optional[str] = None

                                    if isinstance(transform_result, TransformResultComplete):
                                        result = transform_result.value
                                        return_code = transform_result.return_code or 0
                                        short_desc = transform_result.short_desc
                                    else:
                                        result = transform_result

                                    all_results[this_task_index] = result
                                    return return_code, short_desc

                                except Exception as ex:
                                    if return_exceptions:
                                        all_results[this_task_index] = ex

                                    raise

                            # ----------------------------------------------------------------------

                            if num_steps is None:
                                return Execute

                            return num_steps, Execute

                        # ----------------------------------------------------------------------

                        return log_filename, Prepare

                    # ----------------------------------------------------------------------

                    _ExecuteTask(
                        desc,
                        task_data,
                        Init,
                        status_factory,
                        on_task_complete_func,
                        is_debug=dm.is_debug,
                    )

        # ----------------------------------------------------------------------

        with ThreadPoolExecutor(
            max_workers=num_threads,
        ) as executor:
            futures = [executor.submit(Impl, thread_index) for thread_index in range(num_threads)]

            for future in futures:
                future.result()

    return all_results


# ----------------------------------------------------------------------
def _TransformNotCompressed(
    temp_directory: Path,
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData],
    prepare_func: TransformTasksExTypes.PrepareFuncType[TransformedType],
    *,
    quiet: bool,
    num_threads: int,
    refresh_per_second: Optional[float],
    return_exceptions: bool,
) -> list[
    Union[
        None,
        TransformedType,
        Exception,  # If `return_exceptions` is True and an exception was encountered
    ],
]:
    """Executes tasks with one executor per task."""

    # Update the task context with the task index
    for task_index, task in enumerate(tasks):
        task.context = (task_index, task.context)

    # ----------------------------------------------------------------------
    def RestoreTaskContext():
        for task in tasks:
            task.context = task.context[1]

    # ----------------------------------------------------------------------

    with ExitStack(RestoreTaskContext):
        all_results: list[None | TransformedType | Exception] = [
            None,
        ] * len(tasks)

        # ----------------------------------------------------------------------
        def Init(
            context: tuple[int, Any],
        ) -> tuple[Path, ExecuteTasksTypes.PrepareFuncType]:
            task_index, context = context

            log_filename = temp_directory / "{:06}.log".format(task_index)

            # ----------------------------------------------------------------------
            def Prepare(
                on_simple_status_func: Callable[[str], None],
            ) -> Union[
                tuple[int, ExecuteTasksTypes.ExecuteFuncType],
                ExecuteTasksTypes.ExecuteFuncType,
            ]:
                prepare_result = prepare_func(context, on_simple_status_func)

                num_steps: Optional[int] = None
                transform_func: Optional[TransformTasksExTypes.TransformFuncType] = None

                if isinstance(prepare_result, tuple):
                    num_steps, transform_func = prepare_result
                else:
                    transform_func = prepare_result

                assert transform_func is not None

                # ----------------------------------------------------------------------
                def Execute(
                    status: Status,
                ) -> tuple[int, Optional[str]]:
                    try:
                        transform_result = transform_func(status)

                        return_code = 0
                        result: Any = None
                        short_desc: Optional[str] = None

                        if isinstance(transform_result, TransformResultComplete):
                            result = transform_result.value
                            return_code = transform_result.return_code or 0
                            short_desc = transform_result.short_desc
                        else:
                            result = transform_result

                        all_results[task_index] = result
                        return return_code, short_desc

                    except Exception as ex:
                        if return_exceptions:
                            all_results[task_index] = ex

                        raise

                # ----------------------------------------------------------------------

                if num_steps is None:
                    return Execute

                return num_steps, Execute

            # ----------------------------------------------------------------------

            return log_filename, Prepare

        # ----------------------------------------------------------------------

        ExecuteTasks(
            dm,
            desc,
            tasks,
            Init,
            quiet=quiet,
            max_num_threads=num_threads,
            refresh_per_second=refresh_per_second,
        )

        return all_results
