from __future__ import annotations

import unittest
from pathlib import Path


class ESP32ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.component = Path(__file__).resolve().parents[1] / "esp32" / "components" / "shufu"

    def test_sdk_only_calls_node_and_has_no_local_llm_entry_point(self) -> None:
        client = (self.component / "src" / "shufu_client.c").read_text(encoding="utf-8")
        header = (self.component / "include" / "shufu_client.h").read_text(encoding="utf-8")
        combined = (client + header).lower()
        self.assertIn("/shufu/v3/invoke/stream", combined)
        self.assertNotIn("llama", combined)
        self.assertNotIn("gguf", combined)

    def test_tool_boundary_has_no_dynamic_execution_primitives(self) -> None:
        sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                self.component / "include" / "shufu_tools.h",
                self.component / "src" / "shufu_tools.c",
            ]
        ).lower()
        for forbidden in ["system(", "popen(", "dlopen(", "exec(", "eval("]:
            self.assertNotIn(forbidden, sources)
        self.assertIn("allow_side_effect", sources)
        self.assertIn("shufu_tool_permission_denied", sources)

    def test_stream_parser_is_bounded_and_allocation_free(self) -> None:
        header = (self.component / "include" / "shufu_stream.h").read_text(encoding="utf-8")
        source = (self.component / "src" / "shufu_stream.c").read_text(encoding="utf-8")
        self.assertIn("SHUFU_STREAM_LINE_CAPACITY 1024", header)
        self.assertNotIn("malloc(", source)
        self.assertNotIn("realloc(", source)


if __name__ == "__main__":
    unittest.main()
