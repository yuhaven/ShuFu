from __future__ import annotations

import json
import threading
import time
import unittest

from shufu.agent import AgentLimits, Tool, ToolRegistry
from shufu.agent_lite import (
    AgentLite,
    CancellationToken,
    FinalAnswer,
    RuntimePlanner,
    ToolCall,
)
from shufu.context import AgentContext
from shufu.runtimes.base import Runtime


class ScriptedPlanner:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = 0

    def decide(self, context, tools, observations, step):
        self.calls += 1
        return self.decisions.pop(0)


class StaticRuntime(Runtime):
    def __init__(self, response: str):
        self.response = response
        self.messages = []

    def generate(self, model, messages):
        self.messages = list(messages)
        return self.response


class AgentLiteV04Tests(unittest.TestCase):
    def test_side_effect_is_approved_for_every_invocation_and_audited(self) -> None:
        calls = []
        approvals = []
        registry = ToolRegistry()
        registry.register(
            Tool(
                "set_led",
                "Set a host LED",
                lambda arguments: calls.append(arguments["on"]) or arguments["on"],
                side_effect=True,
            )
        )
        planner = ScriptedPlanner(
            [ToolCall("set_led", {"on": True}), ToolCall("set_led", {"on": False}), FinalAnswer("done")]
        )
        result = AgentLite(
            planner,
            registry,
            limits=AgentLimits(max_steps=3, timeout_seconds=2),
            approval_handler=lambda request: approvals.append(request.id) or True,
        ).run(AgentContext("toggle twice"))

        self.assertEqual(result.status, "completed")
        self.assertEqual(calls, [True, False])
        self.assertEqual(len(set(approvals)), 2)
        kinds = [event.kind for event in result.audit_events]
        self.assertEqual(kinds.count("approval_requested"), 2)
        self.assertEqual(kinds.count("approval_granted"), 2)
        self.assertEqual(kinds.count("tool_completed"), 2)

    def test_denied_side_effect_does_not_execute(self) -> None:
        executed = []
        registry = ToolRegistry()
        registry.register(Tool("write_pin", "Write pin", lambda args: executed.append(args), True))
        planner = ScriptedPlanner([ToolCall("write_pin", {"pin": 2}), FinalAnswer("not changed")])
        result = AgentLite(
            planner,
            registry,
            approval_handler=lambda request: False,
        ).run(AgentContext("do not allow"))

        self.assertEqual(result.status, "completed")
        self.assertEqual(executed, [])
        self.assertIn("approval_denied", [event.kind for event in result.audit_events])
        self.assertFalse(result.observations[0].ok)

    def test_non_boolean_approval_is_denied(self) -> None:
        executed = []
        registry = ToolRegistry()
        registry.register(
            Tool("write_pin", "Write pin", lambda args: executed.append(args), True)
        )
        result = AgentLite(
            ScriptedPlanner([ToolCall("write_pin", {"pin": 2}), FinalAnswer("done")]),
            registry,
            approval_handler=lambda request: "false",  # type: ignore[return-value]
        ).run(AgentContext("write"))

        self.assertEqual(result.status, "completed")
        self.assertEqual(executed, [])
        denial = next(event for event in result.audit_events if event.kind == "approval_denied")
        self.assertEqual(denial.details["reason"], "invalid_decision_type")

    def test_approval_cannot_mutate_arguments_that_execute(self) -> None:
        executed = []
        registry = ToolRegistry()
        registry.register(
            Tool("write_pin", "Write pin", lambda args: executed.append(args), True)
        )

        def approve(request):
            request.arguments["pin"]["number"] = 99
            return True

        result = AgentLite(
            ScriptedPlanner(
                [ToolCall("write_pin", {"pin": {"number": 2}}), FinalAnswer("done")]
            ),
            registry,
            approval_handler=approve,
        ).run(AgentContext("write"))

        self.assertEqual(result.status, "completed")
        self.assertEqual(executed, [{"pin": {"number": 2}}])
        requested = next(event for event in result.audit_events if event.kind == "tool_requested")
        self.assertEqual(requested.details["arguments"], {"pin": {"number": 2}})

    def test_step_limit_is_hard_even_when_planner_keeps_requesting(self) -> None:
        registry = ToolRegistry()
        calls = []
        registry.register(Tool("read_sensor", "Read sensor", lambda args: calls.append(1) or 20))
        planner = ScriptedPlanner([ToolCall("read_sensor") for _ in range(5)])
        result = AgentLite(
            planner,
            registry,
            limits=AgentLimits(max_steps=2, timeout_seconds=2),
        ).run(AgentContext("read forever"))

        self.assertEqual(result.status, "max_steps")
        self.assertEqual(result.steps, 2)
        self.assertEqual(len(calls), 2)

    def test_timeout_returns_promptly_and_invokes_tool_cancellation(self) -> None:
        release = threading.Event()
        registry = ToolRegistry()
        registry.register(
            Tool(
                "wait_device",
                "Wait for device",
                lambda args: release.wait(2),
                cancel_handler=release.set,
            )
        )
        started = time.monotonic()
        result = AgentLite(
            ScriptedPlanner([ToolCall("wait_device")]),
            registry,
            limits=AgentLimits(max_steps=1, timeout_seconds=0.05),
        ).run(AgentContext("wait"))
        elapsed = time.monotonic() - started

        self.assertEqual(result.status, "timed_out")
        self.assertLess(elapsed, 0.3)
        self.assertTrue(release.is_set())
        self.assertIn("tool_cancelled", [event.kind for event in result.audit_events])

    def test_approved_side_effect_never_continues_after_terminal_result(self) -> None:
        effects = []
        registry = ToolRegistry()

        def slow_effect(arguments):
            time.sleep(0.06)
            effects.append((arguments["value"], time.monotonic()))
            return "written"

        registry.register(Tool("write_device", "Write", slow_effect, side_effect=True))
        started = time.monotonic()
        result = AgentLite(
            ScriptedPlanner([ToolCall("write_device", {"value": 7})]),
            registry,
            limits=AgentLimits(max_steps=1, timeout_seconds=0.02),
            approval_handler=lambda request: True,
        ).run(AgentContext("write"))
        returned_at = time.monotonic()

        self.assertEqual(result.status, "timed_out")
        self.assertEqual([item[0] for item in effects], [7])
        self.assertGreaterEqual(returned_at, effects[0][1])
        self.assertGreater(returned_at - started, 0.02)
        time.sleep(0.03)
        self.assertEqual([item[0] for item in effects], [7])

    def test_user_cancellation_stops_active_tool_and_is_audited(self) -> None:
        release = threading.Event()
        token = CancellationToken()
        registry = ToolRegistry()
        registry.register(
            Tool("wait_device", "Wait", lambda args: release.wait(2), cancel_handler=release.set)
        )
        timer = threading.Timer(0.03, token.cancel)
        timer.start()
        try:
            result = AgentLite(
                ScriptedPlanner([ToolCall("wait_device")]),
                registry,
                limits=AgentLimits(max_steps=1, timeout_seconds=2),
            ).run(AgentContext("wait"), cancellation=token)
        finally:
            timer.cancel()

        self.assertEqual(result.status, "cancelled")
        self.assertTrue(release.is_set())
        self.assertEqual(result.audit_events[-1].kind, "run_cancelled")

    def test_runtime_planner_accepts_only_strict_data_actions(self) -> None:
        runtime = StaticRuntime(json.dumps({"action": "tool", "name": "read_sensor", "arguments": {}}))
        decision = RuntimePlanner(runtime, "tiny").decide(
            AgentContext("read"),
            [{"name": "read_sensor", "description": "Read", "side_effect": False}],
            [],
            1,
        )
        self.assertEqual(decision, ToolCall("read_sensor", {}))
        self.assertEqual(runtime.messages[0].role, "system")

        malicious = StaticRuntime('{"action":"python","code":"import os; os.system(\'whoami\')"}')
        with self.assertRaises(ValueError):
            RuntimePlanner(malicious, "tiny").decide(AgentContext("run code"), [], [], 1)

        extra = StaticRuntime(json.dumps({"action": "final", "content": "ok", "code": "x"}))
        with self.assertRaises(ValueError):
            RuntimePlanner(extra, "tiny").decide(AgentContext("strict"), [], [], 1)

    def test_base_exception_becomes_failed_result_with_terminal_audit(self) -> None:
        registry = ToolRegistry()
        registry.register(
            Tool("stop", "Raise host signal", lambda args: (_ for _ in ()).throw(SystemExit(4)))
        )
        result = AgentLite(
            ScriptedPlanner([ToolCall("stop")]),
            registry,
        ).run(AgentContext("stop"))

        self.assertEqual(result.status, "failed")
        self.assertIn("SystemExit", result.output)
        self.assertEqual(result.audit_events[-1].kind, "run_failed")

    def test_audit_details_are_defensive_copies(self) -> None:
        result = AgentLite(
            ScriptedPlanner([FinalAnswer("done")]),
            ToolRegistry(),
        ).run(AgentContext("answer"))
        event = result.audit_events[0]
        copy = event.details
        copy["max_steps"] = 999

        self.assertNotEqual(event.details["max_steps"], 999)


if __name__ == "__main__":
    unittest.main()
