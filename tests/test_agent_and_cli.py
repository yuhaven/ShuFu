from __future__ import annotations

import unittest

from shufu.agent import AgentLimits, Tool, ToolRegistry
from shufu.cli import is_loopback


class AgentAndCliTests(unittest.TestCase):
    def test_tool_side_effect_requires_explicit_approval(self) -> None:
        registry = ToolRegistry()
        registry.register(Tool("set_led", "Set LED state", lambda args: args["on"], side_effect=True))
        with self.assertRaises(PermissionError):
            registry.execute("set_led", {"on": True})
        self.assertTrue(registry.execute("set_led", {"on": True}, allow_side_effect=True))

    def test_agent_limits_are_hard_bounded(self) -> None:
        self.assertEqual(AgentLimits().max_steps, 3)
        with self.assertRaises(ValueError):
            AgentLimits(max_steps=100)

    def test_lan_requires_explicit_enablement_boundary(self) -> None:
        self.assertTrue(is_loopback("127.0.0.1"))
        self.assertFalse(is_loopback("0.0.0.0"))


if __name__ == "__main__":
    unittest.main()

