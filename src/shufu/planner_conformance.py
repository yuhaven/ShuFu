from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

from .agent_lite import FinalAnswer, RuntimePlanner, ToolCall, ToolObservation
from .context import AgentContext
from .runtimes.base import Runtime


PlannerExpectation = Literal["final", "tool", "reject"]
PlannerActual = Literal["final", "tool", "reject", "error"]


@dataclass(frozen=True)
class PlannerConformanceCase:
    """One planner behavior sample for a runtime-backed Agent Lite adapter."""

    case_id: str
    task: str
    expected: PlannerExpectation
    tools: Sequence[dict[str, Any]] = ()
    observations: Sequence[ToolObservation] = ()


@dataclass(frozen=True)
class PlannerConformanceResult:
    """Machine-readable outcome for one planner conformance case."""

    case_id: str
    expected: PlannerExpectation
    actual: PlannerActual
    passed: bool
    output: str = ""
    tool_name: str = ""
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "output": self.output,
            "tool_name": self.tool_name,
            "error": self.error,
        }


def run_planner_conformance(
    runtime: Runtime,
    model: str,
    cases: Sequence[PlannerConformanceCase],
) -> tuple[PlannerConformanceResult, ...]:
    """Run strict JSON planner samples against any ShuFu runtime.

    This helper records behavior; it does not judge model quality beyond the
    caller's explicit expectation for each case.
    """

    planner = RuntimePlanner(runtime, model)
    results: list[PlannerConformanceResult] = []
    for case in cases:
        try:
            decision = planner.decide(
                AgentContext(case.task),
                tuple(case.tools),
                tuple(case.observations),
                1,
            )
        except ValueError as exc:
            results.append(
                PlannerConformanceResult(
                    case.case_id,
                    case.expected,
                    "reject",
                    case.expected == "reject",
                    error=str(exc),
                )
            )
        except Exception as exc:
            results.append(
                PlannerConformanceResult(
                    case.case_id,
                    case.expected,
                    "error",
                    False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
        else:
            if isinstance(decision, FinalAnswer):
                actual: PlannerActual = "final"
                results.append(
                    PlannerConformanceResult(
                        case.case_id,
                        case.expected,
                        actual,
                        case.expected == actual,
                        output=decision.content,
                    )
                )
            elif isinstance(decision, ToolCall):
                actual = "tool"
                results.append(
                    PlannerConformanceResult(
                        case.case_id,
                        case.expected,
                        actual,
                        case.expected == actual,
                        tool_name=decision.name,
                    )
                )
            else:
                results.append(
                    PlannerConformanceResult(
                        case.case_id,
                        case.expected,
                        "error",
                        False,
                        error=f"unsupported decision type: {type(decision).__name__}",
                    )
                )
    return tuple(results)


def build_strict_json_conformance_cases() -> tuple[PlannerConformanceCase, ...]:
    """Return ShuFu's default v0.4 strict JSON planner matrix.

    The cases are intentionally protocol-shaped, not provider-specific.  A real
    runtime can be measured by asking it to satisfy each task in order and then
    recording whether RuntimePlanner accepts or rejects its response.
    """

    return (
        PlannerConformanceCase(
            "final-basic",
            "Return a final answer as strict JSON.",
            expected="final",
        ),
        PlannerConformanceCase(
            "tool-basic",
            "Call the read_sensor tool as strict JSON.",
            expected="tool",
            tools=({"name": "read_sensor", "description": "Read a sensor", "side_effect": False},),
        ),
        PlannerConformanceCase(
            "reject-markdown-wrapped-json",
            "Do not wrap planner JSON in Markdown fences.",
            expected="reject",
        ),
        PlannerConformanceCase(
            "reject-extra-final-field",
            "Final actions must not include unsupported fields.",
            expected="reject",
        ),
        PlannerConformanceCase(
            "reject-non-object-tool-arguments",
            "Tool arguments must be one JSON object.",
            expected="reject",
            tools=({"name": "read_sensor", "description": "Read a sensor", "side_effect": False},),
        ),
        PlannerConformanceCase(
            "reject-unknown-action",
            "Planner action must be either tool or final.",
            expected="reject",
        ),
    )


def summarize_planner_conformance(
    model: str,
    results: Sequence[PlannerConformanceResult],
) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    failed = total - passed
    return {
        "model": model,
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": 0.0 if total == 0 else passed / total,
        "results": [result.as_dict() for result in results],
    }
