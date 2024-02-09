# ----------------------------------------------------------------------
# |
# |  ExecuteTasks_TestManual.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2024-01-13 20:50:28
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2024
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Manual tests for ExecuteTasks.py."""

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
# Standard:
# `python Build.py Test`
#
# Code Coverage:
# `python Build.py Test --code-coverage`
#
# `ExecuteTasks_TestManual.py`
# ----------------------------
#
# Standard:
# `pytest tests/dbrownell_Common/ExecuteTasks_TestManual.py -vv --capture=no`
#
# Code Coverage:
# `pytest tests/dbrownell_Common/ExecuteTasks_TestManual.py -vv --capture=no --cov=dbrownell_Common.ExecuteTasks`
#
# Code Coverage with lcov output:
# `pytest tests/dbrownell_Common/ExecuteTasks_TestManual.py -vv --capture=no --cov=dbrownell_Common.ExecuteTasks --cov-report=lcov:tests\dbrownell_Common\lcov.info`
#


import multiprocessing
import sys
import time

from io import StringIO
from pathlib import Path
from typing import Any, Callable, cast

import pytest

from dbrownell_Common.ExecuteTasks import *
from dbrownell_Common import PathEx
from dbrownell_Common.Streams.DoneManager import DoneManager, Flags


# ----------------------------------------------------------------------
@pytest.mark.parametrize("is_interactive", [True, False])
def test_Standard(is_interactive):
    sys.stdout.write("\n")

    if is_interactive:
        stream = sys.stdout
    else:
        stream = StringIO()

    num_tasks = int(multiprocessing.cpu_count() * 1.5)
    num_steps = 20

    with DoneManager.Create(
        stream,
        "Executing tasks",
        flags=Flags.Create(verbose=True),
    ) as dm:
        # ----------------------------------------------------------------------
        def Execute(context, status):
            for x in range(num_steps):
                status.OnProgress(x, "Iteration {}".format(x))
                status.SetTitle("{}.{}".format(context, x))

                time.sleep(0.25)

            if context % 5 == 0:
                status.OnInfo("{} is a multiple of 5".format(context))
                return context * 2, 0

            if context & 1:
                status.OnInfo("{} is odd".format(context), verbose=True)
                return context * 2, 1

            return context * 2, -1

        # ----------------------------------------------------------------------

        results = _ExecuteTasks(
            dm,
            Execute,
            num_tasks=num_tasks,
            num_steps=num_steps,
        )

    for index, result in enumerate(results):
        assert result == index * 2

    sys.stdout.write("\n")


# ----------------------------------------------------------------------
def test_SingleThread():
    sys.stdout.write("\n")

    num_tasks = 5
    num_steps = 10

    with DoneManager.Create(sys.stdout, "Executing tasks...") as dm:
        # ----------------------------------------------------------------------
        def Execute(context, status):
            for x in range(num_steps):
                status.OnProgress(x, "Iteration {}".format(x))
                time.sleep(0.25)

            return context * 2, 0

        # ----------------------------------------------------------------------

        results = _ExecuteTasks(
            dm,
            Execute,
            num_tasks=num_tasks,
            num_steps=num_steps,
            max_num_threads=1,
        )

    for index, result in enumerate(results):
        assert result == index * 2

    sys.stdout.write("\n")


# ----------------------------------------------------------------------
def test_YieldQueueExecutor():
    sys.stdout.write("\n")

    num_tasks = int(multiprocessing.cpu_count() * 1.5)
    num_steps = 20

    results: list[Optional[int]] = [
        None,
    ] * num_tasks

    with DoneManager.Create(sys.stdout, "Executing tasks...") as dm:
        with YieldQueueExecutor(dm, "Queue") as executor:
            for index in range(num_tasks):
                # ----------------------------------------------------------------------
                def Prepare(
                    on_simple_status_func: Callable[[str], None],  # pylint: disable=unused-argument
                    index=index,
                ) -> tuple[int, YieldQueueExecutorTypes.ExecuteFuncType]:
                    # ----------------------------------------------------------------------
                    def Execute(status: Status) -> Optional[str]:
                        for x in range(num_steps):
                            status.OnProgress(x, "Iteration {}".format(x))
                            time.sleep(0.25)

                        results[index] = index * 2

                    # ----------------------------------------------------------------------

                    return num_steps, Execute

                # ----------------------------------------------------------------------

                executor(str(index), Prepare)

    for index, result in enumerate(results):
        assert result == index * 2

    sys.stdout.write("\n")


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
def _ExecuteTasks(
    dm: DoneManager,
    execute_func: Callable[
        [int, Status],  # context
        tuple[int, int],  # updated context, return code
    ],
    *,
    num_tasks: int = 5,
    num_steps: Optional[int] = None,
    **execute_tasks_kwargs: Any,
) -> list[int]:
    task_data = [
        TaskData(
            str(value),
            value,
            None,
        )
        for value in range(num_tasks)
    ]

    results = [
        None,
    ] * len(task_data)

    # ----------------------------------------------------------------------
    def Init(context: Any) -> tuple[Path, ExecuteTasksTypes.PrepareFuncType]:
        # ----------------------------------------------------------------------
        def Prepare(
            on_simple_status_func: Callable[[str], None]
        ) -> ExecuteTasksTypes.ExecuteFuncType | tuple[int, ExecuteTasksTypes.ExecuteFuncType]:
            # ----------------------------------------------------------------------
            def Execute(status: Status) -> int:
                result, return_code = execute_func(context, status)

                results[context] = result
                return return_code

            # ----------------------------------------------------------------------

            if num_steps is None:
                return Execute

            return num_steps, Execute

        # ----------------------------------------------------------------------

        return PathEx.CreateTempFileName(), Prepare

    # ----------------------------------------------------------------------

    ExecuteTasks(dm, "Tasks", task_data, Init, **execute_tasks_kwargs)

    return cast(list[int], results)
