# ----------------------------------------------------------------------
# |
# |  ExecuteTasks_UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-13 10:18:13
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Unit tests for ExecuteTasks.py."""

# Testing Challenges
# ==================
# `ExecuteTasks.py` has proven to be very difficult to test for a couple of reasons:
#
# 1) The implementation executes across a number of threads which means the results are non-
#    deterministic.
#
# 2) The implementation relies on sys.stdout, the interactive nature of streams, and whether
#    a stream is headless or not. The way in which a test is run impacts all of these.
#
# Because of these factors, I have broken the tests into different categories:
#
# A) `ExecuteTasks_UnitTest.py`: Those things that can be verified automatically.
# B) `ExecuteTasks_TestManual.py`: Those things that cannot be verified automatically.
#
# Both of these tests should be run when introducing changes in `ExecuteTasks.py`.
#
# I wish that I knew of a better way to write these tests so that they didn't have to be run across
# multiple files and were fully automated. However, I have not been able to figure out a way to do
# that yet.
#
# To Run the Tests
# ================
#
# `ExecuteTasks_UnitTest.py`
# --------------------------
#
# `uv run pytest`
#
# `ExecuteTasks_TestManual.py`
# ----------------------------
#
# `uv run pytest tests/ExecuteTasks_TestManual.py --no-cov`

import re
import textwrap

from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Any, Callable, cast, Iterator, Optional

import pytest

from dbrownell_Common.ExecuteTasks import *
from dbrownell_Common import ExecuteTasks as ExecuteTasksImpl
from dbrownell_Common import PathEx
from dbrownell_Common.Streams import StreamDecorator
from dbrownell_Common.Streams.DoneManager import DoneManager
from dbrownell_Common.Streams.TextWriter import TextWriter


# ----------------------------------------------------------------------
def test_ExecuteTasksSink():
    sink = _CreateSink()

    with DoneManager.Create(sink, "Executing tasks") as dm:
        results = _ExecuteTasks(dm, lambda x: (x * 2, 0))

    for index, result in enumerate(results):
        assert result == index * 2

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Executing tasks...
          Tasks (5 items)...DONE! (0, <Scrubbed Time>, 5 items succeeded, no items with errors, no items with warnings)
        DONE! (0, <Scrubbed Time>)
        """,
    )


# ----------------------------------------------------------------------
def test_ExecuteTasksStream():
    stream = _FakeStream()

    with DoneManager.Create(stream, "Executing tasks") as dm:
        results = _ExecuteTasks(dm, lambda x: (x * 2, 0))

    for index, result in enumerate(results):
        assert result == index * 2

    stream.content[6] = _Scrub(cast(str, stream.content[6]))
    stream.content[-1] = _Scrub(cast(str, stream.content[-1]))

    assert stream.content == [
        "Executing tasks...",
        None,
        "\n",
        "  ",
        "Tasks (5 items)...",
        None,
        "DONE! (0, <Scrubbed Time>, 5 items succeeded, no items with errors, no items with warnings)",
        "\n",
        None,
        "DONE! (0, <Scrubbed Time>)\n",
    ]


# ----------------------------------------------------------------------
@pytest.mark.parametrize("no_compress_tasks", [False, True])
def test_TransformTasks(no_compress_tasks):
    sink = _CreateSink()

    num_tasks = int(multiprocessing.cpu_count() * 1.5)

    with DoneManager.Create(sink, "Transforming tasks") as dm:
        results = _TransformTasks(
            dm,
            lambda x, _: x * 2,
            num_tasks=num_tasks,
            no_compress_tasks=no_compress_tasks,
        )

    for index, result in enumerate(results):
        assert result == index * 2

    assert _Scrub(sink.getvalue()) == textwrap.dedent(
        """\
        Transforming tasks...
          Tasks ({num_tasks} items)...DONE! (0, <Scrubbed Time>, {num_tasks} items succeeded, no items with errors, no items with warnings)
        DONE! (0, <Scrubbed Time>)
        """,
    ).format(
        num_tasks=num_tasks,
    )


# ----------------------------------------------------------------------
def test_YieldQueueExecutor() -> None:
    sink = _CreateSink()

    results: list[Optional[int]] = [
        None,
    ] * 10

    with DoneManager.Create(sink, "Queue Executor") as dm:
        with YieldQueueExecutor(dm, "Queue") as executor:
            for index in range(len(results)):
                # ----------------------------------------------------------------------
                def Prepare(
                    on_simple_status_func: Callable[[str], None],
                    index=index,
                ) -> YieldQueueExecutorTypes.ExecuteFuncType:
                    # ----------------------------------------------------------------------
                    def Execute(status: Status) -> Optional[str]:
                        results[index] = index
                        return None

                    # ----------------------------------------------------------------------

                    return Execute

                # ----------------------------------------------------------------------

                executor(str(index), Prepare)

    sink = sink.getvalue()
    assert dm.result == 0, (dm.result, sink)

    for index, result in enumerate(results):
        assert result == index


# ----------------------------------------------------------------------
def test_StatusDisplayIsTaskDisplay() -> None:
    # The status associated with a task should be created with the task's display value rather than
    # the description associated with the collection of tasks.
    status_factory = _RecordingInternalStatusFactory()

    task_data = TaskData("The Task", None)

    ExecuteTasksImpl._ExecuteTask(
        "The Tasks",
        task_data,
        _CreateInitFunc(lambda status: 0),
        status_factory,
        lambda _: None,
        is_debug=False,
    )

    assert status_factory.displays == ["The Task"]
    assert task_data.result == 0


# ----------------------------------------------------------------------
def test_StatusDisplayIsTaskDisplayWhenCatastrophicError() -> None:
    # The description associated with the collection of tasks is still used when describing
    # catastrophic errors.
    status_factory = _RecordingInternalStatusFactory()

    # ----------------------------------------------------------------------
    def Execute(status: Status) -> int:
        raise Exception("Catastrophic error")

    # ----------------------------------------------------------------------

    task_data = TaskData("The Task", None)

    ExecuteTasksImpl._ExecuteTask(
        "The Tasks",
        task_data,
        _CreateInitFunc(Execute),
        status_factory,
        lambda _: None,
        is_debug=False,
    )

    assert status_factory.displays == ["The Task"]
    assert task_data.result == CATASTROPHIC_TASK_FAILURE_RESULT
    assert task_data.short_desc == "The Tasks failed"


# ----------------------------------------------------------------------
def test_SetTitleOverridesTaskDisplay() -> None:
    # `Status.SetTitle` should override the display associated with the task.
    progress_bar = _RecordingProgressBar()

    status_factory = ExecuteTasksImpl._ProgressBarExperienceInternalStatusFactory(
        StreamDecorator.StreamDecorator.YieldStdoutContext(StringIO(), "", persist_content=True),
        cast(Any, progress_bar),
        cast(Any, 0),
        quiet=False,
        is_output_verbose=False,
    )

    # ----------------------------------------------------------------------
    def Execute(status: Status) -> int:
        status.SetTitle("The Title")
        return 0

    # ----------------------------------------------------------------------

    task_data = TaskData("The Task", None)

    ExecuteTasksImpl._ExecuteTask(
        "The Tasks",
        task_data,
        _CreateInitFunc(Execute),
        status_factory,
        lambda _: None,
        is_debug=False,
    )

    assert task_data.result == 0

    # The task's display is used when the status is created and is then overridden by `SetTitle`.
    assert progress_bar.descriptions == ["The Task", "The Title"]


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
class _RecordingProgressBar:
    """Captures the descriptions written to a progress bar."""

    # ----------------------------------------------------------------------
    def __init__(self) -> None:
        self.descriptions: list[str] = []

    # ----------------------------------------------------------------------
    def update(self, task_id, **kwargs) -> None:
        description = kwargs.get("description", None)
        if description is not None:
            self.descriptions.append(description.strip())

    # ----------------------------------------------------------------------
    def start_task(self, task_id) -> None:
        pass

    # ----------------------------------------------------------------------
    def stop_task(self, task_id) -> None:
        pass


# ----------------------------------------------------------------------
class _RecordingInternalStatus(ExecuteTasksImpl._InternalStatus):
    # ----------------------------------------------------------------------
    def SetNumSteps(self, *args, **kwargs) -> None:
        pass

    # ----------------------------------------------------------------------
    def SetTitle(self, *args, **kwargs) -> None:
        pass

    # ----------------------------------------------------------------------
    def OnProgress(self, *args, **kwargs) -> bool:
        return True

    # ----------------------------------------------------------------------
    def OnInfo(self, *args, **kwargs) -> None:
        pass


# ----------------------------------------------------------------------
class _RecordingInternalStatusFactory(ExecuteTasksImpl._InternalStatusFactory):
    """Captures the display values used when creating status objects."""

    # ----------------------------------------------------------------------
    def __init__(self) -> None:
        self.displays: list[str] = []

    # ----------------------------------------------------------------------
    @contextmanager
    def GenerateInternalStatus(
        self,
        display: str,
    ) -> Iterator[_RecordingInternalStatus]:
        self.displays.append(display)
        yield _RecordingInternalStatus()

    # ----------------------------------------------------------------------
    def Stop(self) -> None:
        pass


# ----------------------------------------------------------------------
class _FakeStream(TextWriter):
    # ----------------------------------------------------------------------
    def __init__(
        self,
        *,
        fileno: int = 123,
        isatty: bool = False,
        is_headless: bool = True,
        is_interactive: bool = False,
        supports_colors: bool = False,
    ):
        self.content: list[Optional[str]] = []
        self._fileno = fileno
        self._isatty = isatty

        Capabilities(
            stream=self,
            is_headless=is_headless,
            is_interactive=is_interactive,
            supports_colors=supports_colors,
        )

    # ----------------------------------------------------------------------
    def isatty(self) -> bool:
        return self._isatty

    # ----------------------------------------------------------------------
    def write(
        self,
        content: str,
    ) -> int:
        self.content.append(content)
        return len(content)

    # ----------------------------------------------------------------------
    def flush(self) -> None:
        self.content.append(None)

    # ----------------------------------------------------------------------
    def fileno(self) -> int:
        return self._fileno

    # ----------------------------------------------------------------------
    def close(self) -> None:
        pass


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
def _ExecuteTasks(
    dm: DoneManager,
    execute_func: Callable[
        [int],  # context
        tuple[int, int],  # updated context, return code
    ],
    **execute_tasks_kwargs: Any,
) -> list[int]:
    task_data = [
        TaskData(
            str(value),
            value,
            None,
        )
        for value in range(5)
    ]

    results = [
        None,
    ] * len(task_data)

    # ----------------------------------------------------------------------
    def Init(context: Any) -> tuple[Path, ExecuteTasksTypes.PrepareFuncType]:
        # ----------------------------------------------------------------------
        def Prepare(on_simple_status_func: Callable[[str], None]) -> ExecuteTasksTypes.ExecuteFuncType:
            # ----------------------------------------------------------------------
            def Execute(status: Status) -> int:
                result, return_code = execute_func(context)

                results[context] = result
                return return_code

            # ----------------------------------------------------------------------

            return Execute

        # ----------------------------------------------------------------------

        return PathEx.CreateTempFileName(), Prepare

    # ----------------------------------------------------------------------

    ExecuteTasks(dm, "Tasks", task_data, Init, **execute_tasks_kwargs)

    return cast(list[int], results)


# ----------------------------------------------------------------------
def _TransformTasks(
    dm: DoneManager,
    transform_func: Callable[[int, Status], int],
    *,
    num_tasks: int = 5,
    **transform_tasks_kwargs: Any,
) -> list[int]:
    results = TransformTasks(
        dm,
        "Tasks",
        [TaskData(str(value), value) for value in range(num_tasks)],
        transform_func,
        **transform_tasks_kwargs,
    )

    return cast(list[int], results)


# ----------------------------------------------------------------------
def _CreateInitFunc(
    execute_func: ExecuteTasksTypes.ExecuteFuncType,
) -> ExecuteTasksTypes.InitFuncType:
    # ----------------------------------------------------------------------
    def Init(context: Any) -> tuple[Path, ExecuteTasksTypes.PrepareFuncType]:
        # ----------------------------------------------------------------------
        def Prepare(on_simple_status_func: Callable[[str], None]) -> ExecuteTasksTypes.ExecuteFuncType:
            return execute_func

        # ----------------------------------------------------------------------

        return PathEx.CreateTempFileName(), Prepare

    # ----------------------------------------------------------------------

    return Init


# ----------------------------------------------------------------------
def _CreateSink(
    supports_colors: bool = False,
) -> StringIO:
    sink = StringIO()

    Capabilities(
        stream=sink,
        is_headless=True,
        is_interactive=False,
        supports_colors=supports_colors,
    )

    return sink


# ----------------------------------------------------------------------
def _Scrub(
    content: str,
) -> str:
    return re.sub(
        r"\d+:\d{2}:\d{2}(?:\.\d+)?",
        "<Scrubbed Time>",
        content,
    )
