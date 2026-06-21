from __future__ import annotations

import io
import tempfile
import threading
import unittest
from contextlib import redirect_stdout

from shufu.cli import main
from shufu.client import ShuFuClient
from shufu.memory import MemoryStore
from shufu.node import ShuFuNode
from shufu.runtimes.echo import EchoRuntime
from shufu.service import ShuFuHTTPServer


class V03StreamingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.memory = MemoryStore(self.temp.name)
        self.server = ShuFuHTTPServer(
            ("127.0.0.1", 0), ShuFuNode(EchoRuntime(), self.memory), token="v03-secret"
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = ShuFuClient(self.url, "v03-secret")

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_ndjson_stream_has_contiguous_events_and_unicode_deltas(self) -> None:
        events = list(
            self.client.invoke_stream("点亮设备", session_id="edge", stream_chunk_size=3)
        )
        self.assertEqual(events[0]["type"], "start")
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual([event["sequence"] for event in events], list(range(len(events))))
        streamed = "".join(event["delta"] for event in events if event["type"] == "delta")
        self.assertIn("点亮设备", streamed)
        self.assertEqual(events[-1]["output_chars"], len(streamed))

    def test_cli_stream_prints_only_generated_text(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(
                [
                    "invoke",
                    "hello-edge",
                    "--url",
                    self.url,
                    "--token",
                    "v03-secret",
                    "--session",
                    "cli-v03",
                    "--stream",
                    "--stream-chunk-size",
                    "2",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("hello-edge", output.getvalue())

    def test_capabilities_advertise_v03_without_breaking_legacy_primary(self) -> None:
        capabilities = self.client.capabilities()
        self.assertEqual(capabilities["protocol_version"], "0.2")
        self.assertIn(capabilities["latest_protocol_version"], {"0.3", "0.4"})
        self.assertIn("0.3", capabilities["protocol_versions"])
        self.assertTrue(capabilities["memory"]["dual_cursor_sync"])


if __name__ == "__main__":
    unittest.main()
