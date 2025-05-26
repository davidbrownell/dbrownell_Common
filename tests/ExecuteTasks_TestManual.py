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

import sys

import pytest

from dbrownell_Common.ExecuteTasks import *
from dbrownell_Common.Streams.DoneManager import DoneManager, Flags as DoneManagerFlags


# ----------------------------------------------------------------------
class TestExecuteTasks:
    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("single_threaded", [False, True], ids=["multithreaded", "single_threaded"])
    @pytest.mark.parametrize("experience_type", ["ProgressBar", "Simple"])
    def test_Success(self, experience_type, single_threaded):
        self.__class__._Execute(
            experience_type,
            lambda context: (0, f"{context} - done"),
            15,
            None,
            single_threaded=single_threaded,
        )

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("verbose", [False, True], ids=["not_verbose", "verbose"])
    @pytest.mark.parametrize("single_threaded", [False, True], ids=["multithreaded", "single_threaded"])
    @pytest.mark.parametrize("experience_type", ["ProgressBar", "Simple"])
    def test_SuccessWithInfo(self, experience_type, single_threaded, verbose):
        self.__class__._Execute(
            experience_type,
            lambda context: (0, f"{context} - done"),
            15,
            None,
            single_threaded=single_threaded,
            send_info=True,
            verbose=verbose,
        )

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("return_code", [-1, 1], ids=["Error", "Warning"])
    @pytest.mark.parametrize("experience_type", ["ProgressBar", "Simple"])
    def test_NotSuccess(self, experience_type, return_code):
        self.__class__._Execute(
            experience_type,
            lambda context: (return_code, f"The result was {return_code}."),
            num_steps=5,
            num_tasks=2,
        )

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("experience_type", ["ProgressBar", "Simple"])
    def test_ErrorOnPrepare(self, experience_type):
        assert (
            self.__class__._Execute(
                experience_type,
                lambda context: (0, None),
                num_steps=1,
                num_tasks=1,
                error_on_prepare=True,
            )
            == CATASTROPHIC_TASK_FAILURE_RESULT
        )

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("experience_type", ["ProgressBar", "Simple"])
    def test_ErrorOnInit(self, experience_type):
        assert (
            self.__class__._Execute(
                experience_type,
                lambda context: (0, None),
                num_steps=1,
                num_tasks=1,
                error_on_init=True,
            )
            == CATASTROPHIC_TASK_FAILURE_RESULT
        )

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("experience_type", ["ProgressBar", "Simple"])
    def test_ErrorOnExecute(self, experience_type):
        # ----------------------------------------------------------------------
        def Execute(context: int) -> tuple[int, Optional[str]]:
            raise Exception("Error on `Execute`")

        # ----------------------------------------------------------------------

        assert (
            self.__class__._Execute(
                experience_type,
                Execute,
                num_steps=1,
                num_tasks=1,
            )
            == CATASTROPHIC_TASK_FAILURE_RESULT
        )

    # ----------------------------------------------------------------------
    def test_ExecutionLock(self):
        self.__class__._Execute(
            "ProgressBar",
            lambda context: (0, f"{context} - done"),
            num_steps=10,
            num_tasks=5,
            execution_lock=threading.Lock(),
        )

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    def _Execute(
        experience_type: str,
        get_execute_result_func: Callable[[int], tuple[int, Optional[str]]],
        num_steps: int,
        num_tasks: Optional[int],
        *,
        single_threaded: bool = False,
        verbose: bool = False,
        send_info: bool = False,
        error_on_init: bool = False,
        error_on_prepare: bool = False,
        execution_lock: Optional[threading.Lock] = None,
    ) -> int:
        experience_type_enum = ExperienceType[experience_type]
        num_tasks = num_tasks or (3 if single_threaded else 10)

        if single_threaded:
            max_num_threads = 1
        elif experience_type_enum == ExperienceType.ProgressBar:
            max_num_threads = 7
        else:
            max_num_threads = None

        # ----------------------------------------------------------------------
        def Init(context: int) -> tuple[Path, ExecuteTasksTypes.PrepareFuncType]:
            if error_on_init:
                raise Exception("An exception during `Init`")

            # ----------------------------------------------------------------------
            def Execute(status: Status) -> tuple[int, Optional[str]]:
                status.SetTitle(f"Testing {context}...")

                if send_info:
                    status.OnInfo(f"{context} has started")
                    status.OnInfo(f"{context} has started and will execute {num_steps} steps.", verbose=True)

                for x in range(num_steps):
                    status.OnProgress(x, str(x))
                    time.sleep(0.200)

                return get_execute_result_func(context)

            # ----------------------------------------------------------------------
            def Prepare(
                on_simple_status_func: Callable[[str], None],
            ) -> tuple[int, ExecuteTasksTypes.ExecuteFuncType]:
                if error_on_prepare:
                    raise Exception("An exception during `Prepare`")

                return num_steps, Execute

            # ----------------------------------------------------------------------

            return PathEx.CreateTempFileName(), Prepare

        # ----------------------------------------------------------------------

        sys.stdout.write("\n")
        with DoneManager.Create(
            sys.stdout,
            "",
            line_prefix="",
            flags=DoneManagerFlags.Create(verbose=verbose),
        ) as dm:
            ExecuteTasks(
                dm,
                "Testing...",
                [TaskData(str(x), x, execution_lock) for x in range(num_tasks)],
                Init,
                experience_type=experience_type_enum,
                max_num_threads=max_num_threads,
            )

            return dm.result


# ----------------------------------------------------------------------
class TestTransformTasksEx:
    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("single_threaded", [False, True], ids=["multithreaded", "single_threaded"])
    @pytest.mark.parametrize("experience_type", ["ProgressBar", "Simple"])
    def test_Success(self, experience_type, single_threaded):
        assert self.__class__._Execute(
            experience_type,
            lambda context: context * 2,
            10,
            single_threaded=single_threaded,
        ) == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    # ----------------------------------------------------------------------
    def test_LimitedNumberOfThreads(self):
        assert self.__class__._Execute(
            None,
            lambda context: context * 2,
            10,
            max_num_threads=5,
        ) == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("return_exceptions", [False, True])
    def test_ReturnExceptions(self, return_exceptions):
        # ----------------------------------------------------------------------
        def Transform(context: int) -> int:
            raise Exception(f"Error on {context}")

        # ----------------------------------------------------------------------

        result = self.__class__._Execute(
            None,
            Transform,
            5,
            return_exceptions=return_exceptions,
            expected_result=-1 if return_exceptions else CATASTROPHIC_TASK_FAILURE_RESULT,
        )

        if return_exceptions:
            assert len(result) == 5

            for x, result in enumerate(result):
                assert isinstance(result, Exception)
                assert str(result) == f"Error on {x}"
        else:
            assert result == [None, None, None, None, None]

    # ----------------------------------------------------------------------
    def test_CompleteTransformResult(self):
        result = self.__class__._Execute(
            None,
            lambda context: CompleteTransformResult(
                context * 2,
                12345,
                f"This will be displayed as a warning ({context})",
            ),
            5,
            expected_result=12345,
        )

        assert result == [0, 2, 4, 6, 8]

    # ----------------------------------------------------------------------
    def test_ManyTasks(self):
        # ----------------------------------------------------------------------
        def Transform(context: int) -> int:
            time.sleep(0.2)
            return context * 2

        # ----------------------------------------------------------------------

        num_tasks = multiprocessing.cpu_count() * 3

        result = self.__class__._Execute(None, Transform, num_tasks)

        assert result == [x * 2 for x in range(num_tasks)]

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("return_exceptions", [False, True])
    def test_ManyTasksReturnExceptions(self, return_exceptions):
        # ----------------------------------------------------------------------
        def Transform(context: int) -> int:
            raise Exception(f"Error on {context}")

        # ----------------------------------------------------------------------

        num_tasks = multiprocessing.cpu_count() * 3

        result = self.__class__._Execute(
            None,
            Transform,
            num_tasks,
            return_exceptions=return_exceptions,
            expected_result=-1 if return_exceptions else CATASTROPHIC_TASK_FAILURE_RESULT,
        )

        if return_exceptions:
            assert len(result) == num_tasks

            for x, result in enumerate(result):
                assert isinstance(result, Exception)
                assert str(result) == f"Error on {x}"
        else:
            assert result == [None] * num_tasks

    # ----------------------------------------------------------------------
    def test_ManyTasksCompleteTransformResult(self):
        # ----------------------------------------------------------------------
        def Transform(context: int) -> CompleteTransformResult:
            return CompleteTransformResult(
                context * 2,
                12345,
                f"This will be displayed as a warning ({context})",
            )

        # ----------------------------------------------------------------------

        num_tasks = multiprocessing.cpu_count() * 3

        result = self.__class__._Execute(
            None,
            Transform,
            num_tasks,
            expected_result=12345,
        )

        assert result == [x * 2 for x in range(num_tasks)]

    # ----------------------------------------------------------------------
    @staticmethod
    def _Execute(
        experience_type: Optional[str],
        transform_func: Callable[[int], Union[int, CompleteTransformResult]],
        num_tasks: int,
        num_steps: int = 1,
        *,
        single_threaded: bool = False,
        verbose: bool = False,
        no_compress_tasks: bool = False,
        return_exceptions: bool = False,
        expected_result: int = 0,
        max_num_threads: Optional[int] = None,
    ) -> list[Union[None, object, Exception]]:
        experience_type_enum = None if experience_type is None else ExperienceType[experience_type]

        if max_num_threads is None:
            if single_threaded:
                max_num_threads = 1
            elif experience_type_enum == ExperienceType.ProgressBar:
                max_num_threads = 7

        # ----------------------------------------------------------------------
        def Prepare(
            context: int,
            on_simple_status_func: Callable[[str], None],
        ) -> Union[
            tuple[int, TransformTasksExTypes.TransformFuncType],
            TransformTasksExTypes.TransformFuncType,
        ]:
            # ----------------------------------------------------------------------
            def Execute(status: Status) -> Union[int, CompleteTransformResult]:
                for x in range(num_steps):
                    if num_steps != 1:
                        status.OnProgress(x, str(x))

                    time.sleep(0.2)

                    result = transform_func(context)

                return result

            # ----------------------------------------------------------------------

            if num_steps == 1:
                return Execute

            return num_steps, Execute

        # ----------------------------------------------------------------------

        sys.stdout.write("\n")
        with DoneManager.Create(
            sys.stdout,
            "",
            line_prefix="",
            flags=DoneManagerFlags.Create(verbose=verbose),
        ) as dm:
            results = TransformTasksEx(
                dm,
                "Transforming...",
                [TaskData(str(x), x) for x in range(num_tasks)],
                Prepare,
                experience_type=experience_type_enum,
                max_num_threads=max_num_threads,
                no_compress_tasks=no_compress_tasks,
                return_exceptions=return_exceptions,
            )

            assert dm.result == expected_result
            return results


# ----------------------------------------------------------------------
class TestTransformTasks:
    # ----------------------------------------------------------------------
    def test_Standard(self):
        assert self.__class__._Execute(
            None,
            lambda context: context * 2,
            10,
        ) == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    # ----------------------------------------------------------------------
    @staticmethod
    def _Execute(
        experience_type: Optional[str],
        transform_func: Callable[[int], Union[int, CompleteTransformResult]],
        num_tasks: int,
        num_steps: int = 1,
        *,
        single_threaded: bool = False,
        verbose: bool = False,
        no_compress_tasks: bool = False,
        return_exceptions: bool = False,
        expected_result: int = 0,
        max_num_threads: Optional[int] = None,
    ) -> list[Union[None, object, Exception]]:
        experience_type_enum = None if experience_type is None else ExperienceType[experience_type]

        if max_num_threads is None:
            if single_threaded:
                max_num_threads = 1
            elif experience_type_enum == ExperienceType.ProgressBar:
                max_num_threads = 7

        # ----------------------------------------------------------------------
        def Transform(
            context: int,
            status: Status,
        ) -> Union[CompleteTransformResult, int]:
            return transform_func(context)

        # ----------------------------------------------------------------------

        sys.stdout.write("\n")
        with DoneManager.Create(
            sys.stdout,
            "",
            line_prefix="",
            flags=DoneManagerFlags.Create(verbose=verbose),
        ) as dm:
            results = TransformTasks(
                dm,
                "Transforming...",
                [TaskData(str(x), x) for x in range(num_tasks)],
                Transform,
                experience_type=experience_type_enum,
                max_num_threads=max_num_threads,
                no_compress_tasks=no_compress_tasks,
                return_exceptions=return_exceptions,
            )

            assert dm.result == expected_result
            return results


# ----------------------------------------------------------------------
class TestYieldQueueExecutor:
    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("single_threaded", [False, True], ids=["multithreaded", "single_threaded"])
    @pytest.mark.parametrize("experience_type", ["ProgressBar", "Simple"])
    def test_Standard(self, experience_type, single_threaded):
        assert (
            self.__class__._Execute(
                experience_type,
                lambda: "Done!",
                num_tasks=10,
                num_steps=5,
                single_threaded=single_threaded,
            )
            == 0
        )

    # ----------------------------------------------------------------------
    def test_WithEnqueueDelay(self):
        assert (
            self.__class__._Execute(
                "ProgressBar",
                lambda: "Done!",
                num_tasks=10,
                num_steps=5,
                add_enqueue_delay=True,
            )
            == 0
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def _Execute(
        experience_type: Optional[str],
        execute_func: Callable[[], str],
        num_tasks: int,
        num_steps: int = 1,
        *,
        single_threaded: bool = False,
        verbose: bool = False,
        max_num_threads: Optional[int] = None,
        add_enqueue_delay: bool = False,
    ) -> int:
        experience_type_enum = None if experience_type is None else ExperienceType[experience_type]

        if max_num_threads is None:
            if single_threaded:
                max_num_threads = 1
            elif experience_type_enum == ExperienceType.ProgressBar:
                max_num_threads = 7

        # ----------------------------------------------------------------------
        def Prepare(
            on_simple_status_func: Callable[[str], None],
        ) -> Union[
            tuple[int, YieldQueueExecutorTypes.ExecuteFuncType],
            YieldQueueExecutorTypes.ExecuteFuncType,
        ]:
            # ----------------------------------------------------------------------
            def Execute(status: Status) -> Optional[str]:
                for x in range(num_steps):
                    if num_steps != 1:
                        status.OnProgress(x, str(x))

                    time.sleep(0.2)

                return execute_func()

            # ----------------------------------------------------------------------

            if num_steps is None:
                return Execute

            return num_steps, Execute

        # ----------------------------------------------------------------------

        sys.stdout.write("\n")
        with DoneManager.Create(
            sys.stdout,
            "",
            line_prefix="",
            flags=DoneManagerFlags.Create(verbose=verbose),
        ) as dm:
            with YieldQueueExecutor(
                dm,
                "Running Tasks...",
                experience_type=experience_type_enum,
                quiet=False,
                max_num_threads=max_num_threads,
            ) as enqueue_func:
                for x in range(num_tasks):
                    if add_enqueue_delay and x == 6:
                        time.sleep(5)

                    enqueue_func(str(x), Prepare)

            return dm.result
