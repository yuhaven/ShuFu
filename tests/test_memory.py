from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from shufu.memory import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_session_history_and_portable_artifact_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = MemoryStore(source_dir)
            source.add_message("project-a", "user", "创建说明文档")
            source.add_message("project-a", "assistant", "# ShuFu\n第一版内容")
            artifact = source.add_artifact_bytes(
                "project-a", "README.md", "# ShuFu\n第一版内容".encode(), "text/markdown"
            )

            bundle = source.export_bundle("project-a")
            target = MemoryStore(target_dir)
            counts = target.import_bundle(bundle)

            self.assertEqual(counts, {"sessions": 1, "messages": 2, "artifacts": 1})
            self.assertEqual([m.content for m in target.history("project-a")], ["创建说明文档", "# ShuFu\n第一版内容"])
            restored = target.artifact(artifact["id"])
            self.assertEqual(restored["content"], "# ShuFu\n第一版内容".encode())
            self.assertEqual(restored["sha256"], artifact["sha256"])

    def test_duplicate_import_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = MemoryStore(source_dir)
            source.add_message("s", "user", "hello")
            bundle = source.export_bundle()
            target = MemoryStore(target_dir)
            target.import_bundle(bundle)
            counts = target.import_bundle(bundle)
            self.assertEqual(counts, {"sessions": 0, "messages": 0, "artifacts": 0})

    def test_export_file_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = MemoryStore(root / "source")
            source.add_message("s", "user", "hello")
            path = source.export_to_file(root / "bundle.json")
            target = MemoryStore(root / "target")
            target.import_from_file(path)
            self.assertEqual(target.history("s")[0].content, "hello")

    def test_incremental_bundle_only_contains_changes_after_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = MemoryStore(temp)
            store.add_message("s", "user", "first")
            first = store.export_bundle("s")
            store.add_message("s", "assistant", "second")
            delta = store.export_bundle("s", after=first["cursor"])
            self.assertEqual(delta["schema_version"], 2)
            self.assertEqual([item["content"] for item in delta["messages"]], ["second"])
            self.assertGreater(delta["cursor"], first["cursor"])

    def test_v1_legacy_bundle_remains_importable(self) -> None:
        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as target_dir:
            source = MemoryStore(source_dir)
            source.add_message("s", "user", "legacy")
            legacy = source.export_bundle("s", target_schema=1)
            self.assertEqual(legacy["schema_version"], 1)
            target = MemoryStore(target_dir)
            target.import_bundle(legacy)
            self.assertEqual(target.history("s")[0].content, "legacy")


if __name__ == "__main__":
    unittest.main()
