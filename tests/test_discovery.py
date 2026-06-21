from __future__ import annotations

import socket
import unittest

from shufu.discovery import DiscoveryResponder, discover_nodes


def free_udp_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


class DiscoveryTests(unittest.TestCase):
    def test_local_discovery_round_trip(self) -> None:
        port = free_udp_port()
        responder = DiscoveryResponder(
            node_id="node-test",
            name="Test Node",
            service_port=17878,
            advertise_host="127.0.0.1",
            discovery_port=port,
        )
        responder.start()
        try:
            nodes = discover_nodes(
                timeout=0.5,
                discovery_port=port,
                targets=("127.0.0.1",),
            )
        finally:
            responder.stop()
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].node_id, "node-test")
        self.assertEqual(nodes[0].url, "http://127.0.0.1:17878")


if __name__ == "__main__":
    unittest.main()
