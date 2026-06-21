from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
from dataclasses import asdict
from pathlib import Path

from .agent import AgentLimits, Tool, ToolRegistry
from .agent_audit import JsonlAuditSink
from .agent_lite import AgentLite, ApprovalRequest, RuntimePlanner
from .client import ShuFuClient
from .context import ContextBuilder
from .discovery import DiscoveryResponder, discover_nodes, preferred_lan_address
from .memory import MemoryStore
from .node import ShuFuNode
from .runtimes import EchoRuntime, LlamaCppRuntime, OpenAICompatibleRuntime, Runtime
from .service import serve
from .summary import SummaryStore
from .types import InvokeRequest


def default_home() -> Path:
    """Return the user data directory, honoring ``SHUFU_HOME`` for portability."""

    override = os.getenv("SHUFU_HOME")
    return Path(override) if override else Path.home() / ".shufu"


def is_loopback(host: str) -> bool:
    """Resolve a host and require every returned address to be loopback."""

    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return all(address[4][0].startswith("127.") or address[4][0] == "::1" for address in socket.getaddrinfo(host, None))
    except socket.gaierror:
        return False


def build_runtime(args: argparse.Namespace) -> Runtime:
    """Construct the selected backend only after validating required options."""

    if args.runtime == "echo":
        return EchoRuntime()
    if args.runtime == "llama":
        if not args.model_path:
            raise ValueError("--model-path is required for llama runtime")
        return LlamaCppRuntime(args.model_path, args.context_size)
    if args.runtime == "openai":
        if not args.base_url:
            raise ValueError("--base-url is required for openai runtime")
        return OpenAICompatibleRuntime(args.base_url, args.api_key)
    raise ValueError(f"Unknown runtime: {args.runtime}")


def runtime_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the shared runtime selector used by ``run`` and ``serve``."""

    parser.add_argument("--runtime", choices=["echo", "llama", "openai"], default="echo")
    parser.add_argument("--model-path")
    parser.add_argument("--context-size", type=int, default=4096)
    parser.add_argument("--base-url")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"))


def command_run(args: argparse.Namespace) -> int:
    """Run one prompt or an interactive local conversation."""

    memory = MemoryStore(args.home)
    node = ShuFuNode(build_runtime(args), memory)

    def ask(prompt: str) -> str:
        result = node.invoke(
            InvokeRequest(args.model, args.session, prompt, memory_window=args.memory_window)
        )
        print(result.output)
        if args.save_output:
            target = Path(args.save_output).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(result.output, encoding="utf-8")
            artifact = memory.add_artifact_file(args.session, target)
            print(f"Saved artifact: {target} ({artifact['id']})")
        return result.output

    if args.prompt:
        ask(args.prompt)
        return 0
    print("ShuFu interactive mode. Type /exit to quit.")
    while True:
        try:
            prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if prompt in {"/exit", "/quit"}:
            break
        if prompt:
            ask(prompt)
    return 0


def command_serve(args: argparse.Namespace) -> int:
    """Start a node while enforcing explicit consent for LAN exposure."""

    # Binding beyond loopback is a security boundary, not a convenience default.
    if not is_loopback(args.host) and not args.allow_lan:
        raise ValueError("Non-loopback host requires explicit --allow-lan")
    node = ShuFuNode(build_runtime(args), MemoryStore(args.home))
    print(f"ShuFu node listening on http://{args.host}:{args.port}")
    if not is_loopback(args.host) and not args.token:
        print("Warning: LAN node has no token. Use --token for a shared secret.", file=sys.stderr)
    responder = None
    if args.allow_lan and not args.no_discovery:
        responder = DiscoveryResponder(
            node_id=node.memory.node_id,
            name=args.name or platform.node() or "ShuFu Node",
            service_port=args.port,
            advertise_host=args.advertise_host or preferred_lan_address(),
            discovery_port=args.discovery_port,
        )
        responder.start()
        print(f"Discovery enabled on UDP {args.discovery_port}")
    try:
        serve(node, args.host, args.port, args.token)
    finally:
        if responder:
            responder.stop()
    return 0


def command_invoke(args: argparse.Namespace) -> int:
    """Invoke an already running node and print only the generated text."""

    client = ShuFuClient(args.url, args.token)
    if args.stream:
        for event in client.invoke_stream(
            args.prompt,
            model=args.model,
            session_id=args.session,
            memory_window=args.memory_window,
            stream_chunk_size=args.stream_chunk_size,
        ):
            if event.get("type") == "delta":
                print(event["delta"], end="", flush=True)
        print()
    else:
        result = client.invoke(
            args.prompt,
            model=args.model,
            session_id=args.session,
            memory_window=args.memory_window,
        )
        print(result["output"])
    return 0


def command_memory(args: argparse.Namespace) -> int:
    """Inspect, export, import, or attach files to portable memory."""

    memory = MemoryStore(args.home)
    if args.memory_command == "list":
        print(json.dumps({"sessions": memory.sessions(), "artifacts": memory.artifacts(args.session)}, ensure_ascii=False, indent=2))
    elif args.memory_command == "messages":
        print(
            json.dumps(
                [asdict(message) for message in memory.history(args.session, args.limit)],
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.memory_command == "export":
        print(memory.export_to_file(args.path, args.session))
    elif args.memory_command == "import":
        print(json.dumps(memory.import_from_file(args.path), ensure_ascii=False))
    elif args.memory_command == "add-artifact":
        print(json.dumps(memory.add_artifact_file(args.session, args.path), ensure_ascii=False, indent=2))
    return 0


def command_summary(args: argparse.Namespace) -> int:
    """Create and inspect provenance-verified derived summaries."""

    memory = MemoryStore(args.home)
    store = SummaryStore(Path(args.home) / "derived", memory)
    if args.summary_command == "add":
        record = store.add(
            args.session,
            args.content,
            args.source_message_id,
        )
        print(json.dumps(asdict(record), ensure_ascii=False, indent=2))
    elif args.summary_command == "list":
        print(
            json.dumps(
                [asdict(record) for record in store.list(args.session)],
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.summary_command == "show":
        print(json.dumps(asdict(store.get(args.summary_id)), ensure_ascii=False, indent=2))
    return 0


def command_agent(args: argparse.Namespace) -> int:
    """Run one local, bounded Agent Lite task with explicit context selection."""

    if args.runtime == "echo":
        raise ValueError("Agent Lite requires --runtime llama or --runtime openai")
    memory = MemoryStore(args.home)
    summary_store = SummaryStore(Path(args.home) / "derived", memory)
    context = ContextBuilder(memory, summaries=summary_store).build(
        args.session,
        args.prompt,
        selected_artifact_ids=args.artifact_id,
        selected_summary_ids=args.summary_id,
        memory_window=args.memory_window,
    )
    registry = ToolRegistry()
    registry.register(
        Tool(
            "list_artifacts",
            "List metadata for artifacts in the current session",
            lambda arguments: memory.artifacts(args.session),
        )
    )

    def save_text_artifact(arguments: dict[str, object]) -> dict[str, object]:
        name = str(arguments.get("name", "agent-output.txt"))
        content = str(arguments.get("content", ""))
        mime_type = str(arguments.get("mime_type", "text/plain"))
        if not content or len(content.encode("utf-8")) > 64 * 1024:
            raise ValueError("artifact content must contain 1-65536 UTF-8 bytes")
        if mime_type not in {"text/plain", "text/markdown", "application/json"}:
            raise ValueError("artifact MIME type is not allowed")
        return memory.add_artifact_bytes(
            args.session,
            name,
            content.encode("utf-8"),
            mime_type,
        )

    registry.register(
        Tool(
            "save_text_artifact",
            "Save bounded text into the current session artifact store",
            save_text_artifact,
            side_effect=True,
        )
    )

    def approve(request: ApprovalRequest) -> bool:
        preview = json.dumps(request.arguments, ensure_ascii=False)
        if len(preview) > 512:
            preview = preview[:512] + "…[truncated]"
        print(
            f"Approval required for {request.tool_name}: {request.description}\n"
            f"Arguments: {preview}",
            file=sys.stderr,
        )
        try:
            return input("Approve this invocation once? [y/N] ").strip().lower() in {
                "y",
                "yes",
            }
        except (EOFError, KeyboardInterrupt):
            return False

    audit_path = Path(args.home) / "audit" / "agent-runs.jsonl"
    result = AgentLite(
        RuntimePlanner(build_runtime(args), args.model),
        registry,
        limits=AgentLimits(args.max_steps, args.timeout),
        approval_handler=approve,
        audit_sink=JsonlAuditSink(audit_path),
    ).run(context)
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "status": result.status,
                "output": result.output,
                "steps": result.steps,
                "observations": [asdict(item) for item in result.observations],
                "audit_path": str(audit_path.resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.status == "completed" else 1


def command_doctor(args: argparse.Namespace) -> int:
    """Print a machine-readable local environment readiness report."""

    report = {
        "shufu": "0.4.0",
        "python": platform.python_version(),
        "system": platform.system(),
        "machine": platform.machine(),
        "home": str(Path(args.home).expanduser().resolve()),
        "local_runtime": "echo ready; llama optional",
        "status": "ready",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def command_discover(args: argparse.Namespace) -> int:
    """Discover LAN nodes during a bounded UDP response window."""

    nodes = discover_nodes(timeout=args.timeout, discovery_port=args.port)
    print(json.dumps([node.__dict__ for node in nodes], ensure_ascii=False, indent=2))
    return 0


def command_sync(args: argparse.Namespace) -> int:
    """Synchronize memory with legacy v0.2 or dual-cursor v0.3 semantics."""

    client = ShuFuClient(args.url, args.token)
    memory = MemoryStore(args.home)
    if args.protocol == "v3":
        capabilities = client.capabilities()
        remote_node_id = str(capabilities["node_id"])
        state = memory.sync_state(remote_node_id)
        if args.direction == "pull":
            bundle = client.sync_pull_v3(
                after=int(state["pulled_cursor"]),
                session_id=args.session,
                artifact_mode=args.artifact_mode,
            )
            imported = memory.import_bundle(bundle, external_resolver=client.resolve_artifact_ref)
            state = memory.update_sync_state(
                remote_node_id, pulled_cursor=int(bundle.get("cursor", 0))
            )
            print(json.dumps({"pull": imported, "sync_state": state}, ensure_ascii=False))
            return 0

        push_after = int(state["pushed_cursor"])
        push_bundle = memory.export_for_peer(
            remote_node_id, args.session, artifact_mode="chunks"
        )
        exchanged = client.sync_exchange(
            push_bundle,
            push_after=push_after,
            pull_after=int(state["pulled_cursor"]),
            session_id=args.session,
            artifact_mode=args.artifact_mode,
        )
        state = memory.update_sync_state(
            remote_node_id,
            pushed_cursor=int(exchanged["acknowledged_push_cursor"]),
        )
        result: dict[str, object] = {
            "push": exchanged["imported"],
            "sync_state": state,
        }
        if args.direction == "both":
            pulled = exchanged["pull_bundle"]
            imported = memory.import_bundle(
                pulled, external_resolver=client.resolve_artifact_ref
            )
            state = memory.update_sync_state(
                remote_node_id, pulled_cursor=int(pulled.get("cursor", 0))
            )
            result.update({"pull": imported, "sync_state": state})
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.direction in {"push", "both"}:
        pushed = client.sync_push(
            memory.export_bundle(args.session, target_schema=2, artifact_mode="inline")
        )
        print(json.dumps({"push": pushed}, ensure_ascii=False))
    if args.direction in {"pull", "both"}:
        bundle = client.sync_pull(after=args.after, session_id=args.session)
        imported = memory.import_bundle(bundle)
        print(json.dumps({"pull": imported, "cursor": bundle.get("cursor", 0)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the complete CLI grammar in one place for testability."""

    parser = argparse.ArgumentParser(prog="shufu", description="Bring intelligence to every device.")
    parser.add_argument("--home", default=str(default_home()))
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a local model conversation")
    run.add_argument("prompt", nargs="?")
    run.add_argument("--model", default="assistant")
    run.add_argument("--session", default="default")
    run.add_argument("--memory-window", type=int, default=20)
    run.add_argument("--save-output")
    runtime_arguments(run)
    run.set_defaults(func=command_run)

    server = sub.add_parser("serve", help="Start a ShuFu model node")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=7878)
    server.add_argument("--allow-lan", action="store_true")
    server.add_argument("--token")
    server.add_argument("--name")
    server.add_argument("--advertise-host")
    server.add_argument("--discovery-port", type=int, default=7879)
    server.add_argument("--no-discovery", action="store_true")
    runtime_arguments(server)
    server.set_defaults(func=command_serve)

    invoke = sub.add_parser("invoke", help="Invoke a running ShuFu node")
    invoke.add_argument("prompt")
    invoke.add_argument("--url", default="http://127.0.0.1:7878")
    invoke.add_argument("--token")
    invoke.add_argument("--model", default="assistant")
    invoke.add_argument("--session", default="default")
    invoke.add_argument("--memory-window", type=int, default=20)
    invoke.add_argument("--stream", action="store_true", help="Consume the v0.3 NDJSON stream")
    invoke.add_argument("--stream-chunk-size", type=int, default=64)
    invoke.set_defaults(func=command_invoke)

    memory = sub.add_parser("memory", help="Inspect and move portable memory")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    memory_list = memory_sub.add_parser("list")
    memory_list.add_argument("--session")
    memory_messages = memory_sub.add_parser("messages")
    memory_messages.add_argument("--session", default="default")
    memory_messages.add_argument("--limit", type=int, default=20)
    memory_export = memory_sub.add_parser("export")
    memory_export.add_argument("path")
    memory_export.add_argument("--session")
    memory_import = memory_sub.add_parser("import")
    memory_import.add_argument("path")
    memory_artifact = memory_sub.add_parser("add-artifact")
    memory_artifact.add_argument("path")
    memory_artifact.add_argument("--session", default="default")
    memory.set_defaults(func=command_memory)

    summary = sub.add_parser("summary", help="Manage separate, traceable summary memory")
    summary_sub = summary.add_subparsers(dest="summary_command", required=True)
    summary_add = summary_sub.add_parser("add")
    summary_add.add_argument("content")
    summary_add.add_argument("--session", default="default")
    summary_add.add_argument(
        "--source-message-id",
        action="append",
        required=True,
        help="Exact raw message ID; repeat for each source",
    )
    summary_list = summary_sub.add_parser("list")
    summary_list.add_argument("--session", default="default")
    summary_show = summary_sub.add_parser("show")
    summary_show.add_argument("summary_id")
    summary.set_defaults(func=command_summary)

    agent = sub.add_parser("agent", help="Run the bounded v0.4 Agent Lite locally")
    agent.add_argument("prompt")
    agent.add_argument("--model", default="assistant")
    agent.add_argument("--session", default="default")
    agent.add_argument("--memory-window", type=int, default=20)
    agent.add_argument("--artifact-id", action="append", default=[])
    agent.add_argument("--summary-id", action="append", default=[])
    agent.add_argument("--max-steps", type=int, default=3)
    agent.add_argument("--timeout", type=float, default=30.0)
    runtime_arguments(agent)
    agent.set_defaults(func=command_agent)

    doctor = sub.add_parser("doctor", help="Inspect the local environment")
    doctor.set_defaults(func=command_doctor)

    discover = sub.add_parser("discover", help="Discover ShuFu nodes on the LAN")
    discover.add_argument("--timeout", type=float, default=1.0)
    discover.add_argument("--port", type=int, default=7879)
    discover.set_defaults(func=command_discover)

    sync = sub.add_parser("sync", help="Synchronize portable memory with a ShuFu node")
    sync.add_argument("--url", default="http://127.0.0.1:7878")
    sync.add_argument("--token")
    sync.add_argument("--session")
    sync.add_argument("--direction", choices=["pull", "push", "both"], default="both")
    sync.add_argument("--after", type=int, default=0)
    sync.add_argument("--protocol", choices=["v2", "v3"], default="v3")
    sync.add_argument(
        "--artifact-mode",
        choices=["auto", "inline", "chunks", "external"],
        default="auto",
    )
    sync.set_defaults(func=command_sync)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; convert expected configuration failures into usage errors."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (
        ValueError,
        RuntimeError,
        FileNotFoundError,
        KeyError,
        PermissionError,
        TypeError,
    ) as exc:
        parser.error(str(exc))
        return 2
