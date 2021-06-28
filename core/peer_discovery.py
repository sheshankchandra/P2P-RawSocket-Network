# Local network peer discovery using UDP broadcast packets

import json
import time
import socket
import threading
from typing import Dict, Any, List, Optional
from protocol.constants import DEFAULT_UDP_PORT, BROADCAST_INTERVAL, PEER_TIMEOUT_SEC

class PeerInfo:
    def __init__(self, node_id: str, ip: str, tcp_port: int, last_seen: float, shared_count: int = 0):
        self.node_id = node_id
        self.ip = ip
        self.tcp_port = tcp_port
        self.last_seen = last_seen
        self.shared_count = shared_count

    def __repr__(self):
        return f"<Peer {self.node_id[:8]}@{self.ip}:{self.tcp_port}>"

class UDPPeerDiscovery:
    def __init__(self, node_id: str, tcp_port: int, udp_port: int = DEFAULT_UDP_PORT, get_shared_count_cb=None):
        self.node_id = node_id
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.get_shared_count_cb = get_shared_count_cb
        self.known_peers = {}
        self.peers_lock = threading.Lock()
        self._running = False

    def _beacon_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while self._running:
            try:
                data = json.dumps({"node_id": self.node_id, "tcp_port": self.tcp_port, "timestamp": time.time()}).encode()
                for target_ip in ["<broadcast>", "255.255.255.255", "127.0.0.1"]:
                    try:
                        sock.sendto(data, (target_ip, self.udp_port))
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(BROADCAST_INTERVAL)
        sock.close()
