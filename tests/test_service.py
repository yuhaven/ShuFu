from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from shufu.client import ShuFuClient
from shufu.memory import MemoryStore
from shufu.node import ShuFuNode
from shufu.runtimes.echo import EchoRuntime
from shufu.service import ShuFuHTTPServer


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        node = ShuFuNode(EchoRuntime(), MemoryStore(self.temp.name))
        self.server = ShuFuHTTPServer(("127.0.0.1", 0), node, token="secret")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_invoke_and_capabilities(self) -> None:
        client = ShuFuClient(self.url, "secret")
        capabilities = client.capabilities()
        self.assertEqual(capabilities["protocol_version"], "0.2")
        self.assertEqual(capabilities["latest_protocol_version"], "0.4")
        self.assertTrue(capabilities["memory"]["incremental_sync"])
        self.assertTrue(capabilities["agent"]["agent_lite"])
        self.assertFalse(capabilities["agent"]["http_transport"])
        first = client.invoke("hello", session_id="same")
        second = client.invoke("again", session_id="same")
        self.assertIn("hello", first["output"])
        self.assertIn("已延续 1 轮上下文", second["output"])

    def test_token_is_required_when_configured(self) -> None:
        request = urllib.request.Request(
            f"{self.url}/shufu/v1/capabilities", method="GET"
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request)
        self.assertEqual(caught.exception.code, 401)

    def test_artifact_upload_and_export(self) -> None:
        body = json.dumps(
            {
                "session_id": "project",
                "name": "notes.md",
                "mime_type": "text/markdown",
                "content_base64": "IyBTaHVGDQo=",
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.url}/shufu/v1/artifacts",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer secret"},
        )
        with urllib.request.urlopen(request) as response:
            artifact = json.loads(response.read())
        export_request = urllib.request.Request(
            f"{self.url}/shufu/v1/memory/export?session_id=project",
            headers={"Authorization": "Bearer secret"},
        )
        with urllib.request.urlopen(export_request) as response:
            bundle = json.loads(response.read())
        self.assertEqual(bundle["artifacts"][0]["id"], artifact["id"])

    def test_v2_incremental_sync_round_trip(self) -> None:
        client = ShuFuClient(self.url, "secret")
        client.invoke("desktop message", session_id="sync")
        first = client.sync_pull(session_id="sync")
        self.assertEqual(first["schema_version"], 2)
        self.assertEqual(len(first["messages"]), 2)
        client.invoke("next", session_id="sync")
        delta = client.sync_pull(after=first["cursor"], session_id="sync")
        self.assertEqual([message["content"] for message in delta["messages"]], ["next", "ShuFu[assistant]，已延续 1 轮上下文: next"])


if __name__ == "__main__":
    unittest.main()
