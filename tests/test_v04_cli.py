from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from shufu.cli import main
from shufu.memory import MemoryStore
from shufu.runtimes.base import Runtime


class ScriptedRuntime(Runtime):
    name = "scripted"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)

    def generate(self, model, messages):
        return self.responses.pop(0)


class V04CliTests(unittest.TestCase):
    def test_summary_cli_uses_exact_raw_message_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            message_id = MemoryStore(temp).add_message("project", "user", "raw source")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--home",
                        temp,
                        "summary",
                        "add",
                        "derived summary",
                        "--session",
                        "project",
                        "--source-message-id",
                        message_id,
                    ]
                )
            payload = json.loads(output.getvalue())

            self.assertEqual(code, 0)
            self.assertEqual(payload["session_id"], "project")
            self.assertEqual(payload["sources"][0]["message_id"], message_id)

    def test_agent_cli_runs_with_explicit_context_and_redacted_audit(self) -> None:
        responses = [
            json.dumps(
                {
                    "action": "tool",
                    "name": "save_text_artifact",
                    "arguments": {
                        "name": "answer.md",
                        "content": "private generated text",
                        "mime_type": "text/markdown",
                    },
                }
            ),
            json.dumps({"action": "final", "content": "private final answer"}),
        ]
        with tempfile.TemporaryDirectory() as temp:
            output = io.StringIO()
            with (
                patch("shufu.cli.build_runtime", return_value=ScriptedRuntime(responses)),
                patch("builtins.input", return_value="yes"),
                redirect_stdout(output),
            ):
                code = main(
                    [
                        "--home",
                        temp,
                        "agent",
                        "make an artifact",
                        "--runtime",
                        "openai",
                        "--base-url",
                        "http://unused",
                    ]
                )
            payload = json.loads(output.getvalue())
            audit_text = (Path(temp) / "audit" / "agent-runs.jsonl").read_text(
                encoding="utf-8"
            )

            self.assertEqual(code, 0)
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(len(MemoryStore(temp).artifacts("default")), 1)
            self.assertNotIn("private generated text", audit_text)
            self.assertNotIn("private final answer", audit_text)
            self.assertIn("[REDACTED]", audit_text)

    def test_echo_runtime_is_rejected_for_agent_planning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(SystemExit) as caught:
                main(["--home", temp, "agent", "task"])
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
