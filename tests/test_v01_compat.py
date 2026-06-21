from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request

from shufu.client import ShuFuClient
from shufu.memory import MemoryStore
from shufu.node import ShuFuNode
from shufu.runtimes.echo import EchoRuntime
from shufu.service import ShuFuHTTPServer


class V01CompatibilityTests(unittest.TestCase):
    """Protect the public behavior documented by protocol-v0.1.md."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.memory = MemoryStore(self.temp.name)
        self.server = ShuFuHTTPServer(
            ("127.0.0.1", 0),
            ShuFuNode(EchoRuntime(), self.memory),
            token="v01-test",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_v1_invoke_contract_and_session_memory(self) -> None:
        client = ShuFuClient(self.url, "v01-test")
        first = client.invoke("legacy hello", model="assistant", session_id="v01")
        second = client.invoke("legacy again", model="assistant", session_id="v01")

        for result in (first, second):
            self.assertEqual(result["model"], "assistant")
            self.assertEqual(result["session_id"], "v01")
            self.assertIsInstance(result["output"], str)
            self.assertTrue(result["output"])
            self.assertIsInstance(result["created_at"], str)
            self.assertTrue(result["created_at"])
        self.assertIn("legacy hello", first["output"])
        self.assertIn("legacy again", second["output"])

    def test_v1_memory_export_stays_schema_one(self) -> None:
        ShuFuClient(self.url, "v01-test").invoke("remember me", session_id="legacy")
        request = urllib.request.Request(
            f"{self.url}/shufu/v1/memory/export?session_id=legacy",
            headers={"Authorization": "Bearer v01-test"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            bundle = json.loads(response.read().decode("utf-8"))

        self.assertEqual(bundle["schema_version"], 1)
        self.assertNotIn("cursor", bundle)
        self.assertEqual(bundle["sessions"][0]["id"], "legacy")
        self.assertEqual(len(bundle["messages"]), 2)

    def test_schema_one_bundle_round_trip(self) -> None:
        self.memory.add_message("portable", "user", "v0.1 portable memory")
        bundle = self.memory.export_bundle("portable", target_schema=1)

        with tempfile.TemporaryDirectory() as destination:
            imported = MemoryStore(destination)
            counts = imported.import_bundle(bundle)

            self.assertEqual(bundle["schema_version"], 1)
            self.assertEqual(counts["sessions"], 1)
            self.assertEqual(counts["messages"], 1)
            self.assertEqual(imported.history("portable")[0].content, "v0.1 portable memory")

    def test_v1_capabilities_advertise_v01_support(self) -> None:
        capabilities = ShuFuClient(self.url, "v01-test").capabilities()

        self.assertIn("0.1", capabilities["protocol_versions"])
        self.assertIn(1, capabilities["memory"]["bundle_schemas"])


if __name__ == "__main__":
    unittest.main()
