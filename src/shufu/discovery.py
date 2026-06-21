from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass


DISCOVERY_PORT = 7879
DISCOVERY_REQUEST = b"SHUFU_DISCOVER_V2"


@dataclass(frozen=True)
class DiscoveredNode:
    """Untrusted node advertisement returned by UDP discovery."""

    node_id: str
    name: str
    url: str
    protocol_version: str
    address: str


def preferred_lan_address() -> str:
    """Infer the outbound LAN address without sending application data.

    RFC 5737's 192.0.2.1 is used only to make the OS choose a route; UDP
    ``connect`` does not transmit a packet here.  Hostname resolution is the
    fallback for restricted environments.
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 9))
        return str(sock.getsockname()[0])
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()


class DiscoveryResponder:
    """Background UDP responder enabled only for explicitly shared LAN nodes."""

    def __init__(
        self,
        *,
        node_id: str,
        name: str,
        service_port: int,
        advertise_host: str,
        discovery_port: int = DISCOVERY_PORT,
    ) -> None:
        self.node_id = node_id
        self.name = name
        self.service_port = service_port
        self.advertise_host = advertise_host
        self.discovery_port = discovery_port
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stopped = threading.Event()

    def start(self) -> None:
        """Start one idempotent daemon thread that answers discovery probes."""

        if self._thread is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.discovery_port))
        sock.settimeout(0.2)
        self._socket = sock
        self._thread = threading.Thread(target=self._run, name="shufu-discovery", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        """Serve fixed discovery requests until :meth:`stop` closes the socket."""

        assert self._socket is not None
        payload = json.dumps(
            {
                "service": "shufu",
                "node_id": self.node_id,
                "name": self.name,
                "url": f"http://{self.advertise_host}:{self.service_port}",
                "protocol_version": "0.2",
            }
        ).encode("utf-8")
        while not self._stopped.is_set():
            try:
                data, address = self._socket.recvfrom(2048)
                if data == DISCOVERY_REQUEST:
                    self._socket.sendto(payload, address)
            except TimeoutError:
                continue
            except OSError:
                if not self._stopped.is_set():
                    raise

    def stop(self) -> None:
        """Stop the responder and release its port; safe after repeated calls."""

        self._stopped.set()
        if self._socket is not None:
            self._socket.close()
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._socket = None
        self._thread = None

    def __enter__(self) -> "DiscoveryResponder":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


def discover_nodes(
    *,
    timeout: float = 1.0,
    discovery_port: int = DISCOVERY_PORT,
    targets: tuple[str, ...] = ("255.255.255.255",),
) -> list[DiscoveredNode]:
    """Broadcast a probe and return unique, minimally validated advertisements.

    Discovery establishes reachability, not identity.  Callers should display
    the URL or use a pre-shared token before sending sensitive memory.
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", 0))
    deadline = time.monotonic() + timeout
    found: dict[str, DiscoveredNode] = {}
    try:
        for target in targets:
            sock.sendto(DISCOVERY_REQUEST, (target, discovery_port))
        while time.monotonic() < deadline:
            sock.settimeout(max(0.01, deadline - time.monotonic()))
            try:
                data, address = sock.recvfrom(4096)
            except TimeoutError:
                break
            try:
                payload = json.loads(data.decode("utf-8"))
                if payload.get("service") != "shufu":
                    continue
                node = DiscoveredNode(
                    node_id=str(payload["node_id"]),
                    name=str(payload["name"]),
                    url=str(payload["url"]),
                    protocol_version=str(payload["protocol_version"]),
                    address=str(address[0]),
                )
                # node_id is the deduplication key because one node can answer
                # through more than one interface during the discovery window.
                found[node.node_id] = node
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
                continue
    finally:
        sock.close()
    return sorted(found.values(), key=lambda item: (item.name, item.node_id))
