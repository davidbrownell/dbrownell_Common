# ----------------------------------------------------------------------
# |
# |  TextWriter.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-12-18 16:36:52
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023-24
# |  Distributed under the MIT License.
# |
# ----------------------------------------------------------------------
"""Contains the TextWriter object"""

from abc import abstractmethod, ABC


# ----------------------------------------------------------------------
class TextWriter(ABC):
    """\
    Abstract base class used to define the minimum set of functionality required to be considered
    a text writer.
    """

    # ----------------------------------------------------------------------
    @abstractmethod
    def isatty(self) -> bool:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def write(
        self,
        content: str,
    ) -> int:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def flush(self) -> None:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def close(self) -> None:
        raise Exception("Abstract method")  # pragma: no cover
