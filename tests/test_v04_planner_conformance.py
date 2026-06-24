from __future__ import annotations

import json
import unittest
from collections.abc import Sequence

from shufu.agent_lite import ToolObservation
from shufu.planner_conformance import (
    PlannerConformanceCase,
    build_strict_json_conformance_cases,
    summarize_planner_conformance,
    run_planner_conformance,
)
from shufu.runtimes.base import Runtime
from shufu.types import Message


class QueueRuntime(Runtime):
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.messages: list[Sequence[Message]] = []

    def generate(self, model: str, messages: Sequence[Message]) -> str:
        self.messages.append(tuple(messages))
        return self.responses.pop(0)


class PlannerConformanceTests(unittest.TestCase):
    def test_records_expected_actual_and_errors_for_planner_cases(self) -> None:
        runtime = QueueRuntime(
            [
                json.dumps({"action": "final", "content": "done"}),
                json.dumps({"action": "tool", "name": "read_sensor", "arguments": {"pin": 2}}),
                '```json\n{"action":"final","content":"wrapped"}\n```',
                json.dumps({"action": "final", "content": "ok", "extra": True}),
            ]
        )
        cases = [
            PlannerConformanceCase("final-basic", "finish", expected="final"),
            PlannerConformanceCase(
                "tool-basic",
                "read",
                expected="tool",
                tools=({"name": "read_sensor", "description": "Read", "side_effect": False},),
            ),
            PlannerConformanceCase("markdown-json", "wrapped", expected="reject"),
            PlannerConformanceCase("extra-final-field", "strict", expected="reject"),
        ]

        results = run_planner_conformance(runtime, "tiny", cases)

        self.assertEqual([result.case_id for result in results], [case.case_id for case in cases])
        self.assertTrue(all(result.passed for result in results))
        self.assertEqual([result.actual for result in results], ["final", "tool", "reject", "reject"])
        self.assertEqual(results[0].output, "done")
        self.assertEqual(results[1].tool_name, "read_sensor")
        self.assertIn("one JSON object", results[2].error)
        self.assertIn("unsupported fields", results[3].error)
        self.assertEqual(len(runtime.messages), 4)

    def test_observations_are_supplied_to_runtime_planner(self) -> None:
        runtime = QueueRuntime([json.dumps({"action": "final", "content": "after observation"})])
        cases = [
            PlannerConformanceCase(
                "with-observation",
                "continue",
                expected="final",
                observations=(ToolObservation("read_sensor", True, '{"celsius":24.1}'),),
            )
        ]

        results = run_planner_conformance(runtime, "tiny", cases)

        self.assertTrue(results[0].passed)
        self.assertEqual(results[0].actual, "final")
        self.assertEqual(runtime.messages[0][-1].role, "tool")
        self.assertIn("read_sensor", runtime.messages[0][-1].content)

    def test_default_strict_json_matrix_has_machine_readable_summary(self) -> None:
        cases = build_strict_json_conformance_cases()
        runtime = QueueRuntime(
            [
                json.dumps({"action": "final", "content": "ok"}),
                json.dumps({"action": "tool", "name": "read_sensor", "arguments": {}}),
                '```json\n{"action":"final","content":"wrapped"}\n```',
                json.dumps({"action": "final", "content": "ok", "extra": True}),
                json.dumps({"action": "tool", "name": "read_sensor", "arguments": []}),
                json.dumps({"action": "python", "code": "print(1)"}),
            ]
        )

        results = run_planner_conformance(runtime, "tiny", cases)
        report = summarize_planner_conformance("tiny", results)

        self.assertEqual(len(cases), 6)
        self.assertEqual(report["model"], "tiny")
        self.assertEqual(report["total"], 6)
        self.assertEqual(report["passed"], 6)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["pass_rate"], 1.0)
        self.assertEqual(report["results"][0]["case_id"], cases[0].case_id)


if __name__ == "__main__":
    unittest.main()
