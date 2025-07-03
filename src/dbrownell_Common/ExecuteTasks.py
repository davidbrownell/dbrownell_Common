"""Functionality to invoke a series of tasks in parallel."""

import datetime
import multiprocessing
import shutil
import sys
import threading
import time
import traceback

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import auto, Enum
from pathlib import Path
from typing import cast, Generic, Optional, Protocol, TypeVar, Union
from unittest.mock import MagicMock

from dbrownell_Common.ContextlibEx import ExitStack
from dbrownell_Common.InflectEx import inflect
from dbrownell_Common import PathEx
from dbrownell_Common.Streams.Capabilities import Capabilities
from dbrownell_Common.Streams.DoneManager import DoneManager
from dbrownell_Common.Streams.StreamDecorator import StreamDecorator
from dbrownell_Common import TextwrapEx
from rich.progress import Progress, TaskID, TimeElapsedColumn


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
CATASTROPHIC_TASK_FAILURE_RESULT = -123

DISPLAY_COLUMN_WIDTH = int(Capabilities.DEFAULT_COLUMNS * 0.50)
STATUS_COLUMN_WIDTH = int(Capabilities.DEFAULT_COLUMNS * 0.30)

# ----------------------------------------------------------------------
TaskDataContextT_contra = TypeVar("TaskDataContextT_contra", contravariant=True)


@dataclass
class TaskData(Generic[TaskDataContextT_contra]):
    """Data associated with a single task."""

    # ----------------------------------------------------------------------
    # |  These values are populated by the caller

    display: str
    context: TaskDataContextT_contra

    # Set this value if the task needs to be processed exclusively with respect to other `TaskData`
    # objects created with the same `execution_lock` instance.
    execution_lock: Optional[threading.Lock] = field(default=None)

    # ----------------------------------------------------------------------
    # |  These values are populated during task execution
    result: int = field(init=False)
    short_desc: Optional[str] = field(init=False)

    execution_time: datetime.timedelta = field(init=False)
    log_filename: Path = field(init=False)


# ----------------------------------------------------------------------
class ExperienceType(Enum):
    """The type of experience."""

    Simple = auto()
    ProgressBar = auto()


# ----------------------------------------------------------------------
class Status(ABC):
    """Abstract interface for an object that can be used to interact with an actively running task."""

    # ----------------------------------------------------------------------
    @abstractmethod
    def SetTitle(self, title: str) -> None:
        """Set the title of the task."""
        raise Exception("Abstract method")  # pragma: no cover  # noqa: EM101, TRY002, TRY003

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnProgress(
        self,
        zero_based_step: Optional[int],
        status: Optional[str],
    ) -> bool:
        """Respond to a progress update for the task; return False to cancel the task."""
        raise Exception("Abstract method")  # pragma: no cover  # noqa: EM101, TRY002, TRY003

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnInfo(
        self,
        value: str,
        *,
        verbose: bool = False,
    ) -> None:
        """Respond to an info message for the task."""
        raise Exception("Abstract method")  # pragma: no cover  # noqa: EM101, TRY002, TRY003

    # ----------------------------------------------------------------------
    @abstractmethod
    def Log(
        self,
        message: str,
    ) -> None:
        """Write a message to the log file."""
        raise Exception("Abstract method")  # pragma: no cover  # noqa: EM101, TRY002, TRY003


# ----------------------------------------------------------------------
class ExecuteTasksTypes:
    """Types used by `ExecuteTasks`."""

    # ----------------------------------------------------------------------
    class InitFuncType(Protocol[TaskDataContextT_contra]):
        """Initialize a task for execution."""

        def __call__(  # noqa: D102
            self,
            context: TaskDataContextT_contra,
        ) -> tuple[
            Path,  # Log filename
            "ExecuteTasksTypes.PrepareFuncType",
        ]: ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class PrepareFuncType(Protocol):
        """Prepare a task for execution."""

        def __call__(  # noqa: D102
            self,
            on_simple_status_func: Callable[
                [
                    str,  # status
                ],
                None,
            ],
        ) -> Union[
            tuple[
                int,  # Number of steps to execute
                "ExecuteTasksTypes.ExecuteFuncType",
            ],
            "ExecuteTasksTypes.ExecuteFuncType",
        ]: ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class ExecuteFuncType(Protocol):
        """Execute a task."""

        def __call__(  # noqa: D102
            self,
            status: Status,
        ) -> Union[
            tuple[
                int,  # Result code
                Optional[str],  # Final status message
            ],
            int,
        ]:  # Result code
            ...  # pragma: no cover


# ----------------------------------------------------------------------
@dataclass
class CompleteTransformResult:
    """Complex result returned by a transform function."""

    value: object
    return_code: Optional[int] = field(default=None)
    short_desc: Optional[str] = field(default=None)


# Note that this definition is here for backwards compatibility. The class was named
# `TransformResultComplete` prior to 0.14.8 and was renamed to `CompleteTranformResult` in 0.14.8.
TransformResultComplete = CompleteTransformResult


# ----------------------------------------------------------------------
class TransformTasksExTypes:
    """Types used by `TransformTasksEx`."""

    # ----------------------------------------------------------------------
    class PrepareFuncType(Protocol[TaskDataContextT_contra]):
        """Prepare a task for execution."""

        def __call__(  # noqa: D102
            self,
            context: TaskDataContextT_contra,
            on_simple_status_func: Callable[
                [
                    str,  # status
                ],
                None,
            ],
        ) -> Union[
            tuple[
                int,  # Number of steps to execute
                "TransformTasksExTypes.TransformFuncType",
            ],
            "TransformTasksExTypes.TransformFuncType",
        ]: ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class TransformFuncType(Protocol):
        """Transform a context value associated with a task."""

        def __call__(  # noqa: D102
            self,
            status: Status,
        ) -> Union[CompleteTransformResult, object]: ...  # pragma: no cover


# ----------------------------------------------------------------------
class TransformTasksTypes:
    """Types used by `TransformTasks`."""

    # ----------------------------------------------------------------------
    class TransformFuncType(Protocol[TaskDataContextT_contra]):
        """Transforms a context value associated with a task."""

        def __call__(  # noqa: D102
            self,
            context: TaskDataContextT_contra,
            status: Status,
        ) -> Union[CompleteTransformResult, object]: ...  # pragma: no cover


# ----------------------------------------------------------------------
class TransformError(Exception):
    """Exception raised when the `Transform` function encounters errors when processing a task."""


# ----------------------------------------------------------------------
class YieldQueueExecutorTypes:
    """Types used by `YieldQueueExecutor`."""

    # ----------------------------------------------------------------------
    class PrepareFuncType(Protocol):
        """Prepare a task for execution."""

        def __call__(  # noqa: D102
            self,
            on_simple_status_func: Callable[
                [
                    str,  # status
                ],
                None,
            ],
        ) -> Union[
            tuple[
                int,  # Number of steps to execute
                "YieldQueueExecutorTypes.ExecuteFuncType",
            ],
            "YieldQueueExecutorTypes.ExecuteFuncType",
        ]: ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class ExecuteFuncType(Protocol):
        """Execute a task."""

        def __call__(  # noqa: D102
            self,
            status: Status,
        ) -> Optional[str]: ...  # pragma: no cover

    # ----------------------------------------------------------------------
    class EnqueueFuncType(Protocol):
        """Enqueue a task for execution."""

        def __call__(  # noqa: D102
            self,
            description: str,
            prepare_func: "YieldQueueExecutorTypes.PrepareFuncType",
        ) -> None: ...


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def ExecuteTasks(
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData[TaskDataContextT_contra]],
    init_func: ExecuteTasksTypes.InitFuncType[TaskDataContextT_contra],
    *,
    experience_type: Optional[ExperienceType] = None,
    quiet: bool = False,
    max_num_threads: Optional[int] = None,
    refresh_per_second: Optional[float] = None,
) -> None:
    """Execute the specified tasks in parallel."""

    with _GenerateExperienceData(
        experience_type,
        len(tasks),
        dm,
        desc,
        tasks,
        refresh_per_second,
        quiet=quiet,
    ) as experience_data:
        if max_num_threads == 1 or len(tasks) == 1:
            # Single threaded
            for task_data, status_factory in zip(
                tasks, experience_data.internal_status_factories, strict=True
            ):
                with ExitStack(status_factory.Stop):
                    _ExecuteTask(
                        desc,
                        task_data,
                        init_func,
                        status_factory,
                        experience_data.on_task_data_complete_func,
                        is_debug=dm.is_debug,
                    )
        else:
            # Multi-threaded
            with ThreadPoolExecutor(
                max_workers=max_num_threads,
            ) as executor:
                # ----------------------------------------------------------------------
                def Impl(
                    task_data: TaskData,
                    status_factory: _InternalStatusFactory,
                ) -> None:
                    with ExitStack(status_factory.Stop):
                        _ExecuteTask(
                            desc,
                            task_data,
                            init_func,
                            status_factory,
                            experience_data.on_task_data_complete_func,
                            is_debug=dm.is_debug,
                        )

                # ----------------------------------------------------------------------

                futures = [
                    executor.submit(Impl, task_data, status_factory)
                    for task_data, status_factory in zip(
                        tasks, experience_data.internal_status_factories, strict=True
                    )
                ]

                for future in futures:
                    future.result()


# ----------------------------------------------------------------------
def TransformTasksEx(
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData[TaskDataContextT_contra]],
    prepare_func: TransformTasksExTypes.PrepareFuncType[TaskDataContextT_contra],
    *,
    experience_type: Optional[ExperienceType] = None,
    quiet: bool = False,
    max_num_threads: Optional[int] = None,
    refresh_per_second: Optional[float] = None,
    no_compress_tasks: bool = False,
    return_exceptions: bool = False,
) -> list[Union[None, object, Exception]]:
    """Execute functions that return values; use this version for tasks whose values are transformed in multiple steps or require custom preparation."""

    with _YieldTemporaryDirectory(dm) as temp_directory:
        cpu_count = multiprocessing.cpu_count()

        num_threads = min(len(tasks), cpu_count)
        if max_num_threads:
            num_threads = min(num_threads, max_num_threads)

        if no_compress_tasks or num_threads < cpu_count:
            impl_func = _TransformNotCompressed
        else:
            impl_func = _TransformCompressed

        return impl_func(
            dm,
            desc,
            tasks,
            prepare_func,
            temp_directory,
            experience_type=experience_type,
            quiet=quiet,
            num_threads=num_threads,
            refresh_per_second=refresh_per_second,
            return_exceptions=return_exceptions,
        )


# ----------------------------------------------------------------------
def TransformTasks(
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData[TaskDataContextT_contra]],
    transform_func: TransformTasksTypes.TransformFuncType[TaskDataContextT_contra],
    *,
    experience_type: Optional[ExperienceType] = None,
    quiet: bool = False,
    max_num_threads: Optional[int] = None,
    refresh_per_second: Optional[float] = None,
    no_compress_tasks: bool = False,
    return_exceptions: bool = False,
) -> list[Union[None, object, Exception]]:
    """Execute functions that return values; use this version for single-step tasks that do not require extensive perparation."""

    # ----------------------------------------------------------------------
    def Prepare(
        context: TaskDataContextT_contra,
        on_simple_status_func: Callable[[str], None],  # noqa: ARG001
    ) -> TransformTasksExTypes.TransformFuncType:
        return lambda status: transform_func(context, status)

    # ----------------------------------------------------------------------

    return TransformTasksEx(
        dm,
        desc,
        tasks,
        Prepare,
        experience_type=experience_type,
        quiet=quiet,
        max_num_threads=max_num_threads,
        refresh_per_second=refresh_per_second,
        no_compress_tasks=no_compress_tasks,
        return_exceptions=return_exceptions,
    )


# ----------------------------------------------------------------------
@contextmanager
def YieldQueueExecutor(  # noqa: PLR0915
    dm: DoneManager,
    desc: str,
    *,
    experience_type: Optional[ExperienceType] = None,
    quiet: bool = False,
    max_num_threads: Optional[int] = None,
    refresh_per_second: Optional[float] = None,
) -> Iterator[YieldQueueExecutorTypes.EnqueueFuncType]:
    """Yield a callable that can be used to enqueue tasks executed by workers running across multiple threads."""

    idle_title = "Waiting for tasks..."

    with _YieldTemporaryDirectory(dm) as temp_directory:
        num_threads = max_num_threads or multiprocessing.cpu_count()

        with _GenerateExperienceData(
            experience_type,
            None,
            dm,
            desc,
            [TaskData(idle_title, thread_index) for thread_index in range(num_threads)],
            quiet=quiet,
            refresh_per_second=refresh_per_second,
        ) as experience_data:
            queue: list[tuple[str, YieldQueueExecutorTypes.PrepareFuncType]] = []
            queue_lock = threading.Lock()

            available_condition = threading.Condition()

            quit_event = threading.Event()

            # ----------------------------------------------------------------------
            def Enqueue(
                description: str,
                prepare_func: YieldQueueExecutorTypes.PrepareFuncType,
            ) -> None:
                with queue_lock:
                    queue.append((description, prepare_func))

                with available_condition:
                    available_condition.notify()

            # ----------------------------------------------------------------------
            def Impl(
                thread_index: int,
            ) -> None:
                log_filename = temp_directory / f"{thread_index:06}.log"
                status_factory = experience_data.internal_status_factories[thread_index]

                with ExitStack(status_factory.Stop):
                    while True:
                        task_desc: str | None = None
                        prepare_func: YieldQueueExecutorTypes.PrepareFuncType | None = None

                        with available_condition:  # noqa: SIM117
                            with queue_lock:
                                if queue:
                                    task_desc, prepare_func = queue.pop(0)
                                elif quit_event.is_set():
                                    break

                            if task_desc is None or prepare_func is None:
                                available_condition.wait()
                                continue

                        assert task_desc is not None
                        assert prepare_func is not None

                        # ----------------------------------------------------------------------
                        def Init(
                            *args,  # noqa: ARG001
                            task_desc: str = task_desc,
                            prepare_func: YieldQueueExecutorTypes.PrepareFuncType = prepare_func,
                            **kwargs,  # noqa: ARG001
                        ) -> tuple[Path, ExecuteTasksTypes.PrepareFuncType]:
                            # ----------------------------------------------------------------------
                            def Prepare(
                                on_simple_status_func: Callable[[str], None],
                            ) -> Union[
                                tuple[int, ExecuteTasksTypes.ExecuteFuncType],
                                ExecuteTasksTypes.ExecuteFuncType,
                            ]:
                                prepare_result = prepare_func(on_simple_status_func)

                                num_steps: Optional[int] = None
                                execute_func: Optional[YieldQueueExecutorTypes.ExecuteFuncType] = None

                                if isinstance(prepare_result, tuple):
                                    num_steps, execute_func = prepare_result
                                else:
                                    execute_func = prepare_result

                                assert execute_func is not None

                                # ----------------------------------------------------------------------
                                def Execute(status: Status) -> tuple[int, Optional[str]]:
                                    status.SetTitle(task_desc)

                                    # ----------------------------------------------------------------------
                                    def OnExit() -> None:
                                        status.SetTitle(idle_title)
                                        cast(_InternalStatus, status).SetNumSteps(None)

                                    # ----------------------------------------------------------------------

                                    with ExitStack(OnExit):
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
                            experience_data.on_task_data_complete_func,
                            is_debug=dm.is_debug,
                        )

            # ----------------------------------------------------------------------

            with ThreadPoolExecutor(
                max_workers=num_threads,
            ) as executor:
                futures = [executor.submit(Impl, thread_index) for thread_index in range(num_threads)]

                yield Enqueue

                quit_event.set()

                with available_condition:
                    available_condition.notify_all()

                for future in futures:
                    future.result()


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
class _InternalStatus(Status):
    """Augmented interface that adds internal functionality to the `Status` interface."""

    # ----------------------------------------------------------------------
    def __init__(self) -> None:
        self._log_messages: list[str] = []

    # ----------------------------------------------------------------------
    @abstractmethod
    def SetNumSteps(
        self,
        num_steps: Optional[int],
    ) -> None:
        """Set the number of steps for the task."""
        raise Exception("Abstract method")  # pragma: no cover  # noqa: EM101, TRY002, TRY003

    # ----------------------------------------------------------------------
    def Log(self, message: str) -> None:
        self._log_messages.append(message)

    # ----------------------------------------------------------------------
    @property
    def log_messages(self) -> str:
        """Return a single string containing all the log messages."""
        return "\n".join(self._log_messages)


# ----------------------------------------------------------------------
class _InternalStatusFactory(ABC):
    """Abstract interface for an object that can be used to create a `_InternalStatus` object."""

    # ----------------------------------------------------------------------
    @abstractmethod
    @contextmanager
    def GenerateInternalStatus(
        self,
        display: str,
    ) -> Iterator[_InternalStatus]:
        """Generate a `_InternalStatus` object."""
        raise Exception("Abstract method")  # pragma: no cover  # noqa: EM101, TRY002, TRY003

    # ----------------------------------------------------------------------
    @abstractmethod
    def Stop(self) -> None:
        """Stop all created `_InternalStatus` objects."""
        raise Exception("Abstract method")  # pragma: no cover  # noqa: EM101, TRY002, TRY003


# ----------------------------------------------------------------------
@dataclass
class _ExperienceData:
    """Data used in creating an ExecuteTasks experience."""

    internal_status_factories: list[_InternalStatusFactory]
    on_task_data_complete_func: Callable[[TaskData], None]


# ----------------------------------------------------------------------
class _ProgressBarExperienceInternalStatus(_InternalStatus):
    # ----------------------------------------------------------------------
    def __init__(
        self,
        stdout_context: StreamDecorator.YieldStdoutContext,
        progress_bar: Progress,
        task_id: TaskID,
        *,
        is_output_verbose: bool,
    ) -> None:
        super().__init__()

        self._stdout_context = stdout_context
        self._progress_bar = progress_bar
        self._task_id = task_id
        self._is_output_verbose = is_output_verbose

        self._num_steps: Optional[int] = None
        self._current_step: Optional[int] = None

    # ----------------------------------------------------------------------
    def SetNumSteps(self, num_steps: Optional[int]) -> None:
        if num_steps is None:
            self._num_steps = None
            self._current_step = None
        else:
            assert self._num_steps is None
            assert self._current_step is None

            self._num_steps = num_steps
            self._current_step = 0

        self._progress_bar.update(
            self._task_id,
            completed=self._current_step,
            refresh=False,
            total=self._num_steps,
            visible=self._num_steps is not None,
        )

    # ----------------------------------------------------------------------
    def SetTitle(self, title: str) -> None:
        self._progress_bar.update(
            self._task_id,
            description=_CreateProgressBarDescription(title, self._stdout_context.line_prefix),
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

        self._progress_bar.update(
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
            if not self._is_output_verbose:
                return

            assert TextwrapEx.VERBOSE_COLOR_ON == "\033[;7m", "Ensure that the colors stay in sync"
            prefix = "[black on white]VERBOSE:[/] "
        else:
            assert TextwrapEx.INFO_COLOR_ON == "\033[;7m", "Ensure that the colors stay in sync"
            prefix = "[black on white]INFO:[/] "

        self._progress_bar.print(
            "{}{}{}".format(
                self._stdout_context.line_prefix,
                prefix,
                value,
            ),
            highlight=False,
        )

        self._stdout_context.persist_content = True


# ----------------------------------------------------------------------
class _ProgressBarExperienceInternalStatusFactory(_InternalStatusFactory):
    # ----------------------------------------------------------------------
    def __init__(
        self,
        stdout_context: StreamDecorator.YieldStdoutContext,
        progress_bar: Progress,
        task_id: TaskID,
        *,
        quiet: bool,
        is_output_verbose: bool,
    ) -> None:
        self._stdout_context = stdout_context
        self._progress_bar = progress_bar
        self._task_id = task_id
        self._quiet = quiet
        self._is_output_verbose = is_output_verbose

    # ----------------------------------------------------------------------
    @contextmanager
    def GenerateInternalStatus(
        self,
        display: str,
    ) -> Iterator[_ProgressBarExperienceInternalStatus]:
        self._progress_bar.update(
            self._task_id,
            completed=0,
            description=_CreateProgressBarDescription(display, self._stdout_context.line_prefix),
            refresh=False,
            status="",
            total=None,
            visible=not self._quiet,
        )

        self._progress_bar.start_task(self._task_id)
        with ExitStack(lambda: self._progress_bar.stop_task(self._task_id)):
            yield _ProgressBarExperienceInternalStatus(
                self._stdout_context,
                self._progress_bar,
                self._task_id,
                is_output_verbose=self._is_output_verbose,
            )

    # ----------------------------------------------------------------------
    def Stop(self) -> None:
        self._progress_bar.update(
            self._task_id,
            refresh=False,
            visible=False,
        )


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
@contextmanager
def _GenerateExperienceData(
    experience_type: Optional[ExperienceType],
    num_tasks_display_value: Optional[int],
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData],
    refresh_per_second: Optional[float],
    *,
    quiet: bool,
) -> Iterator[_ExperienceData]:
    if experience_type is None:
        experience_type = (
            ExperienceType.ProgressBar if dm.capabilities.is_interactive else ExperienceType.Simple
        )

    # Create the heading
    if num_tasks_display_value is not None:
        desc = desc.removesuffix("...")

        items_text = inflect.no("item", num_tasks_display_value)  # type: ignore[reportArgumentType]

        if desc:
            desc += f" ({items_text})"
        else:
            desc = items_text

        desc += "..."

    # Display the stats
    success_count = 0
    warning_count = 0
    error_count = 0

    count_lock = threading.Lock()

    with dm.Nested(
        desc,
        [
            lambda: "{} succeeded".format(inflect.no("item", success_count)),  # type: ignore[reportArgumentType]
            lambda: "{} with errors".format(inflect.no("item", error_count)),  # type: ignore[reportArgumentType]
            lambda: "{} with warnings".format(inflect.no("item", warning_count)),  # type: ignore[reportArgumentType]
        ],
    ) as execute_dm:
        # ----------------------------------------------------------------------
        def OnTaskDataComplete(
            task_data: TaskData,
        ) -> tuple[int, int, int]:
            nonlocal success_count, warning_count, error_count

            assert task_data.result is not None

            with count_lock:
                if task_data.result < 0:
                    error_count += 1

                    if execute_dm.result >= 0:
                        execute_dm.result = task_data.result

                elif task_data.result > 0:
                    warning_count += 1

                    if execute_dm.result >= 0:
                        execute_dm.result = task_data.result

                else:
                    success_count += 1

            return success_count, warning_count, error_count

        # ----------------------------------------------------------------------

        if experience_type == ExperienceType.ProgressBar:
            with _GenerateProgressBarExperienceData(
                num_tasks_display_value,
                execute_dm,
                tasks,
                OnTaskDataComplete,
                quiet=quiet,
                refresh_per_second=refresh_per_second,
            ) as experience_data:
                yield experience_data
        elif experience_type == ExperienceType.Simple:
            with _GenerateSimpleExperienceData(
                execute_dm,
                tasks,
                OnTaskDataComplete,
                quiet=quiet,
            ) as experience_data:
                yield experience_data
        else:
            assert False, experience_type  # pragma: no cover  # noqa: B011, PT015


# ----------------------------------------------------------------------
@contextmanager
def _GenerateSimpleExperienceData(
    dm: DoneManager,
    tasks: list[TaskData],
    on_task_data_complete_func: Callable[[TaskData], tuple[int, int, int]],
    *,
    quiet: bool,
) -> Iterator[_ExperienceData]:
    output_lock = threading.Lock()

    # ----------------------------------------------------------------------
    class InternalStatus(_InternalStatus):
        # ----------------------------------------------------------------------
        def SetNumSteps(self, *args, **kwargs) -> None:
            pass

        # ----------------------------------------------------------------------
        def SetTitle(self, *args, **kwargs) -> None:
            pass

        # ----------------------------------------------------------------------
        def OnProgress(self, *args, **kwargs) -> bool:  # noqa: ARG002
            return True

        # ----------------------------------------------------------------------
        def OnInfo(self, *args, **kwargs) -> None:
            pass

    # ----------------------------------------------------------------------
    class InternalStatusFactory(_InternalStatusFactory):
        # ----------------------------------------------------------------------
        @contextmanager
        def GenerateInternalStatus(self, *args, **kwargs) -> Iterator[InternalStatus]:  # noqa: ARG002
            yield InternalStatus()

        # ----------------------------------------------------------------------
        def Stop(self) -> None:
            pass

    # ----------------------------------------------------------------------
    def OnTaskDataComplete(
        task_data: TaskData,
    ) -> None:
        on_task_data_complete_func(task_data)

        if (
            not quiet
            and task_data.result != 0
            and task_data.log_filename is not None
            and task_data.log_filename.is_file()
        ):
            content = "{name}: {result}{short_desc} [{suffix}]\n".format(
                name=task_data.display,
                result=task_data.result,
                short_desc=" ({})".format(task_data.short_desc) if task_data.short_desc else "",
                suffix=(
                    str(task_data.log_filename)
                    if dm.capabilities.is_headless
                    else TextwrapEx.CreateAnsiHyperLink(
                        "file:///{}".format(task_data.log_filename.as_posix()),
                        "View Log",
                    )
                ),
            )

            with output_lock:
                if task_data.result < 0:
                    dm.WriteError(content)
                else:
                    dm.WriteWarning(content)

    # ----------------------------------------------------------------------

    yield _ExperienceData(
        [InternalStatusFactory() for _ in tasks],
        OnTaskDataComplete,
    )


# ----------------------------------------------------------------------
def _CreateProgressBarDescription(
    value: str,
    line_prefix: str,
    *,
    indent: bool = True,
) -> str:
    return TextwrapEx.BoundedLJust(
        "{}{}{}".format(
            line_prefix,
            "  " if indent else "",
            value,
        ),
        DISPLAY_COLUMN_WIDTH,
    )


# ----------------------------------------------------------------------
@contextmanager
def _GenerateProgressBarExperienceData(
    num_tasks_display_value: Optional[int],
    dm: DoneManager,
    tasks: list[TaskData],
    on_task_data_complete_func: Callable[[TaskData], tuple[int, int, int]],
    refresh_per_second: Optional[float],
    *,
    quiet: bool,
) -> Iterator[_ExperienceData]:
    with dm.YieldStdout() as stdout_context:
        stdout_context.persist_content = False

        # Technically speaking, it would be more correct to use `stdout_context.stream` here
        # rather than referencing `sys.stdout` directly, but it is really hard to work with mocked
        # stream as mocks will create mocks for everything called on the mock. Use sys.stdout
        # directly to avoid that particular problem.
        assert stdout_context.stream is sys.stdout or isinstance(stdout_context.stream, MagicMock), (
            stdout_context.stream
        )

        progress_bar = Progress(
            *Progress.get_default_columns(),
            TimeElapsedColumn(),
            "{task.fields[status]}",
            console=Capabilities.Get(sys.stdout).CreateRichConsole(sys.stdout),
            transient=True,
            refresh_per_second=refresh_per_second or 4,  # This is the number of refreshes per second
        )

        total_progress_id = progress_bar.add_task(
            _CreateProgressBarDescription(
                "Total Progress",
                stdout_context.line_prefix,
                indent=False,
            ),
            status="",
            total=num_tasks_display_value,
            visible=True,
        )

        # ----------------------------------------------------------------------
        def OnTaskDataComplete(
            task_data: TaskData,
        ) -> None:
            if not quiet and task_data.result != 0:
                if task_data.result < 0:
                    assert TextwrapEx.ERROR_COLOR_ON == "\033[31;1m", "Ensure that the colors stay in sync"
                    color = "red"
                    header = "ERROR"
                else:
                    assert TextwrapEx.WARNING_COLOR_ON == "\033[33;1m", "Ensure that the colors stay in sync"
                    color = "yellow"
                    header = "WARNING"

                if not task_data.log_filename.is_file():
                    suffix = ""
                else:
                    if dm.capabilities.is_headless:
                        suffix = str(task_data.log_filename)
                    else:
                        suffix = "[link=file:///{}]View Log[/]".format(task_data.log_filename.as_posix())

                    suffix = r" \[{}]".format(suffix)

                progress_bar.print(
                    r"{prefix}[bold {color}]{header}:[/] {name}: {result}{short_desc}{suffix}".format(
                        prefix=stdout_context.line_prefix,
                        color=color,
                        header=header,
                        name=task_data.display,
                        result=task_data.result,
                        short_desc=(" ({})".format(task_data.short_desc) if task_data.short_desc else ""),
                        suffix=suffix,
                    ),
                    highlight=False,
                )

                stdout_context.persist_content = True

            success_count, warning_count, error_count = on_task_data_complete_func(task_data)

            if dm.capabilities.supports_colors:
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
                (warning_on, warning_count, inflect.plural_verb("warning", warning_count)),  # type: ignore[reportArgumentType]
            ]:
                content = "0" if count == 0 else "{}{}{}".format(color_on, count, color_off)

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

        status_factories: list[_InternalStatusFactory] = [
            _ProgressBarExperienceInternalStatusFactory(
                stdout_context,
                progress_bar,
                progress_bar.add_task(
                    _CreateProgressBarDescription(task.display, stdout_context.line_prefix),
                    start=False,
                    status="",
                    total=None,
                    visible=False,
                ),
                quiet=quiet,
                is_output_verbose=dm.is_verbose,
            )
            for task in tasks
        ]

        stdout_context.stream.write("\r{}\r".format(" " * len(enqueueing_status)))
        stdout_context.stream.flush()

        progress_bar.start()
        with ExitStack(progress_bar.stop):
            yield _ExperienceData(status_factories, OnTaskDataComplete)


# ----------------------------------------------------------------------
def _ExecuteTask(  # noqa: PLR0915
    desc: str,
    task_data: TaskData[TaskDataContextT_contra],
    init_func: ExecuteTasksTypes.InitFuncType[TaskDataContextT_contra],
    status_factory: _InternalStatusFactory,
    on_task_data_complete_func: Callable[[TaskData[TaskDataContextT_contra]], None],
    *,
    is_debug: bool,
) -> None:
    with ExitStack(lambda: on_task_data_complete_func(task_data)):
        start_time = time.perf_counter()

        with status_factory.GenerateInternalStatus(desc) as internal_status:
            try:
                task_data.log_filename, prepare_func = init_func(task_data.context)

                # ----------------------------------------------------------------------
                def OnSimpleStatus(value: str) -> None:
                    internal_status.OnProgress(None, value)

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
                def AcquireExecutionLock() -> Iterator[None]:
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
                        internal_status.SetNumSteps(num_steps)

                    execute_result = execute_func(internal_status)

                    if isinstance(execute_result, tuple):
                        task_data.result, task_data.short_desc = execute_result
                    else:
                        task_data.result = execute_result
                        task_data.short_desc = None

            except KeyboardInterrupt:
                raise

            except Exception as ex:
                error = traceback.format_exc() if is_debug else str(ex)
                error = error.strip()

                if not error:
                    error = traceback.format_exc().strip()

                if not hasattr(task_data, "log_filename"):
                    # If here, this error happened before we received anything from the initial callback.
                    # Create a log file and write the exception information to it.
                    task_data.log_filename = PathEx.CreateTempFileName()
                    assert task_data.log_filename is not None

                    task_data.log_filename.write_text(error)
                else:
                    with task_data.log_filename.open("a+") as f:
                        f.write(f"\n\n{error}\n")

                if isinstance(ex, TransformError):
                    result = 1
                    short_desc = f"{task_data.display} failed"
                else:
                    result = CATASTROPHIC_TASK_FAILURE_RESULT
                    short_desc = f"{desc} failed"

                task_data.result = result
                task_data.short_desc = short_desc

            finally:
                assert hasattr(task_data, "result")
                assert hasattr(task_data, "short_desc")
                assert hasattr(task_data, "log_filename")

                log_messages = internal_status.log_messages
                if log_messages:
                    with task_data.log_filename.open("a+") as f:
                        f.write(f"\n\n{log_messages}\n")

                task_data.execution_time = datetime.timedelta(seconds=time.perf_counter() - start_time)


# ----------------------------------------------------------------------
@contextmanager
def _YieldTemporaryDirectory(
    dm: DoneManager,
) -> Iterator[Path]:
    temp_directory = PathEx.CreateTempDirectory()

    # ----------------------------------------------------------------------
    def OnExit() -> None:
        # Remove the temporary directory if everything worked as expected or there aren't any log
        # files to view
        if dm.result == 0 or not any(temp_directory.iterdir()):
            shutil.rmtree(temp_directory)
            return

        if dm.capabilities.is_headless:
            dm.WriteInfo(
                f"\nThe temporary directory '{temp_directory}' was preserved due to errors encountered while executing tasks."
            )
        else:
            dm.WriteInfo(
                "\nThe {} was preserved due to errors encountered while executing tasks.".format(
                    TextwrapEx.CreateAnsiHyperLink(
                        f"file:///{temp_directory.as_posix()}",
                        "temporary working directory",
                    )
                )
            )

    # ----------------------------------------------------------------------

    with ExitStack(OnExit):
        yield temp_directory


# ----------------------------------------------------------------------
def _TransformNotCompressed(
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData[TaskDataContextT_contra]],
    prepare_func: TransformTasksExTypes.PrepareFuncType[TaskDataContextT_contra],
    temp_directory: Path,
    *,
    experience_type: Optional[ExperienceType],
    quiet: bool,
    num_threads: int,
    refresh_per_second: Optional[float],
    return_exceptions: bool,
) -> list[Union[None, object, Exception]]:
    # Update the task context with the task index
    for task_index, task_data in enumerate(tasks):
        task_data.context = (task_index, task_data.context)  # type: ignore[assignment]

    # ----------------------------------------------------------------------
    def RestoreTaskContext() -> None:
        for task_data in tasks:
            task_data.context = task_data.context[1]  # type: ignore[index]

    # ----------------------------------------------------------------------

    with ExitStack(RestoreTaskContext):
        all_results: list[Union[None, object, Exception]] = [None] * len(tasks)

        # ----------------------------------------------------------------------
        def Init(
            context: tuple[int, TaskDataContextT_contra],
        ) -> tuple[Path, ExecuteTasksTypes.PrepareFuncType]:
            task_index, original_context = context
            del context

            log_filename = temp_directory / f"{task_index:06}.log"

            # ----------------------------------------------------------------------
            def Prepare(
                on_simple_status_func: Callable[[str], None],
            ) -> Union[
                tuple[int, ExecuteTasksTypes.ExecuteFuncType],
                ExecuteTasksTypes.ExecuteFuncType,
            ]:
                prepare_result = prepare_func(original_context, on_simple_status_func)

                num_steps: Optional[int] = None
                transform_func: Optional[TransformTasksExTypes.TransformFuncType] = None

                if isinstance(prepare_result, tuple):
                    num_steps, transform_func = prepare_result
                else:
                    transform_func = prepare_result

                assert transform_func is not None

                # ----------------------------------------------------------------------
                def Execute(status: Status) -> tuple[int, Optional[str]]:
                    try:
                        transform_result = transform_func(status)

                        return_code = 0
                        result: Optional[object] = None
                        short_desc: Optional[str] = None

                        if isinstance(transform_result, CompleteTransformResult):
                            return_code = transform_result.return_code or 0
                            result = transform_result.value
                            short_desc = transform_result.short_desc
                        else:
                            result = transform_result

                        all_results[task_index] = result
                        return return_code, short_desc  # noqa: TRY300

                    except Exception as ex:
                        if not return_exceptions:
                            raise

                        all_results[task_index] = ex
                        return -1, str(ex)

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
            cast(list[TaskData[tuple[int, TaskDataContextT_contra]]], tasks),
            Init,
            experience_type=experience_type,
            quiet=quiet,
            max_num_threads=num_threads,
            refresh_per_second=refresh_per_second,
        )

        return all_results


# ----------------------------------------------------------------------
def _TransformCompressed(
    dm: DoneManager,
    desc: str,
    tasks: list[TaskData[TaskDataContextT_contra]],
    prepare_func: TransformTasksExTypes.PrepareFuncType[TaskDataContextT_contra],
    temp_directory: Path,
    *,
    experience_type: Optional[ExperienceType],
    quiet: bool,
    num_threads: int,
    refresh_per_second: Optional[float],
    return_exceptions: bool,
) -> list[Union[None, object, Exception]]:
    assert num_threads > 1, num_threads

    all_results: list[Union[None, object, Exception]] = [None] * len(tasks)

    with _GenerateExperienceData(
        experience_type,
        len(tasks),
        dm,
        desc,
        [TaskData("", thread_index) for thread_index in range(num_threads)],
        quiet=quiet,
        refresh_per_second=refresh_per_second,
    ) as experience_data:
        task_index = 0
        task_index_lock = threading.Lock()

        # ----------------------------------------------------------------------
        def Impl(
            thread_index: int,
        ) -> None:
            nonlocal task_index

            log_filename = temp_directory / f"{thread_index:06}.log"
            status_factory = experience_data.internal_status_factories[thread_index]

            with ExitStack(status_factory.Stop):
                while True:
                    with task_index_lock:
                        if task_index == len(tasks):
                            break

                        this_task_index = task_index
                        task_index += 1

                    task_data = tasks[this_task_index]

                    # ----------------------------------------------------------------------
                    def Init(
                        *args,  # noqa: ARG001
                        this_task_index: int = this_task_index,
                        task_data: TaskData[TaskDataContextT_contra] = task_data,
                        **kwargs,  # noqa: ARG001
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
                            def Execute(status: Status) -> tuple[int, Optional[str]]:
                                try:
                                    transform_result = transform_func(status)

                                    return_code = 0
                                    result: Optional[object] = None
                                    short_desc: Optional[str] = None

                                    if isinstance(transform_result, CompleteTransformResult):
                                        result = transform_result.value
                                        return_code = transform_result.return_code or 0
                                        short_desc = transform_result.short_desc
                                    else:
                                        result = transform_result

                                    all_results[this_task_index] = result
                                    return return_code, short_desc  # noqa: TRY300

                                except Exception as ex:
                                    if not return_exceptions:
                                        raise

                                    all_results[this_task_index] = ex
                                    return -1, str(ex)

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
                        experience_data.on_task_data_complete_func,
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
