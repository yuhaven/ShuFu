from __future__ import annotations

import tempfile
import unittest

from shufu.memory import MemoryStore
from shufu.node import ShuFuNode
from shufu.runtimes.echo import EchoRuntime
from shufu.types import InvokeRequest


class NodeTests(unittest.TestCase):
    def test_second_turn_uses_same_session_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            node = ShuFuNode(EchoRuntime(), MemoryStore(temp))
            first = node.invoke(InvokeRequest("assistant", "project", "第一轮"))
            second = node.invoke(InvokeRequest("assistant", "project", "第二轮"))
            self.assertIn("第一轮", first.output)
            self.assertIn("已延续 1 轮上下文", second.output)
            self.assertEqual(len(node.memory.history("project")), 4)

    def test_empty_input_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            node = ShuFuNode(EchoRuntime(), MemoryStore(temp))
            with self.assertRaises(ValueError):
                node.invoke(InvokeRequest("assistant", "project", "  "))


if __name__ == "__main__":
    unittest.main()

