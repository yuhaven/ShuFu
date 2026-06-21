from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, Callable


@dataclass(frozen=True)
class AgentLimits:
    """Hard safety limits enforced by the v0.4 Agent Lite loop.

    These are deliberately small host-side limits.  A planner can request work,
    but cannot raise either limit from inside a run.
    """

    max_steps: int = 3
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if not 1 <= self.max_steps <= 10:
            raise ValueError("max_steps must be between 1 and 10")
        if not 0 < self.timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 0 and 300")


@dataclass(frozen=True)
class Tool:
    """A host-registered callable exposed to an agent by a stable name."""

    name: str
    description: str
    handler: Callable[[dict[str, Any]], Any]
    side_effect: bool = False
    cancel_handler: Callable[[], None] | None = None


class ToolRegistry:
    """Host-owned tool allowlist; model-generated code is never evaluated.

    The registry intentionally owns no planning loop.  :mod:`shufu.agent_lite`
    composes this host-owned allowlist with a planner, while the host remains
    responsible for approving every side effect.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register one tool, rejecting ambiguous names and replacements."""

        # Wire-level tool names stay ASCII so Python, Kotlin, C, and MCU clients
        # enforce exactly the same allowlist instead of disagreeing on Unicode.
        if re.fullmatch(r"[A-Za-z0-9_]{1,64}", tool.name) is None:
            raise ValueError(
                "Tool name must contain 1-64 ASCII letters, numbers or underscores"
            )
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def describe(self) -> list[dict[str, Any]]:
        """Return model-safe metadata without exposing Python callables."""

        return [
            {"name": tool.name, "description": tool.description, "side_effect": tool.side_effect}
            for tool in self._tools.values()
        ]

    def get(self, name: str) -> Tool:
        """Return registered metadata without exposing the registry mapping.

        Agent Lite uses this method to decide whether a particular invocation
        needs approval.  The callable still remains host supplied; model output
        is never evaluated as Python, shell, or dynamic code.
        """

        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(name)
        return tool

    def execute(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        allow_side_effect: bool = False,
    ) -> Any:
        """Execute an allowed tool after validating its side-effect boundary."""

        tool = self.get(name)
        if tool.side_effect and not allow_side_effect:
            raise PermissionError(f"Tool requires explicit side-effect approval: {name}")
        if not isinstance(arguments, Mapping):
            raise TypeError("Tool arguments must be an object")
        # Give tools an ordinary detached dict so a handler cannot mutate the
        # planner's action object or a read-only Mapping implementation.
        return tool.handler(dict(arguments))
