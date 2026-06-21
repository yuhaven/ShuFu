from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from shufu.types import Message


class Runtime(ABC):
    """Minimal adapter contract implemented by every inference backend."""

    name = "runtime"

    @abstractmethod
    def generate(self, model: str, messages: Sequence[Message]) -> str:
        """Generate one assistant response from the supplied memory window.

        Runtime implementations must not write memory themselves.  Keeping that
        side effect in ``ShuFuNode`` makes backend swaps deterministic.
        """
