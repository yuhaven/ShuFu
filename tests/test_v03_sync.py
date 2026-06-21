from __future__ import annotations

import base64
import copy
import tempfile
import threading
import unittest
import urllib.request

from shufu.client import ShuFuClient
from shufu.memory import MemoryStore
from shufu.node import ShuFuNode
from shufu.runtimes.echo import EchoRuntime
from shufu.service import ShuFuHTTPServer


class V03MemoryTests(unittest.TestCase):
    def test_chunked_artifact_round_trip_and_integrity_failure(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = MemoryStore(source_dir)
            record = source.add_artifact_bytes("s", "sensor.bin", b"0123456789", "application/octet-stream")
            bundle = source.export_bundle(
                target_schema=3,
                artifact_mode="chunks",
                artifact_chunk_size=3,
            )
            encoded = bundle["artifacts"][0]
            self.assertEqual(encoded["content_encoding"], "chunked-base64")
            self.assertEqual(len(encoded["content_chunks"]), 4)
            target = MemoryStore(target_dir)
            target.import_bundle(bundle)
            self.assertEqual(target.artifact(record["id"])["content"], b"0123456789")

            damaged = copy.deepcopy(bundle)
            damaged["artifacts"][0]["content_chunks"][0]["content_base64"] = base64.b64encode(b"bad").decode()
            with self.assertRaisesRegex(ValueError, "chunk hash mismatch"):
                MemoryStore(target_dir + "-damaged").import_bundle(damaged)

    def test_schema_two_remains_inline_and_importable(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = MemoryStore(source_dir)
            source.add_artifact_bytes("legacy", "v2.txt", b"v2")
            bundle = source.export_bundle(target_schema=2, artifact_mode="chunks")
            self.assertEqual(bundle["schema_version"], 2)
            self.assertIn("content_base64", bundle["artifacts"][0])
            self.assertNotIn("content_chunks", bundle["artifacts"][0])
            MemoryStore(target_dir).import_bundle(bundle)

    def test_external_reference_requires_explicit_resolver(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = MemoryStore(source_dir)
            source.add_artifact_bytes("s", "external.bin", b"external")
            bundle = source.export_bundle(target_schema=3, artifact_mode="external")
            with self.assertRaisesRegex(ValueError, "explicit resolver"):
                MemoryStore(target_dir).import_bundle(bundle)

    def test_peer_cursors_only_advance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = MemoryStore(temp)
            first = store.update_sync_state("remote", pushed_cursor=9, pulled_cursor=7)
            second = store.update_sync_state("remote", pushed_cursor=2, pulled_cursor=3)
            self.assertEqual(first["pushed_cursor"], 9)
            self.assertEqual(second["pushed_cursor"], 9)
            self.assertEqual(second["pulled_cursor"], 7)


class V03SyncServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.remote_temp = tempfile.TemporaryDirectory()
        self.local_temp = tempfile.TemporaryDirectory()
        self.remote = MemoryStore(self.remote_temp.name)
        self.local = MemoryStore(self.local_temp.name)
        self.remote.add_message("remote-session", "user", "from remote")
        self.local.add_message("local-session", "user", "from local")
        self.server = ShuFuHTTPServer(
            ("127.0.0.1", 0), ShuFuNode(EchoRuntime(), self.remote), token="sync-secret"
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = ShuFuClient(
            f"http://127.0.0.1:{self.server.server_address[1]}", "sync-secret"
        )

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.remote_temp.cleanup()
        self.local_temp.cleanup()

    def test_dual_cursor_exchange_moves_both_deltas(self) -> None:
        push = self.local.export_bundle(after=0, target_schema=3, artifact_mode="chunks")
        exchanged = self.client.sync_exchange(push, push_after=0, pull_after=0)
        self.assertEqual(exchanged["acknowledged_push_cursor"], push["cursor"])
        self.local.import_bundle(exchanged["pull_bundle"])
        self.assertEqual(self.remote.history("local-session")[0].content, "from local")
        self.assertEqual(self.local.history("remote-session")[0].content, "from remote")

        state = self.local.update_sync_state(
            exchanged["remote_node_id"],
            pushed_cursor=exchanged["acknowledged_push_cursor"],
            pulled_cursor=exchanged["pull_bundle"]["cursor"],
        )
        self.local.add_message("local-session", "user", "local delta")
        delta = self.local.export_for_peer(
            exchanged["remote_node_id"], artifact_mode="chunks"
        )
        self.assertEqual([message["content"] for message in delta["messages"]], ["local delta"])

    def test_external_reference_and_range_are_same_node_verified(self) -> None:
        record = self.remote.add_artifact_bytes("s", "large.bin", b"abcdefghij")
        bundle = self.client.sync_pull_v3(artifact_mode="external")
        imported = self.local.import_bundle(bundle, external_resolver=self.client.resolve_artifact_ref)
        self.assertEqual(imported["artifacts"], 1)
        self.assertEqual(self.local.artifact(record["id"])["content"], b"abcdefghij")

        request = urllib.request.Request(
            f"{self.client.base_url}/shufu/v3/artifacts/{record['id']}/content",
            headers={"Authorization": "Bearer sync-secret", "Range": "bytes=2-5"},
        )
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"cdef")


if __name__ == "__main__":
    unittest.main()
